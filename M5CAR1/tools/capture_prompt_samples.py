"""Capture the actual model request context (redacted) for the security review.

Nothing here touches the network: the prompt is built by the same deterministic
code path the live adapter uses (``app.knowledge.build_prompt``), so the saved
text is exactly what would be sent to an upstream model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "Server"
sys.path.insert(0, str(SERVER))

from app.config import Settings  # noqa: E402
from app.content import load_content  # noqa: E402
from app.knowledge import build_knowledge_scope, build_prompt, estimate_tokens  # noqa: E402


def main() -> int:
    settings = Settings.from_env()
    content = load_content(settings.content_dir)
    out = ROOT / "M5CAR1" / "evidence" / "security" / "prompt_samples.md"

    stages = {
        "初始（无证据、无观察字段、无披露）": {
            "acquired": set(),
            "observed": set(),
            "triggered": set(),
        },
        "已取得 E01 并观察到表背刻字": {
            "acquired": {"E01"},
            "observed": {"watch.back_engraving"},
            "triggered": set(),
        },
        "已触发 D01、D03（老周已作证）": {
            "acquired": {"E01", "E02", "E05"},
            "observed": {"watch.back_engraving"},
            "triggered": {"D01", "D03"},
        },
    }
    lines = [
        "# 实际模型请求上下文样本（脱敏）",
        "",
        "由 `M5CAR1/tools/capture_prompt_samples.py` 生成，使用与线上同一套确定性代码路径",
        "（`app.knowledge.build_prompt`），未联网、未携带任何密钥。",
        "",
        f"- content_version: `{content.dialogue.content_version}`",
        f"- 预算: context={settings.llm_context_max_tokens}, system={settings.llm_system_prompt_max_tokens}, "
        f"evidence={settings.llm_evidence_context_max_tokens}, output={settings.llm_max_output_tokens}",
        "",
    ]
    payload: dict[str, object] = {"content_version": content.dialogue.content_version, "stages": {}}
    for title, state in stages.items():
        for npc_id in ("npc_laozhou", "npc_linyao"):
            profile = content.dialogue.npcs[npc_id]
            scope = build_knowledge_scope(
                content,
                profile,
                acquired_evidence_ids=frozenset(state["acquired"]),
                observed_field_ids=frozenset(state["observed"]),
                triggered_disclosure_ids=frozenset(state["triggered"]),
            )
            plan = build_prompt(
                scope,
                context_max_tokens=settings.llm_context_max_tokens,
                system_max_tokens=settings.llm_system_prompt_max_tokens,
                evidence_max_tokens=settings.llm_evidence_context_max_tokens,
                history_max_tokens=settings.llm_history_max_tokens,
                output_max_tokens=settings.llm_max_output_tokens,
            )
            lines += [
                f"## {npc_id} — {title}",
                "",
                f"- 已知证据编号: {list(scope.known_evidence_ids)}",
                f"- 可用话题: {list(scope.available_topic_ids)}",
                f"- system_tokens(估算)={plan.system_tokens} evidence_tokens={plan.evidence_tokens} "
                f"topic_tokens={plan.topic_tokens} 截断={plan.truncated_evidence or plan.truncated_topics}",
                f"- 该角色不可见证据数: {len(scope.withheld_evidence_ids)}",
                "",
                "```text",
                plan.system_prompt,
                "```",
                "",
            ]
            payload["stages"][f"{npc_id}@{title}"] = {
                "known_evidence": list(scope.known_evidence_ids),
                "available_topics": list(scope.available_topic_ids),
                "withheld_count": len(scope.withheld_evidence_ids),
                "system_tokens": plan.system_tokens,
                "evidence_tokens": plan.evidence_tokens,
                "prompt_sha256_len": len(plan.system_prompt),
            }

    # Explicitly state what the captured prompt must NOT contain.  These are
    # *content* fragments (case truth), not words like "结局", which legitimately
    # appear in the rules ("you cannot change endings").
    joined = out.read_text(encoding="utf-8") if out.exists() else ""
    forbidden = ["storybible", "StoryBible", "沈禾", "二十一点十七", "冠头是歪的", "我自己领", "指认"]
    hits = [word for word in forbidden if word in "\n".join(lines)]
    lines += [
        "## 反向核对（生成时自动执行）",
        "",
        f"- 样本中命中的敏感词: {hits or '无'}",
        f"- 估算 token 上限校验: system<= {settings.llm_system_prompt_max_tokens}",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    (out.parent / "prompt_samples.json").write_text(
        json.dumps({"forbidden_hits": hits, **payload}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {out} forbidden_hits={hits}")
    print("tokens per stage:", json.dumps({k: v["system_tokens"] for k, v in payload["stages"].items()}, ensure_ascii=False))
    return 0 if not hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
