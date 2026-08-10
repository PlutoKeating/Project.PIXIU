"""Command-line entry point for scoring captured PIXIU predictions."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .dataset import EvalInputError, load_dataset, load_predictions
from .eval import EvalConfigurationError, EvalService, write_report
from .reference import build_reference_dataset
from .models import ReportStatus


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.foundation.eval",
        description="Score captured predictions and emit JSON/Markdown reports.",
    )
    parser.add_argument("--dataset", required=True, help="UTF-8 JSON path or reference-v1")
    parser.add_argument("--predictions", required=True, help="UTF-8 JSON captured predictions")
    parser.add_argument("--output-dir", required=True, help="explicit report output directory")
    parser.add_argument("--stem", default="eval-report", help="report filename stem")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        dataset = (
            build_reference_dataset()
            if args.dataset == "reference-v1"
            else load_dataset(args.dataset)
        )
        predictions = load_predictions(args.predictions)
        report = EvalService().evaluate_predictions(dataset, predictions)
        json_path, markdown_path = write_report(
            report,
            args.output_dir,
            stem=args.stem,
            overwrite=args.overwrite,
        )
    except (EvalInputError, EvalConfigurationError, FileExistsError) as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": report.overall_status.value,
                "json_report": str(json_path),
                "markdown_report": str(markdown_path),
            },
            ensure_ascii=False,
        )
    )
    if report.overall_status is ReportStatus.PASS:
        return 0
    if report.overall_status is ReportStatus.FAIL:
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
