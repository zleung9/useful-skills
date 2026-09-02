#!/usr/bin/env python3
"""
Research Committee — Blackboard Management & Committee Invocation Helper

Usage:
    # Idea lifecycle
    python committee.py init <idea_id> <field_context> [--user-lang=zh]
    python committee.py state <idea_id>
    python committee.py list

    # Committee invocation
    python committee.py invoke <idea_id> <agent> <candidate>
    python committee.py invoke-all <idea_id> <candidate>    # invoke all 4 agents in parallel

    # Merge & decision
    python committee.py merge <idea_id> <candidate>          # Oracle merges packs into MergePack
    python committee.py approve <idea_id> <candidate>       # Oracle writes FinalTopicSpec
    python committee.py kill <idea_id> <candidate>         # Oracle kills and switches

    # Resume
    python committee.py resume <idea_id>                     # Check state and decide next step

    # Read
    python committee.py read <idea_id> <pack_name> [candidate]
    python committee.py read-all <idea_id> [candidate]      # Read all packs for a candidate

    # Blackboard
    python committee.py blackboard-root                      # Print blackboard root path
    python committee.py next-phase <idea_id> <phase>        # Manually update phase

Blackboard root: ~/.hermes/research-committee/blackboard/ideas/<idea_id>/
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── Config ──────────────────────────────────────────────────────────────────

BLACKBOARD_ROOT = Path.home() / ".hermes" / "research-committee" / "blackboard" / "ideas"
SKILL_REFS_DIR = Path(__file__).parent.parent / "references"
SCRIPTS_DIR = Path(__file__).parent

PERSONAS = {
    "literature-scout": "literature-scout-persona.md",
    "feasibility-analyst": "feasibility-analyst-persona.md",
    "venue-strategist": "venue-strategist-persona.md",
    "red-team-critic": "red-team-critic-persona.md",
}

# Agent invocation order
COMMITTEE_SEQUENCE = ["literature-scout", "feasibility-analyst", "venue-strategist", "red-team-critic"]

# ─── Persona helpers ─────────────────────────────────────────────────────────

def get_persona(agent: str) -> str:
    path = SKILL_REFS_DIR / PERSONAS[agent]
    if not path.exists():
        raise ValueError(f"Persona file not found: {path}")
    return path.read_text()

# ─── Idea lifecycle ──────────────────────────────────────────────────────────

def init_idea(idea_id: str, field_context: str = "", user_lang: str = "zh") -> None:
    """Initialize a new idea directory with state.json."""
    idea_dir = BLACKBOARD_ROOT / idea_id
    idea_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "schema": "IdeaState/v1",
        "idea_id": idea_id,
        "phase": "DRAFT",
        "candidates": [],
        "revision_count": 0,
        "max_revisions": 1,
        "user_lang": user_lang,
        "field_context": field_context,
        "history": [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    state_path = idea_dir / "state.json"
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(f"✓ Initialized: {idea_id} [{state['phase']}]")
    print(f"  Path: {state_path}")


def read_state(idea_id: str) -> dict:
    state_path = BLACKBOARD_ROOT / idea_id / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"No state.json found for idea: {idea_id}")
    return json.loads(state_path.read_text())


def write_state(idea_id: str, state: dict, note: str = "") -> None:
    """Update state with phase transition history."""
    old_phase = state.get("phase", "?")
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    if note:
        state["history"].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "phase": state["phase"],
            "note": note,
        })
    state_path = BLACKBOARD_ROOT / idea_id / "state.json"
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(f"  [{idea_id}] {old_phase} → {state['phase']}")


def update_phase(idea_id: str, new_phase: str, note: str = "") -> None:
    state = read_state(idea_id)
    state["phase"] = new_phase
    write_state(idea_id, state, note)


def list_ideas() -> None:
    """List all ideas with their current phase."""
    if not BLACKBOARD_ROOT.exists():
        print("No ideas found.")
        return
    ideas = []
    for idea_dir in sorted(BLACKBOARD_ROOT.iterdir()):
        if idea_dir.is_dir():
            state_file = idea_dir / "state.json"
            if state_file.exists():
                state = json.loads(state_file.read_text())
                phase = state.get("phase", "?")
                candidates = state.get("candidates", [])
                revision = state.get("revision_count", 0)
                ideas.append((idea_dir.name, phase, candidates, revision))
            else:
                ideas.append((idea_dir.name, "NO STATE", [], 0))

    if not ideas:
        print("No ideas found.")
        return

    print(f"Blackboard: {BLACKBOARD_ROOT}")
    print(f"{'Idea ID':<30} {'Phase':<12} {'Candidates':<20} {'Revisions'}")
    print("-" * 80)
    for name, phase, candidates, revision in ideas:
        cand_str = ", ".join(candidates) if candidates else "none"
        print(f"{name:<30} {phase:<12} {cand_str:<20} {revision}")


# ─── Pack I/O ─────────────────────────────────────────────────────────────────

def pack_path(idea_id: str, pack_name: str, candidate: str = None) -> Path:
    if candidate:
        return BLACKBOARD_ROOT / idea_id / f"{pack_name}_{candidate}.json"
    return BLACKBOARD_ROOT / idea_id / f"{pack_name}.json"


def read_pack(idea_id: str, pack_name: str, candidate: str = None) -> Optional[dict]:
    path = pack_path(idea_id, pack_name, candidate)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_pack(idea_id: str, pack_name: str, data: dict, candidate: str = None) -> None:
    path = pack_path(idea_id, pack_name, candidate)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  ✓ Wrote: {path.name}")


def pack_exists(idea_id: str, pack_name: str, candidate: str = None) -> bool:
    return pack_path(idea_id, pack_name, candidate).exists()


def list_packs(idea_id: str) -> list[str]:
    """List all pack files for an idea."""
    idea_dir = BLACKBOARD_ROOT / idea_id
    if not idea_dir.exists():
        return []
    return sorted([f.name for f in idea_dir.iterdir() if f.suffix == ".json"])


# ─── Committee task generation ────────────────────────────────────────────────

def get_committee_task(agent: str, idea_id: str, candidate: str) -> str:
    """Generate the committee member task prompt (printed for delegation)."""
    persona = get_persona(agent)

    pack_map = {
        "literature-scout": "10_literature",
        "feasibility-analyst": "11_feasibility",
        "venue-strategist": "12_venue",
        "red-team-critic": "20_critique",
    }

    # What files each agent reads as input
    input_map = {
        "literature-scout": ["00_idea_spec.json", f"01_candidate_{candidate}.json"],
        "feasibility-analyst": ["00_idea_spec.json", f"01_candidate_{candidate}.json"],
        "venue-strategist": [
            "00_idea_spec.json",
            f"01_candidate_{candidate}.json",
            f"10_literature_{candidate}.json",
            f"11_feasibility_{candidate}.json",
            f"30_merge_{candidate}.json",
        ],
        "red-team-critic": ["*"],  # reads everything for this candidate
    }

    output_file = f"{pack_map[agent]}_{candidate}.json"
    input_files = input_map.get(agent, [])

    input_files_str = "\n".join(f'  - `blackboard/ideas/{idea_id}/{f}`' for f in input_files)

    return f"""You are invoking **{agent}** for idea `{idea_id}` candidate `{candidate}`.

## Your task
Read the input files from the blackboard, apply your committee persona, and write your pack.

## Input files to read:
{input_files_str}

## Output file to write
`blackboard/ideas/{idea_id}/{output_file}`

## Your persona
{persona}

## Instructions
1. Read all required input files from the blackboard at `~/.hermes/research-committee/blackboard/ideas/{idea_id}/`
2. Apply your committee member persona and expertise
3. Write the output JSON file matching the schema in `~/.hermes/skills/research-committee/references/SCHEMAS.md`
4. The output file MUST have a valid `schema` field matching the expected pack type
5. Write ONLY your own designated output file — do not write any other pack

## Blackboard root
`~/.hermes/research-committee/blackboard/ideas/{idea_id}/`

## Language rule
All JSON keys must be in English. All text content (titles, statements, descriptions) must be in the same language as the user who submitted this idea. If the user wrote in Chinese, write Chinese content. If English, write English.
"""


def get_merge_task(idea_id: str, candidate: str) -> str:
    """Generate the Oracle merge task prompt."""
    return f"""You are Oracle 🔮 merging committee packs into a MergePack for idea `{idea_id}` candidate `{candidate}`.

## Your task
1. Read: `10_literature_{candidate}.json`, `11_feasibility_{candidate}.json`, `12_venue_{candidate}.json`
2. Read the IdeaSpec: `00_idea_spec.json`
3. Read the CandidateSpec: `01_candidate_{candidate}.json`
4. Write: `30_merge_{candidate}.json`

## What you must produce

**integrated_pitch** (2-3 sentences):
Synthesize all three packs into one coherent "why this candidate is worth doing."

**strongest_points** (at least 3):
One each from: literature perspective, feasibility perspective, venue perspective.

**weakest_points** (at least 3):
One each from: literature perspective, feasibility perspective, venue perspective.

**oracle_prior**:
Your independent prior belief about this candidate before red-team critique:
```json
{{
  "novelty": "high|medium|low",
  "feasibility": "high|medium|low",
  "publishability": "high|medium|low",
  "reason": "string — your honest assessment"
}}
```

**consensus_analysis**:
Where do the literature-scout, feasibility-analyst, and venue-strategist agree? Where do they disagree?

## Schema
Follow MergePack/v1 schema in `~/.hermes/skills/research-committee/references/SCHEMAS.md`.

## Output
Write `~/.hermes/research-committee/blackboard/ideas/{idea_id}/30_merge_{candidate}.json`
"""


def get_decision_prompt(idea_id: str, candidate: str) -> str:
    """Generate the Oracle decision task prompt."""
    critique = read_pack(idea_id, f"20_critique", candidate)
    merge = read_pack(idea_id, f"30_merge", candidate)
    literature = read_pack(idea_id, f"10_literature", candidate)
    feasibility = read_pack(idea_id, f"11_feasibility", candidate)

    verdict = critique.get("verdict", "unknown") if critique else "NO CRITIQUE FOUND"
    kill_reason = critique.get("kill_reason_if_kill", "N/A") if critique else "N/A"
    alt_direction = critique.get("alternative_direction_hint", "none") if critique else "none"
    fatal_count = len(critique.get("fatal_flaws", [])) if critique else "?"
    major_count = len(critique.get("major_concerns", [])) if critique else "?"
    novelty = literature.get("novelty_verdict", {}).get("level", "?") if literature else "?"
    feasibility_score = feasibility.get("feasibility_score", "?") if feasibility else "?"

    return f"""You are Oracle 🔮 making a decision for idea `{idea_id}` candidate `{candidate}`.

## Evidence on the table

**LiteraturePack** (novelty): {novelty}
**FeasibilityPack** (score): {feasibility_score}
**CritiquePack** verdict: **{verdict}**
**Fatal flaws**: {fatal_count}
**Major concerns**: {major_count}

Kill reason (if kill): {kill_reason}
Alternative direction (if kill): {alt_direction}

## Decision rules

**KILL** if ANY of:
- novelty_verdict.level == "low"
- feasibility_score < 0.4
- fatal_flaws > 0
- no six_month_deliverable

**REVISE** if:
- No fatal flaws, but major_concerns exist with repair_tickets
- novelty + feasibility both acceptable, but narrative has fixable issues
- Maximum 1 revision cycle allowed

**PASS** if ALL of:
- novelty_verdict.level != "low"
- feasibility_score ≥ 0.6
- fatal flaws = 0
- All major concerns have repair_tickets
- Venue has executable path

## Your job

1. Read all packs for `{idea_id}` candidate `{candidate}`
2. Apply the decision rules above
3. Execute the decision:
   - **kill**: Print "## Decision: KILL" + kill reason + alternative_direction_hint. Then switch to other candidate or generate new direction.
   - **revise**: Print "## Decision: REVISE" + list of repair_tickets. After fix, re-run red-team-critic.
   - **pass**: Print "## Decision: PASS" and then call `committee.py approve {idea_id} {candidate}`

## After decision

If **kill with other candidate available**: Load the other candidate's packs and present its verdict summary.
If **kill with no other candidate**: Generate a new candidate direction from `alternative_direction_hint`.
"""


# ─── Convenience commands ─────────────────────────────────────────────────────

def invoke_agent(agent: str, idea_id: str, candidate: str) -> None:
    """Print the committee task for an agent (callable by delegate_task wrapper)."""
    if agent not in PERSONAS:
        raise ValueError(f"Unknown agent: {agent}. Valid: {list(PERSONAS.keys())}")
    print(get_committee_task(agent, idea_id, candidate))


def invoke_all(idea_id: str, candidate: str) -> None:
    """Print instructions for invoking all 4 committee agents in parallel."""
    print(f"# Invoking all committee agents for {idea_id} candidate {candidate}\n")
    for agent in COMMITTEE_SEQUENCE:
        print(f"\n{'='*60}")
        print(f"# {agent.upper()}")
        print('='*60)
        invoke_agent(agent, idea_id, candidate)


def read_all_packs(idea_id: str, candidate: str = None) -> None:
    """Read and display all packs for an idea."""
    if candidate:
        packs_to_read = [
            ("IdeaSpec", None),
            (f"Candidate {candidate}", None),
            (f"Literature {candidate}", candidate),
            (f"Feasibility {candidate}", candidate),
            (f"Merge {candidate}", candidate),
            (f"Venue {candidate}", candidate),
            (f"Critique {candidate}", candidate),
        ]
    else:
        packs = list_packs(idea_id)
        print(f"Available packs for {idea_id}:")
        for p in packs:
            print(f"  - {p}")
        return

    for label, cand in packs_to_read:
        if cand:
            pack_name = label.split()[0].lower()
            # Map label to pack prefix
            prefix_map = {
                "literature": "10_literature",
                "feasibility": "11_feasibility",
                "merge": "30_merge",
                "venue": "12_venue",
                "critique": "20_critique",
            }
            pack_name = prefix_map.get(pack_name, pack_name)
            data = read_pack(idea_id, pack_name, cand)
        else:
            if "Candidate" in label:
                cand_letter = label[-1]
                data = read_pack(idea_id, f"01_candidate_{cand_letter}")
            else:
                data = read_pack(idea_id, "00_idea_spec")
        print(f"\n{'='*60}")
        print(f"# {label}")
        print('='*60)
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("  [not found]")


def resume_idea(idea_id: str) -> dict:
    """Check state of an idea and suggest next step."""
    state = read_state(idea_id)
    phase = state.get("phase", "?")
    candidates = state.get("candidates", [])
    revision = state.get("revision_count", 0)
    packs = list_packs(idea_id)

    print(f"\n{'='*50}")
    print(f"Idea: {idea_id}")
    print(f"Phase: {phase} | Revisions: {revision}/{state.get('max_revisions', 1)}")
    print(f"Candidates: {candidates or 'none'}")
    print(f"Packs on blackboard ({len(packs)}):")
    for p in packs:
        print(f"  - {p}")

    # Determine next step
    if phase == "DRAFT":
        print("\n→ Next: Generate IdeaSpec + Candidate A/B (Phase 0)")
    elif phase == "TRIAGED":
        print(f"\n→ Next: Run Phase 1 for candidates: {candidates}")
        print(f"  committee.py invoke-all {idea_id} A")
        print(f"  committee.py invoke-all {idea_id} B")
    elif phase == "EVALUATING":
        # Check which packs exist
        needed = []
        for c in candidates:
            for prefix in ["10_literature", "11_feasibility"]:
                if not pack_exists(idea_id, prefix, c):
                    needed.append(f"{prefix}_{c}")
        if needed:
            print(f"\n→ Still missing: {needed}")
        else:
            print(f"\n→ Next: Merge packs for {candidates}")
            for c in candidates:
                print(f"  committee.py merge {idea_id} {c}")
    elif phase == "SYNTHESIZED":
        # Check venue
        missing_venue = [c for c in candidates if not pack_exists(idea_id, "12_venue", c)]
        if missing_venue:
            print(f"\n→ Missing venue packs: {missing_venue}")
        else:
            print(f"\n→ Next: Red team critique")
            for c in candidates:
                print(f"  committee.py invoke {idea_id} red-team-critic {c}")
    elif phase == "CRITIQUED":
        print(f"\n→ Next: Oracle makes decision")
        for c in candidates:
            critique = read_pack(idea_id, "20_critique", c)
            v = critique.get("verdict", "?") if critique else "?"
            print(f"  {c}: verdict = {v}")
    elif phase == "REVISING":
        print(f"\n→ In revision cycle {revision}. After fix, re-run critique.")
    elif phase == "APPROVED":
        final = read_pack(idea_id, "40_final_topic")
        if final:
            print(f"\n✓ APPROVED. FinalTopicSpec:")
            print(f"  Title: {final.get('title', 'N/A')}")
            print(f"  One-sentence test: {final.get('one_sentence_test', 'N/A')}")
    elif phase == "REJECTED":
        print("\n✗ REJECTED. No viable candidate found.")
        alt = state.get("last_kill_reason", "")
        if alt:
            print(f"  Last kill reason: {alt}")

    return state


# ─── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    # ── Idea lifecycle ──
    if cmd == "init":
        if len(sys.argv) < 3:
            print("Usage: committee.py init <idea_id> [field_context] [--user-lang=zh|en]")
            sys.exit(1)
        idea_id = sys.argv[2]
        field_context = ""
        user_lang = "zh"
        for arg in sys.argv[3:]:
            if arg.startswith("--user-lang="):
                user_lang = arg.split("=")[1]
            else:
                field_context = arg
        init_idea(idea_id, field_context, user_lang)

    elif cmd == "state":
        if len(sys.argv) < 3:
            print("Usage: committee.py state <idea_id>")
            sys.exit(1)
        state = read_state(sys.argv[2])
        print(json.dumps(state, indent=2, ensure_ascii=False))

    elif cmd == "list":
        list_ideas()

    elif cmd == "next-phase":
        if len(sys.argv) < 4:
            print("Usage: committee.py next-phase <idea_id> <phase>")
            sys.exit(1)
        update_phase(sys.argv[2], sys.argv[3])

    # ── Committee invocation ──
    elif cmd == "invoke":
        if len(sys.argv) < 5:
            print("Usage: committee.py invoke <idea_id> <agent> <candidate>")
            sys.exit(1)
        _, _, idea_id, agent, candidate = sys.argv
        invoke_agent(agent, idea_id, candidate)

    elif cmd == "invoke-all":
        if len(sys.argv) < 4:
            print("Usage: committee.py invoke-all <idea_id> <candidate>")
            sys.exit(1)
        _, _, idea_id, candidate = sys.argv
        invoke_all(idea_id, candidate)

    # ── Merge & decision ──
    elif cmd == "merge":
        if len(sys.argv) < 4:
            print("Usage: committee.py merge <idea_id> <candidate>")
            sys.exit(1)
        _, _, idea_id, candidate = sys.argv
        print(get_merge_task(idea_id, candidate))

    elif cmd == "approve":
        if len(sys.argv) < 4:
            print("Usage: committee.py approve <idea_id> <candidate>")
            sys.exit(1)
        _, _, idea_id, candidate = sys.argv
        update_phase(idea_id, "APPROVED", f"Candidate {candidate} passed committee")
        final = read_pack(idea_id, "40_final_topic", candidate)
        if final:
            print(f"✓ FinalTopicSpec written for {candidate}")

    elif cmd == "kill":
        if len(sys.argv) < 4:
            print("Usage: committee.py kill <idea_id> <candidate>")
            sys.exit(1)
        _, _, idea_id, candidate = sys.argv
        state = read_state(idea_id)
        state["phase"] = "REJECTED"
        state["history"].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "phase": "REJECTED",
            "note": f"Candidate {candidate} killed",
        })
        write_state(idea_id, state)
        print(f"✗ {idea_id} candidate {candidate} KILLED. Switch to other candidate or generate new direction.")

    elif cmd == "decision":
        if len(sys.argv) < 4:
            print("Usage: committee.py decision <idea_id> <candidate>")
            sys.exit(1)
        _, _, idea_id, candidate = sys.argv
        print(get_decision_prompt(idea_id, candidate))

    # ── Resume & read ──
    elif cmd == "resume":
        if len(sys.argv) < 3:
            print("Usage: committee.py resume <idea_id>")
            sys.exit(1)
        resume_idea(sys.argv[2])

    elif cmd == "read":
        if len(sys.argv) < 4:
            print("Usage: committee.py read <idea_id> <pack_name> [candidate]")
            sys.exit(1)
        idea_id = sys.argv[2]
        pack_name = sys.argv[3]
        candidate = sys.argv[4] if len(sys.argv) > 4 else None
        data = read_pack(idea_id, pack_name, candidate)
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Pack not found: {pack_name}_{candidate if candidate else ''}")

    elif cmd == "read-all":
        if len(sys.argv) < 3:
            print("Usage: committee.py read-all <idea_id> [candidate]")
            sys.exit(1)
        idea_id = sys.argv[2]
        candidate = sys.argv[3] if len(sys.argv) > 3 else None
        read_all_packs(idea_id, candidate)

    # ── Blackboard utilities ──
    elif cmd == "blackboard-root":
        print(BLACKBOARD_ROOT)

    elif cmd == "packs":
        if len(sys.argv) < 3:
            print("Usage: committee.py packs <idea_id>")
            sys.exit(1)
        for p in list_packs(sys.argv[2]):
            print(f"  {p}")

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
