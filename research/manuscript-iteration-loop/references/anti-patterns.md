# Anti-Patterns: How the Loop Goes Wrong and How to Catch It Early

The seven-step loop has a well-defined structure, but it's easy to violate the structure in ways that feel productive in the moment and corrupt the output days later. This file catalogues the most common failure modes and their remedies.

When the loop starts feeling "off" — stuck, circular, exhausting, or producing versions that are worse than V2 — check this list first before doing anything else.

---

## Anti-Pattern 1 — Editing V1 After Step 2 Has Started

**What it looks like:** The user has already collected parallel drafts from three models (Step 2 complete). While reviewing the drafts, the user spots a logical gap in V1 and wants to "quickly fix" V1 before scoring.

**Why it's wrong:** The three drafts are already expressions of V1's logic chain. Fixing V1 now invalidates the drafts — you'd need to rerun Step 2 with each model for the fix to propagate. If you don't rerun, the scoring in Step 3 will be against a V1 that no longer exists.

**Remedy:** If the gap in V1 is small (wording-level, clarification), absorb it into Step 5's refinement round. If the gap is structural (a whole missing argument), **abort Step 3, rewrite V1, rerun Step 2**. Don't compromise.

---

## Anti-Pattern 2 — The "Best Model" Drifts into Its Own Voice

**What it looks like:** V2 was assembled with strong contributions from all three models. By V3, the "best model" has subtly replaced Gemini-origin sentences with its own voice rewrites. By V4, the manuscript reads entirely in one model's voice.

**Why it's wrong:** The diversity was the *point*. When the best model homogenizes V2 back into its own voice, it undoes the key value of the multi-model loop.

**Remedy:** When giving V2 to the best model for Step 5, include an explicit instruction: "V2 contains sentences from multiple models, deliberately selected for their specific strengths. Do not rewrite sentences that were not originally yours unless you are proposing a specific change with a named reason." Flag and reject any proposals that silently rewrite a cross-model sentence without a named reason.

---

## Anti-Pattern 3 — Graders Agree Too Much

**What it looks like:** Every cell in the rubric matrix comes back with a tight cluster (e.g., 9 / 9 / 8.5). The user feels reassured and moves quickly to Step 4.

**Why it's wrong:** Graders that agree too much are either (a) reading each other's context, (b) all anchored to the same safe middle, or (c) the prompt didn't give them permission to disagree.

**Remedy:** Check three things. (1) Was each grader prompted independently with no reference to other graders' output? (2) Did the prompt explicitly invite contrarian assessment? (3) Did the prompt specify a sharp enough quantifiable anchor? Re-prompt independently if needed.

---

## Anti-Pattern 4 — Graders Disagree on What They're Measuring

**What it looks like:** The scores are spread wide (e.g., 9 / 6 / 3 on a single slot) but the graders are talking past each other — Grader A scores for clarity, Grader B for novelty, Grader C for fit-to-venue.

**Why it's wrong:** The matrix becomes uninterpretable. The slot-level winner is arbitrary.

**Remedy:** Re-anchor. The original prompt under-specified what "contribution to [quantifiable anchor]" meant. Rewrite the Step 3 prompt with a more specific anchor and re-score.

---

## Anti-Pattern 5 — Refinement Rounds Without Estimated-Impact Commitments

**What it looks like:** The best model proposes five refinements but doesn't attach numerical estimated impacts, or attaches vague ones like "significantly improves quality."

**Why it's wrong:** Without estimated impact, there's no closed loop. The model can propose arbitrary changes with no accountability.

**Remedy:** Enforce the format. If the best model returns proposals without estimated-impact numbers, send them back with: "Please reformat each proposal with a specific 'Estimated impact' field. This is a commitment field — if the round's cumulative estimated impact doesn't materialize in the next round's scoring, we'll know the estimates were over-optimistic."

---

## Anti-Pattern 6 — The Loop Goes On Too Long

**What it looks like:** V4 is done, then V5, then V6. Each round produces <0.5 percentage points of estimated improvement. The user keeps pushing for another refinement pass.

**Why it's wrong:** At this stage, the ceiling is determined by factors outside the prose — data quality, experimental evidence, novelty, venue fit.

**Remedy:** Set a stopping rule in advance: "If a round produces ≤1 percentage point of estimated improvement in the anchor, this is the ceiling." When triggered, tell the user plainly.

---

## Anti-Pattern 7 — Skipping Step 0 Because a Draft Exists

**What it looks like:** The user arrives with a nearly-finished paper and says "I just need some polish, let's start at Step 3." Three rounds later the polished paper is desk-rejected because the venue was wrong all along.

**Why it's wrong:** Step 0 is the only step that can catch a venue-mismatch or framing-mismatch error.

**Remedy:** Even when the user insists on skipping Step 0, do a 5-minute mini-version: ask "What venue are you targeting? What's the strategic angle? Have you stress-tested the angle against an alternative?" If the answers are hand-wavy, push back hard.

---

## Anti-Pattern 8 — Losing the Version Tracker

**What it looks like:** Three weeks into the loop, the user can't find V2. Or model outputs from Step 2 were never labeled. Or a sentence from V3 was silently edited between V3 and V4.

**Why it's wrong:** The audit trail is what lets the user understand why each decision was made. Without it, the final manuscript is a black box.

**Remedy:** Commit to the version tracker from Step 0. If the tracker is lost, pause the loop and reconstruct it from available artifacts before continuing.

---

## Anti-Pattern 9 — Over-Trusting a Single Grader's Editorial Instinct

**What it looks like:** Grader A gave particularly sharp scores in Step 3. The user defers to that grader's judgment for the rest of the loop. By V4, the manuscript has been optimized for what one model thinks the venue will like.

**Why it's wrong:** Any single model's "editorial instinct" is a hypothesis, not a ground truth. The loop's power comes from *triangulating across models*.

**Remedy:** At Steps 5 and 6, even after picking a "best model," paste V3 into at least one other model for a second opinion. If the second opinion disagrees on ≥2 of the N proposals, the user should re-examine.

---

## Anti-Pattern 10 — Letting the User Write Their Own Rewrites at Step 4 Without Rubric Anchoring

**What it looks like:** At Step 4, the user elects "rewrite" on several sentences in their own voice, which are subtly worse than any of the three model options.

**Why it's wrong:** The rubric captures specific editorial preferences. When the user rewrites in their habitual voice, they're optimizing against a different implicit anchor.

**Remedy:** When the user requests a rewrite, ask: "Can you tell me which element of the rubric's top-scored option you're trying to preserve, and what specifically you're trying to improve? Then I'll draft a version that matches your intent while staying anchored to the rubric."

---

## General Principle: Structural Fixes Beat Tactical Ones

Most of these anti-patterns have the same cure: **go back to the last step that produced a clean output, and restart from there.** This feels expensive in the moment but is almost always cheaper than patching downstream. If V1's logic is broken, rewrite V1 and rerun Step 2. If the rubric is broken, re-prompt Step 3. Discipline at each step is what makes the loop converge; compromises compound.

---

*Last updated: 2026-04-18*
