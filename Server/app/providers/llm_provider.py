"""Real LLM adapter (OpenAI-compatible chat completions).

Configuration is entirely environment based; no key is ever logged, echoed in
an error, returned to Unity, or committed.  The provider is optional: without
LLM_BASE_URL / LLM_MODEL / LLM_API_KEY the service reports
``model_available: false`` and keeps serving fixed lines, while free input
returns a structured fallback result.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import Settings
from ..security import ModelOutputRejected, validate_model_reply
from .base import (
    OUTCOME_COMPLETED,
    OUTCOME_INVALID_OUTPUT,
    OUTCOME_MODEL_UNAVAILABLE,
    OUTCOME_TIMEOUT,
    OUTCOME_UNSAFE_OUTPUT,
    ProviderRequest,
    ProviderResult,
)

MAX_OUTPUT_TOKENS = 220


class LlmProvider:
    kind = "external_model"
    is_synthetic = False

    def __init__(
        self,
        settings: Settings,
        *,
        provider_id: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self.provider_id = provider_id or settings.llm_provider_id
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._closed = False

    @property
    def available(self) -> bool:
        return self._settings.llm_configured and not self._closed

    async def aclose(self) -> None:
        """Release the pooled HTTP connection (idempotent)."""

        self._closed = True
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

    def _client_or_none(self) -> httpx.AsyncClient | None:
        # The AsyncClient is created lazily: the module-level ``app`` is built
        # at import time, and no HTTP connection should be opened (or any
        # event-loop resource bound) before the first real request.
        if self._closed or not self._settings.llm_configured:
            return None
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._settings.ai_timeout_ms / 1000.0,
                transport=self._transport,
            )
        return self._client

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        started = time.perf_counter()

        def elapsed() -> int:
            return int((time.perf_counter() - started) * 1000)

        client = self._client_or_none()
        if client is None:
            return ProviderResult(
                outcome=OUTCOME_MODEL_UNAVAILABLE,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail="llm_not_configured",
                latency_ms=elapsed(),
            )

        payload = {
            "model": self._settings.llm_model,
            "messages": [
                {"role": "system", "content": self._system_prompt(request)},
                {"role": "user", "content": request.player_input},
            ],
            "temperature": 0.7,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "stream": False,
        }
        url = f"{self._settings.llm_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        try:
            # Non-blocking: a slow upstream must never freeze other sessions.
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.TimeoutException:
            return ProviderResult(
                outcome=OUTCOME_TIMEOUT,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail="upstream_timeout",
                latency_ms=elapsed(),
            )
        except httpx.HTTPStatusError as exc:
            # Status only; response bodies may echo the request and must not be
            # copied into client-visible details or logs.
            return ProviderResult(
                outcome=OUTCOME_MODEL_UNAVAILABLE,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail=f"upstream_status_{exc.response.status_code}",
                latency_ms=elapsed(),
            )
        except httpx.HTTPError:
            return ProviderResult(
                outcome=OUTCOME_MODEL_UNAVAILABLE,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail="upstream_transport_error",
                latency_ms=elapsed(),
            )

        try:
            raw_content = self._extract_content(response)
            text, suggestion = validate_model_reply(
                raw_content,
                npc_id=request.npc_id,
                available_topic_ids=set(request.available_topic_ids),
            )
        except ModelOutputRejected as exc:
            return ProviderResult(
                outcome=OUTCOME_UNSAFE_OUTPUT
                if exc.fallback_reason == "unsafe_output"
                else OUTCOME_INVALID_OUTPUT,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail=exc.detail,
                latency_ms=elapsed(),
            )

        return ProviderResult(
            outcome=OUTCOME_COMPLETED,
            provider_kind=self.kind,
            provider_id=self.provider_id,
            is_synthetic=False,
            text=text,
            suggested_topic_id=suggestion,
            latency_ms=elapsed(),
        )

    def _extract_content(self, response: httpx.Response) -> str:
        try:
            body: Any = response.json()
        except ValueError:
            raise ModelOutputRejected("invalid_output", "response_not_json") from None
        if not isinstance(body, dict):
            raise ModelOutputRejected("invalid_output", "response_not_object")
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelOutputRejected("invalid_output", "response_missing_choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise ModelOutputRejected("invalid_output", "response_choice_not_object")
        message = first.get("message")
        if not isinstance(message, dict):
            raise ModelOutputRejected("invalid_output", "response_missing_message")
        content = message.get("content")
        if isinstance(content, list):
            # Some providers return content parts; join text parts only.
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            content = "".join(text_parts)
        if not isinstance(content, str):
            raise ModelOutputRejected("invalid_output", "response_content_not_text")
        return content

    def _system_prompt(self, request: ProviderRequest) -> str:
        topics = ", ".join(request.available_topic_ids) or "(none)"
        evidence = ", ".join(request.acquired_evidence_ids) or "(none)"
        return (
            f"你是叙事调查游戏《回声失物招领处：末班车之后》中的角色“{request.display_name}”"
            f"（{request.npc_id}）。\n"
            "只以该角色第一人称说一句自然中文回应，保持既定人物知识与语气；"
            "不编造未获批准的剧情事实，不解释系统、不输出 Markdown 或 HTML。\n"
            "输出必须是一个 JSON 对象，且只包含以下键：\n"
            f'- "npc_id": 必须是 "{request.npc_id}"\n'
            '- "text": 不超过 120 个汉字的中文台词\n'
            '- "suggested_topic_id": 可选，只能取自可用话题列表\n'
            "你没有能力发放证据、改变任务/进度、触发披露或执行任何命令，"
            "也不要声称自己拥有这些能力。\n"
            f"玩家已获得证据编号：{evidence}\n"
            f"当前可用话题：{topics}"
        )
