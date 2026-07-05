# Worked example: a long task handed off cleanly

A generic illustration — no real project. The point is to show the *shape* of a good
handoff: exact numbers preserved, a must-not-break rule carried verbatim, artifacts
pointed at by absolute path and re-runnable, decisions with reasons, and an honest
`[unverified]` marker.

## The situation

A multi-day task: clean a messy records dataset, re-tier each record into A/B/C bands
by a score, and produce a summary report. By the time the context window is filling,
the cleaning script works, tiers are assigned, the report is half-drafted, and one
figure is still unconfirmed. The work must continue tomorrow on a different machine.

Two things would be fatal to lose: the **exact tier cutoffs** (a summary might round
them) and the rule that **no record may be labeled "confirmed" without a source
match** (dropping it would silently corrupt the output).

## The state file (key sections, filled)

```
# TO THE NEXT SESSION — records re-tiering + report

_Last updated: 2025-03-14 18:40_

## START HERE
- What this is: clean the records set, assign A/B/C tiers by score, write the report.
- Where we are: cleaning done, tiers assigned, report ~50% drafted.
- Do next: finish the report's "Tier B" section — see NEXT TASK.
- Must not break: C1 — never label a record "confirmed" without a source match (full list below).
- Read order: this file, then the files in ARTIFACT INDEX at their absolute paths.

## INVIOLABLE CONSTRAINTS
- **C1:** A record may be labeled "confirmed" ONLY if it has a matching source row. No exceptions.
- **C2:** Do NOT declare the report "final" — it is a draft until the client review pass.

## STATUS
Cleaning and tiering are complete and reproducible from the script below. The report
draft covers Tier A and the intro; Tier B and the summary table remain. One figure
(Tier C count) is in dispute — see OPEN ISSUES.

## NEXT TASK
Write the "Tier B" section of /home/work/records/report.md, using the counts produced
by re-running /home/work/records/tier.py (do not hand-type the numbers).

## ARTIFACT INDEX   (work continues on a different machine -> portability anchors given)
| Absolute path | What it is | How to re-verify / re-run | Portability anchor |
|---|---|---|---|
| /home/work/records/tier.py | cleaning + tiering script | `python /home/work/records/tier.py` regenerates tiers.csv | repo records-cleanup @ a1b2c3d |
| /home/work/records/tiers.csv | tiered output (ground truth) | produced by tier.py; do not edit by hand | regenerate from tier.py |
| /home/work/records/report.md | the draft report | read it | repo records-cleanup @ a1b2c3d |

## INVARIANTS
- Goal: deliver a draft tier report the client can review.
- In scope: cleaning, tiering, report. Out of scope: client-facing formatting.
- Key fixed numbers / tiers: A = score ≥ 80, B = 50–79, C = < 50. (Exact; do not round.)

## DECISIONS & CHANGELOG
- 2025-03-13 Chose score-band tiers over quartiles because the client specified fixed cutoffs.
- 2025-03-14 Dropped 12 rows with no source — kept as /home/work/records/dropped.csv for audit.

### D1. Handling of records with no source row
- consultation: "12 records have no matching source row — drop them, impute a source, or keep them unlabeled?"
- asked because: C1 forbids labeling them "confirmed", and the report needs a defensible denominator.
- options considered: drop with audit file / impute from nearest neighbor / keep unlabeled.
- chosen: "drop them, keep an audit file" (user's words).
- rationale / evidence: imputation would manufacture the source matches C1 exists to prevent; the client audits row counts.
- rejected — do not resurrect: imputing sources — it fabricates exactly what C1 forbids; holds unless the client supplies the missing source extract.
- downstream implication: report denominators exclude the 12 rows; cite dropped.csv when counts are questioned.
- source/confidence: visible transcript.

## OPEN ISSUES / UNKNOWNS
- [ ] `[unverified]` Tier C count shows 41 in tiers.csv but 39 in an earlier note — re-run tier.py to settle before citing it in the report.
```

Notice what the file does: the cutoffs are stated **exactly** ("A = score ≥ 80 … do
not round"), the constraint is **verbatim**, the numbers live in a **re-runnable
script** rather than being transcribed, the dropped-rows decision carries its **reason
and an audit artifact**, and the disputed count is honestly flagged `[unverified]`
with the way to settle it. The user-consulted decision (D1) carries its **full
record** — why the question was asked, what was rejected and under what conditions —
so a later session cannot innocently re-propose imputation as a fresh idea.

On Windows the same Artifact Index entry would read, e.g.
`C:\Users\you\records\tier.py | cleaning + tiering script |
python C:\Users\you\records\tier.py | repo records-cleanup @ a1b2c3d` — absolute path
plus the same portability anchor, so it resolves on either OS.

(If a second precision-critical task were active under the same directory, this file
would be named for its task — e.g. `TO_THE_NEXT_SESSION_records-retier.md` — because the
rule is one active file per *task*, not per directory.)

## The relay prompt (what gets pasted into the fresh session)

In the actual handoff message this block is printed **last**, read back verbatim from
the saved relay file — paths and caveats stated before it, nothing after it.

```
You are resuming an in-progress task. You start cold: the files are the source of
truth, not memory. Don't reconstruct from a summary — read the real state.

The state file: repo records-cleanup @ a1b2c3d -> TO_THE_NEXT_SESSION.md. On a new
machine, clone that repo at a1b2c3d first; on the original machine it resolved to
/home/work/records/TO_THE_NEXT_SESSION.md.

Read first, in order:
1. The state file above — top to bottom.
2. Then the files in its ARTIFACT INDEX — on a different machine, clone records-cleanup
   @ a1b2c3d to materialize the /home/work/records/... paths before opening them.

Where things stand: cleaning and tiering done and reproducible; report ~50% drafted;
one figure (Tier C count) disputed and marked [unverified].

Your single next action: write the "Tier B" section of /home/work/records/report.md
using counts from re-running /home/work/records/tier.py (don't hand-type numbers).

Inviolable constraints — obey exactly (same IDs as the state file):
- C1: A record may be labeled "confirmed" ONLY if it has a matching source row. No exceptions.
- C2: Do NOT declare the report "final" — it is a draft until the client review pass.

Before you act: confirm you can restate, from the files alone, the goal, both
constraints, and your next action. Anything marked [unverified] is not yet established
— settle it before relying on it.
```

## What the self-sufficiency audit caught

Running the audit before handoff surfaced the Tier C discrepancy (41 vs 39). Rather
than smooth it over, the author re-ran the script — confirming 41 — and could have
updated the file to a settled fact. The version above intentionally leaves it
`[unverified]` to show the honest interim state: the handoff names the conflict and
the way to resolve it, so the next session can't unknowingly cite the wrong number.
That is the whole game — the boundary is crossed with the precision, the rules, and
the open questions all intact.

## A second shape: non-file artifacts and no-filesystem runtimes

The same discipline survives two cases the first example doesn't show.

**A large or non-file artifact** — a multi-GB model checkpoint, a cloud bucket, a
database table — is pointed at, never transcribed, and re-running it to "re-derive" is
infeasible. The Artifact Index row gives a *locator* and a *cheap probe* in place of a
re-runnable script:

| Locator | What it is | How to re-verify (cheap probe) | Portability anchor |
|---|---|---|---|
| `s3://acme-models/run-2025-03-14/model.ckpt` | trained checkpoint (4.2 GB) | `aws s3 ls s3://acme-models/run-2025-03-14/`; sha256 == `9f3c…` | bucket `acme-models`, prefix `run-2025-03-14/` |
| `bigquery: proj.analytics.tiers` | tiered output table | `SELECT COUNT(*) FROM proj.analytics.tiers` → 41 | dataset `proj.analytics` |

The checksum and the row count are the *settle-on-resume* probe — not a full re-run,
but enough to catch drift on something you cannot cheaply rebuild.

**A runtime with no writable filesystem** — a pure chat/API surface, a browser-only
agent — has nowhere to put a state *file*. The discipline is unchanged; only the
substrate moves: the state file becomes one self-contained block pasted into the relay
(or a gist / shared-doc URL), and the Artifact Index points by URL + ID instead of by
path. Verbatim constraints (C1, C2, …), the portability anchors, and the
self-sufficiency audit all still apply — you are carrying the letter in the message body
instead of on disk.
