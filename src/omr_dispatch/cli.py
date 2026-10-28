"""
Walking Skeleton Command-Line Interface (`src/omr_dispatch/cli.py`).

Compliant with:
- ADR-0008: Structured logging, no raw sys.stdout write via built-ins in src/ (T20 rule).
- ADR-0013: Delivery strategy via walking skeleton (ADR-0013 Option 2).
- ADR-0016: Unified Assessment entity and capability branching (OMR_MCQ & MARKS_ENTRY_TOTALS).
- ADR-0017: Multi-tenant tenant context (mandatory org_id).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from omr_dispatch.diagnostics import evaluate_batch
from omr_dispatch.ingestion import (
    import_marks_entry,
    import_roster,
    import_submissions,
    import_test_paper,
)
from omr_dispatch.models import (
    AssessmentKind,
    EvaluationBundle,
    IngestionError,
)


def _write_stdout(message: str) -> None:
    """Write text to standard output stream per ADR-0008."""
    sys.stdout.write(message)
    sys.stdout.flush()


def _write_stderr(message: str) -> None:
    """Write error text to standard error stream per ADR-0008."""
    sys.stderr.write(message)
    sys.stderr.flush()


def _format_summary_text(bundle: EvaluationBundle) -> str:
    """Format human-readable summary text for batch evaluation."""
    bm = bundle.batch_metrics
    lines = [
        "============================================================",
        f" Batch Evaluation Summary: {bundle.assessment_name or bundle.test_id or 'Assessment'}",
        "============================================================",
        f" Assessment Kind : {bundle.kind.value}",
        f" Organization ID : {bundle.org_id}",
        f" Enrolled Count  : {bm.enrolled_count}",
        f" Present Count   : {bm.present_count}",
        f" Absent Count    : {bm.absent_count}",
        f" Total Score Sum : {bm.total_score_sum}",
        f" Class Average   : {bm.class_average}",
        f" Topper Score    : {bm.topper_net_marks or bm.topper_marks}",
        f" PTM Required    : {bm.ptm_eligible_count} students",
        "============================================================",
        f" Total Student Reports : {len(bundle.student_reports)}",
        f" Total Contacts Assessed: {len(bundle.contacts)}",
        "============================================================\n",
    ]
    return "\n".join(lines)


def run_batch_pipeline(
    input_path: Path,
    output_path: Path,
    kind: AssessmentKind | str | None = None,
    org_id: str = "DEFAULT_INSTITUTION",
) -> EvaluationBundle:
    """
    Execute the thin walking skeleton pipeline:
    Ingest golden fixture -> Batch evaluation -> Structured JSON run manifest.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    # Resolve assessment kind
    target_kind: AssessmentKind | None = None
    if kind:
        target_kind = AssessmentKind(kind) if isinstance(kind, str) else kind

    bundle: EvaluationBundle

    if target_kind == AssessmentKind.MARKS_ENTRY_TOTALS or (
        target_kind is None
        and input_path.is_file()
        and "marks" in input_path.name.lower()
    ) or (
        target_kind is None
        and input_path.is_dir()
        and (input_path / "marks_entry_50.json").exists()
        and not (input_path / "test_paper_300.json").exists()
    ):
        # Path A: MARKS_ENTRY_TOTALS
        sheet_file = (
            input_path
            if input_path.is_file()
            else (input_path / "marks_entry_50.json")
        )
        marks_res = import_marks_entry(sheet_file, org_id=org_id)
        if not marks_res.is_success or marks_res.records is None:
            raise IngestionError(f"Failed to ingest marks entry sheet from {sheet_file}")

        # Check for optional admissions roster
        roster_file = (
            input_path / "admissions_300.json"
            if input_path.is_dir() and (input_path / "admissions_300.json").exists()
            else None
        )
        roster_records = None
        if roster_file:
            roster_res = import_roster(roster_file, org_id=org_id)
            if roster_res.is_success and roster_res.records:
                roster_records = roster_res.records

        # The marks entry sheet model
        raw_sheet = json.loads(sheet_file.read_text(encoding="utf-8"))
        bundle = evaluate_batch(
            assessment=raw_sheet,
            admissions=roster_records,
            submissions=None,
            org_id=org_id,
        )

    else:
        # Path B: OMR_MCQ
        paper_file: Path
        admissions_file: Path
        submissions_file: Path

        if input_path.is_dir():
            paper_file = input_path / "test_paper_300.json"
            admissions_file = input_path / "admissions_300.json"
            submissions_file = input_path / "submissions_300.json"
        else:
            parent = input_path.parent
            paper_file = parent / "test_paper_300.json"
            admissions_file = parent / "admissions_300.json"
            submissions_file = parent / "submissions_300.json"

        paper_res = import_test_paper(paper_file, org_id=org_id)
        if not paper_res.is_success or paper_res.records is None:
            raise IngestionError(f"Failed to import test paper from {paper_file}")

        roster_res = import_roster(admissions_file, org_id=org_id)
        if not roster_res.is_success or roster_res.records is None:
            raise IngestionError(f"Failed to import roster from {admissions_file}")

        sub_res = import_submissions(submissions_file, org_id=org_id)
        if not sub_res.is_success or sub_res.records is None:
            raise IngestionError(f"Failed to import submissions from {submissions_file}")

        bundle = evaluate_batch(
            assessment=paper_res.records[0],
            admissions=roster_res.records,
            submissions=sub_res.records,
            org_id=org_id,
        )

    # Write structured JSON manifest (ADR-0013)
    manifest_data: dict[str, Any] = {
        "schema_version": bundle.schema_version,
        "org_id": bundle.org_id,
        "kind": bundle.kind.value,
        "assessment_name": bundle.assessment_name,
        "test_id": bundle.test_id,
        "batch_metrics": bundle.batch_metrics.model_dump(),
        "student_reports": [r.model_dump() for r in bundle.student_reports],
        "contacts": [c.to_golden_dict() for c in bundle.contacts],
    }

    manifest_file = output_path / "run_manifest.json"
    manifest_file.write_text(
        json.dumps(manifest_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return bundle


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for omr-dispatch (ADR-0013)."""
    parser = argparse.ArgumentParser(
        prog="omr-dispatch",
        description="Deterministic OMR diagnostics and notification engine for schools.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # 'run-batch' subcommand
    run_parser = subparsers.add_parser(
        "run-batch",
        help="Execute dry run batch evaluation from input fixtures to output manifest.",
    )
    run_parser.add_argument(
        "--input",
        "-i",
        required=True,
        type=Path,
        help="Path to input directory or file containing assessment fixtures.",
    )
    run_parser.add_argument(
        "--output",
        "-o",
        required=True,
        type=Path,
        help="Path to output directory for run_manifest.json.",
    )
    run_parser.add_argument(
        "--kind",
        "-k",
        choices=["OMR_MCQ", "MARKS_ENTRY_TOTALS"],
        default=None,
        help="Assessment kind (auto-detected if omitted).",
    )
    run_parser.add_argument(
        "--org-id",
        default="DEFAULT_INSTITUTION",
        help="Institutional tenant identifier (default: DEFAULT_INSTITUTION).",
    )

    args = parser.parse_args(argv)

    if not args.subcommand or args.subcommand == "run-batch":
        # If no subcommand passed but arguments match run-batch flags
        if not hasattr(args, "input") or not args.input:
            parser.print_help(sys.stderr)
            return 1

        try:
            bundle = run_batch_pipeline(
                input_path=args.input,
                output_path=args.output,
                kind=args.kind,
                org_id=args.org_id,
            )
            summary_text = _format_summary_text(bundle)
            _write_stdout(summary_text)
            _write_stdout(
                f"[OK] Walking skeleton run manifest written to: {args.output / 'run_manifest.json'}\n"
            )
            return 0
        except Exception as exc:
            _write_stderr(f"[ERROR] Batch evaluation failed: {exc}\n")
            return 1

    parser.print_help(sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
