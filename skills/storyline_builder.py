"""Build a final storyline summary from confirmed anchors and clustered risks."""

from __future__ import annotations


def _detect_significance_risk(issue_clusters: dict | None) -> str:
    if not issue_clusters:
        return "unknown"
    for item in issue_clusters["items"]:
        if item["issue_type"] == "significance":
            return "significance_issue_detected"
    return "clear"


def build_storyline(
    storyline_confirmed: dict,
    core_claims_confirmed: dict,
    issue_clusters: dict | None = None,
) -> dict:
    cluster_items = issue_clusters["items"] if issue_clusters else []
    main_risks = [
        {
            "cluster_id": item["cluster_id"],
            "issue_type": item["issue_type"],
            "problem": item["problem"],
        }
        for item in cluster_items[:5]
    ][:5]

    supporting_results = [
        item["text"]
        for item in core_claims_confirmed.get("items", [])
        if item["label"] in {"primary", "secondary"}
    ][:3]

    return {
        "document_name": storyline_confirmed["document_name"],
        "main_problem": storyline_confirmed.get("problem", "Main problem not confirmed."),
        "main_gap": storyline_confirmed.get("gap", "Main gap not confirmed."),
        "core_contribution": storyline_confirmed.get("contribution", "Core contribution not confirmed."),
        "supporting_results": supporting_results,
        "main_risks": main_risks,
        "significance_risk": _detect_significance_risk(issue_clusters),
        "significance": storyline_confirmed.get("significance", "Significance not confirmed."),
        "evidence_path": storyline_confirmed.get("evidence_path", []),
    }
