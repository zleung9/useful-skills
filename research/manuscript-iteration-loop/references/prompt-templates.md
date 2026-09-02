# Prompt Templates for Each Step

These are reusable prompt skeletons for each step of the loop. Written in English — the user can translate to their fluent language; the structure is what matters.

When helping the user compose a prompt, always customize the bracketed placeholders. Never paste these verbatim.

---

## § Step 0 — Strategy consultation prompt

Use when the user has a draft (or a near-draft) and wants to decide whether its positioning is right before investing in polish.

```
I am preparing a manuscript for submission to [TARGET VENUE — e.g., Nature, JAMA, Harvard Business Review, a specific grant call]. My credentials and team context are [BRIEF, E.G., "I am an associate editor at [journal]; my group has strong reputation in [field A] but we have limited publications in [field B, the one this paper engages]"].

I have attached the draft [and supplementary material / supporting documents].

My main concern is [STATE CONCERN CONCISELY — e.g., "I'm unsure whether our core claim is pitched at the right level of generality for this venue, and whether our team's profile is strong enough for the reviewer pool this venue draws from"].

Please do the following:

1. Read the draft carefully and identify what the genuinely strongest claim is — not necessarily what I've foregrounded, but what the evidence most directly supports.

2. Propose 2–4 alternative strategic angles (framings / emphases / entry points) that this same underlying work could take. For each, write 3–5 sentences on what the framing is and why it would appeal to this specific venue's editorial instinct.

3. For each angle, estimate the submission probability and the acceptance probability at the target venue, and at 1–2 likely fallback venues. State the probability as a range (e.g., "25–35%") and briefly justify the range.

4. Recommend the angle you would pick, and explain the single most impactful revision (with no or minimal new experiments/data) that would realize that angle. Also flag the 1–2 reviewer-attack-surfaces each angle exposes.

5. If you think none of the angles realistically clears the venue's bar given what's in the draft, say so plainly.

Be direct. I'm not looking for validation; I'm looking for the diagnosis a senior colleague would give over a whiteboard.
```

**What to do with the output:** Collect the response from each model (typically 3). Put them side by side. Look for: (a) agreement on the strongest claim, (b) the most-recommended angle, (c) the angle with the highest probability ceiling. If models converge, that's the angle. If they diverge, pick the angle whose reasoning the user finds most persuasive, and note which models disagreed.

---

## § Step 2 — Parallel drafting prompt

Use this after V1 (the logic draft) is locked. Paste the same prompt into each model independently. Do not mention the other models.

```
I am preparing a manuscript for [TARGET VENUE]. The strategic angle I have chosen is [STATE THE ANGLE IN 1–2 SENTENCES].

Below is the logic draft (V1) for the [title / abstract / introduction / the section you're iterating]. It is deliberately written in [mixed language / loose prose] — the goal is to convey the logic chain and key terms I want preserved, not to be the final prose.

[PASTE V1 HERE]

Please produce a complete, venue-appropriate draft based on this V1 that:
- Preserves the logic chain and key technical terms exactly as I have framed them.
- Is written in natural, publication-ready [English / target language], at the register and typical length of [target venue] for this section.
- Does not add new claims, reframe the argument, or import conventional tropes of the field unless V1 explicitly invites them.
- Foregrounds the chosen strategic angle in the first one or two sentences.

Return only the draft. I will compare your version side-by-side with drafts from other sources afterward.
```

**What to do with the output:** Label each model's output clearly — e.g., `=== [ModelName] draft, [timestamp] ===` — and store them in the version tracker. Do not edit them yet. They are the raw inputs to Step 3.

---

## § Step 3 — Sentence-level scoring prompt (back-to-back critique)

Use this after collecting drafts from every model in Step 2. Paste this prompt into each model (including the ones that drafted in Step 2 — self-evaluation is useful).

```
I have collected [N] complete drafts of the [title / abstract / introduction / section] of a manuscript targeted at [TARGET VENUE]. I would like you to evaluate them from the perspective of a [QUANTIFIABLE ANCHOR EVALUATOR — e.g., "Nature chief editor plus domain editor conducting triage for desk-to-peer-review decisions", or "NIH study section chair evaluating for fundability", or "HBR managing editor evaluating for feature placement"].

Below are the [N] drafts, labeled by source:

=== Draft A (Source: [ModelName1]) ===
[PASTE DRAFT A]

=== Draft B (Source: [ModelName2]) ===
[PASTE DRAFT B]

=== Draft C (Source: [ModelName3]) ===
[PASTE DRAFT C]

Please do the following, in order:

1. Sentence-by-sentence scoring. Break each draft into its sentences (keep the order each draft has). For each sentence slot, score the sentence from each draft on a 1–10 scale on its contribution to [quantifiable anchor]. Give a one-sentence reason per score.

2. Slot-level winner. For each sentence slot, state which draft's sentence you would pick for a fusion draft, and in one sentence say why.

3. Overall draft ranking. Rank the [N] drafts overall, with the quantifiable anchor's estimated probability for each as a range (e.g., "Nature desk-to-peer-review: 32–42%").

4. Optimal fusion recommendation. List the sentences (by draft and slot) you would pick if assembling a fusion draft, and state the estimated probability for that fusion draft.

5. Caveats. Note any reviewer-attack-surfaces that would remain even in the best fusion draft — these are what no amount of prose polish can fix and will require experimental, data, or structural work.

Be direct, specific, and willing to deprecate your own previous output if another draft's sentence is stronger. Your credibility here is in calibration, not in self-consistency.
```

**What to do with the output:** You now have 3 scoring matrices (one from each grader). Align them into a single master matrix where rows = sentence slots and columns include one score per grader per draft. The "best model" emerges either as the draft that the majority of graders rank highest overall, or — if the user prefers — the grader whose commentary is most useful across slots.

---

## § Step 5 — N-point refinement with estimated-impact closed loop

Use this after V2 is assembled. Paste into the "best model" chosen in Step 3.

```
Attached is V2 of the [section] of a manuscript for [TARGET VENUE]. V2 was assembled by picking the strongest sentences from multiple drafts and is structurally locked — I am not changing the logic chain or the sentence structure at this stage.

My goal at this stage is word-choice refinement only. Please propose exactly [N — typically 5] specific wording changes that would most improve [quantifiable anchor], without altering sentence structure or information content.

For each of the [N] proposals, use this exact format:

**Proposal #[i]: [short descriptive name]**
- **Current:** [exact current text from V2, verbatim]
- **Proposed:** [exact proposed replacement, verbatim]
- **Reason:** [2–4 sentences. What reviewer-attack-surface does this close? What anchor does it restore?]
- **Estimated impact:** [e.g., "+1.5 percentage points on Nature desk-to-peer-review probability"]

After the [N] proposals, briefly rank them by estimated impact and note any that interact with each other.

At the end, give your total estimated impact if all [N] are applied. Also state the estimated probability ceiling that still can't be closed by wording alone, and what would be needed to close it (more data, different figures, etc.).

Be specific and be willing to justify each proposal against a hypothetical skeptical reviewer. Do not propose changes that would reopen structural or logical decisions already made in V2.
```

**What to do with the output:** Walk the user through each proposal. For each, ask: accept, reject, or accept with modification. Record the decision. Apply the accepted changes. The resulting document is V3.

---

## § Step 6 — Length and format polish

Use this after V3 is locked. Paste into the "best model".

```
Attached is V3 of the [section] of a manuscript for [TARGET VENUE]. V3 is wording-locked.

My final concerns are length and format. For [TARGET VENUE]'s typical [section type], the typical word count is roughly [X–Y words] and the typical paragraph count is [Z]. My current V3 is [current word count]. [If known, state citation format, terminology consistency issues, etc.]

Please propose exactly [M — typically 3] changes that would best align V3 to [TARGET VENUE]'s length and format norms without reopening logic, structure, or wording decisions already made.

Typical levers at this stage:
- Compressing an over-long paragraph (specify which, and how to cut, preserving meaning).
- Trimming redundancy (identify the specific redundant phrase, propose the tighter wording).
- Resolving terminology inconsistency.
- Adjusting citation density to venue norms.
- Fixing paragraph rhythm (short/long/short is a common venue pattern).

For each of the [M] proposals, use the same format as Step 5 (Current, Proposed, Reason, Estimated impact). Confirm a total word count after all [M] are applied.

If V3 is already within the target length and format range, say so plainly and propose fewer than [M] changes.
```

**What to do with the output:** Accept/reject each. Apply the accepted changes. The result is V4 — the final manuscript.

---

## Meta-Prompt: Asking the User for the Quantifiable Anchor

If the user is unclear about what their quantifiable anchor should be, ask them directly:

> "For this loop to work, we need one concrete number that every model can commit to and argue over. What number feels right to you from these options, or do you want to propose your own?"

Present 2–4 options specific to the user's context:

| Manuscript type | Good anchor | Example number |
|---|---|---|
| Nature / Science / top-field journal paper | Desk-review-to-peer-review probability | 30–40% |
| Second-tier journal paper | Major-revision-or-accept probability | 40–55% |
| NIH R01 grant | Fundable-score probability | 15–25% |
| NSF proposal | Recommended-for-funding probability | 10–20% |
| HBR / Wall Street Journal feature | Accepted-for-print probability | 8–15% |
| Board memo / CEO recommendation | Probability the board approves | 40–70% |
| Cold outreach email | Reply-from-named-recipient probability | 5–25% |
| Grant rebuttal | Probability of overturning the prior decision | 15–35% |

---

*Last updated: 2026-04-18*
