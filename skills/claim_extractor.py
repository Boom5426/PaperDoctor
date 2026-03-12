"""Extract paragraph-level claims from parsed paper content."""

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
    "improves",
    "outperforms",
    "can help",
    "suggests",
)

CLAIM_EXTRACTION_SYSTEM_PROMPT = """
You extract paragraph-level author claims from academic writing.
Return strict JSON with keys:
- has_claim
- claim_text
- status

Rules:
- If the paragraph clearly states a core claim, set has_claim=true and return the shortest faithful claim span.
- If there is no clear claim, set has_claim=false and claim_text=null.
- status must be one of:
  - explicit_marker
  - inferred_claim
  - descriptive_paragraph
  - no_explicit_claim
  - empty_paragraph
- Do not invent content not present in the paragraph.
""".strip()


def _split_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]


def _find_claim(text: str) -> tuple[bool, str | None, str]:
    sentences = _split_sentences(text)
    for sentence in sentences:
        lower_sentence = sentence.lower()
        if any(marker in lower_sentence for marker in CLAIM_MARKERS):
            return True, sentence, "explicit_marker"
    if len(sentences) == 1 and len(sentences[0].split()) >= 8:
        return False, None, "no_explicit_claim"
    if not sentences:
        return False, None, "empty_paragraph"
    return False, None, "descriptive_paragraph"


def _extract_claim_with_llm(text: str, llm_client) -> tuple[bool, str | None, str] | None:
    if not llm_client or not llm_client.is_configured:
        return None

    user_prompt = json.dumps({"paragraph_text": text}, ensure_ascii=False, indent=2)
    try:
        payload = llm_client.chat_json(CLAIM_EXTRACTION_SYSTEM_PROMPT, user_prompt)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    if not {"has_claim", "claim_text", "status"}.issubset(payload):
        return None
    if not isinstance(payload["has_claim"], bool):
        return None
    if payload["claim_text"] is not None and not isinstance(payload["claim_text"], str):
        return None
    if not isinstance(payload["status"], str):
        return None
    return payload["has_claim"], payload["claim_text"], payload["status"]


def extract_claims(paper_raw: dict, llm_client=None) -> dict:
    items: list[dict] = []

    for section in paper_raw["sections"]:
        for paragraph in section["paragraphs"]:
            extracted = _extract_claim_with_llm(paragraph["text"], llm_client)
            has_claim, claim_text, status = extracted or _find_claim(paragraph["text"])
            items.append(
                {
                    "paragraph_id": paragraph["id"],
                    "section": section["title"],
                    "has_claim": has_claim,
                    "claim_text": claim_text,
                    "status": status,
                    "source_text": paragraph["text"],
                }
            )

    return {
        "document_name": paper_raw["document_name"],
        "item_count": len(items),
        "items": items,
    }
