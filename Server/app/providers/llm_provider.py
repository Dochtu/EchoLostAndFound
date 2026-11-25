"""OpenAI-compatible model adapter with fail-closed M5-C-A-R1 controls.

Order of checks in :meth:`LlmProvider.generate` -- deliberately cheap and
side-effect free first:

1. provider configured and not closed;
2. circuit breaker allows a call (no paid retry storm);
3. the prompt fits the hard context/token budget (otherwise refuse *before*
   any network I/O);
4. a global upstream-concurrency slot is free (no unbounded fan-out);
5. the durable budget reserves one attempt and a conservative token
   reservation (before any network I/O);
6. exactly one HTTP request is sent -- never retried;
7. the reply is schema/security/knowledge validated and the attempt is
   finished with the upstream usage when present, or marked
   ``usage_known = 0`` (conservative reservation charged) when it is not.

No API key is logged, returned, or placed in an error detail.  Response
bodies are never copied into client-visible fields.  A synthetic/test upstream
(self-identified by a response header or by explicit configuration) is
reported as ``is_synthetic = True`` and never counts as a verified real model.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from ..breaker import CircuitBreaker
from ..budget import RequestBudget, ReserveResult
from ..config import Settings
from ..knowledge import (
    KnowledgeScope,
    KnownEvidence,
    build_prompt,
    estimate_tokens,
)
from ..model_state import ModelState
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

DEFAULT_MAX_OUTPUT_TOKENS = 220


class LlmProvider:
    kind = "external_model"
    is_synthetic = False

    def __init__(
        self,
        settings: Settings,
        *,
        budget: RequestBudget | None = None,
        provider_id: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        breaker: CircuitBreaker | None = None,
        state: ModelState | None = None,
        clock=time.perf_counter,
    ) -> None:
        self._settings = settings
        self.provider_id = provider_id or settings.llm_provider_id
        self._budget = budget
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._closed = False
        self._clock = clock
        self.breaker = breaker or CircuitBreaker(
            settings.llm_breaker_threshold,
            settings.llm_breaker_cooldown_seconds,
            clock=self._clock,
        )
        self._semaphore = asyncio.Semaphore(max(1, settings.llm_max_concurrency))
        self.state = state or ModelState(
            entry_mode=settings.entry_mode,
            provider_kind=self.kind,
            provider_id=self.provider_id,
            configured=settings.llm_configured,
            synthetic_by_config=settings.llm_test_upstream,
        )

    @property
    def available(self) -> bool:
        return bool(
            self._settings.llm_configured
            and self._budget is not None
            and self._budget.unavailable_reason is None
            and not self._closed
        )

    @property
    def budget(self) -> RequestBudget | None:
        return self._budget

    async def aclose(self) -> None:
        """Release the pooled HTTP connection (idempotent)."""

        self._closed = True
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

    def _client_or_none(self) -> httpx.AsyncClient | None:
        # Created lazily: the module-level ``app`` is built at import time and
        # no connection (or event-loop resource) may exist before the first
        # real request.
        if self._closed or not self._settings.llm_configured or self._budget is None:
            return None
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._settings.ai_timeout_ms / 1000.0,
                transport=self._transport,
            )
        return self._client

    # ----------------------------------------------------------------- result

    def _failure(self, detail: str, started: float, *, outcome: str = OUTCOME_MODEL_UNAVAILABLE) -> ProviderResult:
        return ProviderResult(
            outcome=outcome,
            provider_kind="fallback",
            provider_id=self.provider_id,
            is_synthetic=True,
            failure_detail=detail,
            latency_ms=self._elapsed_ms(started),
        )

    def _elapsed_ms(self, started: float) -> int:
        return max(0, int((self._clock() - started) * 1000))

    # ---------------------------------------------------------------- generate

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        started = self._clock()
        client = self._client_or_none()
        if client is None:
            return self._failure("llm_not_configured", started)

        prompt = self._prompt_plan(request)
        if prompt is None:
            # The prompt cannot be built inside the hard context budget.  No
            # upstream call and no budget attempt is spent: the conversation
            # degrades to the approved fixed line instead.
            return self._failure("context_budget_exceeded", started)

        if not self.breaker.allow():
            return self._failure("circuit_open", started)

        wait_s = max(0.05, min(self._settings.ai_timeout_ms, max(1, request.timeout_ms)) / 1000.0)
        if not await self._acquire_slot(wait_s):
            # Local backpressure, not an upstream error: do not trip the
            # circuit breaker for our own concurrency cap.
            return self._failure("upstream_busy", started)

        reserved: ReserveResult | None = None
        try:
            assert self._budget is not None
            reserved = self._budget.reserve(
                session_id=request.session_id or request.request_id,
                request_id=request.request_id,
                model=self._settings.llm_model,
                npc_id=request.npc_id,
                reserved_tokens=self._settings.llm_token_reservation,
            )
            if not reserved.allowed:
                # Budget/ledger problems are *not* upstream failures: do not
                # feed them into the circuit breaker.
                return self._failure(reserved.reason or "budget_unavailable", started)
            return await self._call_upstream(
                client, request, prompt, reserved.attempt_id, started
            )
        finally:
            self._release_slot()

    async def _call_upstream(
        self,
        client: httpx.AsyncClient,
        request: ProviderRequest,
        prompt: Any,
        attempt_id: int | None,
        started: float,
    ) -> ProviderResult:
        payload: dict[str, Any] = {
            "model": self._settings.llm_model,
            "messages": [
                {"role": "system", "content": prompt.system_prompt},
                {"role": "user", "content": self._trim_input(request.player_input)},
            ],
            "temperature": 0.7,
            "max_tokens": self._settings.llm_max_output_tokens,
            "stream": False,
        }
        if self._settings.llm_json_mode:
            payload["response_format"] = {"type": "json_object"}
        url = f"{self._settings.llm_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        timeout = max(
            0.1,
            min(self._settings.ai_timeout_ms, max(1, request.timeout_ms)) / 1000.0,
        )

        try:
            response = await client.post(
                url, json=payload, headers=headers, timeout=timeout
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            return self._finish_failure(attempt_id, "upstream_timeout", started, OUTCOME_TIMEOUT)
        except httpx.HTTPStatusError as exc:
            # Status only; response bodies may echo the request and must not
            # be copied into client-visible details or logs.
            detail = f"upstream_status_{exc.response.status_code}"
            return self._finish_failure(attempt_id, detail, started)
        except httpx.HTTPError:
            return self._finish_failure(attempt_id, "upstream_transport_error", started)

        synthetic = self._is_test_response(response)
        prompt_tokens, completion_tokens, usage_known = self._usage_tokens(response)
        forbidden = (
            request.knowledge.forbidden_facts if request.knowledge is not None else ()
        )
        known_evidence = (
            request.knowledge.known_evidence_ids
            if request.knowledge is not None
            else tuple(request.acquired_evidence_ids)
        )
        try:
            raw_content, finish_reason = self._extract_content(response)
            if finish_reason == "length":
                raise ModelOutputRejected("invalid_output", "response_truncated")
            text, suggestion = validate_model_reply(
                raw_content,
                npc_id=request.npc_id,
                available_topic_ids=set(request.available_topic_ids),
                forbidden_facts=forbidden,
                known_evidence_ids=known_evidence,
            )
        except ModelOutputRejected as exc:
            outcome = (
                OUTCOME_UNSAFE_OUTPUT
                if exc.fallback_reason == "unsafe_output"
                else OUTCOME_INVALID_OUTPUT
            )
            self._budget_finish(
                attempt_id,
                "failed",
                self._elapsed_ms(started),
                prompt_tokens,
                completion_tokens,
                exc.detail,
                usage_known=usage_known,
            )
            self.breaker.record_failure()
            self.state.record_failure(exc.detail)
            return ProviderResult(
                outcome=outcome,
                provider_kind="fallback",
                provider_id=self.provider_id,
                is_synthetic=True,
                failure_detail=exc.detail,
                latency_ms=self._elapsed_ms(started),
            )

        self._budget_finish(
            attempt_id,
            "completed",
            self._elapsed_ms(started),
            prompt_tokens,
            completion_tokens,
            None,
            usage_known=usage_known,
        )
        self.breaker.record_success()
        self.state.record_success(synthetic=synthetic)
        return ProviderResult(
            outcome=OUTCOME_COMPLETED,
            provider_kind=self.kind,
            provider_id=self.provider_id,
            is_synthetic=synthetic,
            text=text,
            suggested_topic_id=suggestion,
            latency_ms=self._elapsed_ms(started),
            consumed_tokens=prompt_tokens + completion_tokens,
            usage_known=usage_known,
            billing_uncertain=not usage_known,
        )

    def _finish_failure(
        self,
        attempt_id: int | None,
        detail: str,
        started: float,
        outcome: str = OUTCOME_MODEL_UNAVAILABLE,
    ) -> ProviderResult:
        # A failed call has no reliable usage: the ledger keeps the reserved
        # amount (conservative accounting) and marks billing uncertain.
        self._budget_finish(
            attempt_id, "failed", self._elapsed_ms(started), 0, 0, detail, usage_known=False
        )
        self.breaker.record_failure()
        self.state.record_failure(detail)
        return ProviderResult(
            outcome=outcome,
            provider_kind="fallback",
            provider_id=self.provider_id,
            is_synthetic=True,
            failure_detail=detail,
            latency_ms=self._elapsed_ms(started),
            billing_uncertain=True,
        )

    def _budget_finish(
        self,
        attempt_id: int | None,
        status: str,
        latency_ms: int,
        prompt_tokens: int,
        completion_tokens: int,
        error: str | None,
        *,
        usage_known: bool = False,
    ) -> None:
        if attempt_id is None or self._budget is None:
            return
        try:
            self._budget.finish(
                attempt_id,
                status,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                error=error,
                tokens_known=usage_known,
                billing_uncertain=not usage_known,
            )
        except Exception:  # noqa: BLE001 - ledger failures disable live use
            # ``finish`` already marks the ledger unavailable on sqlite errors.
            return

    # ------------------------------------------------------------- semaphore

    async def _acquire_slot(self, timeout_s: float) -> bool:
        # Wait briefly for a free upstream slot instead of failing immediately:
        # parallel player turns queue behind the concurrency cap, and only a
        # genuine backlog beyond the request timeout is refused locally.
        # A positive timeout is required - ``wait_for(..., timeout=0)`` cancels
        # even an immediately-ready acquire.
        if not self._semaphore.locked():
            await self._semaphore.acquire()
            return True
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout_s)
        except asyncio.TimeoutError:
            return False
        return True

    def _release_slot(self) -> None:
        try:
            self._semaphore.release()
        except ValueError:  # pragma: no cover - defensive
            pass

    # ------------------------------------------------------------- parsing

    def _usage_tokens(self, response: httpx.Response) -> tuple[int, int, bool]:
        """Return ``(prompt, completion, known)``.

        A missing ``usage`` object is *not* zero consumption.  It is returned
        as unknown so the caller charges the conservative reservation and
        records ``usage_known = 0`` instead of pretending the call was free.
        """

        try:
            body = response.json()
        except ValueError:
            return 0, 0, False
        if not isinstance(body, dict):
            return 0, 0, False
        usage = body.get("usage")
        if not isinstance(usage, dict):
            return 0, 0, False
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        if not isinstance(prompt, (int, float)) or not isinstance(
            completion, (int, float)
        ):
            return 0, 0, False
        return max(0, int(prompt)), max(0, int(completion)), True

    def _is_test_response(self, response: httpx.Response) -> bool:
        """A synthetic upstream must never be reported as a real model."""

        if self._settings.llm_test_upstream:
            return True
        header = self._settings.llm_test_upstream_header
        return bool(response.headers.get(header, "").strip())

    def _extract_content(self, response: httpx.Response) -> tuple[str, str | None]:
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
        finish_reason = first.get("finish_reason")
        message = first.get("message")
        if not isinstance(message, dict):
            raise ModelOutputRejected("invalid_output", "response_missing_message")
        content = message.get("content")
        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            content = "".join(text_parts)
        if not isinstance(content, str):
            raise ModelOutputRejected("invalid_output", "response_content_not_text")
        return content, finish_reason if isinstance(finish_reason, str) else None

    def _trim_input(self, text: str) -> str:
        limit = self._settings.llm_input_max_chars
        if len(text) <= limit:
            return text
        return text[:limit]

    # --------------------------------------------------------------- prompt

    def _scope_for(self, request: ProviderRequest) -> KnowledgeScope:
        if request.knowledge is not None:
            return request.knowledge
        # Providers used directly (tests, custom adapters) may not have a
        # content-derived scope.  Send strictly less: ids only, no titles.
        return KnowledgeScope(
            npc_id=request.npc_id,
            display_name=request.display_name,
            known_evidence=tuple(
                KnownEvidence(evidence_id=evidence_id, title="")
                for evidence_id in request.acquired_evidence_ids
            ),
            available_topics=tuple(
                (topic_id, "") for topic_id in request.available_topic_ids
            ),
            triggered_disclosure_ids=(),
            withheld_evidence_ids=(),
            other_npc_ids=(),
            forbidden_facts=(),
        )

    def _prompt_plan(self, request: ProviderRequest) -> Any:
        settings = self._settings
        scope = self._scope_for(request)
        plan = build_prompt(
            scope,
            context_max_tokens=settings.llm_context_max_tokens,
            system_max_tokens=settings.llm_system_prompt_max_tokens,
            evidence_max_tokens=settings.llm_evidence_context_max_tokens,
            history_max_tokens=settings.llm_history_max_tokens,
            output_max_tokens=settings.llm_max_output_tokens,
        )
        user_tokens = estimate_tokens(self._trim_input(request.player_input))
        total = (
            plan.system_tokens
            + user_tokens
            + settings.llm_max_output_tokens
            + 2 * 8  # message framing
        )
        if total > settings.llm_context_max_tokens:
            return None
        if plan.system_tokens > settings.llm_system_prompt_max_tokens:
            return None
        if plan.evidence_tokens > settings.llm_evidence_context_max_tokens:
            return None
        if plan.history_tokens > settings.llm_history_max_tokens:
            return None
        return plan
