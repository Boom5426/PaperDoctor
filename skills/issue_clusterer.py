"""Merge paragraph-level issues into paper-level issue clusters."""

from __future__ import annotations

from collections import defaultdict

ISSUE_ORDER = {
    "evidence": 0,
    "scope": 1,
    "validation": 2,
    "contribution": 3,
    "gap": 4,
    "narrative": 5,
    "significance": 6,
}


def _cluster_key(item: dict) -> tuple[str, str, str]:
    if item["issue_type"] in {"gap", "narrative", "contribution"}:
        theme = item["section"].lower()
    elif item["issue_type"] in {"validation", "evidence"}:
        claim_text = item["claim"]["claim_text"] or item["logical_vulnerability"]
        theme = " ".join(claim_text.lower().split()[:3])
    else:
        claim_text = item["claim"]["claim_text"] or item["logical_vulnerability"]
        theme = " ".join(claim_text.lower().split()[:4])
    return item["issue_type"], item["section"], theme


def build_issue_clusters(logic_map: dict) -> dict:
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for item in logic_map["items"]:
        grouped[_cluster_key(item)].append(item)

    clusters: list[dict] = []
    for index, ((issue_type, section, theme), items) in enumerate(grouped.items(), start=1):
        lead = sorted(items, key=lambda item: (item["priority"], item["paragraph_id"]))[0]
        clusters.append(
            {
                "cluster_id": f"cluster_{index}",
                "issue_type": issue_type,
                "section": section,
                "theme": theme,
                "priority": min(item["priority"] for item in items),
                "problem": lead["logical_vulnerability"],
                "source_issue_ids": [item["issue_id"] for item in items],
                "source_paragraph_ids": [item["paragraph_id"] for item in items],
                "claim_examples": [
                    item["claim"]["claim_text"]
                    for item in items
                    if item["claim"]["claim_text"]
                ][:3],
                "evidence_summary": [
                    evidence["value"]
                    for item in items
                    for evidence in item["evidence"]["items"]
                ][:5],
                "representative_span": lead["source_text"],
            }
        )

    clusters.sort(
        key=lambda item: (
            item["priority"],
            ISSUE_ORDER.get(item["issue_type"], 99),
            item["section"],
            item["cluster_id"],
        )
    )
    return {
        "document_name": logic_map["document_name"],
        "item_count": len(clusters),
        "items": clusters,
    }
