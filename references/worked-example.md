# Worked example: a cold cross-machine resume

This synthetic example shows the schema; it is not a real project.

## Situation

A records report is half complete. The exact tier cutoffs and the rule against
unsourced confirmation are load-bearing. The report draft contains dirty WIP and the
next session runs on another machine.

## State

```markdown
# TO THE NEXT SESSION — records report

_TTNS schema: 2_
_Handoff ID: records-report_
_Status: active_
_Target: cross-machine_
_State locator: repo:https://github.com/example/records.git@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa#handoff/01_TO_THE_NEXT_SESSION.md_
_Last updated: 2026-07-11T18:00:00+09:00_
_Superseded by: none_

## START HERE
<!-- TTNS:BEGIN:ORIENTATION -->
- **Goal:** deliver a reviewable records report
- **Done when:** every tier section is drafted and A1 reproduces the counts
- **Current phase:** tiering verified; report draft is half complete
- **Waiting on:** none
<!-- TTNS:END:ORIENTATION -->
- Next: write the Tier B section.
- Highest-risk rules: C1, C2, G1.
- Read order: this state, then A1 and A3 only.

## INVIOLABLE CONSTRAINTS
<!-- TTNS:BEGIN:INVIOLABLE_CONSTRAINTS -->
- **C1:** A record may be labeled "confirmed" ONLY if it has a matching source row. No exceptions.
- **C2:** Do NOT declare the report final before client review.
<!-- TTNS:END:INVIOLABLE_CONSTRAINTS -->

## ACTIVE ACTION GUARDS
<!-- TTNS:BEGIN:ACTIVE_ACTION_GUARDS -->
- **G1:** Do not publish the report; this handoff authorizes draft editing only.
<!-- TTNS:END:ACTIVE_ACTION_GUARDS -->

## STATUS
<!-- TTNS:BEGIN:STATUS -->
Cleaning and tiering are complete. A1 reproduces the counts. A3 contains the current
dirty draft; Tier B and the summary remain.
<!-- TTNS:END:STATUS -->

## NEXT TASK
<!-- TTNS:BEGIN:NEXT_TASK -->
Use A1 to write only the Tier B section in A3, then stop before publishing.
Required artifact IDs: A1, A3
<!-- TTNS:END:NEXT_TASK -->

## ARTIFACT INDEX
| ID | Locator on this machine | What it is | Cheapest safe verification | Portable locator |
|---|---|---|---|---|
| A1 | `/work/records/tiers.csv` | verified tier counts | checksum against manifest | state-relative:data/tiers.csv |
| A2 | `/work/records/dropped.csv` | deferred audit rows | row count only if disputed | state-relative:data/dropped.csv |
| A3 | `/work/records/report.md` | dirty report draft | sha256 against bundle manifest | archive:https://example.invalid/records-wip.zip#report.md |

## INVARIANTS
- In scope / out of scope: report prose in; publication out.
- Fixed values: A ≥ 80, B = 50–79, C < 50; source A1.

## DECISIONS
### D1 — unmatched records
- Chosen: omit them from confirmed counts and retain an audit file.
- Because: C1 forbids manufacturing a source match.
- Rejected: imputation while the source extract is unchanged.
- Source: visible user decision.

## OPEN ISSUES
- [ ] Client review remains after this handoff.
```

The commit locator carries the state and clean A1. A3 uses an archive because its
dirty bytes are not present in that commit. A2 is deferred and therefore absent from
the eager relay artifact table.

## Produce

```text
python <skill-root>/scripts/handoff.py finalize \
  --state /work/records/handoff/01_TO_THE_NEXT_SESSION.md \
  --relay /work/records/handoff/02_RELAY_PROMPT.md
```

The helper saves the relay, verifies the whole-state fingerprint, reads the saved
bytes back, and writes a dynamically fenced copy box to stdout. That box is the final
content sent to the next session.

## Resume

The fresh session resolves the repository and WIP archive, reads the state, and
checks the fingerprint before editing, reciting the ack block (Handoff ID, verify
result, C#/G# IDs, the Goal and Waiting on lines, STATUS, NEXT TASK, Last updated)
as a diagnostic, not proof of compliance. It opens A1 and A3 because NEXT TASK requires them; it does not preload
A2. G1 prevents publication. After writing the Tier B section, it updates the same
state and finalizes a new relay.

If the producer closes the state as complete before the old relay is pasted, the
fingerprint/status check fails and the old Tier B action is not executed again.

## Emergency low-context variant

If compaction had been imminent mid-draft, the producer would instead copy
`assets/state-file-template-low-context.md` and fill only its required tokens: the
metadata, the four ORIENTATION lines, C1/C2 as the constraints block, G1 as the
guards block, STATUS, the single NEXT TASK with its required IDs, and the A1/A3
rows. The template already carries `TTNS:LOW_CONTEXT_AUDIT=required`, so the
resuming session completes the full file-only audit in `references/playbook.md` §3
before acting and then flips the marker to `completed`.
