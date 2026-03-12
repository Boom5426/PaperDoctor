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
    args = parser.parse_args()

    result = run(Path(args.document), journal_name=args.journal)
    print("PaperDoctor pipeline completed.")
    print(f"paper_raw.json: {result['paper_raw_path']}")
    print(f"section_roles.json: {result['section_roles_path']}")
    print(f"claims.json: {result['claims_path']}")
    print(f"evidence_map.json: {result['evidence_map_path']}")
    print(f"nature_quality_rubric.json: {result['nature_quality_rubric_path']}")
    print(f"logic_map.json: {result['logic_map_path']}")
    print(f"storyline.json: {result['storyline_path']}")
    print(f"journal_profile.json: {result['journal_profile_path']}")
    print(f"revision_report.md: {result['revision_report_path']}")
    print(f"logic issues: {result['logic_issue_count']}")
    print(f"revision items: {result['revision_item_count']}")
    print(f"llm configured: {result['llm_configured']}")


if __name__ == "__main__":
    main()
