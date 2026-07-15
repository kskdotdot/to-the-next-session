<!--
Emergency low-context state template. Use only on the emergency path in SKILL.md,
when too little context remains for the standard template. Copy to the task root as
NN_TO_THE_NEXT_SESSION.md. Every shipped token here is required — fill them all,
never write unverified guesses into them — then finalize. Add nothing else on this
path; the audit marker below is already in place.

Status: active, or waiting_user while a named user input is awaited.
Target: same-machine | cross-machine. For same-machine, State locator must equal
this file's absolute path; cross-machine locator forms are documented in
state-file-template.md.
-->

# TO THE NEXT SESSION — @@TTNS_FILL_TASK_NAME@@ <!-- fill: short task name -->

_TTNS schema: 2_
_Handoff ID: @@TTNS_FILL_HANDOFF_ID@@_
<!-- fill Handoff ID: stable-task-slug -->
_Status: @@TTNS_FILL_LIFECYCLE_STATUS@@_
<!-- fill Status: active or waiting_user -->
_Target: @@TTNS_FILL_TARGET@@_
_State locator: @@TTNS_FILL_STATE_LOCATOR@@_
_Last updated: @@TTNS_FILL_LAST_UPDATED@@_
<!-- fill Last updated: YYYY-MM-DDTHH:MM:SS+TZ -->
_Superseded by: none_

## START HERE

<!-- fill ORIENTATION: exactly these four lines, this order. Waiting on is none
     while active; when Status is waiting_user, name the exact awaited input. -->
<!-- TTNS:BEGIN:ORIENTATION -->
- **Goal:** @@TTNS_FILL_GOAL@@
- **Done when:** @@TTNS_FILL_DONE_WHEN@@
- **Current phase:** @@TTNS_FILL_CURRENT_PHASE@@
- **Waiting on:** @@TTNS_FILL_WAITING_ON@@
<!-- TTNS:END:ORIENTATION -->

## INVIOLABLE CONSTRAINTS

<!-- fill: one line per load-bearing rule, "- **C1:** <verbatim rule>", C1..Cn -->
<!-- TTNS:BEGIN:INVIOLABLE_CONSTRAINTS -->
@@TTNS_FILL_CONSTRAINTS_BLOCK@@
<!-- TTNS:END:INVIOLABLE_CONSTRAINTS -->

## ACTIVE ACTION GUARDS

<!-- fill: "- None." when no guard is active, else one line per guard, G1..Gn -->
<!-- TTNS:BEGIN:ACTIVE_ACTION_GUARDS -->
@@TTNS_FILL_GUARDS_BLOCK@@
<!-- TTNS:END:ACTIVE_ACTION_GUARDS -->

## STATUS

<!-- fill: present reality in 1-3 sentences -->
<!-- TTNS:BEGIN:STATUS -->
@@TTNS_FILL_STATUS@@
<!-- TTNS:END:STATUS -->

## NEXT TASK

<!-- fill: one concrete action and its stopping condition; IDs like "A1" or none -->
<!-- TTNS:BEGIN:NEXT_TASK -->
@@TTNS_FILL_NEXT_TASK@@
Required artifact IDs: @@TTNS_FILL_NEXT_TASK_ARTIFACT_IDS@@
<!-- TTNS:END:NEXT_TASK -->

## ARTIFACT INDEX

<!-- fill: one table row per artifact NEXT TASK requires; zero rows only when the
     required-IDs line above says none -->
| ID | Locator on this machine | What it is | Cheapest safe verification | Portable locator |
|---|---|---|---|---|
@@TTNS_FILL_ARTIFACT_ROWS@@

## DECISIONS

<!-- Add a "### D1" entry here only if losing it would change the outcome. -->

## OPEN ISSUES

TTNS:LOW_CONTEXT_AUDIT=required

The resuming session must complete the full file-only audit in
references/playbook.md before acting, then change the line above to
TTNS:LOW_CONTEXT_AUDIT=completed.
