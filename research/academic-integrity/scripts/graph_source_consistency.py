#!/usr/bin/env python3
"""Compare source data against reported graph summary values."""

from __future__ import annotations

import argparse
from typing import Dict, List, Optional

from integrity_common import add_common_args, emit_result, load_table, make_finding, make_result, mean, numeric_columns, parse_float, sample_sd


def find_col(row: Dict[str, object], names: List[str]) -> Optional[str]:
    lower = {str(key).lower(): key for key in row.keys()}
    for name in names:
        if name in lower:
            return lower[name]
    return None


def run(source: str, reported: str, tolerance: float) -> Dict[str, object]:
    source_rows = load_table(source)
    reported_rows = load_table(reported)
    source_stats = {
        column: {"n": len(values), "mean": mean(values), "sd": sample_sd(values)}
        for column, values in numeric_columns(source_rows, min_n=2).items()
    }
    findings = []
    for row in reported_rows:
        group_col = find_col(row, ["group", "column", "name", "label", "condition"])
        mean_col = find_col(row, ["mean", "average", "avg"])
        sd_col = find_col(row, ["sd", "std", "standard_deviation"])
        sem_col = find_col(row, ["sem", "se", "stderr", "standard_error"])
        n_col = find_col(row, ["n", "sample_size"])
        if group_col is None:
            continue
        group = str(row.get(group_col))
        if group not in source_stats:
            continue
        stats = source_stats[group]
        if mean_col is not None:
            reported_mean = parse_float(row.get(mean_col))
            if reported_mean is not None and abs(reported_mean - stats["mean"]) > tolerance:
                findings.append(
                    make_finding(
                        method="graph_source_consistency",
                        severity="HIGH",
                        location=group,
                        description="Reported mean does not match the mean recalculated from source data.",
                        statistics={"reported_mean": reported_mean, "source_mean": round(stats["mean"], 6), "tolerance": tolerance},
                    )
                )
        if sd_col is not None:
            reported_sd = parse_float(row.get(sd_col))
            if reported_sd is not None and abs(reported_sd - stats["sd"]) > tolerance:
                findings.append(
                    make_finding(
                        method="graph_source_consistency",
                        severity="MEDIUM",
                        location=group,
                        description="Reported SD does not match source data.",
                        statistics={"reported_sd": reported_sd, "source_sd": round(stats["sd"], 6), "tolerance": tolerance},
                    )
                )
        if sem_col is not None:
            reported_sem = parse_float(row.get(sem_col))
            source_sem = stats["sd"] / (stats["n"] ** 0.5)
            if reported_sem is not None and abs(reported_sem - source_sem) > tolerance:
                findings.append(
                    make_finding(
                        method="graph_source_consistency",
                        severity="MEDIUM",
                        location=group,
                        description="Reported SEM does not match source data.",
                        statistics={"reported_sem": reported_sem, "source_sem": round(source_sem, 6), "tolerance": tolerance},
                    )
                )
        if n_col is not None:
            reported_n = parse_float(row.get(n_col))
            if reported_n is not None and int(reported_n) != stats["n"]:
                findings.append(
                    make_finding(
                        method="graph_source_consistency",
                        severity="MEDIUM",
                        location=group,
                        description="Reported n does not match source data count.",
                        statistics={"reported_n": int(reported_n), "source_n": stats["n"]},
                    )
                )
    return make_result(
        tool="graph_source_consistency",
        input_value={"source": source, "reported": reported},
        findings=findings,
        evidence_files=[source, reported],
        limitations=["Requires reported table rows to name source-data columns/groups. P-values are not recalculated here."],
        metadata={"source_columns": list(source_stats.keys()), "reported_rows": len(reported_rows)},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare source data to reported graph summaries.")
    parser.add_argument("--source", required=True, help="Source data CSV/TSV/XLSX")
    parser.add_argument("--reported", required=True, help="Reported summary CSV/TSV/XLSX with group/mean/sd/sem/n columns")
    parser.add_argument("--tolerance", type=float, default=1e-6)
    add_common_args(parser)
    args = parser.parse_args()
    emit_result(run(args.source, args.reported, args.tolerance), args.format, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
