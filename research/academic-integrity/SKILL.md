---
name: geng-academic-integrity-audit
description: Academic-integrity self-audit skill inspired by Geng Tongxue for manuscripts, revisions, post-publication concerns, and internal lab review, including Nature/Nature Portfolio submissions. Use when the user asks for 耿同学 skill, 学术诚信自查, 自查自纠, 学术造假/数据造假/图片造假/统计异常/论文打假筛查, PubPeer/retraction concern triage, manuscript correction planning, or whether a manuscript may contain fabrication, falsification, image manipulation, duplicate publication, reporting gaps, or other research-integrity risks.
---

# Geng Academic Integrity Audit

Use this skill to help authors, editors, reviewers, or research groups perform academic-integrity self-audits for manuscripts, revisions, post-publication concerns, and internal lab review, including Nature/Nature Portfolio submissions. The goal is corrective self-checking, not public accusation. Report evidence precisely, separate confirmed facts from suspicion, and distinguish honest error, inadequate reporting, questionable research practice, and possible fabrication or falsification.

## Core Stance

- Be rigorous before being sharp: every concern needs a location, observation, rule, severity, and benign alternative explanation.
- Do not call people fraudsters. Say "this evidence pattern is consistent with...", "requires author explanation", or "meets the threshold for formal investigation".
- Use the "Geng Tongxue" voice only as a short optional closing comment. Keep it evidence-led and avoid personal insults.
- If only text is available, state that image integrity and raw-data consistency cannot be fully verified.
- If public web access is available and the manuscript is published, check the DOI/title against official journal pages, PubPeer, Retraction Watch, corrections, expressions of concern, and data/code repositories. Prefer primary or official sources.

## Intake

Ask for or infer the audit package:

- Manuscript/PDF, supplementary information, figure legends, methods, reporting summary, and data/code availability statement.
- Final figures plus uncropped source images for gels/blots/microscopy/flow cytometry.
- Numeric values extracted from graphs/tables as CSV/XLSX where possible.
- Ethics approvals, trial registration, sample-size/power rationale, randomization/blinding records, reagent identifiers, and author contribution/competing-interest statements.
- Any concern letter, reviewer note, PubPeer thread, correction draft, or journal query.

When the user provides a numeric CSV/XLSX, run the bundled screen:

```bash
python3 scripts/geng_numeric_screen.py path/to/data.csv --format markdown --output geng-numeric-screen.md
```

Use the script output as screening evidence only; interpret it in the scientific context.

If the user provides a full manuscript package directory, first inventory what is available: manuscript, supplementary information, source data, final figures, source images, ethics/approval files, trial registrations, code, protocols, and correspondence. Missing materials must appear in the final report.

## Combined Audit Framework

Run the audit across these integrated rule families:

- Geng-style six moves: image reuse, fabricated-looking numeric data, image splicing, statistical anomaly, publication-output anomaly, and citation/method anomaly.
- Five-domain review: data/results, images/figures, methods rigor, structure/citations, authors/journal.
- Three numeric screens: terminal-digit distribution, decimal-pattern consistency, and exact/near data duplication.

Always complete all domains. If evidence is unavailable, mark the domain "not assessable" and specify what files would be needed.

## Journal and Nature Policy Gates

Use these as a submission-readiness and correction-readiness checklist:

1. Image integrity: figures minimally processed; no undisclosed cloning/healing/touch-up; global adjustments only; no hidden lane splicing; gel/blot source images retained and matched to final panels; legends disclose cropping, lane rearrangement, pseudo-colour, gamma/thresholding, deconvolution, and non-adjacent juxtaposition.
2. Data, code, materials, and protocols: a data availability statement exists; minimum data needed to verify and extend the claims is accessible or restrictions are justified; accession IDs/repository links work; code and protocols are available when needed for replication.
3. Reporting standards: randomization, blinding, exclusions, sample-size determination, replication, statistical tests, software versions, and key reagent/material identifiers are reported.
4. Ethics and registration: human/animal/clinical/biosafety approvals are present and consistent with the work; clinical trials are prospectively registered where required; consent and privacy limits are explained.
5. Authorship and accountability: all authors approved the manuscript, author contributions are specific, corresponding author responsibilities are clear, and all authors can help resolve integrity questions.
6. Competing interests and funding: financial and non-financial interests are declared; funder role is stated; undisclosed industry, patent, consultancy, or editorial-board conflicts are flagged.
7. Plagiarism, overlap, and duplicate publication: overlap with in-review, in-press, preprint, conference, or prior group papers is disclosed; reused text/data/figures have permission and citation.
8. Corrections and retractions: if a material error is found, classify whether it needs author correction, editor notification, expression-of-concern discussion, or retraction/institutional investigation.

## Detailed Checks

### 1. Data and Results

Check:

- Mean/SD/SEM/n consistency; p-values compatible with reported tests and sample sizes.
- Too-perfect dose-response curves, implausibly small variance, identical SDs, constant differences between columns, impossible confidence intervals, and rounded p-values at suspicious thresholds.
- P-hacking patterns: many p-values just below 0.05, no null results, selective subgroup reporting, multiple tests without correction.
- Baseline tables that are impossibly balanced or all non-significant when balance should vary.
- Biological or physical plausibility: effect size vs known assay noise, instrument limits, detection limits, and timing.
- Raw-data availability and whether source data reproduce plotted values.

Numeric screen thresholds:

- Terminal digit chi-square above the 0.05 critical value for 9 df is suspicious; for columns with at least 20 values, also flag Cramer's V greater than 0.3 or a terminal digit frequency more than 2x expected.
- Decimal-prefix duplication: more than 5 repeated groups, maximum repeat count at least 3, or repeat rate above 15% is suspicious.
- Exact duplicate values: more than 5 duplicated values or any value repeated at least 3 times in independent continuous measurements is suspicious.
- Escalate when multiple independent screens point to the same figure/table or a core conclusion.

### Script-backed Checks

Use deterministic scripts when their inputs are available. Scripts produce screening evidence, not misconduct findings. Preserve command, input path, output path, and interpretation limits in the report.

Available script suite:

| Script | Use when | Output |
| --- | --- | --- |
| `scripts/geng_numeric_screen.py` | Numeric values from figures/tables are available as CSV/TSV/XLSX/stdin. | Markdown/JSON screen for terminal digits, decimal-prefix repetition, and exact duplicate values. |
| `scripts/package_audit.py` | A manuscript package directory is available. | Missing-materials checklist for manuscript, SI, source data, source images, ethics files, code, and availability statements. |
| `scripts/figure_manifest_builder.py` | Final figures, supplementary figures, or source images are available. | Figure/source-image manifest with filenames, dimensions, hashes, categories, and optional CSV export. |
| `scripts/image_similarity_screen.py` | Multiple scientific images need duplicate/reuse screening. | Candidate repeated images, transformed reuse pairs, similarity scores, and evidence files. |
| `scripts/blot_gel_lane_audit.py` | Western blot or gel images are available. | Lane-boundary and repeated-lane screening report. |
| `scripts/graph_source_consistency.py` | Source data and reported summary graph data are available. | Mean/SD/SEM/n mismatches between source and reported values. |
| `scripts/stats_consistency_check.py` | Raw numeric data are available. | Recomputed descriptive statistics and zero-variance flags. |
| `scripts/microscopy_reuse_screen.py` | Microscopy images are available. | Tile-level reuse/local-cloning candidate report. |
| `scripts/flow_plot_duplicate_screen.py` | Flow-cytometry plot images are available. | Duplicated dot-cloud/gate-image candidate report. |
| `scripts/citation_integrity_check.py` | Reference text, BibTeX, RIS, or DOI lists are available. | Offline DOI, duplicate-reference, and retraction-marker screen. |
| `scripts/report_assembler.py` | Multiple script JSON outputs are available. | Unified Markdown evidence ledger and script-level audit report. |

Shared contract for all scripts:

- Prefer `--format markdown|json` and `--output`.
- JSON outputs should include `tool`, `input`, `findings`, `risk_level`, `evidence_files`, and `limitations` when the script supports them.
- If a required input is unavailable, do the equivalent check manually where possible and mark it as "manual/not script-backed".

### 2. Images and Figures

Check:

- Cross-panel reuse: the same or near-same image represents different samples, groups, time points, treatments, magnifications, stains, channels, replicates, or papers.
- Transform-disguised reuse: duplicated panels after rotation, flipping, resizing, stretching, contrast changes, cropping, local masking, pseudo-colour conversion, or partial overlap.
- Background fingerprints: identical dust, scratches, camera noise, gel speckles, blot background texture, microscope field defects, bubbles, debris, or cell clusters in supposedly independent images.
- Western blots/gels: reused loading controls, repeated bands, cloned lanes, non-adjacent lane splicing, vertical boundary lines, inconsistent background, abrupt exposure changes, missing molecular-weight markers, cropped source scans that omit relevant bands, and final panels that cannot be traced to uncropped originals.
- Blot lane integrity: bands should align with the correct sample order, source membranes, exposure, normalization, and quantification. Flag duplicated beta-actin/GAPDH/tubulin controls across unrelated experiments unless reuse is explicitly valid and disclosed.
- Microscopy: same cells/background reused across conditions; rotated/flipped fields; cloned cells or tissue regions; inconsistent channel merge; undisclosed thresholding, denoising, deconvolution, gamma changes, pseudo-colour, or selective field choice.
- Flow cytometry: duplicated dot clouds, copied quadrants/gates, too-regular distributions, inconsistent compensation, missing gating hierarchy, reused isotype/FMO controls, and population percentages inconsistent with displayed plots.
- Colony, wound-healing, migration, invasion, animal, histology, and microscopy panels: repeated colonies, repeated wound edges, repeated tissue architecture, duplicated animal images, inconsistent scale bars, and field-of-view mismatch.
- Charts and statistical figures: graph values inconsistent with source tables, misleading axes, missing units, non-zero baselines used to exaggerate effects, unequal tick spacing, absent error-bar definitions, asymmetric or implausibly tiny error bars, and duplicated plotted points across panels.
- Composite figure disclosure: every crop, lane removal, non-adjacent juxtaposition, magnification change, and representative-image selection should be disclosed in the legend or methods.
- Cross-paper/preprint reuse: compare figures against supplements, previous versions, preprints, thesis chapters, conference abstracts, and prior group publications when the user provides them or asks for public checks.

Verification procedure:

1. Build a figure map: list every figure/subfigure, sample identity, condition, magnification, channel, source-file name, and legend claim.
2. Compare within each figure, across all figures, and across supplementary items for repeated shapes, backgrounds, controls, and plotted values.
3. Ask for source images when duplication, splicing, or editing cannot be resolved from the PDF. Preserve filenames and metadata when provided.
4. Treat a single ambiguous similarity as a flag requiring source-data verification; escalate only when the reuse is material, undisclosed, and inconsistent with the claimed experiment.

Severity guidance:

- Minor: incomplete legend disclosure, missing source-image label, ambiguous crop.
- Major: undisclosed splicing, repeated loading controls across distinct experiments, final figure not traceable to raw image.
- Critical: same image or data panel represents different experimental conditions without disclosure, local cloning/touch-up hides or creates signal.

### 3. Methods Rigor

Check:

- Experimental controls, randomization, blinding, exclusion criteria, biological vs technical replicates, and independent replication.
- Sample-size/power justification and whether n changes across outcomes without explanation.
- Statistical model assumptions, multiple-comparison correction, paired/unpaired logic, covariate handling, missing-data handling, and pre-specified analyses.
- Reagents/antibodies/cell lines: catalog numbers, RRIDs, lots, validation, STR profiling, mycoplasma testing, species/strain/sex/age.
- Code/software versions, parameters, seeds, preprocessing, normalization, outlier rules, and pipeline provenance.
- Internal consistency: methods match results, figures, supplements, dates, ethics approvals, and available materials.

### 4. Structure, Citations, and Claims

Check:

- Every major claim maps to a result and every result maps to data.
- Citations support the claim stated, not merely the topic.
- Retracted or expression-of-concern papers are identified and treated appropriately.
- Over-citation, irrelevant citation padding, excessive self-citation, or citation cartel patterns.
- Language overreach: "first", "definitive", "paradigm-changing", or clinical claims without adequate evidence.
- Prior/preprint/conference overlap and whether novelty is overstated.

### 5. Authors, Journal, and Timeline

Check:

- Author count and expertise match the work; contribution statements are concrete.
- Corresponding author email and affiliations are plausible, but treat non-institutional email as a weak signal only.
- Received/accepted timeline is plausible for the study and journal; very short review can be a flag, not proof.
- Same group produced many similar high-impact papers in a short time with repeated methods/figures/data.
- Editorial-board, guest-editor, reviewer, funder, industry, patent, or collaboration conflicts are disclosed.

## Risk Rating

Use the highest justified level after considering evidence volume, independence, centrality to claims, and alternative explanations.

| Level | Meaning | Typical Action |
| --- | --- | --- |
| Green: low | No material integrity signal; only routine reporting improvements. | Proceed; fix minor reporting gaps. |
| Yellow: moderate | Isolated or ambiguous concerns that may be honest error or weak reporting. | Request source data/images; revise legends/methods; document explanations. |
| Orange: high | Multiple concerns or a material issue affecting a main figure/result. | Freeze submission; run internal review; contact co-authors; prepare correction if published. |
| Red: severe | Independent evidence suggests image/data manipulation or unreliable core conclusions. | Notify institution/research-integrity officer and journal as appropriate; preserve all records. |
| Black: formal-investigation threshold | Corroborated systematic issues, impossible data, or undisclosed reuse central to the paper. | Formal investigation; consider retraction/correction path; avoid public overclaiming before process. |

## Output Report

Use this structure for every audit:

```markdown
# Geng Academic-Integrity Self-Audit Report

## Object
- Manuscript/paper:
- DOI or identifier:
- Version/date:
- Materials reviewed:
- Materials missing:

## Executive Rating
- Overall risk:
- Core conclusion reliability:
- Immediate recommendation:

## Evidence Ledger
| ID | Domain | Location | Observation | Rule/standard | Severity | Alternative explanation | Required verification |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Domain Review
### 1. Data and Results
### 2. Images and Figures
### 3. Methods Rigor
### 4. Structure, Citations, and Claims
### 5. Authors, Journal, and Timeline
### 6. Journal and Nature Policy Gates

## Script-backed Screen Summary
- Scripts available:
- Scripts run:
- Input table(s), image folders, or package directories:
- Findings:
- Evidence files:
- Interpretation limits:

## Cross-Evidence Assessment
- Are findings independent?
- Do they affect core claims?
- Could benign explanations plausibly resolve them?
- What raw materials are needed?

## Self-Correction Plan
| Action | Owner | Deadline | Evidence to collect | Journal/institution contact needed? |
| --- | --- | --- | --- | --- |

## Suggested Wording
- Author query:
- Journal concern/correction note:
- Internal record-preservation note:

## Geng-Style Closing Comment
One evidence-led sentence, optional.

## Disclaimer
This is an AI-assisted screening report for research-integrity self-checking. It is not a formal misconduct finding. Final determinations require review by the journal, institution, or other competent body.
```

## Self-Correction Decision Rules

- If the issue is a typo, mislabeled axis, incomplete legend, or missing disclosure that does not affect interpretation: prepare a correction and update source documentation.
- If a figure panel, source image, or numeric value is wrong but the original data support the conclusion: replace the panel/value, disclose the error, and preserve the audit trail.
- If the original data are missing, not traceable, or inconsistent with published results: escalate internally before external statements; do not submit or resubmit until resolved.
- If multiple independent core findings fail verification: recommend institutional research-integrity consultation and journal notification.
- If co-authors disagree, preserve records and separate factual evidence from interpretation.

## Evidence Language

Prefer:

- "The same background pattern appears in Fig. 2A and Fig. 4C after rotation; source images are needed."
- "The reported p-value is incompatible with the stated n and test under standard assumptions."
- "This pattern is a red flag for possible undisclosed image reuse, not by itself a misconduct finding."

Avoid:

- "The author is a fraud."
- "This is definitely fake" unless an official investigation has already made that finding.
- Public shaming, speculation about motives, or conclusions unsupported by the audit record.
