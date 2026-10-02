#!/usr/bin/env python3
"""Deterministic state-to-relay transport for to-the-next-session.

The model writes and judges the state. This helper only validates the mechanical
schema, renders exact marked blocks, detects stale relays, saves atomically, and
emits a copy box from saved bytes.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

EXIT_INTERNAL = 1
EXIT_USAGE = 2
EXIT_STATE_INVALID = 3
EXIT_RELAY_STALE = 4
EXIT_IO = 5

SECTION_BUDGETS = {
    "STATUS": 2000,
    "NEXT TASK": 1500,
    "OPEN ISSUES": 3000,
    "INVARIANTS": 2000,
    "ARTIFACT INDEX": 400,
}
BOOT_BUDGET_CHARS = 24000
LIVENESS_TAIL_BYTES = 256 * 1024

LIVE_STATUSES = {"active", "waiting_user"}
TERMINAL_STATUSES = {"complete", "superseded", "abandoned"}
ALL_STATUSES = LIVE_STATUSES | TERMINAL_STATUSES
TARGETS = {"same-machine", "cross-machine"}
BLOCK_NAMES = (
    "INVIOLABLE_CONSTRAINTS",
    "ACTIVE_ACTION_GUARDS",
    "STATUS",
    "NEXT_TASK",
)
TEMPLATE_TOKENS = {
    "@@TTNS_HANDOFF_ID@@",
    "@@TTNS_STATUS@@",
    "@@TTNS_TARGET@@",
    "@@TTNS_STATE_LOCATOR@@",
    "@@TTNS_STATE_ABS_PATH@@",
    "@@TTNS_RELAY_ABS_PATH@@",
    "@@TTNS_STATE_FINGERPRINT@@",
    "@@TTNS_STATUS_TEXT@@",
    "@@TTNS_NEXT_TASK@@",
    "@@TTNS_REQUIRED_ARTIFACT_IDS@@",
    "@@TTNS_REQUIRED_ARTIFACTS@@",
    "@@TTNS_INVIOLABLE_CONSTRAINTS@@",
    "@@TTNS_ACTIVE_ACTION_GUARDS@@",
}
ORIENTATION_TOKEN = "@@TTNS_ORIENTATION@@"
# Lean relay (schema 4) token set: a freshness-checkable pointer to the state, not a
# copy of it. It drops the verbose bodies that duplicate the state file (C#
# constraints, artifact table rows, STATUS paragraph, producing-machine abs paths)
# and keeps only what a cold session needs to locate + verify the state, stay gated
# until it has, orient, and see the single next action plus the still-binding G#
# authority guards.
LEAN_TOKENS = frozenset(
    {
        "@@TTNS_HANDOFF_ID@@",
        "@@TTNS_STATUS@@",
        "@@TTNS_TARGET@@",
        "@@TTNS_STATE_LOCATOR@@",
        "@@TTNS_STATE_FINGERPRINT@@",
        "@@TTNS_NEXT_TASK@@",
        "@@TTNS_REQUIRED_ARTIFACT_IDS@@",
        "@@TTNS_ACTIVE_ACTION_GUARDS@@",
        ORIENTATION_TOKEN,
    }
)
# Schemas 1 through 4 are frozen; schema 5 adds the boot view identity.
RELAY_SCHEMAS = {
    "1": ("relay-prompt-template-v1.md", frozenset(TEMPLATE_TOKENS)),
    "2": ("relay-prompt-template-v2.md", frozenset(TEMPLATE_TOKENS)),
    "3": (
        "relay-prompt-template-v3.md",
        frozenset(TEMPLATE_TOKENS | {ORIENTATION_TOKEN}),
    ),
    "4": ("relay-prompt-template-v4.md", LEAN_TOKENS),
    "5": ("relay-prompt-template.md", LEAN_TOKENS | {
        "@@TTNS_BOOT_LOCATOR@@", "@@TTNS_BOOT_FINGERPRINT@@",
    }),
}
STATE_SCHEMAS = {"1", "2"}
# finalize renders a state through the newest relay schema its state schema can
# fill; verify accepts exactly these pairs (no silent cross-schema acceptance).
STATE_TO_RELAY_SCHEMA = {"1": "2", "2": "5"}
ACCEPTED_RELAY_SCHEMAS = {"1": frozenset({"1", "2"}), "2": frozenset({"3", "4", "5"})}
# ORIENTATION block contract (state schema 2): exactly these labels, this order.
ORIENTATION_LABELS = ("Goal", "Done when", "Current phase", "Waiting on")
# waiting_user must name the awaited input; these values are empty-equivalent
# after strip+casefold.
WAITING_NONE_EQUIVALENTS = {
    "none", "none.", "n/a", "n/a.", "-", "—", "–", "−",
}
# State-template fill-in placeholders: @@TTNS_FILL_<NAME>@@. A leftover one means
# the producing agent forgot to fill the template.
FILL_TOKEN_RE = re.compile(r"@@TTNS_FILL_[A-Z0-9_]+@@")
# Any reserved @@TTNS_*@@ token (fill tokens included). Widened to allow digits so
# it also matches numbered fill tokens such as @@TTNS_FILL_C1@@.
RESERVED_TOKEN_RE = re.compile(r"@@TTNS_[A-Z0-9_]+@@")
TEMPLATE_SENTINELS = (
    "[task name]",
    "[stable-task-slug]",
    "[same-machine or cross-machine]",
    "[absolute path or portable locator described above]",
    "[yyyy-mm-ddthh:mm:ss+tz]",
    "[the exact outcome]",
    "[what is complete, in flight, and blocked]",
    "[the single next task below]",
    "[c# and active g# ids]",
    "[task-wide correctness or scope rule, copied verbatim]",
    "[another task-wide rule, copied verbatim]",
    "[temporary authority/action guard, copied verbatim]",
    "[present reality in 2–6 sentences.",
    "[one concrete action only.",
    "[a1, a3 or none]",
    "[absolute path or uri]",
    "[ground-truth role]",
    "[safe read/checksum/idempotent command]",
    "[state-relative:path or full portable locator; — only for same-machine]",
    "[deferred artifact]",
    "[cheapest safe probe]",
    "[portable locator or —]",
    "[observable definition of done]",
    "[exact boundary]",
    "[exact thresholds, tiers, counts, units, each with a source a#]",
    "[short decision title]",
    "[decision]",
    "[reason/evidence]",
    "[alternative and conditions under which rejection holds]",
    "[visible user instruction / artifact a# / reconstruction marked unverified]",
    "[queued work beyond next task]",
    "[claim and the a#/probe that can settle it]",
)


class TtnsError(Exception):
    """Expected, user-actionable helper failure."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    local_locator: str
    description: str
    verification: str
    portable_locator: str
    source_row: str


@dataclass(frozen=True)
class ParsedState:
    path: Path
    schema: str
    handoff_id: str
    status: str
    target: str
    state_locator: str
    last_updated: str
    superseded_by: str
    orientation_block: str | None
    constraints: str
    guards: str
    status_text: str
    next_task: str
    required_artifact_ids: tuple[str, ...]
    artifacts: dict[str, Artifact]
    canonical_bytes: bytes
    fingerprint: str


def canonical_utf8_lf(raw: bytes) -> bytes:
    """Strict UTF-8, optional BOM removal, LF newlines, exactly a final LF."""
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise TtnsError(EXIT_STATE_INVALID, "state is not strict UTF-8") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return text.encode("utf-8")


def state_fingerprint(raw: bytes) -> str:
    return "sha256-lf:" + hashlib.sha256(canonical_utf8_lf(raw)).hexdigest()


def _read_bytes(path: Path, *, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise TtnsError(EXIT_IO, f"cannot read {label}: {path}") from exc


def _field(text: str, label: str) -> str:
    matches = re.findall(rf"^_{re.escape(label)}: (.*)_$", text, flags=re.MULTILINE)
    if len(matches) != 1 or not matches[0].strip():
        raise TtnsError(EXIT_STATE_INVALID, f"{label} must appear exactly once")
    return matches[0].strip()


def _block(text: str, name: str) -> str:
    begin = f"<!-- TTNS:BEGIN:{name} -->"
    end = f"<!-- TTNS:END:{name} -->"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise TtnsError(
            EXIT_STATE_INVALID, f"{name} begin/end markers must appear exactly once"
        )
    start = text.index(begin) + len(begin)
    finish = text.index(end)
    if finish <= start:
        raise TtnsError(EXIT_STATE_INVALID, f"{name} markers are reversed")
    body = text[start:finish]
    if body.startswith("\n"):
        body = body[1:]
    if body.endswith("\n"):
        body = body[:-1]
    if not body.strip():
        raise TtnsError(EXIT_STATE_INVALID, f"{name} block is empty")
    return body


def _has_placeholder(value: str) -> bool:
    """Placeholder-ish whole values only. Substring heuristics were removed in
    v0.7.0: they rejected legitimate locators such as `C:\\...\\Todo-project\\x.md`.
    Whole-value `[...]`/`<...>` still catches novel placeholders like `[TBD]`;
    fill/reserved-token and template-sentinel checks remain upstream."""
    stripped = value.strip()
    lowered = stripped.casefold()
    return (
        not stripped
        or "@@ttns_" in lowered
        or lowered in {"todo", "tbd", "fill me"}
        or (stripped.startswith("[") and stripped.endswith("]"))
        or (stripped.startswith("<") and stripped.endswith(">"))
    )


def _strip_code(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def _is_absolute_path(value: str) -> bool:
    value = _strip_code(value)
    return bool(
        Path(value).is_absolute()
        or re.match(r"^[A-Za-z]:[\\/]", value)
        or value.startswith("\\\\")
    )


def _is_local_locator(value: str) -> bool:
    value = _strip_code(value)
    return _is_absolute_path(value) or bool(
        re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value)
    )


def _safe_relative(value: str) -> bool:
    value = value.replace("\\", "/")
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def _valid_portable(value: str, *, artifact: bool = False) -> bool:
    value = _strip_code(value)
    if _has_placeholder(value):
        return False
    if artifact and value.startswith("state-relative:"):
        return _safe_relative(value.removeprefix("state-relative:"))
    repo = re.fullmatch(
        r"repo:https?://[^@\s#]+@[0-9a-fA-F]{40}#[^#\r\n]+", value
    )
    if repo:
        return _safe_relative(value.rsplit("#", 1)[1])
    sync = re.fullmatch(r"sync:[A-Za-z0-9._-]+#[^#\r\n]+", value)
    if sync:
        return _safe_relative(value.rsplit("#", 1)[1])
    if value.startswith("archive:") and "#" in value:
        anchor, member = value.removeprefix("archive:").rsplit("#", 1)
        return bool(anchor.strip()) and _safe_relative(member)
    return False


def _validate_orientation(block: str, status: str) -> None:
    """State schema 2: exactly the four labeled lines, fixed order, no
    placeholder values; waiting_user must name the awaited input."""
    lines = [line for line in block.splitlines() if line.strip()]
    if len(lines) != len(ORIENTATION_LABELS):
        raise TtnsError(
            EXIT_STATE_INVALID,
            "ORIENTATION needs exactly these lines in order: "
            + ", ".join(ORIENTATION_LABELS),
        )
    values: dict[str, str] = {}
    for line, label in zip(lines, ORIENTATION_LABELS):
        match = re.fullmatch(rf"- \*\*{re.escape(label)}:\*\* (.+)", line)
        if match is None:
            raise TtnsError(
                EXIT_STATE_INVALID,
                f"ORIENTATION line must be '- **{label}:** <value>'",
            )
        value = match.group(1).strip()
        if _has_placeholder(value):
            raise TtnsError(
                EXIT_STATE_INVALID, f"ORIENTATION {label} is a placeholder"
            )
        values[label] = value
    if (
        status == "waiting_user"
        and values["Waiting on"].strip().casefold() in WAITING_NONE_EQUIVALENTS
    ):
        raise TtnsError(
            EXIT_STATE_INVALID,
            "waiting_user needs the exact awaited input in Waiting on",
        )


def _artifact_rows(text: str) -> dict[str, Artifact]:
    header = (
        "| ID | Locator on this machine | What it is | "
        "Cheapest safe verification | Portable locator |"
    )
    if header not in text:
        raise TtnsError(EXIT_STATE_INVALID, "ARTIFACT INDEX header is missing")
    artifacts: dict[str, Artifact] = {}
    for line in text.splitlines():
        if not re.match(r"^\|\s*A[1-9]\d*\s*\|", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5:
            raise TtnsError(EXIT_STATE_INVALID, "artifact rows must have five cells")
        artifact_id, local, description, verification, portable = cells
        if artifact_id in artifacts:
            raise TtnsError(
                EXIT_STATE_INVALID, f"duplicate artifact ID: {artifact_id}"
            )
        local = _strip_code(local)
        portable = _strip_code(portable)
        if (
            _has_placeholder(local)
            or not _is_local_locator(local)
            or not description
            or not verification
        ):
            raise TtnsError(
                EXIT_STATE_INVALID, f"invalid artifact row: {artifact_id}"
            )
        artifacts[artifact_id] = Artifact(
            artifact_id,
            local,
            description,
            verification,
            portable,
            line,
        )
    return artifacts


def parse_state(path: Path, raw: bytes | None = None) -> ParsedState:
    path = Path(path).resolve()
    if raw is None:
        raw = _read_bytes(path, label="state")
    canonical = canonical_utf8_lf(raw)
    text = canonical.decode("utf-8")
    # Two-stage reject, kept as broad as a single check would be, split so the
    # message tells the agent whether it forgot to fill the template (a) or leaked
    # a reserved render token into state content (b).
    fill_tokens = sorted(set(FILL_TOKEN_RE.findall(text)))
    if fill_tokens:
        raise TtnsError(
            EXIT_STATE_INVALID,
            "state still has unfilled placeholder(s): " + ", ".join(fill_tokens),
        )
    reserved_tokens = sorted(set(RESERVED_TOKEN_RE.findall(text)))
    if reserved_tokens:
        raise TtnsError(
            EXIT_STATE_INVALID,
            "state contains reserved @@TTNS_*@@ token(s) outside the fill "
            "namespace: " + ", ".join(reserved_tokens),
        )
    folded = text.casefold()
    if any(sentinel in folded for sentinel in TEMPLATE_SENTINELS):
        raise TtnsError(EXIT_STATE_INVALID, "state still contains a template sentinel")

    schema = _field(text, "TTNS schema")
    handoff_id = _field(text, "Handoff ID")
    status = _field(text, "Status")
    target = _field(text, "Target")
    state_locator = _field(text, "State locator")
    last_updated = _field(text, "Last updated")
    superseded_by = _field(text, "Superseded by")

    if schema not in STATE_SCHEMAS:
        raise TtnsError(EXIT_STATE_INVALID, "unsupported TTNS schema")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", handoff_id):
        raise TtnsError(EXIT_STATE_INVALID, "invalid Handoff ID")
    if status not in ALL_STATUSES:
        raise TtnsError(EXIT_STATE_INVALID, "invalid Status")
    if target not in TARGETS:
        raise TtnsError(EXIT_STATE_INVALID, "invalid Target")
    try:
        parsed_timestamp = datetime.fromisoformat(last_updated)
    except ValueError as exc:
        raise TtnsError(EXIT_STATE_INVALID, "Last updated must be ISO-8601") from exc
    if parsed_timestamp.tzinfo is None:
        raise TtnsError(EXIT_STATE_INVALID, "Last updated needs a timezone offset")
    if _has_placeholder(state_locator):
        raise TtnsError(EXIT_STATE_INVALID, "State locator is a placeholder")
    if target == "same-machine":
        if not _is_absolute_path(state_locator):
            raise TtnsError(
                EXIT_STATE_INVALID, "same-machine State locator must be absolute"
            )
        if Path(state_locator).resolve() != path:
            raise TtnsError(
                EXIT_STATE_INVALID, "same-machine State locator does not name this state"
            )
    elif not _valid_portable(state_locator):
        raise TtnsError(
            EXIT_STATE_INVALID,
            "cross-machine State locator needs repo@40hex, sync root, or archive",
        )
    if status == "superseded":
        if superseded_by.casefold() == "none":
            raise TtnsError(
                EXIT_STATE_INVALID, "superseded state needs a successor locator"
            )
        successor_ok = (
            _valid_portable(superseded_by)
            if target == "cross-machine"
            else (_is_absolute_path(superseded_by) or _valid_portable(superseded_by))
        )
        if not successor_ok:
            raise TtnsError(EXIT_STATE_INVALID, "invalid successor locator")
    elif superseded_by.casefold() != "none":
        raise TtnsError(
            EXIT_STATE_INVALID, "only superseded state may name a successor"
        )

    orientation_block: str | None = None
    if schema == "2":
        orientation_block = _block(text, "ORIENTATION")
        _validate_orientation(orientation_block, status)

    constraints = _block(text, "INVIOLABLE_CONSTRAINTS")
    guards = _block(text, "ACTIVE_ACTION_GUARDS")
    status_text = _block(text, "STATUS")
    next_task = _block(text, "NEXT_TASK")

    c_ids = re.findall(r"(?m)^- \*\*(C[1-9]\d*):\*\*", constraints)
    if not c_ids or len(c_ids) != len(set(c_ids)):
        raise TtnsError(
            EXIT_STATE_INVALID, "constraints need unique C# IDs and at least C1"
        )
    if guards.strip() not in {"None.", "- None."}:
        g_ids = re.findall(r"(?m)^- \*\*(G[1-9]\d*):\*\*", guards)
        if not g_ids or len(g_ids) != len(set(g_ids)):
            raise TtnsError(
                EXIT_STATE_INVALID, "guards need unique G# IDs or '- None.'"
            )

    required_lines = re.findall(
        r"(?m)^Required artifact IDs: ([^\r\n]+)$", next_task
    )
    if len(required_lines) != 1:
        raise TtnsError(
            EXIT_STATE_INVALID,
            "NEXT TASK needs exactly one 'Required artifact IDs:' line",
        )
    required_text = re.sub(r"\s*<!--.*?-->\s*$", "", required_lines[0]).strip()
    if required_text.casefold() == "none":
        required_ids: tuple[str, ...] = ()
    else:
        required_ids = tuple(part.strip() for part in required_text.split(","))
        if (
            not required_ids
            or any(not re.fullmatch(r"A[1-9]\d*", item) for item in required_ids)
            or len(required_ids) != len(set(required_ids))
        ):
            raise TtnsError(EXIT_STATE_INVALID, "invalid required artifact ID list")

    artifacts = _artifact_rows(text)
    for artifact_id in required_ids:
        artifact = artifacts.get(artifact_id)
        if artifact is None:
            raise TtnsError(
                EXIT_STATE_INVALID, f"required artifact is not indexed: {artifact_id}"
            )
        if target == "cross-machine" and not _valid_portable(
            artifact.portable_locator, artifact=True
        ):
            raise TtnsError(
                EXIT_STATE_INVALID,
                f"required cross-machine artifact lacks portable locator: {artifact_id}",
            )

    return ParsedState(
        path=path,
        schema=schema,
        handoff_id=handoff_id,
        status=status,
        target=target,
        state_locator=state_locator,
        last_updated=last_updated,
        superseded_by=superseded_by,
        orientation_block=orientation_block,
        constraints=constraints,
        guards=guards,
        status_text=status_text,
        next_task=next_task,
        required_artifact_ids=required_ids,
        artifacts=artifacts,
        canonical_bytes=canonical,
        fingerprint=state_fingerprint(raw),
    )


def _heading_spans(text: str, level: int) -> list[tuple[str, int, int]]:
    """Find real Markdown headings, ignoring fenced code and HTML comments."""
    headings = []
    offset = 0
    fence = None
    in_comment = False
    for line in text.splitlines(keepends=True):
        if fence is not None:
            if re.fullmatch(rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*", line):
                fence = None
        elif in_comment:
            if "-->" in line:
                in_comment = False
        elif line.lstrip().startswith("<!--"):
            in_comment = "-->" not in line
        else:
            code = re.match(r" {0,3}(`{3,}|~{3,})", line)
            heading = re.match(rf"^{'#' * level} (.+?)[ \t]*\n?$", line)
            if code:
                fence = code.group(1)
            elif heading:
                headings.append((heading.group(1), offset, offset + len(line)))
        offset += len(line)
    return headings


def _sections(text: str, level: int = 2) -> dict[str, str]:
    headings = _heading_spans(text, level)
    sections = {}
    for index, (name, _start, body_start) in enumerate(headings):
        end = headings[index + 1][1] if index + 1 < len(headings) else len(text)
        if name in sections:
            raise TtnsError(EXIT_STATE_INVALID, f"duplicate section: {name}")
        sections[name] = text[body_start:end]
    return sections


def _required_decisions(next_task: str) -> tuple[str, ...]:
    lines = re.findall(r"(?m)^Required decision IDs: (.*)$", next_task)
    if not lines:
        return ()
    if len(lines) != 1:
        raise TtnsError(EXIT_STATE_INVALID, "duplicate Required decision IDs line")
    value = re.sub(r"\s*<!--.*?-->\s*$", "", lines[0]).strip()
    if value.casefold() == "none":
        return ()
    ids = tuple(part.strip() for part in value.split(","))
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"D[1-9]\d*", item) for item in ids):
        raise TtnsError(EXIT_STATE_INVALID, "invalid required decision ID list")
    return ids


def _char_count(text: str) -> int:
    return len(canonical_utf8_lf(text.encode("utf-8")).decode("utf-8"))


def _marked_block(name: str, body: str) -> str:
    return f"<!-- TTNS:BEGIN:{name} -->\n{body}\n<!-- TTNS:END:{name} -->"


def _boot_budget_marker(boot: bytes) -> str:
    text = boot.decode("utf-8")
    return (f"<!-- TTNS:BOOT_BUDGET=exceeded {len(text)}/{BOOT_BUDGET_CHARS} -->\n"
            if len(text) > BOOT_BUDGET_CHARS else "")


def render_boot(state: ParsedState, *, emergency: bool = False, warn: bool = True) -> bytes:
    """Render selected state sections without rewriting any C#/G# text."""
    sections = _sections(state.canonical_bytes.decode("utf-8"))
    required_d = _required_decisions(state.next_task)
    decisions = {}
    for title, body in _sections(sections.get("DECISIONS", ""), 3).items():
        match = re.match(r"(D[1-9]\d*)\b", title)
        if match:
            decision_id = match.group(1)
            if decision_id in decisions:
                raise TtnsError(EXIT_STATE_INVALID, f"duplicate decision ID: {decision_id}")
            decisions[decision_id] = f"### {title}\n{body}"
    for decision_id in required_d:
        if decision_id not in decisions:
            raise TtnsError(EXIT_STATE_INVALID, f"required decision has no ### subsection: {decision_id}")

    bodies = {
        "STATUS": state.status_text,
        "NEXT TASK": state.next_task,
        "INVARIANTS": sections.get("INVARIANTS", ""),
        "OPEN ISSUES": sections.get("OPEN ISSUES", ""),
    }
    if warn:
        for name, body in bodies.items():
            size = _char_count(body)
            if size > SECTION_BUDGETS[name]:
                print(f"[WARN] {name} {size} chars > {SECTION_BUDGETS[name]}", file=sys.stderr)
        for artifact in state.artifacts.values():
            size = _char_count(artifact.source_row)
            if size > SECTION_BUDGETS["ARTIFACT INDEX"]:
                print(f"[WARN] ARTIFACT INDEX {artifact.artifact_id} {size} chars > {SECTION_BUDGETS['ARTIFACT INDEX']}", file=sys.stderr)

    header = (
        "<!-- TTNS:BOOT_SCHEMA=1 -->\n"
        f"<!-- TTNS:HANDOFF_ID={state.handoff_id} -->\n"
        f"<!-- TTNS:STATE_FINGERPRINT={state.fingerprint} -->\n"
        f"<!-- TTNS:STATE_LOCATOR={state.state_locator} -->\n"
        f"_Status: {state.status}_\n_Target: {state.target}_\n"
        f"_Last updated: {state.last_updated}_\n_Superseded by: {state.superseded_by}_"
    )
    start = []
    if state.orientation_block is not None:
        start.append(_marked_block("ORIENTATION", state.orientation_block))
    for label in ("Next", "Highest-risk rules", "Read order"):
        lines = re.findall(rf"(?m)^- (?:\*\*{label}:\*\*|{label}:) .*$", sections.get("START HERE", ""))
        if len(lines) > 1:
            raise TtnsError(EXIT_STATE_INVALID, f"duplicate START HERE {label} line")
        start.extend(lines)
    parts = ["## START HERE\n" + "\n".join(start)]
    for name, body in (("INVIOLABLE_CONSTRAINTS", state.constraints),
                       ("ACTIVE_ACTION_GUARDS", state.guards),
                       ("STATUS", state.status_text), ("NEXT_TASK", state.next_task)):
        parts.append(f"## {name.replace('_', ' ')}\n" + _marked_block(name, body))
    parts.append("## INVARIANTS\n" + bodies["INVARIANTS"])
    artifact_header = next(line for line in state.canonical_bytes.decode("utf-8").splitlines()
                           if line.startswith("| ID | Locator on this machine |"))
    artifact_table = "\n".join([artifact_header, "|---|---|---|---|---|"] +
                               [state.artifacts[item].source_row for item in state.required_artifact_ids])
    parts.append("## ARTIFACT INDEX\n" + artifact_table)
    decision_text = "".join(decisions[item] for item in required_d)
    parts.append("## DECISIONS\n" + decision_text)
    parts.append("## OPEN ISSUES\n" + bodies["OPEN ISSUES"])
    included = {"START HERE", "INVIOLABLE CONSTRAINTS", "ACTIVE ACTION GUARDS",
                "STATUS", "NEXT TASK", "INVARIANTS", "ARTIFACT INDEX", "DECISIONS", "OPEN ISSUES"}
    omitted = [name for name in sections if name not in included]
    # Older states may use inline D# records; they remain visible in the omission index.
    all_d = dict.fromkeys(re.findall(r"(?m)^(?:### |[-*] \*\*)(D[1-9]\d*)\b", sections.get("DECISIONS", "")))
    for name, ids in (("DECISIONS", [item for item in all_d if item not in required_d]),
                      ("ARTIFACT INDEX", [item for item in state.artifacts if item not in state.required_artifact_ids])):
        if ids:
            omitted.append(name + " " + ",".join(ids))
    completeness = ["## Completeness"]
    for prefix, body in (("C", state.constraints), ("G", state.guards)):
        ids = re.findall(rf"(?m)^- \*\*({prefix}[1-9]\d*):\*\*", body)
        completeness.append(f"- {prefix}# IDs: {','.join(ids) or 'none'}; count: {len(ids)}; body SHA-256: {state_fingerprint(body.encode('utf-8'))}")
    completeness.extend(f"- Omitted: {name} (read in the state when needed)" for name in omitted)
    if not omitted:
        completeness.append("- Omitted: none")
    base = "\n\n".join(parts) + "\n\n" + "\n".join(completeness) + "\n"

    def compose(exceeded: bool) -> str:
        count = 0
        while True:
            marker = f"<!-- TTNS:BOOT_BUDGET=exceeded {count}/{BOOT_BUDGET_CHARS} -->\n" if exceeded else ""
            result = header + "\n" + marker + "\n" + base + f"- Boot characters: {count}/{BOOT_BUDGET_CHARS}\n"
            if len(result) == count:
                return result
            count = len(result)

    rendered = compose(False)
    if len(rendered) > BOOT_BUDGET_CHARS:
        if not emergency:
            sizes = {name: _char_count(body) for name, body in bodies.items()}
            sizes.update({"ARTIFACT INDEX": _char_count(artifact_table), "DECISIONS": _char_count(decision_text)})
            largest = sorted(sizes.items(), key=lambda item: (-item[1], item[0]))[:3]
            advice = ", ".join(f"{name} ({size} chars)" for name, size in largest)
            raise TtnsError(EXIT_STATE_INVALID,
                            f"boot view {len(rendered)} chars > {BOOT_BUDGET_CHARS}; reduce at least "
                            f"{len(rendered) - BOOT_BUDGET_CHARS} chars; largest reducible sections: {advice}")
        rendered = compose(True)
    return rendered.encode("utf-8")


def default_boot_path(relay_path: Path) -> Path:
    name = relay_path.name
    return relay_path.with_name(name.replace("ttns-relay-", "ttns-boot-", 1)
                                if "ttns-relay-" in name else relay_path.stem + ".boot.md")


def _boot_locator(state: ParsedState, boot_path: Path) -> str:
    if state.target == "same-machine":
        return str(boot_path.resolve())
    relative = os.path.relpath(boot_path, state.path.parent).replace("\\", "/")
    if not _safe_relative(relative):
        raise TtnsError(EXIT_STATE_INVALID, "cross-machine boot must be beside or below the state")
    return "state-relative:" + relative


def save_boot(state_path: Path, out: Path | None, *, emergency: bool = False) -> bytes:
    raw = _read_bytes(state_path, label="state")
    state = parse_state(state_path, raw)
    rendered = render_boot(state, emergency=emergency)
    if out is not None:
        if out.resolve() == state.path:
            raise TtnsError(EXIT_STATE_INVALID, "state and boot paths must differ")
        def unchanged():
            if _read_bytes(state_path, label="state") != raw:
                raise TtnsError(EXIT_RELAY_STALE, "state changed during boot")
        atomic_replace(out, rendered, unchanged)
        if _read_bytes(out, label="boot") != rendered:
            raise TtnsError(EXIT_IO, "boot read-back mismatch")
        unchanged()
    return rendered


def load_relay_template_for_schema(
    schema: str, script_path: Path | None = None
) -> str:
    if schema not in RELAY_SCHEMAS:
        raise TtnsError(
            EXIT_RELAY_STALE, f"unsupported_schema: TTNS:RELAY_SCHEMA={schema}"
        )
    filename, expected_tokens = RELAY_SCHEMAS[schema]
    script = Path(script_path or __file__).resolve()
    path = script.parent.parent / "assets" / filename
    raw = _read_bytes(path, label="relay template")
    text = canonical_utf8_lf(raw).decode("utf-8")
    begin = "<!-- TTNS:BEGIN:RELAY_TEMPLATE -->"
    end = "<!-- TTNS:END:RELAY_TEMPLATE -->"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise TtnsError(EXIT_INTERNAL, "shipped relay template markers are invalid")
    body = text[text.index(begin) + len(begin) : text.index(end)]
    body = body.removeprefix("\n").removesuffix("\n")
    found = set(re.findall(r"@@TTNS_[A-Z_]+@@", body))
    if found != expected_tokens:
        raise TtnsError(EXIT_INTERNAL, "shipped relay template tokens are invalid")
    return body + "\n"


def load_relay_template_v1(script_path: Path | None = None) -> str:
    """Frozen pre-v0.6.0 relay template body, kept only to verify old saved relays."""
    return load_relay_template_for_schema("1", script_path)


_SCHEMA_LINE_RE = re.compile(r"(?m)^<!-- TTNS:RELAY_SCHEMA=([^\s]*) -->$")


def _relay_schema(relay_text: str) -> str:
    matches = _SCHEMA_LINE_RE.findall(relay_text)
    if len(matches) != 1:
        # Missing/duplicated schema declaration makes the relay unverifiable. That
        # is a relay-trust problem, not a state-content problem, so it maps to the
        # same EXIT_RELAY_STALE bucket as a stale/tampered relay, not EXIT_STATE_INVALID.
        raise TtnsError(
            EXIT_RELAY_STALE,
            "saved relay must declare exactly one TTNS:RELAY_SCHEMA",
        )
    return matches[0]


def _required_artifacts(state: ParsedState) -> str:
    if not state.required_artifact_ids:
        return "None."
    lines = [
        "| ID | Locator on this machine | What it is | Cheapest safe verification | Portable locator |",
        "|---|---|---|---|---|",
    ]
    lines.extend(state.artifacts[item].source_row for item in state.required_artifact_ids)
    return "\n".join(lines)


def render_relay(
    state: ParsedState, template: str, relay_path: Path,
    *, boot_locator: str | None = None, boot: bytes | None = None,
) -> bytes:
    values = {
        "@@TTNS_HANDOFF_ID@@": state.handoff_id,
        "@@TTNS_STATUS@@": state.status,
        "@@TTNS_TARGET@@": state.target,
        "@@TTNS_STATE_LOCATOR@@": state.state_locator,
        "@@TTNS_STATE_ABS_PATH@@": str(state.path),
        "@@TTNS_RELAY_ABS_PATH@@": str(Path(relay_path).resolve()),
        "@@TTNS_STATE_FINGERPRINT@@": state.fingerprint,
        "@@TTNS_STATUS_TEXT@@": state.status_text,
        "@@TTNS_NEXT_TASK@@": state.next_task,
        "@@TTNS_REQUIRED_ARTIFACT_IDS@@": (
            ", ".join(state.required_artifact_ids)
            if state.required_artifact_ids
            else "none"
        ),
        "@@TTNS_REQUIRED_ARTIFACTS@@": _required_artifacts(state),
        "@@TTNS_INVIOLABLE_CONSTRAINTS@@": state.constraints,
        "@@TTNS_ACTIVE_ACTION_GUARDS@@": state.guards,
    }
    if state.orientation_block is not None:
        values[ORIENTATION_TOKEN] = state.orientation_block
    if boot is not None and boot_locator is not None:
        values["@@TTNS_BOOT_LOCATOR@@"] = boot_locator
        values["@@TTNS_BOOT_FINGERPRINT@@"] = state_fingerprint(boot)
    token_pattern = re.compile(
        "|".join(re.escape(token) for token in sorted(values, key=len, reverse=True))
    )
    rendered = token_pattern.sub(lambda match: values[match.group(0)], template)
    if re.search(r"@@TTNS_[A-Z_]+@@", rendered):
        raise TtnsError(EXIT_INTERNAL, "unrendered relay token")
    if boot is not None:
        marker = _boot_budget_marker(boot)
        if marker:
            rendered = rendered.replace("<!-- TTNS:RELAY_SCHEMA=5 -->\n",
                                        "<!-- TTNS:RELAY_SCHEMA=5 -->\n" + marker, 1)
    return canonical_utf8_lf(rendered.encode("utf-8"))


def atomic_replace(path: Path, data: bytes, pre_replace_check=None) -> None:
    path = Path(path).resolve()
    parent = path.parent
    if not parent.is_dir():
        raise TtnsError(EXIT_IO, f"destination directory does not exist: {parent}")
    temp_path: Path | None = None
    try:
        fd, name = tempfile.mkstemp(
            prefix=".ttns-", suffix=".tmp", dir=str(parent)
        )
        temp_path = Path(name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if pre_replace_check is not None:
            pre_replace_check()
        os.replace(temp_path, path)
        temp_path = None
    except TtnsError:
        raise
    except OSError as exc:
        raise TtnsError(EXIT_IO, f"atomic save failed: {path}") from exc
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _ensure_live(state: ParsedState) -> None:
    if state.status not in LIVE_STATUSES:
        raise TtnsError(
            EXIT_RELAY_STALE, f"terminal state cannot launch work: {state.status}"
        )


def finalize_pair(state_path: Path, relay_path: Path, boot_path: Path | None = None,
                  *, emergency: bool = False) -> bytes:
    state_path = Path(state_path).resolve()
    relay_path = Path(relay_path).resolve()
    if state_path == relay_path:
        raise TtnsError(EXIT_STATE_INVALID, "state and relay paths must differ")
    original_state = _read_bytes(state_path, label="state")
    state = parse_state(state_path, original_state)
    _ensure_live(state)
    template = load_relay_template_for_schema(STATE_TO_RELAY_SCHEMA[state.schema])
    boot = None
    locator = None
    if state.schema == "2" or boot_path is not None:
        boot_path = Path(boot_path or default_boot_path(relay_path)).resolve()
        if boot_path in {state_path, relay_path}:
            raise TtnsError(EXIT_STATE_INVALID, "state, relay, and boot paths must differ")
        boot = render_boot(state, emergency=emergency)
        locator = _boot_locator(state, boot_path)
    rendered = render_relay(state, template, relay_path, boot_locator=locator, boot=boot)

    def state_is_unchanged():
        if _read_bytes(state_path, label="state") != original_state:
            raise TtnsError(EXIT_RELAY_STALE, "state changed during finalize")

    if boot is not None:
        atomic_replace(boot_path, boot, state_is_unchanged)
        if _read_bytes(boot_path, label="boot") != boot:
            raise TtnsError(EXIT_IO, "boot read-back mismatch")
    atomic_replace(relay_path, rendered, state_is_unchanged)
    saved = _read_bytes(relay_path, label="saved relay")
    if saved != rendered:
        raise TtnsError(EXIT_IO, "saved relay read-back mismatch")
    state_is_unchanged()
    verify_pair(state_path, relay_path)
    return saved


def verify_pair(state_path: Path, relay_path: Path, boot_path: Path | None = None) -> bytes:
    state_path = Path(state_path).resolve()
    relay_path = Path(relay_path).resolve()
    first_state = _read_bytes(state_path, label="state")
    state = parse_state(state_path, first_state)
    _ensure_live(state)
    if not relay_path.is_file():
        raise TtnsError(EXIT_RELAY_STALE, f"saved relay is missing: {relay_path}")
    first_relay = _read_bytes(relay_path, label="saved relay")
    canonical_relay = canonical_utf8_lf(first_relay)
    # verify --relay is schema-aware: each relay schema compares against its own
    # (frozen) template so old saved relays keep verifying, and only the exact
    # state-schema/relay-schema pairs finalize can produce are accepted.
    # verify --fingerprint never reaches this path (schema-independent).
    schema = _relay_schema(canonical_relay.decode("utf-8"))
    if schema not in RELAY_SCHEMAS:
        raise TtnsError(
            EXIT_RELAY_STALE, f"unsupported_schema: TTNS:RELAY_SCHEMA={schema}"
        )
    if schema not in ACCEPTED_RELAY_SCHEMAS[state.schema]:
        raise TtnsError(
            EXIT_RELAY_STALE,
            f"relay schema {schema} does not match state schema {state.schema}",
        )
    template = load_relay_template_for_schema(schema)
    boot = None
    locator = None
    first_boot = None
    if schema == "5":
        relay_text = canonical_relay.decode("utf-8")
        locators = re.findall(r"(?m)^<!-- TTNS:BOOT_LOCATOR=(.+) -->$", relay_text)
        if len(locators) != 1:
            raise TtnsError(EXIT_RELAY_STALE, "relay needs exactly one boot locator")
        locator = locators[0]
        if locator.startswith("state-relative:") and _safe_relative(locator.removeprefix("state-relative:")):
            located = state_path.parent / locator.removeprefix("state-relative:")
        elif _is_absolute_path(locator):
            located = Path(locator)
        else:
            raise TtnsError(EXIT_RELAY_STALE, "invalid boot locator")
        boot_path = Path(boot_path or located).resolve()
        if boot_path in {state_path, relay_path} or not boot_path.is_file():
            raise TtnsError(EXIT_RELAY_STALE, "saved boot is missing or its path conflicts")
        first_boot = _read_bytes(boot_path, label="boot")
        # Emergency is accepted only when both generated files carry the exact marker.
        boot = render_boot(state, emergency=True, warn=False)
        if first_boot != boot:
            raise TtnsError(EXIT_RELAY_STALE, "boot is stale or was edited")
    expected = render_relay(state, template, relay_path, boot_locator=locator, boot=boot)
    if canonical_relay != expected:
        raise TtnsError(EXIT_RELAY_STALE, "relay is stale or was edited")
    if _read_bytes(state_path, label="state") != first_state:
        raise TtnsError(EXIT_RELAY_STALE, "state changed during verify")
    if _read_bytes(relay_path, label="saved relay") != first_relay:
        raise TtnsError(EXIT_RELAY_STALE, "relay changed during verify")
    if first_boot is not None and _read_bytes(boot_path, label="boot") != first_boot:
        raise TtnsError(EXIT_RELAY_STALE, "boot changed during verify")
    return first_relay


def verify_fingerprint(state_path: Path, expected: str) -> None:
    state_path = Path(state_path).resolve()
    raw = _read_bytes(state_path, label="state")
    state = parse_state(state_path, raw)
    _ensure_live(state)
    if state.fingerprint != expected:
        raise TtnsError(EXIT_RELAY_STALE, "state fingerprint does not match relay")
    if _read_bytes(state_path, label="state") != raw:
        raise TtnsError(EXIT_RELAY_STALE, "state changed during verify")


def copy_box(saved_relay: bytes) -> bytes:
    if not saved_relay.endswith(b"\n"):
        raise TtnsError(EXIT_INTERNAL, "saved relay must end with LF")
    runs = [len(match) for match in re.findall(rb"`+", saved_relay)]
    fence = b"`" * max(4, (max(runs) + 1) if runs else 4)
    return fence + b"\n" + saved_relay + fence + b"\n"


def close_state(
    state_path: Path, status: str, superseded_by: str | None = None
) -> None:
    state_path = Path(state_path).resolve()
    original = _read_bytes(state_path, label="state")
    state = parse_state(state_path, original)
    _ensure_live(state)
    if status not in TERMINAL_STATUSES:
        raise TtnsError(EXIT_STATE_INVALID, "close status must be terminal")
    if status == "superseded":
        if not superseded_by or _has_placeholder(superseded_by):
            raise TtnsError(
                EXIT_STATE_INVALID, "superseded close needs --superseded-by"
            )
        successor_ok = (
            _valid_portable(superseded_by)
            if state.target == "cross-machine"
            else (_is_absolute_path(superseded_by) or _valid_portable(superseded_by))
        )
        if not successor_ok:
            raise TtnsError(
                EXIT_STATE_INVALID, "invalid --superseded-by locator"
            )
    elif superseded_by:
        raise TtnsError(
            EXIT_STATE_INVALID, "--superseded-by is only valid with superseded"
        )

    text = canonical_utf8_lf(original).decode("utf-8")
    text, count = re.subn(
        r"^_Status: (active|waiting_user)_$",
        lambda _match: f"_Status: {status}_",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise TtnsError(EXIT_STATE_INVALID, "live Status field not found")
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    text, count = re.subn(
        r"^_Last updated: .*_$",
        lambda _match: f"_Last updated: {stamp}_",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise TtnsError(EXIT_STATE_INVALID, "Last updated field not found")
    successor = superseded_by if status == "superseded" else "none"
    text, count = re.subn(
        r"^_Superseded by: .*_$",
        lambda _match: f"_Superseded by: {successor}_",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise TtnsError(EXIT_STATE_INVALID, "Superseded by field not found")
    updated = canonical_utf8_lf(text.encode("utf-8"))

    def state_is_unchanged():
        if _read_bytes(state_path, label="state") != original:
            raise TtnsError(EXIT_RELAY_STALE, "state changed during close")

    atomic_replace(state_path, updated, state_is_unchanged)
    closed = parse_state(state_path)
    if closed.status != status:
        raise TtnsError(EXIT_IO, "closed state read-back mismatch")


def _iso_timestamp(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp is not an ISO string")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return stamp.astimezone(timezone.utc)


def _closed_time(record: dict) -> datetime | None:
    """Accept cost-state records and explicit costState payload equivalents."""
    if record.get("type") == "cost-state":
        payload = record.get("costState", record.get("cost-state", record.get("data", record)))
    elif "costState" in record or "cost-state" in record:
        payload = record.get("costState", record.get("cost-state"))
    else:
        return None
    if not isinstance(payload, dict):
        raise ValueError("invalid cost-state payload")
    start, duration = payload.get("startTime"), payload.get("totalDuration")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (start, duration)) or duration < 0:
        raise ValueError("invalid cost-state timing")
    return datetime.fromtimestamp((start + duration) / 1000, timezone.utc)


def session_liveness(path: Path, stat, cutoff: datetime, now: datetime) -> dict:
    last = None
    closed = None
    problems = set()
    try:
        with path.open("rb") as handle:
            offset = max(0, stat.st_size - LIVENESS_TAIL_BYTES)
            handle.seek(offset)
            tail = handle.read(LIVENESS_TAIL_BYTES)
        if offset:
            # The first tail fragment may be a partial UTF-8 character or JSON record.
            tail = tail.partition(b"\n")[2]
        for line in tail.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("record is not an object")
                if record.get("type") in {"user", "assistant"}:
                    last = _iso_timestamp(record.get("timestamp"))
                candidate = _closed_time(record)
                if candidate is not None:
                    closed = candidate
            except (ValueError, TypeError, OverflowError, OSError):
                problems.add("unsupported or malformed tail record")
    except OSError as exc:
        raise TtnsError(EXIT_IO, f"cannot inspect session: {path.stem}") from exc
    if problems:
        verdict, reason = "unknown", "; ".join(sorted(problems))
    elif last is not None and cutoff <= last <= now:
        verdict, reason = "running", "recent user/assistant timestamp"
    elif last is not None and closed is not None and last <= closed < cutoff:
        verdict, reason = "exited", "closure follows last utterance and predates window"
    else:
        verdict = "unknown"
        reason = ("no user/assistant timestamp in bounded tail" if last is None
                  else "timestamps do not establish recent activity or an old closure")
    return {
        "verdict": verdict, "session": path.stem,
        "last_utterance": last.isoformat() if last else None,
        "closed_at": closed.isoformat() if closed else None,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "size": stat.st_size, "reason": reason,
    }


def liveness(projects_dir: Path, self_id: str | None, since_minutes: float) -> dict:
    if not math.isfinite(since_minutes) or since_minutes <= 0:
        raise TtnsError(EXIT_IO, "since-minutes must be finite and positive")
    now = datetime.now(timezone.utc)
    try:
        cutoff = now - timedelta(minutes=since_minutes)
        if not projects_dir.is_dir():
            raise OSError("projects directory is missing")
        sessions = []
        # Discover actual project directories; never synthesize a project slug.
        def scan_error(error):
            raise error
        for root, dirs, files in os.walk(projects_dir, onerror=scan_error, followlinks=False):
            dirs.sort()
            for name in sorted(files):
                path = Path(root) / name
                if path.suffix != ".jsonl" or path.stem == self_id or path.is_symlink():
                    continue
                stat = path.stat()
                if stat.st_mtime < cutoff.timestamp():
                    continue
                sessions.append(session_liveness(path, stat, cutoff, now))
        return {"sessions": sessions,
                "summary": {verdict: sum(row["verdict"] == verdict for row in sessions)
                            for verdict in ("running", "exited", "unknown")}}
    except (OSError, ValueError, OverflowError) as exc:
        raise TtnsError(EXIT_IO, "cannot complete liveness scan") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="deterministic to-the-next-session relay helper"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    finalize = sub.add_parser("finalize")
    finalize.add_argument("--state", required=True, type=Path)
    finalize.add_argument("--relay", required=True, type=Path)
    finalize.add_argument("--boot", type=Path)
    finalize.add_argument("--emergency", action="store_true")

    boot = sub.add_parser("boot")
    boot.add_argument("--state", required=True, type=Path)
    boot.add_argument("--out", type=Path)
    boot.add_argument("--emergency", action="store_true")

    live = sub.add_parser("liveness")
    live.add_argument("--projects-dir", type=Path, default=Path.home() / ".claude" / "projects")
    live.add_argument("--self", dest="self_id", default=os.environ.get("CLAUDE_CODE_SESSION_ID"))
    live.add_argument("--since-minutes", type=float, default=30)
    live.add_argument("--json", action="store_true")

    verify = sub.add_parser("verify")
    verify.add_argument("--state", required=True, type=Path)
    verify.add_argument("--boot", type=Path)
    target = verify.add_mutually_exclusive_group(required=True)
    target.add_argument("--relay", type=Path)
    target.add_argument("--fingerprint")

    emit = sub.add_parser("emit")
    emit.add_argument("--state", required=True, type=Path)
    emit.add_argument("--relay", required=True, type=Path)
    emit.add_argument("--boot", type=Path)

    close = sub.add_parser("close")
    close.add_argument("--state", required=True, type=Path)
    close.add_argument(
        "--status", required=True, choices=sorted(TERMINAL_STATUSES)
    )
    close.add_argument("--superseded-by")
    return parser


def _write_stdout(data: bytes) -> None:
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "finalize":
            saved = finalize_pair(args.state, args.relay, args.boot, emergency=args.emergency)
            _write_stdout(copy_box(saved))
        elif args.command == "boot":
            saved = save_boot(args.state, args.out, emergency=args.emergency)
            _write_stdout(saved if args.out is None else b"TTNS_BOOT_OK\n")
        elif args.command == "liveness":
            result = liveness(args.projects_dir, args.self_id, args.since_minutes)
            if args.json:
                output = json.dumps(result, ensure_ascii=True, indent=2) + "\n"
            else:
                lines = []
                for row in result["sessions"]:
                    fields = [row["verdict"]] + [f"{key}={row[key] if row[key] is not None else 'none'}"
                        for key in ("session", "last_utterance", "closed_at", "mtime", "size")]
                    if row["verdict"] == "unknown":
                        fields.append("reason=" + row["reason"])
                    lines.append("\t".join(fields))
                lines.append("summary: " + " ".join(f"{k}={v}" for k, v in result["summary"].items()))
                output = "\n".join(lines) + "\n"
            _write_stdout(output.encode("utf-8"))
        elif args.command == "verify":
            if args.relay is not None:
                verify_pair(args.state, args.relay, args.boot)
            else:
                verify_fingerprint(args.state, args.fingerprint)
            _write_stdout(b"TTNS_VERIFY_OK\n")
        elif args.command == "emit":
            saved = verify_pair(args.state, args.relay, args.boot)
            _write_stdout(copy_box(saved))
        elif args.command == "close":
            close_state(args.state, args.status, args.superseded_by)
            _write_stdout(f"TTNS_CLOSE_OK status={args.status}\n".encode("ascii"))
        return 0
    except TtnsError as exc:
        prefix = {
            EXIT_STATE_INVALID: "TTNS_STATE_INVALID",
            EXIT_RELAY_STALE: "TTNS_RELAY_STALE",
            EXIT_IO: "TTNS_IO_ERROR",
        }.get(exc.code, "TTNS_INTERNAL_ERROR")
        print(f"{prefix}: {exc}", file=sys.stderr)
        return exc.code
    except Exception as exc:
        print(
            f"TTNS_INTERNAL_ERROR: unexpected {type(exc).__name__}",
            file=sys.stderr,
        )
        return EXIT_INTERNAL

def _configure_utf8_stdio():
    """CLI entry only (never on import): UTF-8 stdout/stderr with replacement so cp932 consoles never raise
    UnicodeEncodeError, and strict UTF-8 stdin because piped data (JSON specs, prompts) is a UTF-8 contract
    where corruption must surface, not be hidden (procedures/encoding-policy.md)."""
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    try:
        sys.stdin.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass


if __name__ == "__main__":
    _configure_utf8_stdio()
    sys.exit(main())
