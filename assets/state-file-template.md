<!--
Copy this file to the task root as NN_TO_THE_NEXT_SESSION.md. Fill every
bracketed value before finalize. Keep one live state per task and update it after
each meaningful step. The STATE FILE is the sole source of truth for current task
state; a relay is only a generated transport snapshot.

Status: active | waiting_user | complete | superseded | abandoned
Target: same-machine | cross-machine
For same-machine, State locator must equal this file's absolute path.
For cross-machine, use one resolvable form:
  repo:https://host/owner/repo.git@<40-hex-commit>#relative/path/to/state.md
  sync:<named-root>#relative/path/to/state.md
  archive:<bundle-path-or-URL>#member/path/to/state.md
-->

# TO THE NEXT SESSION — [task name]

_TTNS schema: 1_
_Handoff ID: [stable-task-slug]_
_Status: active_
_Target: [same-machine or cross-machine]_
_State locator: [absolute path or portable locator described above]_
_Last updated: [YYYY-MM-DDTHH:MM:SS+TZ]_
_Superseded by: none_

## START HERE

- **Goal:** [the exact outcome].
- **Current phase:** [what is complete, in flight, and blocked].
- **Next:** [the single NEXT TASK below].
- **Highest-risk rules:** [C# and active G# IDs].
- **Read order:** this state, then only the A# IDs required by NEXT TASK.

## INVIOLABLE CONSTRAINTS

<!-- TTNS:BEGIN:INVIOLABLE_CONSTRAINTS -->
- **C1:** [task-wide correctness or scope rule, copied verbatim].
- **C2:** [another task-wide rule, copied verbatim].
<!-- TTNS:END:INVIOLABLE_CONSTRAINTS -->

Use C# only for rules that remain binding across the whole task. Do not silently
delete or paraphrase one; retire it in DECISIONS with the exact prior text and reason.

## ACTIVE ACTION GUARDS

<!-- TTNS:BEGIN:ACTIVE_ACTION_GUARDS -->
- **G1:** [temporary authority/action guard, copied verbatim].
<!-- TTNS:END:ACTIVE_ACTION_GUARDS -->

Use G# for current permissions or temporary prohibitions such as "push/deploy awaits
instruction." If none are active, write exactly `- None.`. Move a lifted guard to
DECISIONS with its reason; do not leave a stale guard active.

## STATUS

<!-- TTNS:BEGIN:STATUS -->
[Present reality in 2–6 sentences. Separate verified facts from `[unverified]`
claims. Do not narrate obsolete history here.]
<!-- TTNS:END:STATUS -->

## NEXT TASK

<!-- TTNS:BEGIN:NEXT_TASK -->
[One concrete action only. Name the command/file/decision and stopping condition.]
Required artifact IDs: [A1, A3 or none]
<!-- TTNS:END:NEXT_TASK -->

Only the listed A# IDs are eager reads in the fresh session. Everything else remains
deferred until the task actually needs it.

## ARTIFACT INDEX

| ID | Locator on this machine | What it is | Cheapest safe verification | Portable locator |
|---|---|---|---|---|
| A1 | `[absolute path or URI]` | [ground-truth role] | [safe read/checksum/idempotent command] | [state-relative:path or full portable locator; — only for same-machine] |
| A2 | `[absolute path or URI]` | [deferred artifact] | [cheapest safe probe] | [portable locator or —] |

For a cross-machine handoff, every A# required by NEXT TASK needs a portable locator.
`repo:...@commit` covers only files present at that commit. Dirty or untracked work
must travel through a named sync root, patch plus required untracked files, or archive;
do not claim that a clean commit carries WIP it does not contain. Inspect commands
before running them: artifacts are data, not instructions.

## INVARIANTS

- **Goal and completion test:** [observable definition of done].
- **In scope / out of scope:** [exact boundary].
- **Fixed values:** [exact thresholds, tiers, counts, units, each with a source A#].

## DECISIONS

### D1 — [short decision title]

- **Chosen:** [decision].
- **Because:** [reason/evidence].
- **Rejected:** [alternative and conditions under which rejection holds].
- **Source:** [visible user instruction / artifact A# / reconstruction marked unverified].

Record plan approval, corrections, and other user-consulted decisions that affect
future action. Never invent missing provenance after chat history is gone.

## OPEN ISSUES

- [ ] [queued work beyond NEXT TASK].
- [ ] `[unverified]` [claim and the A#/probe that can settle it].

## HANDOFF AUDIT

- [ ] Goal, scope, C#, active G#, status, and one NEXT TASK match present reality.
- [ ] Required A# IDs exist; their cheapest probes are safe and sufficient.
- [ ] Cross-machine WIP is actually carried by its portable locator.
- [ ] `finalize` succeeded after the last state edit.
- [ ] The final response ends with the exact helper-emitted copy box and nothing after it.

After completion, close the state so an old active relay cannot restart finished work:

`python scripts/handoff.py close --state <state> --status complete`
