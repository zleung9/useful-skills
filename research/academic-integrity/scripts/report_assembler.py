#!/usr/bin/env python3
"""Assemble multiple script JSON outputs into one Markdown audit report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from integrity_common import add_common_args, emit_result, make_result, risk_level


def load_result(path: Path) -> Dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "findings" not in data:
        raise ValueError(f"{path} does not look like a script result JSON")
    data["_source_file"] = str(path)
    return data


def assemble(paths: List[str]) -> Dict[str, object]:
    files: List[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.glob("*.json")))
        else:
            files.append(path)
    results = [load_result(path) for path in files]
    findings = []
    evidence_files = []
    for result in results:
        for finding in result.get("findings", []):
            finding = dict(finding)
            finding.setdefault("statistics", {})
            finding["statistics"]["source_result"] = result.get("_source_file")
            findings.append(finding)
        evidence_files.extend(result.get("evidence_files", []))
    return make_result(
        tool="report_assembler",
        input_value=[str(path) for path in files],
        findings=findings,
        evidence_files=sorted(set(str(item) for item in evidence_files)),
        limitations=["This report assembles screening outputs; final interpretation still requires domain review and source records."],
        metadata={
            "script_results": [
                {
                    "file": result.get("_source_file"),
                    "tool": result.get("tool"),
                    "risk_level": result.get("risk_level"),
                    "finding_count": len(result.get("findings", [])),
                }
                for result in results
            ]
        },
    )


def to_audit_markdown(result: Dict[str, object]) -> str:
    lines = [
        "# Geng Academic-Integrity Script Report",
        "",
        f"- Overall script risk: {result['risk_level']}",
        f"- Result files: {len(result['metadata']['script_results'])}",
        f"- Total findings: {len(result['findings'])}",
        "",
        "## Script Inputs",
        "",
    ]
    for item in result["metadata"]["script_results"]:
        lines.append(f"- `{item['file']}`: {item.get('tool')} ({item.get('risk_level')}), findings={item.get('finding_count')}")
    lines.extend(["", "## Evidence Ledger", ""])
    if not result["findings"]:
        lines.append("No screening flags were detected.")
    else:
        lines.append("| ID | Tool/Method | Severity | Location | Description | Evidence |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for idx, finding in enumerate(result["findings"], 1):
            evidence = ", ".join(f"`{item}`" for item in finding.get("evidence_files", [])[:3])
            description = str(finding.get("description", "")).replace("|", "\\|")
            location = str(finding.get("location", "")).replace("|", "\\|")
            lines.append(
                f"| F{idx:03d} | {finding.get('method', '')} | {finding.get('severity', '')} | {location} | {description} | {evidence} |"
            )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Script results are screening evidence only.",
            "- Review source images, raw data, laboratory records, and author explanations before escalation.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble script JSON outputs into an audit report.")
    parser.add_argument("paths", nargs="+", help="JSON result files or directories containing JSON results")
    add_common_args(parser)
    args = parser.parse_args()
    result = assemble(args.paths)
    if args.format == "markdown":
        text = to_audit_markdown(result)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            print(text)
    else:
        emit_result(result, args.format, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
