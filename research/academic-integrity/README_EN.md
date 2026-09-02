# Geng Classmate Academic-Integrity Self-Audit Skill

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![README](https://img.shields.io/badge/README-ZH%20%7C%20EN-orange)](README.md)

This skill supports academic manuscript submissions, revisions, post-publication concern triage, and internal lab audits, including Nature/Nature Portfolio submissions. It is an executable workflow for detecting possible data fabrication, image manipulation, statistical anomalies, method gaps, citation problems, authorship issues, and correction needs.

The skill is for evidence-based self-audit and self-correction. It does not replace a journal, institution, ethics board, or formal misconduct investigation.

## Files

```text
.
├── SKILL.md
├── README.md
├── README_EN.md
└── scripts/
    ├── blot_gel_lane_audit.py
    ├── citation_integrity_check.py
    ├── figure_manifest_builder.py
    ├── flow_plot_duplicate_screen.py
    ├── geng_numeric_screen.py
    ├── graph_source_consistency.py
    ├── image_similarity_screen.py
    ├── integrity_common.py
    ├── microscopy_reuse_screen.py
    ├── package_audit.py
    ├── report_assembler.py
    └── stats_consistency_check.py
```

## When To Use

- Before submitting to any academic journal, including Nature or another Nature Portfolio journal.
- After receiving concerns from editors, reviewers, PubPeer, readers, or co-authors.
- When checking possible data fabrication, image reuse, Western blot splicing, statistical irregularities, p-hacking, duplicate publication, or citation problems.
- When a PI, corresponding author, or co-author needs a factual self-correction plan.
- When extracted figure/table values are available as CSV/XLSX for numeric screening.

## Full Audit Workflow

### 1. Scientific Images and Figure Integrity

This skill is not limited to numeric checks. Figure review is a core workflow:

- **Image reuse**: check whether the same image or region is used for different samples, treatment groups, time points, magnifications, stains/channels, papers, or supplementary figures.
- **Transformed reuse**: detect reuse hidden by rotation, flipping, resizing, stretching, cropping, contrast adjustment, pseudo-colour conversion, local masking, or partial overlap.
- **Background fingerprints**: compare identical cells, tissue architecture, dust, scratches, camera noise, gel speckles, blot texture, bubbles, debris, and field defects in supposedly independent images.
- **Western blot / gel issues**: repeated loading controls; shared beta-actin/GAPDH/tubulin across unrelated experiments; duplicated bands or lanes; undisclosed non-adjacent lane splicing; vertical boundary lines; abrupt background changes; inconsistent exposure; missing molecular-weight markers; cropped panels that cannot be traced to uncropped source images.
- **Microscopy issues**: reused fields across groups; rotated or flipped fields; cloned cells or tissue regions; inconsistent channel merge; undisclosed thresholding, denoising, gamma adjustment, deconvolution, pseudo-colour, or selective representative-field choice.
- **Flow-cytometry issues**: duplicated dot clouds, copied gates/quadrants, percentages inconsistent with point clouds, missing compensation/gating hierarchy, and reused isotype/FMO/control plots for unrelated experiments.
- **Migration, invasion, wound-healing, colony-formation, animal, and histology panels**: repeated colonies, repeated wound edges, repeated tissue architecture, repeated animal images, inconsistent scale bars, and field-of-view mismatch.
- **Graph manipulation**: plotted values inconsistent with source data; non-zero baselines exaggerating effects; unequal tick spacing; missing units; undefined error bars; error bars too small for the assay noise; repeated data points or error-bar shapes across panels.
- **Composite figure disclosure**: every crop, splice, non-adjacent lane juxtaposition, global brightness/contrast adjustment, representative-image choice, pseudo-colour conversion, and thresholding step should be disclosed in the legend or methods.

The audit first builds a figure map: panel ID, sample, condition, time point, channel, magnification, legend claim, and source filename. It then compares within figures, across figures, supplements, and prior versions. PDF review is only a screen; source images and raw data are required to resolve serious flags.

### 2. Data and Statistical Anomalies

- Check mathematical consistency among mean, SD/SEM, n, confidence intervals, p-values, and statistical tests.
- Flag too-perfect dose-response or time trends, constant between-group differences, identical or implausibly small SDs, and comparisons that are all just significant.
- Look for p-values clustered between 0.01 and 0.05, missing negative results, or multiple comparisons without correction.
- Review baseline tables that are unusually balanced or randomization outcomes that look too perfect.
- Verify whether source data, supplementary tables, or raw records reproduce the plotted values.

### 3. Methods and Reproducibility

- Check randomization, blinding, inclusion/exclusion criteria, sample-size/power analysis, biological replicates, and technical replicates.
- Verify that statistical methods match the data type and handle multiple comparisons, missing values, outliers, and model assumptions.
- Confirm traceability of antibodies, reagents, cell lines, animal strains, software, code, parameters, and versions.
- For human, animal, clinical-trial, or biosafety research, check ethics approval, registration, consent, and privacy statements.

### 4. Citations, Structure, and Author Declarations

- Map every core claim to supporting data and confirm that cited papers support the specific claim.
- Identify retracted papers, expressions of concern, irrelevant citation padding, excessive self-citation, and citation-cartel patterns.
- Check duplicate publication, salami slicing, and undisclosed overlap with preprints, conference papers, theses, or prior group papers.
- Review author contributions, competing interests, funder roles, data availability, code availability, and materials availability.

## Usage

### Get The Repository

```bash
git clone https://github.com/1anj/academic-integrity-skill.git
cd academic-integrity-skill
```

### Codex

Load this directory as a Codex skill, or open the repository as a Codex workspace, then ask:

```text
Use the Geng Tongxue academic-integrity self-audit skill to review this manuscript, assess possible fraud risk, and produce a self-correction plan.
```

### Claude Code

Open this repository in Claude Code, or place this repository and the manuscript materials in the same workspace:

```bash
cd academic-integrity-skill
claude
```

Suggested prompt:

```text
First read SKILL.md, then follow the Geng Tongxue academic-integrity self-audit workflow for the manuscript materials I provide.
Focus on image reuse, Western blot/gel splicing, microscopy reuse, flow-cytometry duplication, numeric/statistical anomalies, method gaps, citations, and author declarations.
Return an evidence ledger, risk rating, and self-correction plan.
```

### Antigravity

Open `academic-integrity-skill` as the project folder in Antigravity. Add `SKILL.md`, `README_EN.md`, `scripts/`, and the manuscript materials to the agent context, then use:

```text
Follow SKILL.md. Run the Geng Tongxue academic-integrity self-audit on the attached manuscript and source materials. Include figure-integrity checks, numeric/statistical screening, method/citation review, risk rating, and a self-correction plan.
```

### Cursor / Windsurf / Continue / VS Code AI

Open this repository as the workspace, pin or reference `SKILL.md`, and place the manuscript PDF, supplements, source images, and numeric tables in the same project folder. Use:

```text
Use SKILL.md to perform the Geng Tongxue academic-integrity self-audit. Do not summarize only; inspect scientific figures, numeric/statistical consistency, methods, citations, author declarations, and journal-policy risks, then produce an actionable correction checklist.
```

### ChatGPT / Claude / Gemini Web Apps

Upload `SKILL.md`, the manuscript PDF, supplementary files, source images or source data, and ask the model to follow `SKILL.md`. If you have CSV/XLSX numeric tables, run the local numeric screening script first and upload its output with the manuscript package.

Recommended inputs:

- Manuscript PDF or draft.
- Supplementary information, figure legends, Methods, and reporting summary.
- Source images, uncropped Western blot/gel/microscopy/flow-cytometry files.
- Extracted numeric values from figures/tables as CSV/XLSX.
- Data/code repository links, ethics approvals, trial registrations, author contributions, and competing-interest statements.
- The exact journal/editor/reviewer/PubPeer concern text, if any.

## Feature Overview

The `scripts/` directory now provides a low-dependency, reproducible, report-friendly screening suite. Except for the shared helper module `integrity_common.py`, each functional script supports `--format markdown|json` and `--output`; JSON outputs use a shared contract with `tool`, `input`, `findings`, `risk_level`, `evidence_files`, and `limitations`. Scripts report screening signals only, not formal misconduct determinations.

### Implemented Modules

| Script | Function | Main Input | Main Output |
| --- | --- | --- | --- |
| `package_audit.py` | Checks package completeness for manuscript, SI, source data, source images, ethics files, code, and availability statements. | Project directory | Missing-materials checklist |
| `figure_manifest_builder.py` | Builds a manifest for final figures, supplementary figures, and source images with filenames, dimensions, hashes, and categories. | Figure/source-image directories | `figure_manifest.csv/json` |
| `image_similarity_screen.py` | Screens image reuse, rotation/flip/crop reuse, and cross-figure duplication candidates. | Image directories | Candidate duplicate pairs and similarity scores |
| `blot_gel_lane_audit.py` | Screens Western blot/gel lane splicing, background discontinuities, repeated bands, and repeated loading controls. | Blot/gel images | Suspicious lanes, boundaries, repeated-band candidates |
| `microscopy_reuse_screen.py` | Uses tile matching to screen reused fields, local cloning, rotated/flipped microscopy reuse. | Microscopy image directory | Suspicious-region coordinates and similarity scores |
| `flow_plot_duplicate_screen.py` | Screens duplicated flow-cytometry dot plots, copied gates, and displayed plot inconsistency candidates. | Flow plot images | Suspicious plot pairs and gating issues |
| `geng_numeric_screen.py` | Screens terminal digits, decimal repeats, and exact duplicate values. | CSV/TSV/XLSX/stdin | Markdown/JSON risk report |
| `stats_consistency_check.py` | Recalculates means, SD/SEM, ranges, and zero-variance flags from raw data. | Raw data | Statistical-consistency report |
| `graph_source_consistency.py` | Compares source data against reported means, SD/SEM, and n values. | Source data and reported summary | Inconsistency table |
| `citation_integrity_check.py` | Offline screen for DOI issues, duplicate references, and retraction/expression-of-concern markers. | Reference list/DOI text | Citation-risk table |
| `report_assembler.py` | Merges script JSON outputs into a unified self-audit report and evidence ledger. | Multiple `*-screen.json` files | `geng-integrity-report.md` |

### Workflow

```bash
python3 scripts/package_audit.py manuscript_package --format json --output package_audit.json
python3 scripts/figure_manifest_builder.py manuscript_package/figures manuscript_package/source_images --csv-output figure_manifest.csv --format json --output figure_manifest.json
python3 scripts/image_similarity_screen.py manuscript_package/figures manuscript_package/source_images --format json --output image_similarity.json
python3 scripts/geng_numeric_screen.py manuscript_package/source_data.csv --format json --output numeric_screen.json
python3 scripts/report_assembler.py package_audit.json figure_manifest.json image_similarity.json numeric_screen.json --output geng-integrity-report.md
```

### Dependency Guidance

- Prefer the Python standard library for core scripts so the audit can run offline.
- Use optional `pandas`, `openpyxl`, and `scipy` for table/statistical enhancement.
- Use optional `Pillow`, `imagehash`, `opencv-python`, `scikit-image`, and `matplotlib` for image screening.
- Use optional `pymupdf` or `pdfplumber` for PDF/figure extraction.
- Citation checks that need network access should provide an `--offline` mode so core auditing is not blocked.

### Review Conclusion

The implemented script suite covers package inventory, figure manifests, image-reuse candidates, blot/gel checks, microscopy checks, flow plot checks, numeric/statistical screening, source-data comparison, offline citation screening, and report assembly. Script outputs remain screening evidence; final interpretation must use source images, raw data, lab records, and author explanations.

## Risk Levels

| Level | Meaning | Suggested action |
| --- | --- | --- |
| Green low | No material integrity signal. | Proceed and fix routine reporting gaps. |
| Yellow moderate | Isolated or ambiguous issues, possibly labeling or reporting problems. | Request source data/images; revise legends, methods, and declarations. |
| Orange high | Multiple concerns or a material issue affecting a main result. | Pause submission/revision and run internal review. |
| Red severe | Independent evidence suggests manipulation or unreliable core conclusions. | Preserve records; consult the institutional research-integrity office and consider journal notification. |
| Black investigation threshold | Systematic issues, impossible data, or distorted core evidence. | Move to formal investigation and correction/retraction assessment. |

## Output

The skill produces a structured Markdown report with:

- Object, version, reviewed materials, and missing materials.
- Overall risk rating and core-conclusion reliability.
- Evidence ledger: location, observation, applicable rule, severity, alternative explanation, and required verification.
- Five technical domains plus journal policy gates, including Nature requirements when relevant.
- Numeric screen summary and interpretation limits.
- Self-correction action register with owners, deadlines, evidence needs, and journal/institution contact decisions.
- Draft language for author queries, journal notices, and internal record-preservation notes.

## Evidence Rules

- A single similar image or isolated numeric anomaly usually means "requires explanation", not "fraud".
- Multiple independent evidence lines affecting the same core conclusion should increase the risk level.
- If source images, raw data, lab records, and study design explain the concern, handle it as correction and documentation.
- If raw data are missing, images are not traceable, core results cannot be reproduced, or author explanations conflict, pause submission/revision and escalate to internal research-integrity review.

## Journal and Nature Policy Anchors

Check the current Nature Portfolio policies before formal submission or response:

- [Nature Portfolio editorial policies](https://www.nature.com/nature-portfolio/editorial-policies)
- [Image integrity and standards](https://www.nature.com/nature-portfolio/editorial-policies/image-integrity)
- [Reporting standards and availability of data, materials, code and protocols](https://www.nature.com/nature-portfolio/editorial-policies/reporting-standards)
- [Authorship](https://www.nature.com/nature-portfolio/editorial-policies/authorship)

Policies can change; verify the target journal page before making a formal decision.

## Limits

- AI does not replace professional image forensics, raw-data audit, institutional investigation, or legal advice.
- PDF-level visual review cannot provide pixel-level ELA, metadata forensics, or exhaustive cross-paper image search.
- A single anomaly usually means "requires explanation", not "fraud".
- Severe conclusions should rely on source data, source images, lab records, code, and author explanations.

## Principle

Be sharp about evidence and careful about people. Audit records should be precise, restrained, and reproducible: evaluate evidence, not motives; describe risk, not gossip; provide a correction path, not unsupported accusations.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=1anj/academic-integrity-skill&type=Date)](https://www.star-history.com/#1anj/academic-integrity-skill&Date)
