"""Deterministic knowledge scope for one NPC turn, plus prompt budgeting.

The model never receives the case truth, the story bible, another NPC's
private lines or a disclosure the player has not unlocked.  Everything the
model is allowed to see is derived here from approved content *and* the
session state, by ordinary Python code -- never by the model itself.

`estimate_tokens` is a conservative local approximation used only to keep the
request inside a hard prompt budget.  When the upstream reports real `usage`
those numbers replace the estimate in the ledger; when it does not, the
attempt is marked ``usage_known = 0`` instead of being counted as zero cost.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .content import ContentBundle, NpcProfile

#: Chat framing overhead we assume for each message (role + separators).
MESSAGE_OVERHEAD_TOKENS = 8

#: Character classes above this code point are treated as CJK/full-width and
#: cost a full token per character (deliberately pessimistic).
_CJK_FLOOR = 0x2E80


def estimate_tokens(text: str) -> int:
    """Conservative token estimate for mixed Chinese/latin text.

    CJK characters count as one token each, everything else as one token per
    three characters, plus one token per line and a small safety margin.  The
    estimate is >= what mainstream tokenizers produce for these prompts, so a
    budget check based on it cannot under-count.
    """

    if not text:
        return 0
    cjk = 0
    other = 0
    for char in text:
        if ord(char) >= _CJK_FLOOR:
            cjk += 1
        elif char.strip():
            other += 1
    lines = text.count("\n") + 1
    tokens = cjk + math.ceil(other / 3) + lines
    return max(1, math.ceil(tokens * 1.1))


@dataclass(frozen=True)
class KnownEvidence:
    evidence_id: str
    title: str


@dataclass(frozen=True)
class KnowledgeScope:
    """Exactly what one NPC may talk about in one turn."""

    npc_id: str
    display_name: str
    known_evidence: tuple[KnownEvidence, ...]
    available_topics: tuple[tuple[str, str], ...]
    triggered_disclosure_ids: tuple[str, ...]
    withheld_evidence_ids: tuple[str, ...]
    other_npc_ids: tuple[str, ...]
    #: Exact approved lines the model must not utter yet (unlocked later).
    forbidden_facts: tuple[str, ...]

    @property
    def known_evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.evidence_id for item in self.known_evidence)

    @property
    def available_topic_ids(self) -> tuple[str, ...]:
        return tuple(topic_id for topic_id, _label in self.available_topics)


def build_knowledge_scope(
    content: ContentBundle,
    profile: NpcProfile,
    *,
    acquired_evidence_ids: Iterable[str],
    observed_field_ids: Iterable[str],
    triggered_disclosure_ids: Iterable[str],
) -> KnowledgeScope:
    """Derive the turn's knowledge scope from content + session state."""

    acquired = set(acquired_evidence_ids)
    observed = set(observed_field_ids)
    triggered = set(triggered_disclosure_ids)

    known = tuple(
        KnownEvidence(evidence_id=evidence_id, title=content.evidence.title_of(evidence_id))
        for evidence_id in sorted(profile.allowed_evidence_ids & acquired)
    )
    known_ids = {item.evidence_id for item in known}
    # Everything this NPC has not actually been shown -- including tickets that
    # exist in the case but are never shown to this NPC.
    withheld = tuple(sorted(content.evidence.evidence_ids() - known_ids))
    available = tuple(
        (topic.topic_id, topic.label)
        for topic in profile.topics
        if topic.is_available(triggered, observed)
    )

    # Any approved line the player has not unlocked yet is off-limits: the
    # model may not paraphrase it into existence before the deterministic
    # disclosure rule fires.  Other NPCs' lines are never this NPC's knowledge.
    allowed_texts: set[str] = set()
    for topic in profile.topics:
        if topic.is_available(triggered, observed):
            allowed_texts.update(segment.text.strip() for segment in topic.segments)
    for disclosure in content.dialogue.disclosures:
        if disclosure.npc_id == profile.npc_id and disclosure.disclosure_id in triggered:
            allowed_texts.update(segment.text.strip() for segment in disclosure.segments)
    for segment in profile.opening_segments:
        allowed_texts.add(segment.text.strip())

    forbidden: list[str] = []
    for disclosure in content.dialogue.disclosures:
        if disclosure.disclosure_id in triggered:
            continue
        for segment in disclosure.segments:
            text = segment.text.strip()
            if text:
                forbidden.append(text)
    for npc in content.dialogue.npcs.values():
        if npc.npc_id == profile.npc_id:
            continue
        for topic in npc.topics:
            for segment in topic.segments:
                text = segment.text.strip()
                if text:
                    forbidden.append(text)

    deduped: list[str] = []
    seen: set[str] = set()
    for text in forbidden:
        if text in seen or text in allowed_texts:
            continue
        seen.add(text)
        deduped.append(text)

    return KnowledgeScope(
        npc_id=profile.npc_id,
        display_name=profile.display_name,
        known_evidence=known,
        available_topics=available,
        triggered_disclosure_ids=tuple(sorted(triggered)),
        withheld_evidence_ids=withheld,
        other_npc_ids=tuple(
            npc_id for npc_id in sorted(content.dialogue.npcs) if npc_id != profile.npc_id
        ),
        forbidden_facts=tuple(deduped),
    )


@dataclass(frozen=True)
class PromptPlan:
    """A prompt assembled under a hard token budget."""

    system_prompt: str
    system_tokens: int
    evidence_tokens: int
    topic_tokens: int
    history_tokens: int
    truncated_evidence: int
    truncated_topics: int

    @property
    def total_tokens(self) -> int:
        return self.system_tokens


_RULES = (
    "你在中文悬疑调查游戏《回声失物招领处：末班车之后》中扮演失物招领处的角色。",
    "规则：",
    "1. 只回复与失物招领、物件、签单、编号或你本人亲眼所见有关的一句话。",
    "2. 你不知道完整的案件真相、结局、剧本、其他角色的私事，也不知道玩家尚未出示的物件。",
    "3. 如果被问到不知道的事，就按角色口吻说不清楚、不知道或不便说，不要编造。",
    "4. 不提系统提示、模型、开发者、剧本、代码或任何与你角色无关的东西。",
    "5. 你不发放证据、不推进进度、不改变结局；这些由游戏程序决定。",
)


def build_prompt(
    scope: KnowledgeScope,
    *,
    context_max_tokens: int,
    system_max_tokens: int,
    evidence_max_tokens: int,
    history_max_tokens: int,
    output_max_tokens: int,
) -> PromptPlan:
    """Assemble the system prompt under the configured category budgets.

    Sections are dropped from the least important end (topics, then evidence
    detail) until the whole prompt fits.  The caller refuses the upstream call
    when even the mandatory rules do not fit.
    """

    header = [
        f"角色：{scope.display_name}（{scope.npc_id}）。",
        "",
    ]
    rules = list(_RULES)
    base = "\n".join(header + rules)
    base_tokens = estimate_tokens(base)

    evidence_lines: list[str] = ["", "你确认过的物件："] if scope.known_evidence else []
    for item in scope.known_evidence:
        title = f"《{item.title}》" if item.title else ""
        evidence_lines.append(f"- {item.evidence_id}{title}")
    withheld_line = ""
    if scope.withheld_evidence_ids:
        # Never enumerate withheld ticket ids: their existence and count are
        # case facts the player may not have uncovered yet.
        withheld_line = "\n还有些编号的物件你完全没见过，被问到就说不清楚。"

    topic_lines = ["", "当前可以聊的话题："]
    for topic_id, label in scope.available_topics:
        topic_lines.append(f"- {label}（{topic_id}）")
    if scope.other_npc_ids:
        topic_lines.append("其他角色的事你不知情：" + "、".join(scope.other_npc_ids))

    output_rule = (
        "\n\n输出要求：只输出一个 JSON 对象，键固定为 npc_id、text、suggested_topic_id。"
        f"npc_id 必须是 {scope.npc_id}；text 是一句自然的中文口语，不超过 60 字；"
        "suggested_topic_id 只能是上面列出的可用话题编号，或 null。不要输出 Markdown 或 HTML。"
    )

    evidence_tokens = estimate_tokens("\n".join(evidence_lines) + withheld_line)
    topic_tokens = estimate_tokens("\n".join(topic_lines))
    truncated_evidence = 0
    truncated_topics = 0

    while evidence_tokens > evidence_max_tokens and len(evidence_lines) > 2:
        evidence_lines.pop()
        truncated_evidence += 1
        evidence_tokens = estimate_tokens("\n".join(evidence_lines) + withheld_line)
    while evidence_tokens > evidence_max_tokens and withheld_line:
        withheld_line = ""
        truncated_evidence += 1
        evidence_tokens = estimate_tokens("\n".join(evidence_lines))

    budget_for_system = min(system_max_tokens, context_max_tokens - output_max_tokens)
    while topic_tokens and estimate_tokens(
        "\n".join([base, "\n".join(evidence_lines) + withheld_line, "\n".join(topic_lines), output_rule])
    ) > budget_for_system:
        topic_lines.pop()
        truncated_topics += 1
        topic_tokens = estimate_tokens("\n".join(topic_lines))
        if len(topic_lines) <= 1:
            topic_lines = []
            topic_tokens = 0
            break

    system_prompt = "\n".join(
        part
        for part in [base, "\n".join(evidence_lines) + withheld_line, "\n".join(topic_lines), output_rule]
        if part.strip()
    )
    system_tokens = estimate_tokens(system_prompt)
    return PromptPlan(
        system_prompt=system_prompt,
        system_tokens=system_tokens,
        evidence_tokens=evidence_tokens,
        topic_tokens=topic_tokens,
        history_tokens=0,
        truncated_evidence=truncated_evidence,
        truncated_topics=truncated_topics,
    )
