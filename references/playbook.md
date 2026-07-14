# Playbook: persist, audit, transport, resume

Use this detail when producing or resuming a real handoff. The helper enforces form;
the agent remains responsible for meaning.

## 1. Persist while work is live

WHEN a meaningful step changes reality → DO update STATUS, NEXT TASK, affected A#
rows, and D# records before continuing → DONE iff the state alone describes the new
present and one next action.

Update the marked body blocks first. Update START HERE and Last updated last, as the
commit point. This keeps an interrupted write behind reality rather than ahead of it.

Classify new information once:

- C#: a task-wide rule whose loss would create a wrong result.
- G#: a currently active permission or action boundary.
- A#: a resolvable ground-truth artifact with its cheapest safe verification.
- D#: a choice plus reason, rejected alternative, holding conditions, and source.
- OPEN ISSUES: work beyond the one NEXT TASK or a claim still unverified.

WHEN a user approves a plan, corrects the work, or chooses among alternatives → DO
record a D# entry from the visible conversation → DONE iff the next session can tell
why the choice was asked, what won, and what must not be resurrected. Mark missing
history `[not visible in current context]`; do not reconstruct provenance as fact.

WHEN a step fails or an approach is abandoned → DO route it by consequence: record a
D# if the failure changed a decision (failure condition, what was observed, and the
retry condition, briefly), otherwise log it in OPEN ISSUES as unresolved and
retryable → DONE iff no failure is dropped as a bare "X failed" without one of those
two homes.

## 2. Choose a transport target

### Same machine

WHEN the next session can read the same filesystem → DO set Target to
`same-machine`, set State locator to the state's exact absolute path, and give each
required A# an absolute path or resolvable URI → DONE iff the helper accepts the state
and each required locator names the intended artifact.

### Cross machine

WHEN any consumer may lack the producing filesystem → DO set Target to
`cross-machine` and use one of these state locator forms → DONE iff the consumer
can materialize the state without the old absolute path:

- `repo:https://host/owner/repo.git@<40-hex-commit>#relative/state.md`
- `sync:<named-root>#relative/state.md`
- `archive:<bundle-path-or-URL>#member/state.md`

For a required A#, use a full portable locator or
`state-relative:relative/artifact` when the state anchor also carries it.

WHEN required work is dirty or untracked → DO transport the actual bytes through a
patch plus required untracked files, named sync root, or archive → DONE iff hashes or
another cheap probe show the consumer received every required WIP file. A repo commit
alone is not DONE unless every required byte exists in that commit.

WHEN a required locator is not content-addressed (for example a mutable sync path or
archive URL) → DO put an expected hash, version, ETag, row count, or equivalent
content identity in Cheapest safe verification → DONE iff the consumer compares the
observed identity before relying on that A#.

The helper checks locator grammar and required A# membership. It intentionally does
not inspect Git status, open an artifact, contact a remote, or construct a bundle.

## 3. File-only pre-handoff audit

Standard same-machine produce is covered by the template-embedded HANDOFF AUDIT
(6 MUST) in `assets/state-file-template.md`. Use this fuller section for
cross-machine transport, the manual fallback, close/supersede, or a deeper review.

Ignore the chat scrollback during this audit. Use only the state and artifacts.

WHEN a boundary is imminent → DO check every item below and repair the state before
finalize → DONE iff every predicate is true:

1. Goal, completion test, scope, and fixed values are recoverable.
2. Each C# is complete and verbatim; each active G# still reflects current authority.
3. STATUS is present reality, not history.
4. NEXT TASK contains one action and exactly one Required artifact IDs line.
5. Every required A# exists in the table and has a safe verification.
6. A cross-machine consumer can resolve the state and every required A#, including
   dirty/untracked WIP.
7. Load-bearing claims point to artifacts; copied constants name their source A#.
8. D# entries preserve reasons and rejected conditions; uncertainties remain marked.
9. No secret or raw credential is present; referenced commands have been inspected.
10. Exactly one live state exists for this task.
11. No shipped bracketed sentinel or reserved relay-template token remains.

Then run:

`python <skill-root>/scripts/handoff.py finalize --state <state.md> --relay <relay.md>`

WHEN finalize succeeds → DO use its stdout unchanged as the last content in the
handoff response → DONE iff the fence interior is byte-identical to the saved relay
and nothing follows its closing fence.

## 4. What the helper proves

The state fingerprint is:

1. Decode strict UTF-8 after removing one leading UTF-8 BOM if present.
2. Convert CRLF and bare CR to LF.
3. Add one final LF only when absent.
4. Apply no trim, Unicode normalization, comment removal, or semantic rewrite.
5. SHA-256 the resulting UTF-8 bytes and prefix `sha256-lf:`.

The whole state is hashed. Any change to status, decision, locator, open issue, or
prose therefore makes the old relay stale and requires finalize again.

`verify --relay` re-renders the complete expected relay and compares it with the
saved relay after only BOM/newline normalization. It catches a state edit, template
change, digest-line edit, or relay-body edit. `verify --fingerprint` is the
portable check when the pasted relay is present but its producing-machine relay file
is not.

Atomic save uses a temporary file in the relay directory, flush, fsync, state
recheck, close, and replace. The helper reads the saved bytes back before emitting.
Rendered relay bytes are UTF-8/LF and always end in LF; copy-box emission rejects a
relay without that terminator instead of inserting a byte that was not saved.
It emits no copy box on invalid, stale, terminal, concurrent, or I/O failure.

The helper does not prove semantic sufficiency. A mechanically valid state can still
omit a crucial reason or point to the wrong artifact; the file-only audit remains
mandatory.

## 5. Resume without duplicating work

WHEN a relay arrives in a fresh session → DO resolve the state, read it, and verify
the relay fingerprint before mutation → DONE iff the current live state matches and
the next action comes from that state rather than memory or /compact.

Apply status before NEXT TASK:

- `active`: continue the one action.
- `waiting_user`: report the waiting condition and make no task mutation.
- `complete`, `superseded`, `abandoned`: treat the relay as stale and
  do not execute the old action.

Open only required A# entries first. Resolve a cross-machine anchor before attempting
the producing-machine path. Run the cheapest safe verification for a load-bearing A#
instead of automatically rerunning an expensive or mutating pipeline.

WHEN the state carries `TTNS:LOW_CONTEXT_AUDIT=required` → DO complete the full
file-only audit in §3 before acting, then change that line to
`TTNS:LOW_CONTEXT_AUDIT=completed` → DONE iff the marker reads `completed` before the
one stated action runs.

Before the first substantive work, recite one block — Handoff ID, verify result (or
`not_run: <reason>`), the C#/G# ID list, STATUS in one line, the single NEXT TASK,
and Last updated — as a diagnostic recitation, not proof of compliance. Read-only
investigation and emergency repair may proceed before it.

WHEN the action advances → DO persist the same state file before another action →
DONE iff STATUS, NEXT TASK, A#, D#, START HERE, and Last updated again agree.

## 6. Close or replace a state

WHEN the task is finished or intentionally abandoned → DO run `close` with
`complete` or `abandoned` → DONE iff status is terminal and an old relay fails
verification.

WHEN a new state replaces this one → DO close with `superseded` and a resolvable
`--superseded-by` locator → DONE iff the old state points to the successor and no
old NEXT TASK can emit.

Close changes lifecycle metadata only. It intentionally leaves the old relay file
untouched so its staleness remains observable.

## 7. Manual-unverified fallback

WHEN Python cannot run → DO fill the state and relay templates manually, label the
relay `manual-unverified`, save it, read it back, and compare each C# and active G#
character for character → DONE iff the saved text is the final fenced block and the
handoff explicitly says fingerprint, atomicity, and full-relay verification did not
run.

Do not invent a digest or claim helper verification.

## 8. Compact a growing state

WHEN current state takes longer to find than its history → DO keep START HERE, C#,
active G#, STATUS, NEXT TASK, required A#, invariants, and live issues near the top;
move resolved history to a referenced archive → DONE iff a cold reader reaches the
current action without loading the archive.

Compress prose, never exact C#/G# text, fixed values, decision reasons, or artifact
locators. Re-run the file-only audit and finalize after compaction.
