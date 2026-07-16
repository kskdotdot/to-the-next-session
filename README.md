# to-the-next-session

[![version](https://img.shields.io/badge/version-0.8.1-blue)](CHANGELOG.md)
[![license](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Python](https://img.shields.io/badge/helper-Python%203.10%2B-3776AB)](scripts/handoff.py)

> Status: **v0.8.1** — usable; interfaces may evolve.

Move precision-critical work to a fresh AI session without trusting a lossy summary.

`/compact` is useful when details are cheap to reconstruct. It is a poor source of
truth when one omitted threshold, rejected alternative, permission guard, or exact
number can change the result. This skill moves that state into durable files before
the conversation disappears.

## The two artifacts

- **STATE FILE:** the sole source of truth for current task intent, constraints,
  decisions, status, next action, and artifact locators.
- **RELAY PROMPT:** a copy-paste launch message deterministically rendered from the
  state, saved, read back, freshness-checked, and emitted as a final fenced box.

The state preserves. The relay launches. A real handoff needs both.

## What v0.5 adds

- deterministic `finalize / verify / emit / close` helper;
- whole-state `sha256-lf` freshness detection;
- atomic relay save and exact read-back copy box;
- C# task constraints, G# active authority guards, A# lazy artifact IDs, D# decisions;
- same-machine and cross-machine locator contracts;
- terminal-state protection against restarting completed work;
- offline regression tests and OpenAI skill metadata.

The helper does not summarize a transcript or write the state for you. The agent
curates meaning; the script prevents mechanical drift.

## What v0.6 adds

- State-template placeholders are now reserved `@@TTNS_FILL_<NAME>@@` tokens instead
  of bracketed sentinels; `finalize` rejects a leftover fill token and a stray
  reserved `@@TTNS_*@@` token as two distinct errors.
- The relay prompt is schema 2: it adds a `TTNS:SKILL=` line and a short ack block
  (Handoff ID, verify result, C#/G# IDs, STATUS, NEXT TASK, Last updated) recited
  before the first substantive work, as a diagnostic, not proof of compliance.
  `verify`/`emit` stay backward-compatible with schema 1 relays saved before this
  release.
- An emergency low-context path covers the case where too little context remains
  for the full produce flow; it marks the state `TTNS:LOW_CONTEXT_AUDIT=required`
  so resume completes the full audit before acting.
- The standard same-machine produce flow is completable from `SKILL.md` and the
  state template alone; `references/playbook.md` is now needed only for
  cross-machine transport, the manual fallback, or close/supersede.

## What v0.7 adds

- State schema 2: the four-line ORIENTATION block (Goal, Done when, Current phase,
  Waiting on) is machine-validated and copied verbatim into the relay, so a cold
  session no longer depends on prose discipline for basic orientation; a
  `waiting_user` state must name the exact awaited input.
- Relay schema 3 carries the orientation block; the v0.6.0 relay template is frozen
  as `relay-prompt-template-v2.md`, and `verify`/`emit` stay backward-compatible
  with schema 1 and schema 2 relays (schema 1 states keep rendering their
  established schema 2 relay byte-for-byte).
- A dedicated emergency template, `state-file-template-low-context.md`, ships only
  required tokens (with whole-block tokens for C#/G#/artifact rows), so the
  low-context path finalizes exactly as documented.
- The lifecycle Status is a fill token, placeholder detection no longer rejects
  legitimate locators such as `...\Todo-project\...`, and frozen-asset tests hash
  canonical UTF-8/LF bytes so a CRLF working tree (e.g. `core.autocrlf=true`)
  cannot fail them.

## What v0.8 adds

- Relay schema 4 — a **lean relay**. The copy-paste launch message no longer reprints
  the parts that already live in the state file (the full C# constraints, the artifact
  table, the STATUS paragraph, the producing-machine absolute paths). It carries only a
  freshness-verified pointer to the state, the four-line orientation, the still-binding
  G# authority guards, the single next-task preview, and the required artifact IDs. Its
  length no longer grows with the constraint set, artifact count, or STATUS length.
- A **bootstrap gate** leads the relay: until the state is resolved, read, and verified,
  the only permitted actions are resolve / read / verify / report — no artifact reads and
  no task, edit, or external action, even though the next-task preview is visible. If the
  state cannot be obtained, the session stops rather than continuing from the pointer.
- The verbose v0.7.0 relay is frozen as `assets/relay-prompt-template-v3.md`; a schema-2
  state now renders schema 4, and `verify`/`emit` still accept a schema-3 relay saved
  before this change (state schema 2 accepts relay schema 3 or 4). The state file, its
  schema, and the fingerprint contract are unchanged.

## Quick start: produce

Copy the template into the active task:

```text
cp <skill-root>/assets/state-file-template.md <task-root>/01_TO_THE_NEXT_SESSION.md
```

Fill every `@@TTNS_FILL_*@@` token and marked block. Keep it current after
meaningful steps, then finalize:

```text
python <skill-root>/scripts/handoff.py finalize \
  --state <task-root>/01_TO_THE_NEXT_SESSION.md \
  --relay <task-root>/02_RELAY_PROMPT.md
```

On success, stdout contains only a dynamically fenced copy box around the exact
saved relay. Use that as the final content of the handoff response; put nothing after
the closing fence.

## Quick start: resume

Resolve and read the state before changing the task. Compare it with the fingerprint
carried by the pasted relay:

```text
python <skill-root>/scripts/handoff.py verify \
  --state <resolved-state.md> \
  --fingerprint sha256-lf:<64-hex>
```

When the saved relay file is also present, use the stronger full comparison:

```text
python <skill-root>/scripts/handoff.py verify \
  --state <resolved-state.md> \
  --relay <saved-relay.md>
```

If verification fails or status is terminal, do not execute the relay's old NEXT
TASK. Read the latest state or report the conflict.

## State model

| ID | Meaning | Relay behavior |
|---|---|---|
| C# | task-wide inviolable constraint | verbatim in the state; relay carries a verified pointer, read from the state |
| G# | currently active permission/action guard | copied verbatim into the relay while active |
| A# | artifact with locator and cheapest safe verification | only required IDs are eager; the table stays in the state |
| D# | chosen decision, reason, rejected option, source | state reference prevents re-litigation |

Statuses:

- live: `active`, `waiting_user`;
- terminal: `complete`, `superseded`, `abandoned`.

Close a completed state:

```text
python <skill-root>/scripts/handoff.py close \
  --state <state.md> \
  --status complete
```

Old relays then fail freshness/status verification instead of restarting the task.

## Moving between machines

For `same-machine`, the State locator is the state's exact absolute path.

For `cross-machine`, use one resolvable anchor plus member path:

```text
repo:https://host/owner/repo.git@<40-hex-commit>#relative/state.md
sync:<named-root>#relative/state.md
archive:<bundle-path-or-URL>#member/state.md
```

Required A# rows need a portable locator too. A commit carries only tracked bytes in
that commit; dirty or untracked WIP needs a patch plus its untracked files, a named
sync root, or an archive. The helper validates form, not the actual Git dirtiness or
bundle contents.

## Fingerprint contract

The helper removes one UTF-8 BOM, decodes strict UTF-8, normalizes CRLF/bare CR to LF,
ensures a final LF, and hashes the entire state with SHA-256. It does not trim,
normalize Unicode, remove comments, or decide which edits are harmless. Any state
change requires a new relay.

`verify --relay` re-renders and compares the whole relay, so retaining the digest
line while editing the relay body still fails. Comparison is schema-aware: a schema
1 relay (saved before v0.6.0) is compared against the frozen v1 template, a schema 2
relay against the frozen v2 template, a schema 3 relay against the frozen v3 template,
and a schema 4 relay against the current lean template — and only the
state-schema/relay-schema pairs finalize can produce are accepted (state 1 → {1, 2},
state 2 → {3, 4}). `verify --fingerprint` does not read the relay file and is
schema-independent.

## Install as a skill

Clone or copy this repository into the skill directory used by your agent. The root
contains `SKILL.md`, and `agents/openai.yaml` supplies Codex/OpenAI UI metadata.
Claude Code, Codex, and other filesystem-capable agents can follow the same state and
helper contract.

Python 3.10+ enables deterministic checks. Without Python, follow
`references/playbook.md` §7 and label the relay `manual-unverified`; never
claim fingerprint or atomic verification ran.

## Repository layout

```text
SKILL.md                         core workflow and triggers
agents/openai.yaml               OpenAI/Codex discovery metadata
assets/state-file-template.md    schema 2 canonical state
assets/state-file-template-low-context.md  emergency low-context state (schema 2)
assets/relay-prompt-template.md  lean deterministic render template (schema 4)
assets/relay-prompt-template-v1.md  frozen schema-1 template (backward-compat verify only)
assets/relay-prompt-template-v2.md  frozen schema-2 template (backward-compat verify only)
assets/relay-prompt-template-v3.md  frozen schema-3 template (backward-compat verify only)
scripts/handoff.py               finalize / verify / emit / close
references/playbook.md           detailed audit and lifecycle
references/when-to-handoff.md    boundary against /compact, memory, planning
references/compact-defense.md    runtime defense guidance
references/worked-example.md     synthetic cross-machine example
tests/                           offline contract tests
```

## Verify this checkout

```text
python -m unittest tests.test_handoff tests.test_package
```

The tests use only temporary files in the checkout and make no network calls.

## Deliberate non-goals

No transcript summarizer, LLM call, daemon, database, clipboard automation, recursive
task search, artifact execution, secret scanner, or automatic semantic completion
judgment. These would add authority or failure modes without improving the core
transport guarantee.

License: [Apache License 2.0](LICENSE).
