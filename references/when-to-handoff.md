# When to hand off

Choose by failure cost, not task length.

## Use this skill

WHEN work will cross a session, machine, person, or context boundary and losing one
exact number, reason, decision, artifact locator, or must-not rule could change the
result → DO create a STATE FILE early and keep it current → DONE iff a cold session
can resume from files alone and receive the saved RELAY PROMPT as a copy-paste box.

Typical triggers include an explicit handoff request, switching devices, delegating
to another person, stopping overnight, or a precision-critical task approaching its
context limit.

## Use /compact or automatic summarization

WHEN continuity is low-stakes and omitted details are cheap to reconstruct → DO use
the runtime's summary facility → DONE iff no load-bearing fact depends only on that
summary.

`/compact` compresses the conversation on the runtime's terms. It is useful for
convenience, but it is not the precision authority for an active handoff.

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

WHEN a short task will finish in the present context and has no costly precision
surface → DO finish it directly → DONE iff no future session needs to reconstruct it.
