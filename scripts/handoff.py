#!/usr/bin/env python3
"""Deterministic state-to-relay transport for to-the-next-session.

The model writes and judges the state. This helper only validates the mechanical
schema, renders exact marked blocks, detects stale relays, saves atomically, and
emits a copy box from saved bytes.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
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
# Relay schema registry: filename and exact token set per schema. v1/v2 are frozen
# assets kept only so old saved relays keep verifying; v3 is the live template.
RELAY_SCHEMAS = {
    "1": ("relay-prompt-template-v1.md", frozenset(TEMPLATE_TOKENS)),
    "2": ("relay-prompt-template-v2.md", frozenset(TEMPLATE_TOKENS)),
    "3": (
        "relay-prompt-template.md",
        frozenset(TEMPLATE_TOKENS | {ORIENTATION_TOKEN}),
    ),
}
STATE_SCHEMAS = {"1", "2"}
# finalize renders a state through the newest relay schema its state schema can
# fill; verify accepts exactly these pairs (no silent cross-schema acceptance).
STATE_TO_RELAY_SCHEMA = {"1": "2", "2": "3"}
ACCEPTED_RELAY_SCHEMAS = {"1": frozenset({"1", "2"}), "2": frozenset({"3"})}
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
    required_text = required_lines[0].strip()
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
    state: ParsedState, template: str, relay_path: Path
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
    token_pattern = re.compile(
        "|".join(re.escape(token) for token in sorted(values, key=len, reverse=True))
    )
    rendered = token_pattern.sub(lambda match: values[match.group(0)], template)
    if re.search(r"@@TTNS_[A-Z_]+@@", rendered):
        raise TtnsError(EXIT_INTERNAL, "unrendered relay token")
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


def finalize_pair(state_path: Path, relay_path: Path) -> bytes:
    state_path = Path(state_path).resolve()
    relay_path = Path(relay_path).resolve()
    if state_path == relay_path:
        raise TtnsError(EXIT_STATE_INVALID, "state and relay paths must differ")
    original_state = _read_bytes(state_path, label="state")
    state = parse_state(state_path, original_state)
    _ensure_live(state)
    template = load_relay_template_for_schema(STATE_TO_RELAY_SCHEMA[state.schema])
    rendered = render_relay(state, template, relay_path)

    def state_is_unchanged():
        if _read_bytes(state_path, label="state") != original_state:
            raise TtnsError(EXIT_RELAY_STALE, "state changed during finalize")

    atomic_replace(relay_path, rendered, state_is_unchanged)
    saved = _read_bytes(relay_path, label="saved relay")
    if saved != rendered:
        raise TtnsError(EXIT_IO, "saved relay read-back mismatch")
    state_is_unchanged()
    verify_pair(state_path, relay_path)
    return saved


def verify_pair(state_path: Path, relay_path: Path) -> bytes:
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
    expected = render_relay(state, template, relay_path)
    if canonical_relay != expected:
        raise TtnsError(EXIT_RELAY_STALE, "relay is stale or was edited")
    if _read_bytes(state_path, label="state") != first_state:
        raise TtnsError(EXIT_RELAY_STALE, "state changed during verify")
    if _read_bytes(relay_path, label="saved relay") != first_relay:
        raise TtnsError(EXIT_RELAY_STALE, "relay changed during verify")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="deterministic to-the-next-session relay helper"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    finalize = sub.add_parser("finalize")
    finalize.add_argument("--state", required=True, type=Path)
    finalize.add_argument("--relay", required=True, type=Path)

    verify = sub.add_parser("verify")
    verify.add_argument("--state", required=True, type=Path)
    target = verify.add_mutually_exclusive_group(required=True)
    target.add_argument("--relay", type=Path)
    target.add_argument("--fingerprint")

    emit = sub.add_parser("emit")
    emit.add_argument("--state", required=True, type=Path)
    emit.add_argument("--relay", required=True, type=Path)

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
            saved = finalize_pair(args.state, args.relay)
            _write_stdout(copy_box(saved))
        elif args.command == "verify":
            if args.relay is not None:
                verify_pair(args.state, args.relay)
            else:
                verify_fingerprint(args.state, args.fingerprint)
            _write_stdout(b"TTNS_VERIFY_OK\n")
        elif args.command == "emit":
            saved = verify_pair(args.state, args.relay)
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


if __name__ == "__main__":
    sys.exit(main())
