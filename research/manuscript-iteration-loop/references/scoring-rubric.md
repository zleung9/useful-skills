# Scoring Rubric: Sentence-Level Matrix, Anchors, and Reading Disagreement

This file explains how to structure the Step 3 scoring output, how to calibrate the quantifiable anchor to the user's manuscript, and how to read across-grader disagreement productively.

---

## Part 1 — The Sentence-Level Rubric Matrix

### What the matrix looks like

The matrix has sentence slots as rows and grader × draft combinations as columns. Each cell holds a score and a short reason.

For a typical manuscript title + abstract + three-paragraph introduction, the slots are roughly:

| Slot | What it does |
|------|-------------|
| Title | Single-line claim-anchor |
| Abstract-1 | Opening (problem or heuristic being challenged) |
| Abstract-2 | Gap or unanswered question |
| Abstract-3 | "Here we..." — the work |
| Abstract-4 | Main finding / counterfactual |
| Abstract-5 | Mechanism / explanatory evidence |
| Abstract-6 | Closing significance |
| Intro-P1-S1 | Cross-scale opening |
| Intro-P1-S2 | Why this problem matters |
| Intro-P1-S3 | Current state of the field (with citations) |
| Intro-P1-S4 | The fundamental question (the punch line of P1) |
| Intro-P1-S5 | Ascent to the meta-frame |
| Intro-P2-S1 | Why this specific system is the test bed |
| Intro-P2-S2–3 | The prevailing heuristic |
| Intro-P2-S4–5 | Why the heuristic is limited + the pointed question |
| Intro-P3-S1 | "Here, using..." — method preview |
| Intro-P3-S2+ | The findings (First / Second / Third or integrated) |
| Intro-P3-end | The closing significance |

The actual slot count depends on the section and venue. The key: every sentence of every draft maps to exactly one slot.

### One fully-worked cell

A well-formed cell for slot "Abstract-4 (counterfactual)" from a Claude grader evaluating a GPT draft might read:

> **9/10** — Directly points at the counterfactual method ("synthesizing the formulation a CIP/AGG-maximizing optimizer would select"), uses the falsification verb which is the strongest available epistemic framing, and the em-dash aside keeps density high without sacrificing readability. Drops half a point because "markedly inferior" is slightly vaguer than a number would be.

Notice what makes this cell good:
- A numerical score.
- A specific quoted phrase or fragment being praised or criticized.
- An **explanation of the half-point deduction** — not just "near-perfect" but "why not perfect."
- An implicit comparison ("strongest available epistemic framing") that makes the score transferable across cells.

### How to fuse the three grader matrices

You will receive three scoring responses, one per grader. Don't just average — the reasoning is the signal. Instead:

1. For each slot, list the three graders' scores side by side (e.g., "9 / 8 / 9").
2. Note the mean and the spread (std dev or simple range).
3. For each slot, write a 1-sentence **consensus verdict** plus a 1-sentence **disagreement note** if the scores spread ≥2 points.
4. Pick the slot-winner draft using the rule: **highest mean wins unless one grader's reasoning reveals a deal-breaker the other two missed.** When that happens, the user (not Claude) makes the call.

### What the overall ranking looks like

After slot-level fusion, produce an overall ranking of the three drafts with each grader's top-level estimate (e.g., "Grader 1: Nature 32–42%; Grader 2: Nature 28–36%; Grader 3: Nature 25–33%"). The "best model" for Steps 5–6 is usually the draft whose **median grader-estimate is highest**.

---

## Part 2 — Calibrating the Quantifiable Anchor

The anchor is the single number every grader commits to and argues over. A poorly-chosen anchor collapses the loop.

### Properties of a good anchor

1. **Specific enough to reason about.** "Quality" is not an anchor. "Desk-review-to-peer-review probability at Nature" is.
2. **Something a senior person in the target audience could plausibly estimate** with reasoning.
3. **Expressed as a probability or a percentage.** Bounded scales are easier to calibrate across graders.
4. **Tied to a decision a real human makes.** (Sends-to-review / doesn't; funds / rejects; approves / returns)
5. **Appropriate to the *stage* of the artifact.** A desk-review anchor is right for a late-stage draft; it's wrong for an early-stage outline.

### Well-Calibrated Anchors by Manuscript Type

| Manuscript type | Good anchor | Example |
|---|---|---|
| Nature / Science / top-field journal paper | Desk-review-to-peer-review probability at venue X | 30–40% |
| Second-tier journal paper | Major-revision-or-accept probability at venue X | 40–55% |
| NIH R01 grant | Fundable-score probability (scoring ≤ payline) | 15–25% |
| NSF proposal | Recommended-for-funding probability | 10–20% |
| HBR / Wall Street Journal feature | Accepted-for-print probability | 8–15% |
| Board memo / CEO recommendation | Probability the board approves the recommendation | 40–70% |
| Legal brief | Probability the court rules in our favor | Varies |
| Cold outreach email | Reply-from-named-recipient probability | 5–25% |
| Grant rebuttal | Probability of overturning the prior decision | 15–35% |
| Philosophy / humanities essay | Acceptance probability at venue X | 10–30% |

### Anchors to Avoid

- **"Is this good?"** — too abstract; graders will each pick their own axis.
- **"How many stars out of five?"** — too coarse; collapses to 4★ for anything competent.
- **"Readability score"** — measures one axis only.
- **"Acceptance probability at Nature" (without "desk review")** — desk-review is the actual bottleneck; peer-review acceptance is dominated by reviewer lottery and is not meaningfully estimable from text.

### When to Switch Anchors Mid-Loop

Common triggers:
- Graders' estimates don't budge across rounds (anchor is too coarse).
- Graders disagree on what counts ("one is estimating P(desk review), another is estimating P(acceptance after revision)").
- The user realizes the target venue is wrong (from Step 0 diagnostics).

When any of these happens: pause the loop, explicitly re-anchor, confirm with the user.

---

## Part 3 — Reading Disagreement Across Graders

Disagreement is signal, not noise.

### Pattern 1 — "The outlier grader caught something"

One grader gives a dramatically lower score than the others (e.g., 9 / 9 / 5). Read the outlier's reason carefully. Often the outlier is raising a reviewer-attack-surface the other two didn't notice.

**Rule of thumb:** when the outlier is *lower*, trust the outlier unless their reasoning is obviously idiosyncratic. Overclaim is the most common failure mode.

### Pattern 2 — "Graders are evaluating different axes"

Scores are spread (e.g., 8 / 5 / 9) but the reasons are talking past each other. Grader A is scoring for clarity; Grader B is scoring for novelty; Grader C is scoring for fit to venue. Re-anchor with a more specific prompt.

### Pattern 3 — "Consistent middling scores"

All three graders give 6–7. The sentence does its job but doesn't earn its keep. The user should decide: keep it, cut it, or rewrite it at Step 5.

### Pattern 4 — "The draft's own grader underscored it"

When a model scores its own sentence lower than other graders score it, that is meaningful signal of self-aware weakness. Use those underscored cells as high-priority rewrite candidates.

### Pattern 5 — "Graders all agree a sentence is strong, but the manuscript still feels weak overall"

If every cell-level score is 8+ but the overall manuscript assessment is mediocre, the problem is structural: the sentences are individually good but they don't compose. Re-examine the logic chain (V1).

---

## Part 4 — What to Do with the Rubric Matrix at Each Step

- **Step 3 output**: full matrix + overall draft ranking + identified "best model."
- **Step 4 input**: user works down the matrix row by row. Rubric's disagreement annotations guide "is the score-8 sentence from draft A actually better than the score-9 sentence from draft B?"
- **Steps 5–6 input**: the "best model" still carries the knowledge of what each slot needs. Each proposal should anchor to the rubric's slot-level analysis.

---

*Last updated: 2026-04-18*
