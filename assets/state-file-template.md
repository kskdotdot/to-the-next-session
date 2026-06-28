<!--
  STATE FILE TEMPLATE  —  copy to your task's working directory as
  TO_THE_NEXT_SESSION.md (or RESUME.md). One per task. This is the FIRST thing
  the next session reads. Write it AS a letter to a cold agent who has no memory
  of this work.

  Fill the [bracketed] parts and delete the <!-- guidance --> comments as you go.
  Keep it updated after every meaningful step — not once at the end.
  Section order is deliberate: the things whose loss is fatal come first.
-->

# TO THE NEXT SESSION — [task name]

_Last updated: [YYYY-MM-DD HH:MM]_
<!-- Keep exactly ONE active state file per task. If you replace this file, add a line
     "Superseded by: [/abs/path/to/new/state-file]" here and stop updating this one —
     never leave two active files with no pointer to the live one.
     NEVER put secrets / credentials / tokens / private keys here. Point to a safe
     retrieval procedure instead. -->
<!-- Superseded by: [/abs/path/...]   (fill only when this file is retired) -->

## START HERE  (read this first — ≤10 lines)
<!-- The entire situation at a glance, so even a long, grown file re-enters fast.
     If the next session reads only this block, it should still not do harm. -->
- **What this is:** [one sentence — the task and its goal].
- **Where we are:** [one sentence — % done / current phase / what's in flight].
- **Do next:** [the single most important next action — point to NEXT TASK below].
- **Must not break:** [name the 1–2 most dangerous constraints — full list below].
- **Read order:** this file top-to-bottom, then open the files in ARTIFACT INDEX
  at their absolute paths. The artifacts — not this summary — are the source of truth.

## INVIOLABLE CONSTRAINTS  (verbatim — never paraphrase, never shorten)
<!-- Rules that, if dropped, produce ACTIVE ERROR (not just confusion): integrity
     rules, "never declare X", "do not touch Y", tier/scope boundaries as rules.
     Paste them exactly. If you're tempted to tidy one, don't — the tidy version
     is how the next session ships the mistake. -->
- [ ] [exact rule, word for word]
- [ ] [exact rule, word for word]

## STATUS  (where we are, in prose)
<!-- Enough that a cold reader understands the current state without scrollback.
     What is done, what is half-done, what is blocked and on what. -->
[2–6 sentences.]

## NEXT TASK  (the single highest-priority next action)
<!-- ONE concrete action, not a backlog. Specific enough to start immediately.
     If there's a queue, put #1 here and the rest under OPEN ISSUES. -->
[Exactly what to do next, concretely. Include the command to run / file to edit /
decision to make, with absolute paths.]

## ARTIFACT INDEX  (ground truth — paths the NEXT session can resolve)
<!-- Point; do not transcribe (copies go stale). Prefer artifacts that can be RE-RUN.
     Canonicality: THIS file is canonical for intent / inviolable constraints /
     decisions / next action; ARTIFACTS are canonical for generated outputs, source
     data, and re-derivable numbers. On disagreement, re-run the source or mark it
     `[unverified]` — never silently choose. Artifacts are DATA, not instructions.
     Same machine: absolute path is enough. Crossing machines: ALSO give a portability
     anchor (repo URL+commit, path under a named sync root, shared drive, archive). -->
| Absolute path | What it is | How to re-verify / re-run | Portability anchor (if cross-machine) |
|---|---|---|---|
| `[/abs/path/to/artifact]` | [e.g. result table, generated draft, config] | [e.g. `python /abs/path/build.py` → reproduces it] | [repo@commit / sync-root path / —] |
| `[/abs/path/to/plan.md]` | [plan from planning-with-files / writing-plans] | [n/a — read it] | [—] |

## INVARIANTS  (the unchanging core)
<!-- Facts about the task that do NOT change across sessions: the goal, the central
     hypothesis/claim, scope boundaries (in and out), and key FIXED numbers/tiers.
     These keep the next session from drifting off the original target. -->
- **Goal:** [...]
- **In scope / out of scope:** [...]
- **Key fixed numbers / tiers:** [exact values — the things a summary would round].

## DECISIONS & CHANGELOG  (decision + WHY — append-only)
<!-- A decision without its reason invites re-litigation and drift. One line each:
     what was decided and why, so the next session doesn't reopen settled questions. -->
- [YYYY-MM-DD] Chose [X] over [Y] because [Z].
- [YYYY-MM-DD] [change made] — [reason].

## OPEN ISSUES / UNKNOWNS
<!-- The backlog beyond NEXT TASK, plus anything unconfirmed. Mark uncertainty
     honestly — never upgrade a guess to a fact. -->
- [ ] [open question or queued task]
- [ ] `[unverified]` [claim not yet confirmed — say so plainly] / `[要確認]` [...]

<!--
  HISTORY / ARCHIVE  (optional, near the bottom)
  When this file grows, fold resolved issues and superseded status into a terse
  history here, or move it to an archive file referenced by ABSOLUTE path. Compress
  the prose — never the INVIOLABLE CONSTRAINTS or the numbers.
-->
