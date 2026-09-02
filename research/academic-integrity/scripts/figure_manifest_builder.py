#!/usr/bin/env python3
"""Build a manifest for figure and source-image files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

from integrity_common import IMAGE_EXTS, add_common_args, emit_result, iter_files, make_result, sha256_file


def image_info(path: Path) -> Dict[str, object]:
    info: Dict[str, object] = {
        "path": str(path),
        "filename": path.name,
        "suffix": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    try:
        from PIL import Image

        with Image.open(path) as image:
            info.update({"width": image.width, "height": image.height, "mode": image.mode})
    except Exception as exc:
        info["image_read_warning"] = str(exc)
    return info


def classify(path: Path) -> str:
    text = " ".join(part.lower() for part in path.parts)
    if any(token in text for token in ["raw", "source", "uncropped", "original"]):
        return "source_image"
    if any(token in text for token in ["supp", "extended"]):
        return "supplementary_figure"
    return "final_or_unknown_figure"


def run(paths: List[str]) -> Dict[str, object]:
    files = iter_files(paths, IMAGE_EXTS)
    records = []
    for file_path in files:
        record = image_info(file_path)
        record["category"] = classify(file_path)
        records.append(record)
    return make_result(
        tool="figure_manifest_builder",
        input_value=paths,
        findings=[],
        evidence_files=[record["path"] for record in records],
        limitations=["Manifest records file-level metadata only; it does not prove panel provenance by itself."],
        metadata={"records": records, "image_count": len(records)},
    )


def write_csv(result: Dict[str, object], output: str) -> None:
    records = result["metadata"]["records"]
    fieldnames = sorted({key for record in records for key in record.keys()})
    with open(output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a figure/source-image manifest.")
    parser.add_argument("paths", nargs="+", help="Figure or source-image paths/directories")
    parser.add_argument("--csv-output", help="Optional CSV manifest path")
    add_common_args(parser)
    args = parser.parse_args()
    result = run(args.paths)
    if args.csv_output:
        write_csv(result, args.csv_output)
    emit_result(result, args.format, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
