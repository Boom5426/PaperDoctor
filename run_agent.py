from __future__ import annotations

import argparse
from pathlib import Path

from paperdoctor.agent import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the minimal PaperDoctor pipeline on a DOCX paper."
    )
    parser.add_argument("document", help="Path to the input .docx file")
    parser.add_argument(
        "--journal",
        default="Nature-family",
        help="Target journal profile for revision planning. Default: Nature-family",
    )
    parser.add_argument(
        "--scope",
        default="full",
        choices=["full", "abstract", "intro", "results"],
        help="Analysis scope. Default: full",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force recomputation instead of reusing cached artifacts.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show more detailed artifact reuse and scope statistics.",
    )
    args = parser.parse_args()

    result = run(
        Path(args.document),
        journal_name=args.journal,
        scope=args.scope,
        refresh=args.refresh,
        verbose=args.verbose,
    )
    print("PaperDoctor pipeline completed.")
    print(f"paper_id: {result['paper_id']}")
    print(f"scope: {result['scope']}")
    print(f"refresh: {result['refresh']}")
    print(f"paper_raw.json: {result['paper_raw_path']}")
    print(f"section_roles.json: {result['section_roles_path']}")
    print(f"claims.json: {result['claims_path']}")
    print(f"evidence_map.json: {result['evidence_map_path']}")
    print(f"nature_quality_rubric.json: {result['nature_quality_rubric_path']}")
    print(f"logic_map.json: {result['logic_map_path']}")
    print(f"storyline.json: {result['storyline_path']}")
    print(f"journal_profile.json: {result['journal_profile_path']}")
    print(f"revision_report.md: {result['revision_report_path']}")
    print(f"session_manifest.json: {result['session_manifest_path']}")
    print(f"logic issues: {result['logic_issue_count']}")
    print(f"revision items: {result['revision_item_count']}")
    print(f"llm configured: {result['llm_configured']}")
    print("Summary:")
    print(f"  reused artifacts: {', '.join(result['reused_artifacts']) if result['reused_artifacts'] else 'None'}")
    print(f"  recomputed artifacts: {', '.join(result['recomputed_artifacts']) if result['recomputed_artifacts'] else 'None'}")
    print(f"  outputs written: {', '.join(result['output_files'])}")
    print(f"  revision report: {result['revision_report_path']}")


if __name__ == "__main__":
    main()
