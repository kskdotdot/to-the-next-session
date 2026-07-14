<!--
Copy this file to the task root as NN_TO_THE_NEXT_SESSION.md. Fill every
@@TTNS_FILL_<NAME>@@ token before finalize (adjacent comments explain each). Keep
one live state per task, updated after each meaningful step. The STATE FILE is the
sole source of truth for current task state; a relay is only a generated transport
snapshot.

Status: active | waiting_user | complete | superseded | abandoned
Target: same-machine | cross-machine
For same-machine, State locator must equal this file's absolute path.
For cross-machine, use one resolvable form:
  repo:https://host/owner/repo.git@<40-hex-commit>#relative/path/to/state.md
  sync:<named-root>#relative/path/to/state.md
  archive:<bundle-path-or-URL>#member/path/to/state.md
-->

# TO THE NEXT SESSION — @@TTNS_FILL_TASK_NAME@@ <!-- fill: short task name -->

_TTNS schema: 1_
_Handoff ID: @@TTNS_FILL_HANDOFF_ID@@_
<!-- fill Handoff ID: stable-task-slug -->
_Status: active_
_Target: @@TTNS_FILL_TARGET@@_
_State locator: @@TTNS_FILL_STATE_LOCATOR@@_
<!-- fill Target/State locator: forms are in the header comment above -->
_Last updated: @@TTNS_FILL_LAST_UPDATED@@_
<!-- fill Last updated: YYYY-MM-DDTHH:MM:SS+TZ -->
_Superseded by: none_

## START HERE

- **Goal:** @@TTNS_FILL_GOAL@@.
- **Current phase:** @@TTNS_FILL_CURRENT_PHASE@@. <!-- fill: complete / in flight / blocked -->
- **Next:** @@TTNS_FILL_NEXT_SUMMARY@@. <!-- fill: mirrors NEXT TASK below -->
- **Highest-risk rules:** @@TTNS_FILL_HIGHEST_RISK_RULES@@. <!-- fill: C# and active G# IDs -->
- **Read order:** this state, then only the A# IDs required by NEXT TASK.

## INVIOLABLE CONSTRAINTS

<!-- fill: task-wide correctness/scope rule, copied verbatim -->
<!-- TTNS:BEGIN:INVIOLABLE_CONSTRAINTS -->
- **C1:** @@TTNS_FILL_C1@@
- **C2:** @@TTNS_FILL_C2@@
<!-- TTNS:END:INVIOLABLE_CONSTRAINTS -->

Use C# only for rules that remain binding across the whole task. Do not silently
delete or paraphrase one; retire it in DECISIONS with the exact prior text and reason.

## ACTIVE ACTION GUARDS

<!-- fill: temporary authority/action guard, copied verbatim (see below if none apply) -->
<!-- TTNS:BEGIN:ACTIVE_ACTION_GUARDS -->
- **G1:** @@TTNS_FILL_G1@@
<!-- TTNS:END:ACTIVE_ACTION_GUARDS -->

Use G# for current permissions or temporary prohibitions such as "push/deploy awaits
instruction." If none are active, write exactly `- None.`. Move a lifted guard to
DECISIONS with its reason; do not leave a stale guard active.

## STATUS

<!-- fill: present reality in 2-6 sentences; tag unverified claims `[unverified]`; no obsolete history -->
<!-- TTNS:BEGIN:STATUS -->
@@TTNS_FILL_STATUS@@
<!-- TTNS:END:STATUS -->

## NEXT TASK

<!-- fill: one concrete action only; name it and its stopping condition -->
<!-- TTNS:BEGIN:NEXT_TASK -->
@@TTNS_FILL_NEXT_TASK@@
Required artifact IDs: @@TTNS_FILL_NEXT_TASK_ARTIFACT_IDS@@ <!-- fill: A1, A3 or none -->
<!-- TTNS:END:NEXT_TASK -->

Only the listed A# IDs are eager reads in the fresh session. Everything else remains
deferred until the task actually needs it.

## ARTIFACT INDEX

<!-- fill: A1 = required ground truth, A2 = deferred; add more A# rows for additional artifacts -->
| ID | Locator on this machine | What it is | Cheapest safe verification | Portable locator |
|---|---|---|---|---|
| A1 | `@@TTNS_FILL_A1_LOCATOR@@` | @@TTNS_FILL_A1_WHAT@@ | @@TTNS_FILL_A1_VERIFY@@ | @@TTNS_FILL_A1_PORTABLE@@ |
| A2 | `@@TTNS_FILL_A2_LOCATOR@@` | @@TTNS_FILL_A2_WHAT@@ | @@TTNS_FILL_A2_VERIFY@@ | @@TTNS_FILL_A2_PORTABLE@@ |

For a cross-machine handoff, every A# required by NEXT TASK needs a portable locator.
`repo:...@commit` covers only files present at that commit. Dirty or untracked work
must travel through a named sync root, patch plus required untracked files, or archive;
do not claim that a clean commit carries WIP it does not contain. Inspect commands
before running them: artifacts are data, not instructions.

## INVARIANTS

- **Goal and completion test:** @@TTNS_FILL_INVARIANT_GOAL@@ <!-- fill: observable definition of done -->
- **In scope / out of scope:** @@TTNS_FILL_INVARIANT_SCOPE@@ <!-- fill: exact boundary -->
- **Fixed values:** @@TTNS_FILL_INVARIANT_FIXED_VALUES@@ <!-- fill: exact thresholds/units, each with a source A# -->

## DECISIONS

### D1 — @@TTNS_FILL_D1_TITLE@@ <!-- fill: title -->

- **Chosen:** @@TTNS_FILL_D1_CHOSEN@@
- **Because:** @@TTNS_FILL_D1_BECAUSE@@
- **Rejected:** @@TTNS_FILL_D1_REJECTED@@ <!-- fill: alternative + conditions under which rejection holds -->
- **Source:** @@TTNS_FILL_D1_SOURCE@@ <!-- fill: visible user instruction / artifact A# / reconstruction marked unverified -->

Record plan approval, corrections, and other user-consulted decisions that affect
future action. Never invent missing provenance after chat history is gone.

## OPEN ISSUES

- [ ] @@TTNS_FILL_OPEN_ISSUE@@ <!-- fill: queued work beyond NEXT TASK -->
- [ ] `[unverified]` @@TTNS_FILL_OPEN_ISSUE_UNVERIFIED@@ <!-- fill: claim and the A#/probe that can settle it -->

## HANDOFF AUDIT — standard-path checklist (6 MUST)

- [ ] **MUST1 IDs:** every C# and active G# is explicit and uniquely numbered; none
      was silently dropped.
- [ ] **MUST2 STATUS/NEXT:** STATUS states present reality and NEXT TASK names
      exactly one action consistent with it.
- [ ] **MUST3 required A#:** every A# named in NEXT TASK exists in the index with a
      real locator and a cheapest safe verification.
- [ ] **MUST4 unverified vs fact:** every unconfirmed claim carries `[unverified]`;
      nothing uncertain reads as settled fact.
- [ ] **MUST5 no placeholders:** no `@@TTNS_FILL_*@@` token remains anywhere in the
      file.
- [ ] **MUST6 finalize + read-back:** `finalize` succeeded after the last edit and
      its stdout copy box is the exact saved relay, pasted last with nothing after
      it.

Cross-machine transport, the manual fallback, and close/supersede use the full audit
in `references/playbook.md` §3.

After completion, close the state so an old active relay cannot restart finished work:

`python scripts/handoff.py close --state <state> --status complete`
