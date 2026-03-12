"""Extract paragraph-level claims with an LLM-led hybrid span selector."""

from __future__ import annotations

import json
import re


CLAIM_MARKERS = (
    "we propose",
    "we present",
    "we show",
    "we find",
    "this paper",
    "our results",
    "this study",
    "we demonstrate",
    "we introduce",
    "we develop",
    "we developed",
    "improves",
    "outperforms",
    "can help",
    "suggests",
)
PRIMARY_MARKERS = (
    "we introduce",
    "we propose",
    "we present",
    "we develop",
    "we developed",
    "we demonstrate",
    "framework",
    "benchmark",
)

CLAIM_EXTRACTION_SYSTEM_PROMPT = """
You extract the best paragraph-level author claim span from academic writing.

Return strict JSON with keys:
- has_claim
- claim_text
- status
- confidence
- rationale

Rules:
- If the paragraph contains a meaningful author claim, set has_claim=true and return the most central faithful span.
- Prefer contribution, objective, result, or interpretation spans over weak transition phrases.
- claim_text must be copied from the paragraph, not rewritten.
- If there is no clear claim, set has_claim=false and claim_text=null.
- status must be one of:
  - explicit_marker
  - inferred_claim
  - descriptive_paragraph
  - no_explicit_claim
  - empty_paragraph
- confidence must be a float between 0 and 1.
- rationale must be one short sentence.
""".strip()


def _split_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]


def _sentence_score(sentence: str, section_title: str, role: str | None) -> int:
    lower_sentence = sentence.lower()
    lower_section = section_title.lower()
    score = 0
    if any(marker in lower_sentence for marker in CLAIM_MARKERS):
        score += 4
    if any(marker in lower_sentence for marker in PRIMARY_MARKERS):
        score += 3
    if any(marker in lower_sentence for marker in ("however", "therefore", "thus", "together", "these results")):
        score += 1
    if any(marker in lower_sentence for marker in ("figure", "fig.", "table", "improves", "outperforms", "significant")):
        score += 2
    if role in {"objective", "contribution", "result", "interpretation", "significance"}:
        score += 2
    if "abstract" in lower_section or "intro" in lower_section:
        score += 1
    if sentence.lower().startswith(("finally, we organized", "first,", "second,", "third,", "finally,")):
        score -= 3
    return score


def _find_claim(text: str, section_title: str, role: str | None = None) -> tuple[bool, str | None, str, float, str]:
    sentences = _split_sentences(text)
    if not sentences:
        return False, None, "empty_paragraph", 0.0, "Paragraph is empty."
    scored = sorted(
        ((-_sentence_score(sentence, section_title, role), index, sentence) for index, sentence in enumerate(sentences)),
        key=lambda item: (item[0], item[1]),
    )
    best_sentence = scored[0][2]
    best_score = -scored[0][0]
    if best_score >= 5:
        status = "explicit_marker" if any(marker in best_sentence.lower() for marker in CLAIM_MARKERS) else "inferred_claim"
        confidence = 0.82 if status == "explicit_marker" else 0.68
        return True, best_sentence, status, confidence, "Best-scoring claim span selected from the paragraph."
    if len(sentences) == 1 and len(sentences[0].split()) >= 8:
        return False, None, "no_explicit_claim", 0.35, "Paragraph is substantive but lacks a clear claim span."
    return False, None, "descriptive_paragraph", 0.4, "Paragraph is mainly descriptive rather than claim-bearing."


def _extract_claim_with_llm(
    *,
    text: str,
    section_title: str,
    role: str | None,
    previous_text: str,
    next_text: str,
    llm_client,
) -> tuple[bool, str | None, str, float, str] | None:
    if not llm_client or not llm_client.is_configured:
        return None

    user_prompt = json.dumps(
        {
            "section_heading": section_title,
            "role_hint": role,
            "paragraph_text": text,
            "previous_paragraph": previous_text,
            "next_paragraph": next_text,
        },
        ensure_ascii=False,
        indent=2,
    )
    try:
        payload = llm_client.chat_json(CLAIM_EXTRACTION_SYSTEM_PROMPT, user_prompt)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    required = {"has_claim", "claim_text", "status", "confidence", "rationale"}
    if not required.issubset(payload):
        return None
    if not isinstance(payload["has_claim"], bool):
        return None
    if payload["claim_text"] is not None and not isinstance(payload["claim_text"], str):
        return None
    if not isinstance(payload["status"], str):
        return None
    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError):
        return None
    if not isinstance(payload["rationale"], str):
        return None
    return (
        payload["has_claim"],
        payload["claim_text"],
        payload["status"],
        max(0.0, min(confidence, 1.0)),
        payload["rationale"].strip() or "LLM claim extraction.",
    )


def extract_claims(paper_raw: dict, section_roles: dict | None = None, llm_client=None) -> dict:
    role_by_paragraph = {item["paragraph_id"]: item for item in section_roles["items"]} if section_roles else {}
    items: list[dict] = []

    for section in paper_raw["sections"]:
        paragraphs = section["paragraphs"]
        for index, paragraph in enumerate(paragraphs):
            previous_text = paragraphs[index - 1]["text"] if index > 0 else ""
            next_text = paragraphs[index + 1]["text"] if index + 1 < len(paragraphs) else ""
            role = role_by_paragraph.get(paragraph["id"], {}).get("role")
            extracted = _extract_claim_with_llm(
                text=paragraph["text"],
                section_title=section["title"],
                role=role,
                previous_text=previous_text,
                next_text=next_text,
                llm_client=llm_client,
            )
            has_claim, claim_text, status, confidence, rationale = extracted or _find_claim(
                paragraph["text"],
                section["title"],
                role,
            )
            items.append(
                {
                    "paragraph_id": paragraph["id"],
                    "section": section["title"],
                    "has_claim": has_claim,
                    "claim_text": claim_text,
                    "status": status,
                    "confidence": round(confidence, 3),
                    "rationale": rationale,
                    "source_text": paragraph["text"],
                }
            )

    return {
        "document_name": paper_raw["document_name"],
        "item_count": len(items),
        "items": items,
    }
