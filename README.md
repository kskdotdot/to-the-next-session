# to-the-next-session

**A tool-agnostic Agent Skill for durable, precision-preserving handoff of an
in-progress task across a context window, session, machine, or person boundary —
so a fresh agent (or you, later, on another device) resumes cold without losing the
exact numbers, decisions, and must-not-break constraints that matter.**

> Status: **v0.2.0** — usable; interfaces may evolve.

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

## What’s inside

```
SKILL.md                          the skill: principles, workflow, safety, when-to-use
assets/state-file-template.md     the state file, each section explained inline
assets/relay-prompt-template.md   the copy-paste relay prompt
references/playbook.md            persist-as-you-go checklist, self-sufficiency audit, compaction
references/when-to-handoff.md     file-relay vs summarization vs memory vs planning
references/worked-example.md      a generic long-task handoff, start to finish
CHANGELOG.md                      version history
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

## License

[Apache License 2.0](LICENSE).
