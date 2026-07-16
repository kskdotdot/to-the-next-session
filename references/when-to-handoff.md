# When to hand off

Activation is gated, not scored. Two gates control initial activation; nothing else
does.

## Use this skill

WHEN the user explicitly asks to preserve, transfer, or resume this task for cold
continuation — handoff, 引き継ぎ, 別セッションで続き, continue on another device,
pause now and resume later, hand the active task to another person — or supplies a
RELAY PROMPT or live STATE FILE as operative continuation input (Gate A) → DO
produce or resume the handoff → DONE iff a cold session can resume from files alone
and receive the saved RELAY PROMPT as a copy-paste box.

WHEN the remaining context window is below 20% — established by a current
model-visible host pre-compaction or low-context signal, or by an explicit user
statement that less than 20% remains or that auto-compact is about to run (Gate B)
→ DO create the STATE FILE and finalize a relay before the automatic summary runs →
DONE iff the saved state and relay exist before compaction.

Never estimate the remaining percentage yourself. If no such signal is visible and
the user has not stated it, Gate B is false: do not infer imminence from task
length, turn count, or context growth. Pre-compaction rescue is best effort, not
guaranteed.

These gates control initial activation only. Once validly started, keep the same
non-terminal handoff current through `waiting_user`, receipt of the requested input,
resume, re-finalization, and close. `waiting_user` by itself never starts a handoff.
"Early" means promptly after a gate opens, not at the start of every long or
precision-critical task.

Not triggers, alone or in combination: importance, precision, task length, turn
count, ordinary context growth, an inferred future boundary, costly reconstruction,
local time, inactivity, expected overnight stopping, routine live sub-agent
delegation, or mentioning, quoting, reviewing, editing, or testing this skill and
its artifacts.

## Use /compact or automatic summarization

WHEN no gate has opened, continuity is low-stakes, and omitted details are cheap
to reconstruct → DO use the runtime's summary facility → DONE iff no load-bearing
fact depends only on that summary.

A bare `/compact` request does not trigger this skill; an explicit request to
preserve the task before compaction satisfies Gate A.

## Use memory

WHEN a fact should persist across unrelated future tasks → DO record it in the
appropriate durable memory → DONE iff it is not carrying one active task's full
status or backlog.

The handoff state is task-scoped and disposable. Memory is cross-task and durable.

## Use planning

WHEN the question is how to divide work inside the current task → DO use a plan →
DONE iff steps and dependencies are clear. If that task later crosses a boundary,
index the plan as A# rather than duplicating it into the state.

Planning and handoff compose: a plan says what the steps are; this skill preserves
the exact task state, decisions, constraints, and required evidence when the current
conversation disappears.

## Skip ceremony

WHEN a task will finish in the present context and no gate has opened → DO finish it
directly → DONE iff no future session needs to reconstruct it.
