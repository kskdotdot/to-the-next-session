# Changelog

All notable changes to this skill are recorded here. Versions follow the
`metadata.version` field in `SKILL.md`.

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
