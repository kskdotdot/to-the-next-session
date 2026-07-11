# Compact defense: do not lose the race

The primary defense is persist-as-you-go: a current STATE FILE already exists before
automatic compaction. The public skill ships the state/relay helper, not a runtime
hook. A host configuration repository may separately integrate deterministic hooks;
for example, sync-config-claudecode maintains `scripts/compact-defense.py` for
Claude Code. Codex and runtimes without equivalent hooks degrade to persistent files
and manual threshold awareness.

## Defense layers

1. Persist STATUS, NEXT TASK, A#, and D# after meaningful work.
2. Warn while enough context remains to finalize a relay.
3. Use a fail-open pre-compaction hook only for deterministic metadata/notice work.
4. After compaction, point the session back to a live state file and prefer it over
   the summary.

WHEN a runtime exposes context usage → DO warn at an early local threshold such as
60% → DONE iff the user or agent still has room to persist and finalize before the
automatic trigger. The exact trigger is runtime-specific; do not claim a universal
percentage.

## Claude Code hook constraints

Claude Code's `PreCompact` exit code 2 blocks compaction. A missing Python script
also commonly exits 2, so a brittle hook can strand every session.

WHEN installing a PreCompact command → DO catch failures and exit 0 by default →
DONE iff missing files, invalid input, permission errors, and backup failures cannot
block compaction.

WHEN deliberate blocking is needed on an interactive machine → DO make it a
per-machine opt-in and emit the runtime's explicit block decision → DONE iff the
default and unattended-machine behavior remain fail-open.

Keep pre-compaction work deterministic:

- write small metadata or a timestamp;
- copy a transcript only under an explicit local opt-in and bounded quota;
- keep backups off synchronized roots when they may contain sensitive data.

Do not ask a shell hook to write the handoff letter, summarize the transcript, or
call a model. Only the active agent can curate C#/G#/A#/D# correctly.

## Post-compaction recovery

WHEN a compacted session starts → DO scan only the task cwd for recognized state
names, ignore explicitly terminal states, and inject a short pointer to every live
candidate → DONE iff the summary cannot silently override a current state and the
hook does not guess among multiple live tasks.

Recognized names include unprefixed and local two-digit forms:

- `TO_THE_NEXT_SESSION*.md`
- `NN_TO_THE_NEXT_SESSION*.md`
- `RESUME*.md`
- `NN_RESUME*.md`

Legacy files without a Status field remain candidates. Recursive filesystem search is
outside this hook's job.
