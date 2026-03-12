"""Annotate paragraph-level rhetorical roles with an LLM-led hybrid classifier."""

from __future__ import annotations

import json


SUPPORTED_ROLES = (
    "background",
    "gap",
    "objective",
    "contribution",
    "method",
    "result",
    "interpretation",
    "limitation",
    "significance",
    "transition",
    "non_core",
)

ROLE_CLASSIFICATION_SYSTEM_PROMPT = """
You classify one academic paragraph into exactly one rhetorical role.

Return strict JSON with keys:
- role
- confidence
- rationale

Allowed role values only:
- background
- gap
- objective
- contribution
- method
- result
- interpretation
- limitation
- significance
- transition
- non_core

Rules:
- Use the paragraph text as the primary signal.
- Use section heading, local context, and storyline anchors only as supporting context.
- Choose one role only.
- confidence must be a float between 0 and 1.
- rationale must be one short sentence.
""".strip()

CONTRIBUTION_MARKERS = ("we propose", "we present", "we introduce", "our contribution", "we develop")
GAP_MARKERS = ("however", "few studies", "remains unclear", "limited", "lack", "challenge")
OBJECTIVE_MARKERS = ("we aim", "we seek", "our goal", "this study investigates", "we ask whether")
METHOD_MARKERS = ("method", "framework", "pipeline", "dataset", "benchmark", "we trained", "we constructed")
RESULT_MARKERS = ("we show", "we find", "outperforms", "improves", "results show", "results indicate")
INTERPRETATION_MARKERS = ("this suggests", "these results indicate", "we interpret", "taken together")
LIMITATION_MARKERS = ("limitation", "limited by", "constraint", "future work", "we caution")
SIGNIFICANCE_MARKERS = ("significance", "implication", "broadly", "this matters", "impact")
TRANSITION_MARKERS = ("next", "to address this", "in contrast", "therefore", "together")


def _fallback_role(section_title: str, text: str) -> tuple[str, float, str]:
    title = section_title.lower()
    content = text.lower()
    if "method" in title or "dataset" in title:
        return "method", 0.72, "Section heading indicates methods or resources."
    if "result" in title or "experiment" in title:
        if any(marker in content for marker in INTERPRETATION_MARKERS):
            return "interpretation", 0.66, "Result section paragraph interprets findings."
        return "result", 0.7, "Section heading indicates reported findings."
    if "discussion" in title or "conclusion" in title:
        if any(marker in content for marker in LIMITATION_MARKERS):
            return "limitation", 0.68, "Discussion language points to limitations."
        if any(marker in content for marker in SIGNIFICANCE_MARKERS):
            return "significance", 0.68, "Discussion language frames broader significance."
        return "interpretation", 0.62, "Discussion paragraph likely interprets reported results."
    if any(marker in content for marker in GAP_MARKERS):
        return "gap", 0.67, "Gap markers indicate an unresolved problem."
    if any(marker in content for marker in OBJECTIVE_MARKERS):
        return "objective", 0.66, "Objective markers indicate the paper goal."
    if any(marker in content for marker in CONTRIBUTION_MARKERS):
        return "contribution", 0.7, "Contribution markers indicate the claimed advance."
    if any(marker in content for marker in METHOD_MARKERS):
        return "method", 0.61, "Method markers indicate procedures or resources."
    if any(marker in content for marker in RESULT_MARKERS):
        return "result", 0.64, "Result markers indicate empirical findings."
    if any(marker in content for marker in INTERPRETATION_MARKERS):
        return "interpretation", 0.62, "Interpretive phrasing explains findings."
    if any(marker in content for marker in LIMITATION_MARKERS):
        return "limitation", 0.62, "Limitation markers indicate caveats."
    if any(marker in content for marker in SIGNIFICANCE_MARKERS):
        return "significance", 0.62, "Significance markers frame broader impact."
    if any(marker in content for marker in TRANSITION_MARKERS):
        return "transition", 0.58, "Paragraph mainly bridges adjacent argumentative steps."
    if "intro" in title or "background" in title:
        return "background", 0.6, "Introduction context defaults to background."
    return "non_core", 0.45, "No strong rhetorical signal was detected."


def _classify_with_llm(
    *,
    paragraph_text: str,
    section_heading: str,
    previous_text: str,
    next_text: str,
    storyline_confirmed: dict | None,
    llm_client,
) -> tuple[str, float, str] | None:
    if not llm_client or not llm_client.is_configured:
        return None

    user_prompt = json.dumps(
        {
            "section_heading": section_heading,
            "paragraph_text": paragraph_text,
            "previous_paragraph": previous_text,
            "next_paragraph": next_text,
            "storyline_confirmed": {
                "problem": storyline_confirmed.get("problem"),
                "gap": storyline_confirmed.get("gap"),
                "contribution": storyline_confirmed.get("contribution"),
                "significance": storyline_confirmed.get("significance"),
            }
            if storyline_confirmed
            else None,
        },
        ensure_ascii=False,
        indent=2,
    )
    try:
        payload = llm_client.chat_json(ROLE_CLASSIFICATION_SYSTEM_PROMPT, user_prompt)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    role = payload.get("role")
    confidence = payload.get("confidence")
    rationale = payload.get("rationale")
    if role not in SUPPORTED_ROLES:
        return None
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        return None
    if not isinstance(rationale, str):
        return None
    return role, max(0.0, min(confidence, 1.0)), rationale.strip() or "LLM role classification."


def annotate_section_roles(paper_raw: dict, storyline_confirmed: dict | None = None, llm_client=None) -> dict:
    items: list[dict] = []

    for section in paper_raw["sections"]:
        paragraphs = section["paragraphs"]
        for index, paragraph in enumerate(paragraphs):
            previous_text = paragraphs[index - 1]["text"] if index > 0 else ""
            next_text = paragraphs[index + 1]["text"] if index + 1 < len(paragraphs) else ""
            classified = _classify_with_llm(
                paragraph_text=paragraph["text"],
                section_heading=section["title"],
                previous_text=previous_text,
                next_text=next_text,
                storyline_confirmed=storyline_confirmed,
                llm_client=llm_client,
            )
            role, confidence, rationale = classified or _fallback_role(section["title"], paragraph["text"])
            items.append(
                {
                    "paragraph_id": paragraph["id"],
                    "section": section["title"],
                    "role": role,
                    "confidence": round(confidence, 3),
                    "rationale": rationale,
                    "source_text": paragraph["text"],
                }
            )

    return {
        "document_name": paper_raw["document_name"],
        "supported_roles": list(SUPPORTED_ROLES),
        "item_count": len(items),
        "items": items,
    }
