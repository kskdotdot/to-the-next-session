# When to hand off (and when not), and how this relates to neighboring skills

The state-file relay is powerful but not free — it asks you to curate. Use it where
curation pays for itself, and reach for a lighter tool where it doesn't. This file
sharpens that judgment and draws the boundary against skills that look adjacent.

## File relay vs automatic summarization vs memory

Three different jobs, often confused:

**File relay (this skill)** — for an in-progress *task* whose precise state must
survive a boundary. The defining feature is that **specific exact things would be
costly to lose**: a threshold, a tier boundary, a measured result, a "never declare X"
rule, the reason a decision went the way it did. You curate what survives, and the
survivors are exact because the next session reads the real artifact, not a paraphrase.

**Automatic summarization (`/compact` and equivalents)** — for *conversational
continuity* when the details are cheap to reconstruct. It is lossy by design: it
compresses the whole transcript and you don't control what it keeps. That's perfectly
fine for low-stakes, exploratory, or chatty work — and a poor fit the moment a single
dropped number or rule would cause a wrong result. Rule of thumb: if you'd be alarmed
to discover the summary quietly omitted one figure, don't rely on the summary.

**Memory** — for *cross-cutting facts you'll reuse on unrelated future tasks*: a
standing preference, where a credential lives, a convention you always follow. Memory
is about *you/the assistant across projects*; file relay is about *one project's full
state across a boundary*. A handoff state file is deliberately throwaway — it dies when
the task finishes. A memory is meant to persist beyond any single task.

### Quick decision

- Crossing a session/machine/person boundary mid-task, with load-bearing numbers or
  must-not-break rules → **file relay**.
- Same session, just want to free up the window on low-stakes work → **summarization**.
- A durable fact useful next month on a different task → **memory**.

These compose. You might summarize a side-thread, keep a relay state file for the main
task, and write one memory for a convention you discovered along the way.

## Boundary against planning skills

`planning-with-files`, `writing-plans`, and `executing-plans` are about *the plan* —
breaking work into steps and tracking progress through them. They mostly assume a
continuous session. This skill is about *surviving the boundary between sessions* with
precision intact. The layers are different and complementary:

- A **plan** answers "what are the steps?"
- A **relay** answers "how does the full state — plan included — cross to a cold agent
  without loss?"

In practice they nest: when you have plan files, list them in the relay's ARTIFACT
INDEX by absolute path. The plan becomes one of the ground-truth artifacts the next
session reads. You don't duplicate the plan into the state file — you point at it.

A tell for which you need: if your worry is "am I doing the right steps in the right
order?", that's planning. If your worry is "when this conversation ends, will the next
session still know the exact tier cutoffs and that it must not claim completion?",
that's this skill.

## When NOT to bother

- **Trivial or short tasks** that will obviously finish inside the current context.
  Building a state file for a five-minute job is ceremony.
- **Throwaway exploration** where being wrong later costs nothing.
- **Work with no precision surface** — nothing exact, no must-not-break rules, easy to
  redo from scratch. There's little for a relay to protect.

The honest signal to start a state file: the work is long *or* precision-critical, and
there's a real chance it outlives this context. When in doubt on a high-stakes task,
start the file early — an empty scaffold costs little, and a missing handoff costs the
whole reconstruction.
