"""Human-in-the-loop alignment checkpoint for storyline and core claims."""

from __future__ import annotations

import sys

MAX_CORE_CLAIMS = 5
MAX_ISSUE_CLUSTERS_FOR_HITL = 10
PRIMARY_CLAIM_MARKERS = ("we introduce", "we propose", "we present", "framework", "we demonstrate", "we develop")


def _normalize(text: str | None) -> str:
    return " ".join((text or "").strip().split())


def build_storyline_draft(
    paper_raw: dict,
    section_roles: dict,
    claims: dict,
) -> dict:
    role_by_paragraph = {item["paragraph_id"]: item for item in section_roles["items"]}
    claim_by_paragraph = {item["paragraph_id"]: item for item in claims["items"]}

    problem = ""
    gap = ""
    contribution = ""
    evidence_path: list[str] = []
    significance = ""
    contribution_candidates: list[str] = []

    for section in paper_raw["sections"]:
        for paragraph in section["paragraphs"]:
            paragraph_id = paragraph["id"]
            role = role_by_paragraph[paragraph_id]["role"]
            claim_item = claim_by_paragraph[paragraph_id]
            text = paragraph["text"]

            if not problem and role in {"background", "gap"}:
                problem = text.split(".")[0].strip() + "."
            if not gap and role == "gap":
                gap = claim_item["claim_text"] or text
            if not contribution and role in {"objective", "contribution"}:
                contribution = claim_item["claim_text"] or text
            if claim_item["claim_text"] and any(marker in claim_item["claim_text"].lower() for marker in PRIMARY_CLAIM_MARKERS):
                contribution_candidates.append(claim_item["claim_text"])
            if role in {"result", "interpretation"} and claim_item["claim_text"]:
                evidence_path.append(claim_item["claim_text"] or text)
            if not significance and role in {"significance", "interpretation", "limitation"}:
                significance = claim_item["claim_text"] or text

    return {
        "document_name": paper_raw["document_name"],
        "problem": _normalize(problem) or "Problem not clearly extracted.",
        "gap": _normalize(gap) or "Gap not clearly extracted.",
        "contribution": _normalize(contribution) or (contribution_candidates[0] if contribution_candidates else (evidence_path[0] if evidence_path else "Contribution not clearly extracted.")),
        "evidence_path": evidence_path[:3],
        "significance": _normalize(significance) or "Significance not clearly extracted.",
    }


def build_core_claim_candidates(
    paper_raw: dict,
    section_roles: dict,
    claims: dict,
    max_claims: int = MAX_CORE_CLAIMS,
) -> dict:
    role_by_paragraph = {item["paragraph_id"]: item for item in section_roles["items"]}

    ranked: list[dict] = []
    role_rank = {
        "contribution": 0,
        "objective": 1,
        "result": 2,
        "interpretation": 3,
        "significance": 4,
        "gap": 5,
        "background": 6,
    }

    for item in claims["items"]:
        if not item["has_claim"] or not item["claim_text"]:
            continue
        role = role_by_paragraph[item["paragraph_id"]]["role"]
        claim_text = item["claim_text"].lower()
        rank = role_rank.get(role, 99)
        if any(marker in claim_text for marker in PRIMARY_CLAIM_MARKERS):
            rank = min(rank, 0)
        ranked.append(
            {
                "claim_id": f"claim_{item['paragraph_id']}",
                "paragraph_id": item["paragraph_id"],
                "section": item["section"],
                "role": role,
                "text": item["claim_text"],
                "default_label": "primary" if role in {"contribution", "objective"} or rank == 0 else "secondary",
                "_rank": rank,
            }
        )

    ranked.sort(key=lambda item: (item["_rank"], item["paragraph_id"]))
    items = []
    for item in ranked[:max_claims]:
        item.pop("_rank", None)
        items.append(item)
    if items and not any(item["default_label"] == "primary" for item in items):
        items[0]["default_label"] = "primary"

    return {
        "document_name": paper_raw["document_name"],
        "item_count": len(items),
        "items": items,
    }


def _interactive_confirm_storyline(storyline_draft: dict) -> dict:
    print("\n[PaperDoctor] HITL checkpoint: storyline draft")
    print("[PaperDoctor] Step 1/3. Press Enter to accept all, or edit selected fields with key=value.")
    print("[PaperDoctor] Example: gap=Existing methods do not isolate causal effects.; contribution=We introduce VC2O.")
    for key in ["problem", "gap", "contribution", "significance"]:
        print(f"  {key}: {storyline_draft[key]}")
    print(f"  evidence_path: {storyline_draft['evidence_path']}")
    raw = input("[PaperDoctor] Storyline edits: ").strip()
    if not raw:
        return storyline_draft

    confirmed = dict(storyline_draft)
    key_map = {
        "problem": "problem",
        "gap": "gap",
        "contribution": "contribution",
        "significance": "significance",
        "evidence_path": "evidence_path",
    }
    for part in raw.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if not value or key not in key_map:
            continue
        if key == "evidence_path":
            confirmed["evidence_path"] = [item.strip() for item in value.split("|") if item.strip()]
        else:
            confirmed[key_map[key]] = value
    return confirmed


def _interactive_confirm_claims(core_claims_draft: dict) -> dict:
    print("\n[PaperDoctor] HITL checkpoint: core claim candidates")
    print("[PaperDoctor] Step 2/3. Keep only the claims that should anchor diagnosis.")
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

    missing = input("[PaperDoctor] Add one missing anchor claim if needed (Enter to skip): ").strip()
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

    primary_count = sum(1 for item in items if item["label"] == "primary")
    if primary_count == 0 and items:
        items[0]["label"] = "primary"

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
    print("[PaperDoctor] Step 3/3. Mark only the exceptions. Defaults already prioritize high-leverage issues.")
    print("[PaperDoctor] Use f=fix, r=reframe, d=defer. Example: 2:r,5:d")
    items: list[dict] = []
    visible_items = issue_clusters["items"][:MAX_ISSUE_CLUSTERS_FOR_HITL]
    for index, item in enumerate(visible_items, start=1):
        default_action = "fix" if item["priority"] <= 2 else "reframe"
        print(
            f"  {index}. [{default_action}] {item['issue_type']} | {item['section']} | {item['problem']}"
        )
    raw = input("[PaperDoctor] Strategy overrides: ").strip().lower()
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
    notes = input("[PaperDoctor] Optional notes for changed items, e.g. 2=no extra experiments (Enter to skip): ").strip()
    note_map = {}
    if notes:
        for part in notes.split(","):
            if ":" not in part:
                continue
            index_text, note_text = part.split(":", 1)
            try:
                note_map[int(index_text.strip())] = note_text.strip()
            except ValueError:
                continue
    for index, item in enumerate(visible_items, start=1):
        default_action = "fix" if item["priority"] <= 2 else "reframe"
        action = {"f": "fix", "r": "reframe", "d": "defer"}.get(label_map.get(index, ""), default_action)
        items.append(
            {
                "cluster_id": item["cluster_id"],
                "issue_type": item["issue_type"],
                "section": item["section"],
                "problem": item["problem"],
                "action": action,
                "rationale": note_map.get(index, ""),
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
        for item in issue_clusters["items"][:MAX_ISSUE_CLUSTERS_FOR_HITL]:
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
