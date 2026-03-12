"""Human-in-the-loop alignment checkpoint for storyline and core claims."""

from __future__ import annotations

import sys


def _normalize(text: str | None) -> str:
    return " ".join((text or "").strip().split())


def build_storyline_draft(
    paper_raw: dict,
    section_roles: dict,
    claims: dict,
    evidence_map: dict,
) -> dict:
    role_by_paragraph = {item["paragraph_id"]: item for item in section_roles["items"]}
    claim_by_paragraph = {item["paragraph_id"]: item for item in claims["items"]}
    evidence_by_paragraph = {item["paragraph_id"]: item for item in evidence_map["items"]}

    problem = ""
    gap = ""
    contribution = ""
    evidence_path: list[str] = []
    significance = ""

    for section in paper_raw["sections"]:
        for paragraph in section["paragraphs"]:
            paragraph_id = paragraph["id"]
            role = role_by_paragraph[paragraph_id]["role"]
            claim_item = claim_by_paragraph[paragraph_id]
            evidence_item = evidence_by_paragraph[paragraph_id]
            text = paragraph["text"]

            if not problem and role in {"Background", "Field Context", "Gap Identification"}:
                problem = text.split(".")[0].strip() + "."
            if not gap and role == "Gap Identification":
                gap = claim_item["claim_text"] or text
            if not contribution and role == "Contribution":
                contribution = claim_item["claim_text"] or text
            if role == "Result Interpretation" and evidence_item["has_evidence"]:
                evidence_path.append(claim_item["claim_text"] or text)
            if not significance and role == "Discussion":
                significance = claim_item["claim_text"] or text

    return {
        "document_name": paper_raw["document_name"],
        "problem": _normalize(problem) or "Problem not clearly extracted.",
        "gap": _normalize(gap) or "Gap not clearly extracted.",
        "contribution": _normalize(contribution) or "Contribution not clearly extracted.",
        "evidence_path": evidence_path[:3],
        "significance": _normalize(significance) or "Significance not clearly extracted.",
    }


def build_core_claim_candidates(
    paper_raw: dict,
    section_roles: dict,
    claims: dict,
    max_claims: int = 7,
) -> dict:
    role_by_paragraph = {item["paragraph_id"]: item for item in section_roles["items"]}

    ranked: list[dict] = []
    role_rank = {
        "Contribution": 0,
        "Result Interpretation": 1,
        "Discussion": 2,
        "Gap Identification": 3,
        "Background": 4,
        "Field Context": 5,
    }

    for item in claims["items"]:
        if not item["has_claim"] or not item["claim_text"]:
            continue
        role = role_by_paragraph[item["paragraph_id"]]["role"]
        ranked.append(
            {
                "claim_id": f"claim_{item['paragraph_id']}",
                "paragraph_id": item["paragraph_id"],
                "section": item["section"],
                "role": role,
                "text": item["claim_text"],
                "default_label": "primary" if role == "Contribution" else "secondary",
                "_rank": role_rank.get(role, 99),
            }
        )

    ranked.sort(key=lambda item: (item["_rank"], item["paragraph_id"]))
    items = []
    for item in ranked[:max_claims]:
        item.pop("_rank", None)
        items.append(item)

    return {
        "document_name": paper_raw["document_name"],
        "item_count": len(items),
        "items": items,
    }


def _interactive_confirm_storyline(storyline_draft: dict) -> dict:
    print("\n[PaperDoctor] HITL checkpoint: storyline draft")
    for key in ["problem", "gap", "contribution", "significance"]:
        print(f"  {key}: {storyline_draft[key]}")
    print(f"  evidence_path: {storyline_draft['evidence_path']}")
    accept = input("[PaperDoctor] Accept storyline draft? [Y/n]: ").strip().lower()
    if accept in {"", "y", "yes"}:
        return storyline_draft

    confirmed = dict(storyline_draft)
    for key in ["problem", "gap", "contribution", "significance"]:
        edited = input(f"[PaperDoctor] Edit {key} (Enter to keep current): ").strip()
        if edited:
            confirmed[key] = edited
    evidence_path = input("[PaperDoctor] Edit evidence_path as ';' separated claims (Enter to keep): ").strip()
    if evidence_path:
        confirmed["evidence_path"] = [part.strip() for part in evidence_path.split(";") if part.strip()]
    return confirmed


def _interactive_confirm_claims(core_claims_draft: dict) -> dict:
    print("\n[PaperDoctor] HITL checkpoint: core claim candidates")
    for index, item in enumerate(core_claims_draft["items"], start=1):
        print(f"  {index}. [{item['default_label']}] {item['section']} | {item['role']} | {item['text']}")
    print("[PaperDoctor] Mark claims with p=primary, s=secondary, r=remove. Example: 1:p,2:s,3:r")
    raw = input("[PaperDoctor] Labels (Enter to accept defaults): ").strip()
    label_map = {}
    if raw:
        for part in raw.split(","):
            if ":" not in part:
                continue
            index_text, label_text = part.split(":", 1)
            try:
                label_map[int(index_text.strip())] = label_text.strip().lower()
            except ValueError:
                continue

    items = []
    for index, item in enumerate(core_claims_draft["items"], start=1):
        label = label_map.get(index, item["default_label"])
        normalized = {"p": "primary", "s": "secondary", "r": "remove"}.get(label, label)
        if normalized == "remove":
            continue
        items.append(
            {
                "claim_id": item["claim_id"],
                "paragraph_id": item["paragraph_id"],
                "section": item["section"],
                "role": item["role"],
                "text": item["text"],
                "label": normalized if normalized in {"primary", "secondary"} else item["default_label"],
            }
        )

    missing = input("[PaperDoctor] Add missing claim (optional, Enter to skip): ").strip()
    if missing:
        items.append(
            {
                "claim_id": f"claim_added_{len(items)+1}",
                "paragraph_id": "manual",
                "section": "Manual",
                "role": "Manual",
                "text": missing,
                "label": "primary",
            }
        )

    return {
        "document_name": core_claims_draft["document_name"],
        "item_count": len(items),
        "items": items,
    }


def run_hitl_alignment_checkpoint(
    storyline_draft: dict,
    core_claims_draft: dict,
) -> tuple[dict, dict]:
    if not sys.stdin.isatty():
        confirmed_claims = [
            {
                "claim_id": item["claim_id"],
                "paragraph_id": item["paragraph_id"],
                "section": item["section"],
                "role": item["role"],
                "text": item["text"],
                "label": item["default_label"],
            }
            for item in core_claims_draft["items"]
            if item["default_label"] != "remove"
        ]
        return storyline_draft, {
            "document_name": core_claims_draft["document_name"],
            "item_count": len(confirmed_claims),
            "items": confirmed_claims,
        }

    storyline_confirmed = _interactive_confirm_storyline(storyline_draft)
    core_claims_confirmed = _interactive_confirm_claims(core_claims_draft)
    return storyline_confirmed, core_claims_confirmed


def _interactive_confirm_issue_strategy(issue_clusters: dict) -> dict:
    print("\n[PaperDoctor] HITL checkpoint: issue strategy")
    print("[PaperDoctor] Mark each cluster as f=fix, r=reframe, d=defer. Press Enter to keep the default.")
    items: list[dict] = []
    for index, item in enumerate(issue_clusters["items"], start=1):
        default_action = "fix" if item["priority"] <= 2 else "reframe"
        print(
            f"  {index}. [{default_action}] {item['issue_type']} | {item['section']} | {item['problem']}"
        )
        raw = input(f"[PaperDoctor] Action for cluster {index} [f/r/d, default={default_action}]: ").strip().lower()
        action = {"f": "fix", "r": "reframe", "d": "defer"}.get(raw, default_action)
        rationale = input("[PaperDoctor] Optional note (Enter to skip): ").strip()
        items.append(
            {
                "cluster_id": item["cluster_id"],
                "issue_type": item["issue_type"],
                "section": item["section"],
                "problem": item["problem"],
                "action": action,
                "rationale": rationale,
            }
        )
    return {
        "document_name": issue_clusters["document_name"],
        "item_count": len(items),
        "items": items,
    }


def run_issue_strategy_checkpoint(issue_clusters: dict) -> dict:
    if not sys.stdin.isatty():
        items = []
        for item in issue_clusters["items"]:
            default_action = "fix" if item["priority"] <= 2 else "reframe"
            items.append(
                {
                    "cluster_id": item["cluster_id"],
                    "issue_type": item["issue_type"],
                    "section": item["section"],
                    "problem": item["problem"],
                    "action": default_action,
                    "rationale": "",
                }
            )
        return {
            "document_name": issue_clusters["document_name"],
            "item_count": len(items),
            "items": items,
        }

    return _interactive_confirm_issue_strategy(issue_clusters)
