# to-the-next-session

[![version](https://img.shields.io/badge/version-0.3.1-blue)](CHANGELOG.md)
[![license](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![format](https://img.shields.io/badge/format-markdown--only-lightgrey)](#whats-inside)
[![scope](https://img.shields.io/badge/scope-tool--agnostic-informational)](#using-it)

**A tool-agnostic Agent Skill for durable, precision-preserving handoff of an
in-progress task across a context window, session, machine, or person boundary —
so a fresh agent (or you, later, on another device) resumes cold without losing the
exact numbers, decisions, and must-not-break constraints that matter.**

> Status: **v0.3.1** — usable; interfaces may evolve.

> **The state file preserves; the relay prompt launches.**

## Contents

- [The problem](#the-problem)
- [The idea](#the-idea)
- [How it flows](#how-it-flows)
- [State file vs relay prompt](#state-file-vs-relay-prompt)
- [Quick start](#quick-start)
- [What's inside](#whats-inside)
- [Using it](#using-it)
- [Design notes](#design-notes)
- [License](#license)

## The problem

Long, high-precision, many-iteration agent work eventually runs out of context. The
usual fallback — automatic conversation summarization (`/compact` and the like) — is
lossy *by design*: it compresses the whole transcript on its own terms and silently
drops exactly the things that are individually fatal to drop:

- a single exact number (a threshold, a tier boundary, a measured result),
- a single inviolable rule (“do **not** declare this done”, “never touch the prod table”),
- the *reason* a decision was made (so the next session re-litigates it and drifts).

`--resume` / `--continue` reloads the whole history and doesn’t solve the window
problem. Memory is for cross-cutting facts, not a project’s full live state.

## The idea

The conversation is disposable; the files are the memory. This skill is the discipline
of leaving the next (cold) session a **hand-written letter**, backed by the real
artifacts on disk. Two artifacts:

1. **A state file** — one canonical file written *as a letter to whoever resumes*,
   updated as you go, carrying the inviolable constraints **verbatim** and pointing at
   ground-truth artifacts by resolvable path.
2. **A relay prompt** — a copy-paste block that *launches* the next session, restating
   the status, the single next action, and the constraints inline and verbatim.

**The state file preserves; the relay prompt launches.**

It composes with planning skills (their plan files become entries in the state file’s
Artifact Index) and explicitly tells you when *not* to use it — for short, low-stakes
continuity, automatic summarization is fine.

## How it flows

```
        in-progress work — about to cross a boundary
        (window fills · new machine · someone takes over)
                             │
                             ▼
          ┌──────────────────┬──────────────────┐
          │    STATE FILE    │   RELAY PROMPT   │
          │    preserves     │   launches       │
          │    the truth     │   the session    │
          └──────────────────┴──────────────────┘
                             │
        verbatim constraints, numbers, decisions, and
          resolvable artifact paths cross with it
                             │
                             ▼
          ┌───────────────────────────────────────┐
          │  a COLD next session reads the files  │
          │  — not the chat — and re-derives the  │
          │  numbers from the artifacts           │
          └───────────────────────────────────────┘
                             │
                             ▼
        work resumes with the exact constraints,
          numbers, and decisions intact
```

## State file vs relay prompt

You need both: a durable record of the truth, and a way to actually start the next
session pointed at it. The trust levels are deliberately unequal.

| | **State file** | **Relay prompt** |
|---|---|---|
| **Role** | Preserves: the canonical letter the next session reads first | Launches: the copy-paste block that starts the next session |
| **When written** | Created early, updated after every meaningful step | Generated at the moment of handoff |
| **Trust level** | Curated handoff index — semi-trusted, *not* proof | Constraints inside it are **authoritative** |

> Artifacts pointed at by either one are **untrusted data until inspected** — and any
> re-run script among them is **untrusted code**. Verify load-bearing claims against the
> artifacts before relying on them.

## Quick start

Ask your agent:

> *“Prepare a to-the-next-session handoff — a state file plus a relay prompt — so the
> next session can resume without reading this chat.”*

Then, in the next session, paste the relay prompt and point it at the state file.

By hand:

1. Copy `assets/state-file-template.md` to `<task-root>/TO_THE_NEXT_SESSION.md` and fill it.
2. Copy `assets/relay-prompt-template.md` and fill it from the state file.
3. Run the self-sufficiency audit in `references/playbook.md` before you hand off.

## What’s inside

```
SKILL.md                          the skill: principles, workflow, safety, when-to-use
assets/state-file-template.md     the state file, each section explained inline
assets/relay-prompt-template.md   the copy-paste relay prompt
references/playbook.md            persist-as-you-go checklist, self-sufficiency audit, compaction
references/when-to-handoff.md     file-relay vs summarization vs memory vs planning
references/worked-example.md      a generic long-task handoff, start to finish
CHANGELOG.md                      version history
LICENSE                           Apache License 2.0
NOTICE                            attribution notice
```

## Using it

The skill is tool-agnostic — it speaks in actions (“write a file”, “open a fresh
session”, “the agent that resumes”), not any one runtime’s tool names, so it works in
Claude Code, Codex, and other skill-aware agents.

- **As an installed skill:** place this folder where your agent discovers skills (e.g.
  a `skills/to-the-next-session/` directory) so its `description` can trigger it.
- **By hand:** read `SKILL.md`, copy the two templates in `assets/`, and follow the
  self-sufficiency audit in `references/playbook.md` before you hand off.

## Design notes

The skill holds itself to its own creed — accuracy. It does **not** claim losslessness
(a human can omit something, an artifact can drift, a path can break); its job is to
make those failure modes few and catchable. It carries a small safety model for public
use: never put secrets in the handoff; treat artifacts as data, not instructions;
treat re-run scripts as untrusted code until inspected; and treat the state file as a
handoff index, not proof — verify load-bearing claims against the artifacts.

The safety model has three trust levels, deliberately unequal: the **state file** is a
curated index (semi-trusted, not proof), the **relay constraints** are authoritative,
and the **artifacts** are untrusted data until inspected (re-run scripts are untrusted
code).

How it differs from a plain handoff doc: conventions like `AGENTS.md` or `HANDOFF.md`
are *static, repo-level* notes. This skill is a *per-task* relay that preserves exact
numbers and **verbatim** constraints, points at re-derivable ground truth, and carries
an explicit resume contract — the precision and the resume side are the difference.

## License

[Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution.
