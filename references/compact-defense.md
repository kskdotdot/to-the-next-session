# Compact defense: not losing the race against auto-compaction

> **Illustrative examples — not a supported component of this skill.** This page
> documents runtime-level countermeasures that pair well with the skill. The snippets
> are examples to adapt to your own configuration, not installable artifacts shipped or
> maintained here; hook APIs belong to your runtime and can change. The skill itself is
> markdown-only and works fully without any of this.

## The race

This skill assumes you get to hand off *deliberately*. But runtimes with automatic
context compaction (e.g. Claude Code's auto-compact) fire on their own schedule —
typically somewhere around 75–85% context usage. When auto-compaction wins the race,
the exact failure this skill exists to prevent happens anyway: decisions are
mishandled, phases get confused, and rejected approaches come back as fresh ideas,
because the summary kept the outcome and dropped the *why*.

Defense in depth, cheapest layer first:

1. **The skill's own discipline.** Persist-as-you-go means the state file is already
   current whenever compaction hits — the letter is written before the fire. This is
   the primary defense and needs no automation.
2. **See it coming.** A context-usage warning (e.g. in a status line) at ~60% leaves
   room to hand off or compact manually before the automatic trigger fires.
3. **Pre-compaction hook.** A deterministic, last-moment side effect just before
   compaction (save a marker/metadata, optionally block an automatic compaction on
   interactive machines).
4. **Post-compaction recovery.** Immediately after compaction, re-point the summarized
   session at ground truth: "a state file exists — trust it over the summary."

## Example: usage-threshold warning

If your runtime exposes context usage (Claude Code passes
`context_window.used_percentage` to status-line commands on stdin), a two-line check
is enough:

```python
pct = data.get("context_window", {}).get("used_percentage", 0)
if pct >= 60:
    line += f"  CTX {pct:.0f}% — handoff soon"
```

## Example: pre-compaction hook (Claude Code `PreCompact`) — and the exit-code trap

```json
"hooks": {
  "PreCompact": [{
    "matcher": "manual|auto",
    "hooks": [{ "type": "command", "command": "python <abs-path>/precompact-hook.py" }]
  }]
}
```

**The trap:** in Claude Code, a `PreCompact` hook that exits with code 2 **blocks the
compaction**. And `python missing-script.py` exits with code 2. A registered hook whose
script has been moved or deleted therefore silently blocks *every* compaction. Design
the command so that no failure mode can produce exit 2 — guard for the script's
existence, catch every exception, and exit 0 on any error. If you want deliberate
blocking (force a manual handoff before an automatic compaction on an interactive
machine), make it an explicit opt-in and emit `{"decision": "block"}` on stdout rather
than relying on exit codes — and never enable it on a machine that runs unattended,
where a blocked compaction strands the run.

Keep the hook's job deterministic side effects only: write a timestamp/marker, save
metadata about what is being compacted, print a notice. Do **not** try to write the
state file from the hook — a shell script cannot write the letter; only the model can,
which is why persist-as-you-go (layer 1) is the real defense.

## Example: post-compaction recovery (Claude Code `SessionStart`, matcher `compact`)

Stdout from a `SessionStart` hook is injected as context. A short pointer is enough:

```json
"hooks": {
  "SessionStart": [{
    "matcher": "compact",
    "hooks": [{ "type": "command", "command": "python <abs-path>/postcompact-note.py" }]
  }]
}
```

where the script prints something like:

> Compaction just occurred; precision may be lost. If a handoff state file
> (TO_THE_NEXT_SESSION.md / RESUME.md) exists at the task root, read it now and trust
> it over the summary. Do not re-propose approaches its DECISIONS section records as
> rejected.

Keep it under ~80 tokens — it is injected into every post-compaction session, whether
or not a handoff exists.

## What not to automate

- Do not generate or edit the state file from a hook (deterministic scripts write
  markers; models write letters).
- Do not summarize the transcript, or call another model, from inside a hook.
- Do not default-block automatic compaction fleet-wide; blocking is an interactive-
  machine opt-in.
- Do not let any hook failure surface as exit code 2 (see the trap above).
