"""Map confirmed claims to supporting evidence spans with an LLM-led hybrid approach."""

from __future__ import annotations

import json
import re


CITATION_PATTERN = re.compile(r"\[[0-9,\-\s]+\]|\([A-Z][A-Za-z]+(?: et al\.)?,\s*\d{4}\)")
FIGURE_TABLE_PATTERN = re.compile(r"\b(?:Figure|Fig\.|Table|Tab\.)\s*\d+\b")
RESULT_MARKERS = (
    "we show",
    "we find",
    "results indicate",
    "results show",
    "accuracy",
    "f1",
    "improves",
    "outperforms",
    "significant",
)
EVIDENCE_LINKING_SYSTEM_PROMPT = """
You map one confirmed paper claim to supporting evidence spans.

Return strict JSON with keys:
- evidence_spans
- evidence_type
- support_level
- missing_expected_evidence
- rationale

Rules:
- evidence_spans must be an array of objects with keys:
  - paragraph_id
  - section
  - span_text
  - anchor_text
- evidence_type must be an array chosen from:
  - figure_table
  - explicit_result
  - citation
  - method_detail
- support_level must be one of:
  - strong
  - partial
  - weak
  - unsupported
- missing_expected_evidence must be an array of short strings.
- rationale must be one short sentence.
- Prefer direct empirical support over generic background citations.
""".strip()


def _token_set(text: str | None) -> set[str]:
    normalized = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    return {token for token in normalized.split() if len(token) > 3}


def _collect_span_evidence(text: str) -> tuple[list[str], list[str]]:
    evidence_types: list[str] = []
    anchors: list[str] = []
    if CITATION_PATTERN.search(text):
        evidence_types.append("citation")
        anchors.extend(CITATION_PATTERN.findall(text)[:2])
    if FIGURE_TABLE_PATTERN.search(text):
        evidence_types.append("figure_table")
        anchors.extend(FIGURE_TABLE_PATTERN.findall(text)[:2])
    if any(marker in text.lower() for marker in RESULT_MARKERS):
        evidence_types.append("explicit_result")
        anchors.append("explicit result statement")
    if any(marker in text.lower() for marker in ("method", "benchmark", "dataset", "framework", "pipeline", "ablation", "control")):
        evidence_types.append("method_detail")
        anchors.append("method detail")
    dedup_types = list(dict.fromkeys(evidence_types))
    dedup_anchors = list(dict.fromkeys(anchors))
    return dedup_types, dedup_anchors


def _candidate_spans_for_claim(claim_text: str, paper_raw: dict, limit: int = 8) -> list[dict]:
    claim_tokens = _token_set(claim_text)
    candidates: list[tuple[int, int, dict]] = []
    for section in paper_raw["sections"]:
        for paragraph in section["paragraphs"]:
            paragraph_tokens = _token_set(paragraph["text"])
            overlap = len(claim_tokens & paragraph_tokens)
            evidence_types, anchors = _collect_span_evidence(paragraph["text"])
            score = overlap * 2 + len(evidence_types)
            if score <= 0:
                continue
            candidates.append(
                (
                    -score,
                    int(paragraph["id"].split("_")[-1]) if paragraph["id"].split("_")[-1].isdigit() else 999999,
                    {
                        "paragraph_id": paragraph["id"],
                        "section": section["title"],
                        "span_text": paragraph["text"],
                        "anchor_text": anchors[0] if anchors else "",
                        "_evidence_types": evidence_types,
                    },
                )
            )
    candidates.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in candidates[:limit]]


def _fallback_map_claim(claim: dict, paper_raw: dict) -> dict:
    candidates = _candidate_spans_for_claim(claim["text"], paper_raw)
    evidence_spans: list[dict] = []
    evidence_type: list[str] = []
    for candidate in candidates[:3]:
        if not candidate["_evidence_types"]:
            continue
        evidence_spans.append(
            {
                "paragraph_id": candidate["paragraph_id"],
                "section": candidate["section"],
                "span_text": candidate["span_text"],
                "anchor_text": candidate["anchor_text"],
            }
        )
        evidence_type.extend(candidate["_evidence_types"])
    evidence_type = list(dict.fromkeys(evidence_type))
    if "figure_table" in evidence_type and "explicit_result" in evidence_type:
        support_level = "strong"
    elif "explicit_result" in evidence_type or len(evidence_spans) >= 2:
        support_level = "partial"
    elif evidence_type:
        support_level = "weak"
    else:
        support_level = "unsupported"
    missing_expected_evidence: list[str] = []
    if support_level in {"weak", "unsupported"}:
        missing_expected_evidence.append("direct result anchor")
    if support_level != "strong" and claim["label"] == "primary":
        missing_expected_evidence.append("figure or benchmark reference")
    rationale = (
        "Claim is linked to direct result-oriented spans."
        if evidence_spans
        else "No local support span with strong lexical overlap was found."
    )
    return {
        "claim_id": claim["claim_id"],
        "claim_text": claim["text"],
        "label": claim["label"],
        "section": claim["section"],
        "evidence_spans": evidence_spans,
        "evidence_type": evidence_type,
        "support_level": support_level,
        "missing_expected_evidence": list(dict.fromkeys(missing_expected_evidence)),
        "rationale": rationale,
    }


def _map_claim_with_llm(claim: dict, paper_raw: dict, llm_client) -> dict | None:
    if not llm_client or not llm_client.is_configured:
        return None
    candidates = _candidate_spans_for_claim(claim["text"], paper_raw)
    user_prompt = json.dumps(
        {
            "claim": claim,
            "candidate_spans": [
                {
                    "paragraph_id": item["paragraph_id"],
                    "section": item["section"],
                    "span_text": item["span_text"],
                    "anchor_text": item["anchor_text"],
                }
                for item in candidates
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
    try:
        payload = llm_client.chat_json(EVIDENCE_LINKING_SYSTEM_PROMPT, user_prompt)
    except Exception:
        return None
    required_keys = {"evidence_spans", "evidence_type", "support_level", "missing_expected_evidence", "rationale"}
    if not isinstance(payload, dict) or not required_keys.issubset(payload):
        return None
    if payload["support_level"] not in {"strong", "partial", "weak", "unsupported"}:
        return None
    if not isinstance(payload["evidence_spans"], list) or not isinstance(payload["evidence_type"], list):
        return None
    if not isinstance(payload["missing_expected_evidence"], list) or not isinstance(payload["rationale"], str):
        return None
    cleaned_spans: list[dict] = []
    for item in payload["evidence_spans"][:4]:
        if not isinstance(item, dict):
            continue
        if not {"paragraph_id", "section", "span_text", "anchor_text"}.issubset(item):
            continue
        cleaned_spans.append(
            {
                "paragraph_id": str(item["paragraph_id"]),
                "section": str(item["section"]),
                "span_text": str(item["span_text"]),
                "anchor_text": str(item["anchor_text"]),
            }
        )
    return {
        "claim_id": claim["claim_id"],
        "claim_text": claim["text"],
        "label": claim["label"],
        "section": claim["section"],
        "evidence_spans": cleaned_spans,
        "evidence_type": [str(item) for item in payload["evidence_type"][:4]],
        "support_level": payload["support_level"],
        "missing_expected_evidence": [str(item) for item in payload["missing_expected_evidence"][:4]],
        "rationale": payload["rationale"].strip(),
    }


def map_evidence(paper_raw: dict, core_claims_confirmed: dict, llm_client=None) -> dict:
    prioritized_claims = sorted(
        core_claims_confirmed["items"],
        key=lambda item: (0 if item["label"] == "primary" else 1, item["claim_id"]),
    )
    items: list[dict] = []
    for claim in prioritized_claims:
        mapped = _map_claim_with_llm(claim, paper_raw, llm_client) or _fallback_map_claim(claim, paper_raw)
        items.append(mapped)
    return {
        "document_name": paper_raw["document_name"],
        "supported_evidence_types": [
            "citation",
            "figure_table",
            "explicit_result",
            "method_detail",
        ],
        "item_count": len(items),
        "items": items,
    }
