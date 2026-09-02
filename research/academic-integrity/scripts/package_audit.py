#!/usr/bin/env python3
"""Audit whether a manuscript package contains required integrity materials."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

from integrity_common import add_common_args, emit_result, iter_files, make_finding, make_result


CATEGORIES: Dict[str, Dict[str, object]] = {
    "manuscript": {"patterns": ["manuscript", "main", "paper", "article"], "exts": {".pdf", ".docx", ".doc", ".tex"}},
    "supplement": {"patterns": ["supp", "supplement", "si", "extended"], "exts": {".pdf", ".docx", ".xlsx", ".csv", ".zip"}},
    "source_data": {"patterns": ["source", "data", "raw", "table"], "exts": {".csv", ".tsv", ".xlsx", ".xlsm", ".txt"}},
    "final_figures": {"patterns": ["figure", "fig", "panel"], "exts": {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf"}},
    "source_images": {"patterns": ["raw", "source", "uncropped", "original", "blot", "gel", "microscopy", "flow"], "exts": {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}},
    "ethics": {"patterns": ["ethic", "irb", "iacuc", "approval", "consent"], "exts": {".pdf", ".docx", ".doc", ".txt", ".md"}},
    "code": {"patterns": ["code", "script", "software", "analysis"], "exts": {".py", ".r", ".R", ".ipynb", ".m", ".sh", ".jl"}},
    "availability": {"patterns": ["availability", "repository", "accession", "protocol", "materials"], "exts": {".txt", ".md", ".docx", ".pdf"}},
}

REQUIRED = {"manuscript", "source_data", "final_figures", "source_images", "ethics"}


def matches(path: Path, spec: Dict[str, object]) -> bool:
    name = path.name.lower()
    parts = " ".join(part.lower() for part in path.parts)
    patterns = spec["patterns"]
    exts = spec["exts"]
    return path.suffix.lower() in exts and any(pattern in name or pattern in parts for pattern in patterns)


def run(root: str) -> Dict[str, object]:
    root_path = Path(root)
    files = iter_files([root], None)
    inventory: Dict[str, List[str]] = {category: [] for category in CATEGORIES}
    for file_path in files:
        for category, spec in CATEGORIES.items():
            if matches(file_path, spec):
                try:
                    display_path = file_path.relative_to(root_path)
                except ValueError:
                    display_path = file_path
                inventory[category].append(str(display_path))

    findings = []
    for category in sorted(REQUIRED):
        if not inventory[category]:
            findings.append(
                make_finding(
                    method="package_completeness",
                    severity="HIGH" if category in {"source_data", "source_images"} else "MEDIUM",
                    location=category,
                    description=f"Required package category appears missing: {category}.",
                    recommendation="Request the missing material before drawing strong integrity conclusions.",
                )
            )
    for category in sorted(set(CATEGORIES) - REQUIRED):
        if not inventory[category]:
            findings.append(
                make_finding(
                    method="package_completeness",
                    severity="LOW",
                    location=category,
                    description=f"Recommended package category was not detected: {category}.",
                    recommendation="Add this material when relevant to improve traceability.",
                )
            )

    return make_result(
        tool="package_audit",
        input_value=root,
        findings=findings,
        evidence_files=[str(path) for paths in inventory.values() for path in paths[:10]],
        limitations=["Filename-based inventory only; absence of a match does not prove the material is unavailable."],
        metadata={"inventory": inventory, "file_count": len(files)},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit manuscript-package completeness.")
    parser.add_argument("root", help="Manuscript package directory")
    add_common_args(parser)
    args = parser.parse_args()
    emit_result(run(args.root), args.format, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
