# Version Tracker — Template and Conventions

This is the template for the working document that holds every version of the manuscript across the seven-step loop, plus the annotations that accompany them.

The design principle is **newest on top, older stacked below**. A reader opening the document sees V4 first, then V3, then V2, then V1, then Step 0 diagnostics.

---

## Template Structure

Copy this as the starting state of your tracker document. Fill in the brackets, add sections as you produce each version, and keep the reverse-chronological order.

```
# [Manuscript title or working identifier] — Iteration Tracker

Target venue: [e.g., Nature, NIH R01, HBR]
Quantifiable anchor: [e.g., "Nature desk-review-to-peer-review probability"]
Current status: [e.g., "V3 locked, about to start Step 6"]
Best model (current): [e.g., "Claude 4.7"]
Iteration started: [YYYY-MM-DD]

================================================================
V4 — FINAL (lock date: YYYY-MM-DD)
================================================================

[Paste V4 content here — the final manuscript]

---- Step 6 diff from V3 (length + format) ----

Proposal 1: [Name] — ACCEPTED | REJECTED | MODIFIED
  Current: [quote]
  Proposed: [quote]
  Reason: [why]
  Estimated impact: [e.g., +0.5 pp]

Proposal 2: ...
Proposal 3: ...

Total estimated impact applied: [e.g., +1.2 pp]
Anchor estimate after V4: [e.g., "38–47% Nature desk-review probability"]


================================================================
V3 — WORDING LOCKED (lock date: YYYY-MM-DD)
================================================================

[Paste V3 content here]

---- Step 5 diff from V2 (wording refinement) ----

Proposal 1: [Name] — ACCEPTED | REJECTED | MODIFIED
  Current: [quote]
  Proposed: [quote]
  Reason: [why]
  Estimated impact: [e.g., +1.5 pp]

... (5 proposals typical) ...

Total estimated impact applied: [e.g., +4 pp]
Anchor estimate after V3: [e.g., "34–44%"]


================================================================
V2 — SENTENCE STRUCTURE LOCKED (lock date: YYYY-MM-DD)
================================================================

[Paste V2 content here]

---- Step 4 assembly log ----

For each slot, record which draft's sentence was chosen, or note a rewrite.

Title: [Chosen from Draft X / Rewrite]
  Reason: [brief]

Abstract-1: [Chosen from Draft X / Rewrite]
  Reason: [brief]

... (one line per slot) ...

Sentences rewritten at Step 4:
- [slot]: original was [quote]; user rewrite is [quote]; reason: [...]


================================================================
V1 → V2 TRANSITION: Rubric Matrix and Drafts
================================================================

---- Step 3 rubric matrix ----

[Paste the fused rubric matrix here. Rows = slots. Columns = Draft A (Model-1) / Draft B (Model-2) / Draft C (Model-3), scores from each grader.]

Summary:
- Overall ranking: [e.g., "Draft A > Draft C > Draft B" by median grader estimate]
- Best model identified: [e.g., "Claude, by a margin of +3 pp on Nature anchor"]
- Notable disagreements: [list]

---- Step 2 parallel drafts ----

=== Draft A: [Model name], generated YYYY-MM-DD HH:MM ===
[Paste full draft A]

=== Draft B: [Model name], generated YYYY-MM-DD HH:MM ===
[Paste full draft B]

=== Draft C: [Model name], generated YYYY-MM-DD HH:MM ===
[Paste full draft C]


================================================================
V1 — LOGIC CHAIN (lock date: YYYY-MM-DD)
================================================================

[Paste V1 here — the mixed-language, logic-forward draft]


================================================================
STEP 0 — STRATEGY CONSULTATION (date: YYYY-MM-DD)
================================================================

---- User's initial framing ----

Target venue: [...]
Stated concerns: [...]
Initial draft attached: [path or summary]

---- Responses from each model ----

=== [Model 1] strategic diagnosis, YYYY-MM-DD HH:MM ===
[Paste full response]

=== [Model 2] strategic diagnosis, YYYY-MM-DD HH:MM ===
[Paste full response]

=== [Model 3] strategic diagnosis, YYYY-MM-DD HH:MM ===
[Paste full response]

---- Consolidated angle chosen ----

Angle: [1–2 sentence description]
Reason for choice: [why this angle won]
Models that agreed: [list]
Models that disagreed and their alternative: [list]

================================================================
END OF TRACKER
================================================================
```

---

## Annotation Conventions

### Timestamps

Use a compact `YYYYMMDDHHMM` format for inline timestamps, and ISO `YYYY-MM-DD HH:MM` for section headers.

### User Questions vs. Model Responses

When the user asks a question of a model, prefix the line with the compact timestamp and the model name being addressed. When the model replies, prefix with `→` and the model name.

Example:
```
202604180900  only-claude47  请对三个模型的标题逐句打分，并说明理由。

→ Claude: 好的。从Nature编辑视角逐句评分如下。Title Gemini版:...
```

### Labeling Outputs

Every block of pasted model output gets a header like:
```
=== GPT output, 2026-04-18 09:40 ===
```

### Mark Rejected Proposals Explicitly

When the user rejects a proposal at Step 5 or Step 6, **keep the rejected proposal** in the tracker with `REJECTED` and a one-line reason. Don't delete. The rejected proposals are part of the reasoning record.

### Keep the Top Section's Status Line Current

The four lines at the very top (target venue / quantifiable anchor / current status / best model) should be updated whenever they change. A user returning after a week needs those four lines to reconstruct state in 30 seconds.

### File Format

Markdown (`.md`) or Word document (`.docx`) both work. If using Markdown, version-control with git for a second audit layer. If using Word, enable "Track Changes."

---

## Where the Tracker Lives

The tracker is the single source of truth for the iteration:

- **Accessible to everyone involved** (user, co-authors, future-Claude in a new conversation)
- **Not edited casually.** Each edit traceable to a step.
- **Copied into new Claude conversations when context resets.**

---

## Minimal Variant

If the full template feels heavy for a smaller manuscript (e.g., a cover letter), this minimal variant is acceptable:

```
# [Title] — Iteration Tracker

Target: [venue/anchor]
Status: [current version]

=== V3 (date) ===
[content]

=== V2 (date) ===
[content]

=== V1 (date) ===
[content]
```

Even this minimal variant keeps reverse-chronological order and date stamps. Don't go below this level.

---

*Last updated: 2026-04-18*
