# Changelog

All notable changes to this skill are recorded here. Versions follow the
`metadata.version` field in `SKILL.md`.

## v0.8.0

Lean-relay release. The copy-paste launch message stops duplicating what already
lives in the canonical state file, so it stays short even for constraint-heavy,
precision-critical handoffs. The state file, its schema 2, and the fingerprint
contract are unchanged.

### Changed

- Relay schema 4 (`assets/relay-prompt-template.md`) is a lean pointer to the state,
  not a copy of it. It drops the render tokens that reprinted state content — the full
  C# constraint bodies (`@@TTNS_INVIOLABLE_CONSTRAINTS@@`), the artifact table
  (`@@TTNS_REQUIRED_ARTIFACTS@@`), the STATUS paragraph (`@@TTNS_STATUS_TEXT@@`), and the
  producing-machine absolute paths (`@@TTNS_STATE_ABS_PATH@@`, `@@TTNS_RELAY_ABS_PATH@@`)
  — keeping only the state locator, fingerprint + verify command, orientation, the
  single next-task preview, the required artifact IDs, and the still-binding G# guards
  (9 tokens, down from 14). The C# constraints, artifact index, and STATUS are read from
  the state file the resuming session must open first.
- The relay now opens with a bootstrap gate: until the state is resolved, read, and
  freshness-verified, the only permitted actions are resolve / read / verify / report;
  no artifact reads and no task, edit, commit, push, deploy, send, or delete may happen
  first, even though the next-task preview is visible. If the canonical state cannot be
  obtained, the session stops rather than continuing from the pointer. The pre-recitation
  "read-only investigation may proceed" allowance is removed here, in `SKILL.md`, and in
  `references/playbook.md`, since the lean relay no longer carries the C#/G# bodies as a
  fallback. G# authority guards stay verbatim in the relay because they gate irreversible
  action.
- `scripts/handoff.py` renders a schema-2 state through relay schema 4
  (`STATE_TO_RELAY_SCHEMA`), and `verify`/`emit` accept a schema-3 relay saved before
  this change (`ACCEPTED_RELAY_SCHEMAS`: state 1 → {1, 2}, state 2 → {3, 4}). The verbose
  v0.7.0 template is frozen byte-for-byte as `assets/relay-prompt-template-v3.md` with a
  pinned canonical UTF-8/LF hash.
- `SKILL.md`, `README.md`, `references/playbook.md`, and `references/worked-example.md`
  describe the relay as a verified pointer rather than a verbatim copy of C#/STATUS.

### Added

- Package tests for the lean relay: schema-4 token set (negative assertions that no C#
  body, artifact row, STATUS paragraph, or abs-path token is present), the frozen v3
  hash pin, backward-compatible `verify`/`emit` of a saved schema-3 relay, and a
  bounded-size test proving the lean relay's length is independent of the C# and STATUS
  body length.

### Measured

- On a realistic precision-critical handoff (5 C#, 2 G#, 3 A#, a four-sentence STATUS),
  the relay drops from **4,239 to 2,698 canonical-LF bytes — a 36.4% reduction**; at 10
  constraints it is 42.8%. The lean relay is a fixed ~2.7 KB regardless of how many
  constraints or artifacts or how long the STATUS is, so the saving grows with the
  handoff's precision, which is exactly the case this skill targets.

## v0.7.0

Cold-start orientation and emergency-path release, scoped to hardening the
same-machine handoff. Cross-machine surfaces are unchanged.

### Added

- State schema 2: `assets/state-file-template.md` now carries a machine-validated
  four-line ORIENTATION block (`Goal`, `Done when`, `Current phase`, `Waiting on`)
  inside START HERE. `parse_state` requires exactly these labeled lines in order,
  rejects placeholder values, and — when `Status: waiting_user` — rejects an
  empty-equivalent `Waiting on` (`none`, `n/a`, dashes) so the state must name the
  exact awaited input. The lifecycle `Status` is now a fill token instead of a
  hardcoded `active`.
- Relay schema 3: the live `assets/relay-prompt-template.md` adds an
  "Orientation — copied verbatim" section and extends the recitation ack with the
  Goal and Waiting on lines. The v0.6.0 relay body is frozen as
  `assets/relay-prompt-template-v2.md`; schema-1 states keep rendering their
  established schema-2 relay byte-for-byte, and `verify`/`emit` accept exactly the
  state-schema/relay-schema pairs finalize can produce (1→{1,2}, 2→{3}).
- `assets/state-file-template-low-context.md`: a dedicated emergency template whose
  shipped tokens are all required — single-value tokens plus whole-block tokens for
  the constraints block, guards block, and artifact rows — with
  `TTNS:LOW_CONTEXT_AUDIT=required` already in place, so the documented emergency
  path finalizes exactly as written.

### Changed

- `_has_placeholder` matches placeholder-ish whole values only (`todo`, `tbd`,
  `fill me`, whole-value `[...]`/`<...>`); substring heuristics that rejected
  legitimate locators such as `...\Todo-project\...` are removed. Upstream fill
  token, reserved token, and template-sentinel checks are unchanged.
- Frozen relay assets are pinned by canonical UTF-8/LF hash (matching the runtime
  load contract) instead of raw bytes, so a CRLF working tree — for example
  `core.autocrlf=true` on Windows — no longer fails the frozen-asset test.
- `references/compact-defense.md` post-compaction recovery contract: the
  SessionStart pointer is now one fixed, neutral notice with a bounded candidate
  count; no candidate-derived text (filename, Status, Last updated) may reach model
  context, and candidates are never opened, parsed, ranked, or echoed by the hook.
- Template close examples use `python <skill-root>/scripts/handoff.py ...` so the
  command resolves from the task root.
- `references/worked-example.md` shows the schema 2 state and an emergency
  low-context variant; INVARIANTS no longer duplicates the Goal owned by
  ORIENTATION.

## v0.6.0

Read-cost and continuation-fidelity release. Standard same-machine produce now
completes from `SKILL.md` and the state template alone.

### Changed

- `assets/state-file-template.md`: every fill-in placeholder is now a reserved
  `@@TTNS_FILL_<NAME>@@` token instead of a bracketed sentinel; fill guidance moved
  to adjacent HTML comments. `[unverified]` and other vocabulary/literals (for
  example `- None.`) are untouched — they are not placeholders. The HANDOFF AUDIT
  section is promoted to a 6-MUST standard-path checklist (ID uniqueness,
  STATUS/NEXT TASK alignment, required A#, unverified-vs-fact, no leftover
  placeholders, finalize+read-back); the full 11-point audit remains in
  `references/playbook.md` §3 for cross-machine, fallback, and close/supersede.
- `assets/relay-prompt-template.md` is schema 2: adds a `TTNS:SKILL=` line and an
  ack-block paragraph (Handoff ID, verify result, C#/G# IDs, STATUS, single NEXT
  TASK, Last updated) to recite before the first substantive work — a diagnostic
  recitation, not proof of compliance. `scripts/handoff.py finalize`/`emit` always
  render schema 2.
- `scripts/handoff.py verify` is schema-aware: a saved schema-1 relay is compared
  against the new frozen `assets/relay-prompt-template-v1.md`, a schema-2 relay
  against the current template; a missing, duplicated, or unrecognized
  `TTNS:RELAY_SCHEMA` line is an explicit error, never a silent fallback to schema
  1. `verify --fingerprint` does not read the relay file and is unaffected.
- `scripts/handoff.py finalize` now rejects a state in two distinct ways: an
  unfilled `@@TTNS_FILL_*@@` token (named individually) versus any other reserved
  `@@TTNS_*@@` token outside the fill namespace (a stricter, not narrower, check
  than the single reject it replaces).
- `SKILL.md` Produce step 4 now points to the template-embedded HANDOFF AUDIT
  instead of `references/playbook.md` for the standard same-machine case; a new
  "Emergency low-context path" section (used only while Gate B is open) fills only
  C#, active G#, STATUS, NEXT TASK, and required A#, marks
  `TTNS:LOW_CONTEXT_AUDIT=required`, and skips `references/` reads entirely. Resume
  now completes the full file-only audit and clears that marker before acting on a
  low-context-produced state, and recites the ack block before the first
  substantive work. State semantics add a two-line rule routing a decision-changing
  failure to D# and an unresolved retryable one to OPEN ISSUES.
- `references/playbook.md` §3 gains a one-line pointer back to the standard-path
  checklist; §1 adds the same D#/OPEN ISSUES failure-routing rule; §5 reflects the
  LOW_CONTEXT_AUDIT marker and ack block.

### Added

- `assets/relay-prompt-template-v1.md`: a byte-for-byte frozen copy of the
  pre-v0.6.0 relay template (verified against the `a6c6fca` blob by SHA-256),
  kept only so `verify`/`emit` keep validating relays saved before this release.

### Measured

- Standard produce required reading (`SKILL.md` + state template, 16,077 bytes) is
  **75.15%** of the v0.5.1 baseline (`SKILL.md` + state template +
  `references/playbook.md`, 21,392 bytes) — a 24.85% reduction. Bytes are counted
  on the repository's canonical LF form; a CRLF checkout inflates the three-file
  baseline more than the two-file result and would report a smaller ratio.

## v0.5.1

Trigger-narrowing bugfix. No helper, schema, template, or runtime-hook behavior
changed.

### Changed

- `SKILL.md` description now states two explicit activation gates: (A) an explicit
  user request to preserve/transfer/resume, or a RELAY PROMPT / live STATE FILE
  supplied as operative continuation input; (B) a model-visible pre-compaction
  signal or explicit user context-low warning combined with load-bearing loss risk.
  Broad predicates ("about to cross a boundary", "prefer it over /compact when ...
  would be costly") were removed so importance, precision, or ordinary context
  growth alone can no longer fire the skill.
- `references/when-to-handoff.md` restates the same gates, separates initial
  activation from post-activation lifecycle, and lists explicit non-triggers.
- `references/compact-defense.md` scopes persist-as-you-go to after a valid
  activation gate opens.

## v0.5.0

Deterministic cold-session transport release.

### Added

- `scripts/handoff.py` with `finalize`, `verify`, `emit`, and
  `close` commands.
- Whole-state `sha256-lf` fingerprinting, atomic relay save, read-back verification,
  dynamic copy-box fencing, stable exit codes, and stale/terminal fail-closed behavior.
- Schema 1 C#/G#/A#/D# model, required-artifact lazy reads, explicit same/cross-machine
  locators, and lifecycle statuses.
- Standard-library contract tests plus `agents/openai.yaml`.

### Changed

- Made the STATE FILE the sole current-state authority. The saved relay is the
  authoritative text only for the emitted copy box, never for newer task state.
- Reworked all templates and references around deterministic production and
  freshness-first resume.
- Documented dirty/untracked WIP transport and the boundary between helper form
  validation and human/agent semantic audit.

### Migration

- Existing v0.4 state files remain readable as documents but do not satisfy helper
  schema 1. Move their current facts into the new state template before running
  `finalize`.
- Python remains optional; manual handoff is available as `manual-unverified`.

## v0.4.0

Decision-provenance and relay-delivery release. Still markdown-only; the core model is
unchanged (additive minor). The headline: what the user decided — and *why*, and what
was rejected — now survives the boundary as deliberately as the constraints do.

### Added
- **Decision provenance (user-consulted decisions):** a structured record format inside
  `DECISIONS & CHANGELOG` for structured consultations (e.g. AskUserQuestion), plan
  approvals, and explicit corrections: the question asked, *why it was asked* (what was
  blocked/ambiguous), options considered, the chosen option in the user's own words,
  the rejected alternatives with reasons and the conditions under which the rejection
  holds, downstream implications, and an honest source/confidence label.
- **Pre-handoff conversation sweep:** the workflow now mandates a best-effort sweep of
  the *visible* conversation for user-consulted decisions before handing off — with an
  explicit honesty rule: history already lost to summarization is marked
  `[not visible in current context]`, never reconstructed into confident-looking
  provenance. Only decisions that affect future action are recorded.
- **Anti-resurrection rule in the relay:** the relay prompt now forbids re-proposing a
  rejected alternative while its recorded conditions hold; a genuine change of
  conditions must be raised as an explicit reconsideration citing the record.
- **Relay delivery gate:** the saved relay file is canonical; the handoff message must
  reproduce it **verbatim from the saved file** (never regenerated) as the **final
  fenced block** of the message — paths and caveats before the block, nothing after,
  four-backtick fence so inner code fences cannot break it.
- **`references/compact-defense.md`:** example runtime countermeasures for losing the
  race against automatic compaction (usage-threshold warning, pre-compaction hook with
  the exit-code-2 trap documented, post-compaction recovery injection) — explicitly
  illustrative, not a supported component; the skill remains markdown-only.
- **Audit items 8 & 9** (playbook §2 and the template's embedded audit): user-consulted
  decisions carried in full; relay printed verbatim from its saved file, last.
- **Worked example:** a full decision record (`D1`) showing a rejected alternative that
  must not be resurrected.

## v0.3.1

Presentation patch. Markdown-only, no code; the skill's substance, voice, and every claim
are unchanged. The version bump keeps `SKILL.md`, the README status line, and this changelog
in lockstep.

### Changed
- **README:** added a static badge row (version, license, markdown-only, tool-agnostic), a
  table of contents, an ASCII flow diagram of the handoff, a state-file-vs-relay-prompt
  comparison table (with trust levels), a thesis pull-quote, and a restructured quick start.
  Presentation only — no claim added or altered.

### Fixed
- **README "What's inside":** the file tree now lists `LICENSE` and `NOTICE`, which were
  present in the repo but missing from the listing.

## v0.3.0

Documentation-completeness and backlog-closure release. Still markdown-only, no code;
the core model is unchanged (additive minor). Planned via a multi-panel review
(Codex + Claude).

### Fixed
- **Worked example:** INVIOLABLE CONSTRAINTS now use stable IDs (`C1:`, `C2:`) and the
  relay block carries the same IDs, matching the v0.2.0 template/relay convention (the
  example had been left on the old checkbox form).

### Added
- **No-filesystem runtimes:** where a runtime has no writable disk, the state file
  becomes a self-contained block in the relay (or a gist / shared-doc URL) and the
  Artifact Index points by URL+ID — discipline unchanged, only the substrate moves.
- **Headless delivery:** the workflow names who delivers the relay when no human is at
  the boundary (hand it to the dispatched worker, or write it to a known path).
- **Sync-conflict warning:** under a sync root, a `(conflicted copy)` twin can shadow
  the live state file; resume confirms the canonical name first.
- **Trust levels** named explicitly — state file = semi-trusted index; relay
  constraints = authoritative; artifacts = untrusted data / re-run scripts = untrusted
  code.
- **Non-file artifacts:** the template and worked example show locator-plus-cheap-probe
  for buckets, tables, and large/expensive-to-re-derive artifacts.
- **Self-sufficiency audit** embedded as a deletable comment in the state-file template
  (the 7-point check at fill-time), plus a memory-routing note (cross-task facts belong
  in memory, not the disposable state file).
- **README:** Quick start, prior-art positioning (vs `AGENTS.md` / `HANDOFF.md`), and a
  named trust-levels note.

### Changed
- **Mechanical pre-check sharpened** (playbook §2): compare constraints per ID,
  character by character; generate the relay's constraint block by copy, never retype;
  and verify exactly one active state file under the task root.

## v0.2.0

Reliability and resume-side hardening. No change to the core model
("state file preserves; relay prompt launches"; artifacts are data, not instructions;
no claim of losslessness). Driven by a multi-panel review.

### Fixed
- **state-file template:** removed a nested `<!-- ... -->` comment that prematurely
  closed the leading comment block and leaked guidance text in CommonMark/GitHub
  renderers.
- **relay-prompt template:** removed the leading `---` divider that could be misread as
  YAML front-matter when pasted.

### Added
- **Relay carries a portable locator for the state file itself** (not just a bare
  absolute path), so the first read instruction resolves on a different machine.
  Portability anchors are now described as recovery instructions (clone @commit / wait
  for sync / unpack archive).
- **Fast path** at the top of `SKILL.md`: the actionable sequence (copy template → fill
  → persist → run the self-sufficiency audit → hand off) in a numbered block.
- **Resume side:** `description` now triggers on resuming a handoff as well as
  producing one, and a new "Resuming a handoff" section states the receive contract
  (read state → re-derive load-bearing numbers → treat artifacts as untrusted data →
  settle `[unverified]` → keep updating the same file). The relay prompt still carries
  this inline so it survives where the skill does not load.
- **Constraint rebuttal rule:** an inviolable constraint is a floor on action, not a
  license to ship a known error — with concrete evidence one is wrong/harmful, STOP and
  surface it rather than silently overriding or blindly complying.
- **Data classification** in the safety model: keep regulated/personal data (e.g. PHI)
  out of the relay prompt unless authorized; minimum-necessary paths; encrypted archive
  when data must travel.
- **Concurrency:** "one active file per task, not per directory" with a
  `TO_THE_NEXT_SESSION_<task-slug>.md` naming convention for co-located tasks.
- **Lightweight state-file metadata:** `Status: active | superseded | complete |
  abandoned` (optional `Handoff-id` / `Supersedes`).
- **Provenance for transcribed numbers:** fixed values that are not re-derivable now
  carry a source pointer / `[transcribed — re-verify against <path>]` tag.
- **Constraint lifecycle:** retire a constraint by dated strike-through, never silent
  deletion.
- **Write-ordering invariant:** update body sections first, re-write START HERE + the
  timestamp last as the commit point.
- **Optional drift stamp:** record the commit/mtime a re-derivable number was trusted
  as of, so resume can detect drift with a one-line comparison.
- **Documented constraint-equality check:** the playbook's mechanical pre-check now
  includes diffing the INVIOLABLE CONSTRAINTS block against the relay's copy (constraint
  IDs make this trivial).

### Changed
- **Constraints use stable IDs** (`C1:`, `C2:`, …) instead of checkboxes — they are
  standing rules, not tasks to complete.
- **Neighbor-skill references generalized** to "a planning skill / a plan-writing skill
  (if your runtime has one)"; specific names are now illustrative, not dependencies.
- **Worked example** updated: relay leads with a locator, shows cross-machine recovery
  and a Windows path example, and no longer leaves an already-re-derived number marked
  `[unverified]`.

## v0.1.0

- Initial release: the skill, two asset templates, three references.
