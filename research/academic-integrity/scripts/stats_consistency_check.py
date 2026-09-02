#!/usr/bin/env python3
"""Recalculate basic summary statistics from raw numeric columns."""

from __future__ import annotations

import argparse
import math

from integrity_common import add_common_args, emit_result, load_table, make_finding, make_result, mean, numeric_columns, sample_sd


def run(input_path: str, min_n: int) -> dict:
    rows = load_table(input_path)
    columns = numeric_columns(rows, min_n=min_n)
    findings = []
    summaries = {}
    for column, values in columns.items():
        sd = sample_sd(values)
        sem = sd / math.sqrt(len(values)) if values else 0.0
        summaries[column] = {"n": len(values), "mean": mean(values), "sd": sd, "sem": sem, "min": min(values), "max": max(values)}
        if len(values) >= 3 and sd == 0:
            findings.append(
                make_finding(
                    method="stats_consistency",
                    severity="HIGH",
                    location=column,
                    description="Column has zero variance across three or more values.",
                    statistics=summaries[column],
                    recommendation="Confirm whether these are true repeated constants, rounded values, or copied data.",
                )
            )
        if len(values) >= 5 and abs(sd) < 1e-12:
            findings.append(
                make_finding(
                    method="stats_consistency",
                    severity="MEDIUM",
                    location=column,
                    description="Column variance is effectively zero.",
                    statistics=summaries[column],
                )
            )
    return make_result(
        tool="stats_consistency_check",
        input_value=input_path,
        findings=findings,
        evidence_files=[input_path],
        limitations=["This script recalculates descriptive statistics only; provide summary tables for direct reported-value comparison."],
        metadata={"summaries": summaries},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Recalculate basic statistics from numeric table columns.")
    parser.add_argument("input", help="Raw data CSV/TSV/XLSX")
    parser.add_argument("--min-n", type=int, default=2)
    add_common_args(parser)
    args = parser.parse_args()
    emit_result(run(args.input, args.min_n), args.format, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
