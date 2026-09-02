#!/usr/bin/env python3
"""Offline citation-integrity screen for DOI and retraction-risk markers."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List

from integrity_common import add_common_args, emit_result, make_finding, make_result


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
RISK_TERMS = ["retracted", "retraction", "withdrawn", "expression of concern", "corrigendum", "erratum"]


def split_references(text: str) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    refs = []
    buffer: List[str] = []
    for line in lines:
        starts_new = bool(re.match(r"^(\[\d+\]|\d+\.|\d+\)|[A-Z][A-Za-z-]+,\s)", line))
        if starts_new and buffer:
            refs.append(" ".join(buffer))
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        refs.append(" ".join(buffer))
    return refs if refs else lines


def run(paths: List[str]) -> Dict[str, object]:
    findings = []
    all_refs: List[str] = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        all_refs.extend(split_references(text))
    seen: Dict[str, int] = {}
    doi_count = 0
    for idx, ref in enumerate(all_refs, 1):
        dois = DOI_RE.findall(ref)
        doi_count += len(dois)
        if not dois:
            findings.append(
                make_finding(
                    method="citation_integrity",
                    severity="LOW",
                    location=f"reference {idx}",
                    description="No DOI detected in reference entry.",
                    statistics={"reference_excerpt": ref[:220]},
                    recommendation="Verify the citation manually if it supports a key claim.",
                )
            )
        for doi in dois:
            key = doi.lower().rstrip(".")
            if key in seen:
                findings.append(
                    make_finding(
                        method="citation_integrity",
                        severity="LOW",
                        location=f"reference {idx}",
                        description="Duplicate DOI detected in reference list.",
                        statistics={"doi": key, "first_seen_reference": seen[key], "duplicate_reference": idx},
                    )
                )
            else:
                seen[key] = idx
        lowered = ref.lower()
        for term in RISK_TERMS:
            if term in lowered:
                findings.append(
                    make_finding(
                        method="citation_integrity",
                        severity="MEDIUM" if term in {"corrigendum", "erratum"} else "HIGH",
                        location=f"reference {idx}",
                        description=f"Reference contains integrity-related marker: {term}.",
                        statistics={"reference_excerpt": ref[:260]},
                        recommendation="Confirm whether the manuscript treats this citation appropriately.",
                    )
                )
    return make_result(
        tool="citation_integrity_check",
        input_value=paths,
        findings=findings,
        evidence_files=paths,
        limitations=["Offline text screen only; it does not query Crossref, PubMed, PubPeer, or Retraction Watch."],
        metadata={"reference_count": len(all_refs), "doi_count": doi_count},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline citation-integrity screen.")
    parser.add_argument("paths", nargs="+", help="Reference text/markdown/bib/ris files")
    add_common_args(parser)
    args = parser.parse_args()
    emit_result(run(args.paths), args.format, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
