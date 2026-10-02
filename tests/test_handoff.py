#!/usr/bin/env python3
"""Contract tests for the deterministic to-the-next-session relay helper."""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
import uuid
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
if (REPO / "SKILL.md").is_file():
    SKILL_ROOT = REPO
else:
    SKILL_ROOT = REPO / "skills" / "to-the-next-session"
HELPER = SKILL_ROOT / "scripts" / "handoff.py"
CODEX_ROOT = REPO / "codex" / "agents-skills" / "to-the-next-session"


def load_helper():
    spec = importlib.util.spec_from_file_location("ttns_handoff", HELPER)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load helper: {HELPER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HandoffContractTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.token = uuid.uuid4().hex
        temporary = tempfile.TemporaryDirectory(prefix=".ttns-test-", dir=Path(__file__).parent)
        self.root = Path(temporary.name)
        self.addCleanup(temporary.cleanup)
        self.state = self.root / "01_state.md"
        self.relay = self.root / "02_relay.md"
        self.artifact = self.root / "artifact.txt"
        self.artifact.write_text("ground truth\n", encoding="utf-8")

    def orientation(
        self,
        *,
        goal="Ship the fixture change end-to-end",
        done_when="All fixture tests pass and the relay round-trips",
        phase="Implementation is in flight",
        waiting="none",
    ):
        return (
            "<!-- TTNS:BEGIN:ORIENTATION -->\n"
            f"- **Goal:** {goal}\n"
            f"- **Done when:** {done_when}\n"
            f"- **Current phase:** {phase}\n"
            f"- **Waiting on:** {waiting}\n"
            "<!-- TTNS:END:ORIENTATION -->"
        )

    def state_text(
        self,
        *,
        schema="1",
        status="active",
        target="same-machine",
        state_locator=None,
        superseded_by="none",
        portable_locator="—",
        required="A1",
        constraints=None,
        guards=None,
        next_task=None,
        start_here=None,
        artifact_locator=None,
    ):
        if state_locator is None:
            state_locator = str(self.state)
        if artifact_locator is None:
            artifact_locator = str(self.artifact)
        if start_here is None:
            if schema == "2":
                start_here = self.orientation()
            else:
                start_here = "- Resume from the canonical state, never from `/compact`."
        if constraints is None:
            constraints = (
                "- **C1:** Keep the threshold exactly ≥ 80.\n"
                "  Continuation text includes ```literal```.\n"
                "- **C2:** Do NOT publish before explicit authorization."
            )
        if guards is None:
            guards = "- **G1:** Push and deploy remain forbidden until explicit user instruction."
        if next_task is None:
            next_task = (
                "Inspect A1 and perform exactly one deterministic continuation step.\n"
                f"Required artifact IDs: {required}"
            )
        return f"""# TO THE NEXT SESSION — fixture

_TTNS schema: {schema}_
_Handoff ID: fixture-001_
_Status: {status}_
_Target: {target}_
_State locator: {state_locator}_
_Last updated: 2026-07-11T12:00:00+09:00_
_Superseded by: {superseded_by}_

## START HERE
{start_here}

## INVIOLABLE CONSTRAINTS
<!-- TTNS:BEGIN:INVIOLABLE_CONSTRAINTS -->
{constraints}
<!-- TTNS:END:INVIOLABLE_CONSTRAINTS -->

## ACTIVE ACTION GUARDS
<!-- TTNS:BEGIN:ACTIVE_ACTION_GUARDS -->
{guards}
<!-- TTNS:END:ACTIVE_ACTION_GUARDS -->

## STATUS
<!-- TTNS:BEGIN:STATUS -->
One phase is complete; the next phase has not started. 日本語の状態も逐語で残す。
<!-- TTNS:END:STATUS -->

## NEXT TASK
<!-- TTNS:BEGIN:NEXT_TASK -->
{next_task}
<!-- TTNS:END:NEXT_TASK -->

## ARTIFACT INDEX
| ID | Locator on this machine | What it is | Cheapest safe verification | Portable locator |
|---|---|---|---|---|
| A1 | `{artifact_locator}` | required ground truth | read and compare | {portable_locator} |
| A2 | `{self.root / 'deferred.txt'}` | deferred material | read only if needed | — |

## INVARIANTS
- Goal: preserve exact continuation across a cold session.

## DECISIONS
- **D1:** Chosen: deterministic relay. Because: stale relays were observed. Rejected: summary-only. Source: user approval.

## OPEN ISSUES
- None.
"""

    def write_state(self, **kwargs):
        text = self.state_text(**kwargs)
        self.state.write_text(text, encoding="utf-8", newline="\n")
        return text

    def write_state_v2(self, *, waiting="none", **kwargs):
        return self.write_state(
            schema="2", start_here=self.orientation(waiting=waiting), **kwargs
        )

    def run_helper(self, *args):
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, str(HELPER), *map(str, args)],
            cwd=self.root,
            capture_output=True,
            env=env,
            check=False,
        )

    def finalize(self):
        return self.run_helper(
            "finalize", "--state", self.state, "--relay", self.relay
        )

    def extract_copy_box(self, stdout):
        first, sep, rest = stdout.partition(b"\n")
        self.assertTrue(sep, stdout)
        self.assertGreaterEqual(len(first), 4)
        self.assertEqual(set(first), {ord("`")})
        closing = b"\n" + first + b"\n"
        self.assertTrue(rest.endswith(closing), stdout)
        return rest[: -len(closing)] + b"\n"

    def test_finalize_saves_and_emits_exact_saved_relay(self):
        self.write_state()
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        saved = self.relay.read_bytes()
        self.assertEqual(self.extract_copy_box(result.stdout), saved)
        self.assertEqual(result.stderr, b"")
        self.assertRegex(saved.decode("utf-8"), r"sha256-lf:[0-9a-f]{64}")

    def test_relay_copies_c_g_status_and_next_blocks_verbatim(self):
        source = self.write_state()
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        relay = self.relay.read_text(encoding="utf-8")
        for name in (
            "INVIOLABLE_CONSTRAINTS",
            "ACTIVE_ACTION_GUARDS",
            "STATUS",
            "NEXT_TASK",
        ):
            match = re.search(
                rf"<!-- TTNS:BEGIN:{name} -->\n(.*?)\n<!-- TTNS:END:{name} -->",
                source,
                re.DOTALL,
            )
            self.assertIsNotNone(match)
            self.assertIn(match.group(1), relay)
        self.assertIn("Required artifact IDs: A1", relay)
        self.assertNotIn("deferred material", relay)

    def test_sha256_lf_normalization_contract(self):
        helper = load_helper()
        text = "α\nβ\n"
        variants = (
            text.encode("utf-8"),
            ("α\r\nβ\r\n").encode("utf-8"),
            ("\ufeffα\rβ").encode("utf-8"),
        )
        fingerprints = {helper.state_fingerprint(v) for v in variants}
        self.assertEqual(len(fingerprints), 1)
        base = helper.state_fingerprint("é\n".encode("utf-8"))
        self.assertNotEqual(base, helper.state_fingerprint("é \n".encode("utf-8")))
        self.assertNotEqual(base, helper.state_fingerprint("é\n\n".encode("utf-8")))
        self.assertNotEqual(
            base,
            helper.state_fingerprint(unicodedata.normalize("NFD", "é\n").encode("utf-8")),
        )

    def test_state_change_and_relay_tamper_block_verify_and_emit(self):
        self.write_state()
        initial = self.finalize()
        self.assertEqual(initial.returncode, 0, initial.stderr.decode(errors="replace"))
        self.state.write_text(
            self.state.read_text(encoding="utf-8").replace(
                "exactly one deterministic continuation step",
                "a different continuation step",
            ),
            encoding="utf-8",
            newline="\n",
        )
        for command in ("verify", "emit"):
            result = self.run_helper(
                command, "--state", self.state, "--relay", self.relay
            )
            self.assertEqual(result.returncode, 4)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"TTNS_RELAY_STALE", result.stderr)

        self.write_state()
        self.assertEqual(self.finalize().returncode, 0)
        original_digest = re.search(
            rb"sha256-lf:[0-9a-f]{64}", self.relay.read_bytes()
        ).group(0)
        self.relay.write_bytes(
            self.relay.read_bytes().replace(b"One phase is complete", b"One phase was altered")
        )
        self.assertIn(original_digest, self.relay.read_bytes())
        result = self.run_helper(
            "emit", "--state", self.state, "--relay", self.relay
        )
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")

    def test_invalid_states_never_overwrite_an_existing_relay(self):
        self.relay.write_bytes(b"previous relay\n")
        cases = {
            "missing marker": self.state_text().replace(
                "<!-- TTNS:END:STATUS -->", "<!-- removed -->"
            ),
            "duplicate constraint id": self.state_text().replace(
                "- **C2:**", "- **C1:**"
            ),
            "missing required artifact": self.state_text(required="A9"),
            "placeholder locator": self.state_text(state_locator="[fill me]"),
            "relative same-machine locator": self.state_text(state_locator="state.md"),
            "branch-only cross-machine": self.state_text(
                target="cross-machine",
                state_locator="repo:https://example.invalid/repo.git@main#state.md",
                portable_locator="state-relative:artifact.txt",
            ),
            "missing required portable locator": self.state_text(
                target="cross-machine",
                state_locator=(
                    "repo:https://example.invalid/repo.git@"
                    + "a" * 40
                    + "#state.md"
                ),
                portable_locator="—",
            ),
            "reserved relay token": self.state_text(
                constraints=(
                    "- **C1:** Preserve this literal @@TTNS_ACTIVE_ACTION_GUARDS@@.\n"
                    "- **C2:** Do not publish."
                )
            ),
            "template sentinel": self.state_text(
                constraints=(
                    "- **C1:** [task-wide correctness or scope rule, copied verbatim].\n"
                    "- **C2:** Do not publish."
                )
            ),
            "superseded without successor": self.state_text(status="superseded"),
            "live with successor": self.state_text(
                status="active",
                superseded_by=str(self.root / "next-state.md"),
            ),
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.state.write_text(text, encoding="utf-8", newline="\n")
                result = self.finalize()
                self.assertEqual(result.returncode, 3)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(self.relay.read_bytes(), b"previous relay\n")

    def test_cross_machine_immutable_locator_and_required_artifact_pass(self):
        locator = (
            "repo:https://example.invalid/repo.git@"
            + "a" * 40
            + "#handoff/01_TO_THE_NEXT_SESSION.md"
        )
        self.write_state(
            target="cross-machine",
            state_locator=locator,
            portable_locator="state-relative:artifact.txt",
        )
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn(locator.encode("utf-8"), self.relay.read_bytes())

    def test_waiting_user_is_live_but_terminal_states_cannot_emit(self):
        self.write_state(
            status="waiting_user",
            required="none",
            next_task=(
                "Wait for the user's named decision; perform no task mutation.\n"
                "Required artifact IDs: none"
            ),
        )
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn(b"waiting_user", self.relay.read_bytes())

        terminal_states = (
            ("complete", "none"),
            ("superseded", str(self.root / "next-state.md")),
            ("abandoned", "none"),
        )
        for status, successor in terminal_states:
            with self.subTest(status=status):
                self.write_state(status=status, superseded_by=successor)
                result = self.finalize()
                self.assertEqual(result.returncode, 4)
                self.assertEqual(result.stdout, b"")

    def test_atomic_replace_failure_and_state_race_preserve_old_relay(self):
        helper = load_helper()
        original = b"old relay\n"
        self.relay.write_bytes(original)
        self.write_state()
        with mock.patch.object(helper.os, "replace", side_effect=OSError("boom")):
            with self.assertRaises(helper.TtnsError) as caught:
                helper.finalize_pair(self.state, self.relay)
        self.assertEqual(caught.exception.code, 5)
        self.assertEqual(self.relay.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".ttns-*.tmp")), [])

        real_atomic = helper.atomic_replace

        def racing_replace(path, data, pre_replace_check=None):
            self.state.write_text(
                self.state.read_text(encoding="utf-8").replace(
                    "One phase is complete", "State changed during finalize"
                ),
                encoding="utf-8",
                newline="\n",
            )
            return real_atomic(path, data, pre_replace_check)

        with mock.patch.object(helper, "atomic_replace", side_effect=racing_replace):
            with self.assertRaises(helper.TtnsError) as caught:
                helper.finalize_pair(self.state, self.relay)
        self.assertEqual(caught.exception.code, 4)
        self.assertEqual(self.relay.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".ttns-*.tmp")), [])

    def test_dynamic_fence_exceeds_internal_backtick_run(self):
        helper = load_helper()
        relay = b"inside ``````` fence\n"
        boxed = helper.copy_box(relay)
        fence = boxed.split(b"\n", 1)[0]
        self.assertGreater(len(fence), 7)
        self.assertEqual(self.extract_copy_box(boxed), relay)
        with self.assertRaises(helper.TtnsError) as caught:
            helper.copy_box(b"relay without final LF")
        self.assertEqual(caught.exception.code, 1)

    def test_close_invalidates_old_relay_without_rewriting_it(self):
        self.write_state()
        self.assertEqual(self.finalize().returncode, 0)
        old_relay = self.relay.read_bytes()
        result = self.run_helper(
            "close", "--state", self.state, "--status", "complete"
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn("_Status: complete_", self.state.read_text(encoding="utf-8"))
        self.assertEqual(self.relay.read_bytes(), old_relay)
        for command in ("verify", "emit"):
            stale = self.run_helper(
                command, "--state", self.state, "--relay", self.relay
            )
            self.assertEqual(stale.returncode, 4)
            self.assertEqual(stale.stdout, b"")

    def test_close_superseded_accepts_a_windows_absolute_successor(self):
        self.write_state()
        successor = r"C:\Users\K\handoff\next-state.md"
        result = self.run_helper(
            "close",
            "--state",
            self.state,
            "--status",
            "superseded",
            "--superseded-by",
            successor,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        state = self.state.read_text(encoding="utf-8")
        self.assertIn("_Status: superseded_", state)
        self.assertIn(f"_Superseded by: {successor}_", state)

    def test_schema2_state_renders_lean_schema5_relay(self):
        source = self.write_state_v2()
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        relay = self.relay.read_text(encoding="utf-8")
        self.assertIn("<!-- TTNS:RELAY_SCHEMA=5 -->", relay)
        # Orientation and the active guards are still copied verbatim.
        match = re.search(
            r"<!-- TTNS:BEGIN:ORIENTATION -->\n(.*?)\n<!-- TTNS:END:ORIENTATION -->",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertIn(match.group(1), relay)
        self.assertIn(
            "Push and deploy remain forbidden until explicit user instruction", relay
        )
        # The bootstrap gate is present; the verbose duplicated bodies are gone.
        self.assertIn("Bootstrap first", relay)
        self.assertNotIn("Keep the threshold exactly", relay)
        self.assertNotIn("日本語の状態も逐語で残す", relay)  # STATUS paragraph
        self.assertNotIn("required ground truth", relay)  # artifact row
        verify = self.run_helper(
            "verify", "--state", self.state, "--relay", self.relay
        )
        self.assertEqual(verify.returncode, 0, verify.stderr.decode(errors="replace"))

    def test_schema2_state_keeps_verifying_a_saved_schema3_relay(self):
        # A schema-2 state accepts both the lean schema-4 relay and a schema-3 relay
        # saved before the v0.8.0 lean change (rendered from the frozen v3 template).
        self.write_state_v2()
        helper = load_helper()
        state = helper.parse_state(self.state)
        frozen_v3 = helper.load_relay_template_for_schema("3")
        v3_bytes = helper.render_relay(state, frozen_v3, self.relay)
        self.assertIn(b"<!-- TTNS:RELAY_SCHEMA=3 -->\n", v3_bytes)
        self.relay.write_bytes(v3_bytes)
        for command in ("verify", "emit"):
            result = self.run_helper(
                command, "--state", self.state, "--relay", self.relay
            )
            self.assertEqual(
                result.returncode, 0, result.stderr.decode(errors="replace")
            )

    def test_schema1_state_keeps_rendering_schema2_relay_bytes(self):
        self.write_state()
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        relay_bytes = self.relay.read_bytes()
        self.assertIn(b"<!-- TTNS:RELAY_SCHEMA=2 -->\n", relay_bytes)
        self.assertNotIn(b"## Orientation", relay_bytes)
        helper = load_helper()
        state = helper.parse_state(self.state)
        frozen_v2 = helper.load_relay_template_for_schema("2")
        self.assertEqual(
            relay_bytes, helper.render_relay(state, frozen_v2, self.relay)
        )

    def test_schema2_orientation_validation_rejects_malformed(self):
        self.relay.write_bytes(b"previous relay\n")
        base = self.orientation()
        cases = {
            "missing block": "- Resume from the canonical state.",
            "wrong order": (
                "<!-- TTNS:BEGIN:ORIENTATION -->\n"
                "- **Done when:** all tests pass\n"
                "- **Goal:** ship the fixture\n"
                "- **Current phase:** in flight\n"
                "- **Waiting on:** none\n"
                "<!-- TTNS:END:ORIENTATION -->"
            ),
            "missing line": base.replace(
                "- **Current phase:** Implementation is in flight\n", ""
            ),
            "extra line": base.replace(
                "<!-- TTNS:END:ORIENTATION -->",
                "- **Extra:** unexpected fifth line\n<!-- TTNS:END:ORIENTATION -->",
            ),
            "empty value": self.orientation(goal=""),
            "placeholder value": self.orientation(goal="[TBD]"),
            "duplicate label": base.replace("- **Done when:**", "- **Goal:**"),
        }
        for label, start_here in cases.items():
            with self.subTest(label=label):
                self.write_state(schema="2", start_here=start_here)
                result = self.finalize()
                self.assertEqual(result.returncode, 3)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(self.relay.read_bytes(), b"previous relay\n")

    def test_schema2_waiting_user_requires_named_input(self):
        for empty in ("none", "None.", "n/a", "-", "—"):
            with self.subTest(value=empty):
                self.write_state_v2(status="waiting_user", waiting=empty)
                self.assertEqual(self.finalize().returncode, 3)
        self.write_state_v2(
            status="waiting_user",
            waiting="The user's decision on the design approval question",
        )
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.write_state_v2(status="active", waiting="none")
        self.assertEqual(self.finalize().returncode, 0)

    def test_verify_rejects_state_relay_schema_mismatch(self):
        helper = load_helper()
        self.write_state_v2()
        state = helper.parse_state(self.state)
        frozen_v2 = helper.load_relay_template_for_schema("2")
        self.relay.write_bytes(helper.render_relay(state, frozen_v2, self.relay))
        result = self.run_helper(
            "verify", "--state", self.state, "--relay", self.relay
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn(b"schema", result.stderr)

        self.write_state()
        self.assertEqual(self.finalize().returncode, 0)
        mutated = self.relay.read_bytes().replace(
            b"<!-- TTNS:RELAY_SCHEMA=2 -->", b"<!-- TTNS:RELAY_SCHEMA=3 -->"
        )
        self.relay.write_bytes(mutated)
        result = self.run_helper(
            "verify", "--state", self.state, "--relay", self.relay
        )
        self.assertEqual(result.returncode, 4)

    def test_locator_values_with_placeholder_like_substrings_are_accepted(self):
        cases = (
            str(self.root / "Todo-project" / "notes.md"),
            str(self.root / "[2026]report" / "notes.md"),
        )
        for locator in cases:
            with self.subTest(locator=locator):
                self.write_state(artifact_locator=locator)
                result = self.finalize()
                self.assertEqual(
                    result.returncode, 0, result.stderr.decode(errors="replace")
                )
        for placeholder in ("TBD", "<pending>", "[fill me]"):
            with self.subTest(placeholder=placeholder):
                self.write_state(artifact_locator=placeholder)
                self.assertEqual(self.finalize().returncode, 3)

    def test_low_context_template_ships_only_required_tokens_and_finalizes(self):
        template_path = SKILL_ROOT / "assets" / "state-file-template-low-context.md"
        text = template_path.read_text(encoding="utf-8")
        tokens = set(re.findall(r"@@TTNS_FILL_[A-Z0-9_]+@@", text))
        expected = {
            "@@TTNS_FILL_TASK_NAME@@",
            "@@TTNS_FILL_HANDOFF_ID@@",
            "@@TTNS_FILL_LIFECYCLE_STATUS@@",
            "@@TTNS_FILL_TARGET@@",
            "@@TTNS_FILL_STATE_LOCATOR@@",
            "@@TTNS_FILL_LAST_UPDATED@@",
            "@@TTNS_FILL_GOAL@@",
            "@@TTNS_FILL_DONE_WHEN@@",
            "@@TTNS_FILL_CURRENT_PHASE@@",
            "@@TTNS_FILL_WAITING_ON@@",
            "@@TTNS_FILL_CONSTRAINTS_BLOCK@@",
            "@@TTNS_FILL_GUARDS_BLOCK@@",
            "@@TTNS_FILL_STATUS@@",
            "@@TTNS_FILL_NEXT_TASK@@",
            "@@TTNS_FILL_NEXT_TASK_ARTIFACT_IDS@@",
            "@@TTNS_FILL_ARTIFACT_ROWS@@",
        }
        self.assertEqual(tokens, expected)
        self.assertIn("TTNS:LOW_CONTEXT_AUDIT=required", text)
        fills = {
            "@@TTNS_FILL_TASK_NAME@@": "emergency fixture",
            "@@TTNS_FILL_HANDOFF_ID@@": "fixture-low-context",
            "@@TTNS_FILL_LIFECYCLE_STATUS@@": "active",
            "@@TTNS_FILL_TARGET@@": "same-machine",
            "@@TTNS_FILL_STATE_LOCATOR@@": str(self.state),
            "@@TTNS_FILL_LAST_UPDATED@@": "2026-07-16T12:00:00+09:00",
            "@@TTNS_FILL_GOAL@@": "Finish the fixture migration",
            "@@TTNS_FILL_DONE_WHEN@@": "All fixture tests pass",
            "@@TTNS_FILL_CURRENT_PHASE@@": "Implementation is in flight",
            "@@TTNS_FILL_WAITING_ON@@": "none",
            "@@TTNS_FILL_CONSTRAINTS_BLOCK@@": "- **C1:** Same-machine only.",
            "@@TTNS_FILL_GUARDS_BLOCK@@": "- None.",
            "@@TTNS_FILL_STATUS@@": "Capture written under low context.",
            "@@TTNS_FILL_NEXT_TASK@@": (
                "Run the single continuation step and stop."
            ),
            "@@TTNS_FILL_NEXT_TASK_ARTIFACT_IDS@@": "A1",
            "@@TTNS_FILL_ARTIFACT_ROWS@@": (
                f"| A1 | `{self.artifact}` | required ground truth "
                "| read and compare | — |"
            ),
        }
        filled = text
        for token, value in fills.items():
            filled = filled.replace(token, value)
        self.state.write_text(filled, encoding="utf-8", newline="\n")
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn(b"<!-- TTNS:RELAY_SCHEMA=5 -->\n", self.relay.read_bytes())

    def test_close_works_on_schema2_state(self):
        self.write_state_v2()
        self.assertEqual(self.finalize().returncode, 0)
        result = self.run_helper(
            "close", "--state", self.state, "--status", "complete"
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn("_Status: complete_", self.state.read_text(encoding="utf-8"))
        stale = self.run_helper(
            "verify", "--state", self.state, "--relay", self.relay
        )
        self.assertEqual(stale.returncode, 4)

    def test_standard_template_with_inline_fill_comments_finalizes(self):
        source = (SKILL_ROOT / "assets" / "state-file-template.md").read_text(encoding="utf-8")
        fills = {
            "LIFECYCLE_STATUS": "active", "TARGET": "same-machine",
            "STATE_LOCATOR": str(self.state), "LAST_UPDATED": "2026-10-03T00:00:00+00:00",
            "NEXT_TASK_ARTIFACT_IDS": "A1", "NEXT_TASK_DECISION_IDS": "D1",
            "A1_LOCATOR": str(self.artifact), "A2_LOCATOR": str(self.artifact),
            "A1_PORTABLE": "none", "A2_PORTABLE": "none", "WAITING_ON": "none",
        }
        source = re.sub(r"@@TTNS_FILL_([A-Z0-9_]+)@@", lambda m: fills.get(m.group(1), "fixture-value"), source)
        self.state.write_text(source, encoding="utf-8")
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        boot = (self.root / "02_relay.boot.md").read_text(encoding="utf-8")
        self.assertIn("### D1", boot)
        for label in ("Next", "Highest-risk rules", "Read order"):
            self.assertIn(f"- **{label}:**", boot)
        self.assertNotIn("MUST7 boot budget", boot)

    def test_boot_selects_complete_blocks_and_required_rows_and_decisions(self):
        source = self.write_state_v2()
        source = source.replace("Required artifact IDs: A1", "Required artifact IDs: A1\nRequired decision IDs: D2 <!-- fill: D3, D7 or none -->")
        source = source.replace("## DECISIONS\n", "## DECISIONS\n### D1 — omitted\nOld choice.\n### D2 — required\nChosen choice.\nBecause: exact evidence.\n")
        source += "\n## EARLIER ENTRY POINTS\nPRIVATE OMITTED DETAIL\n"
        self.state.write_text(source, encoding="utf-8")
        result = self.run_helper("boot", "--state", self.state)
        self.assertEqual(result.returncode, 0, result.stderr)
        boot = result.stdout.decode("utf-8")
        self.assertIn("<!-- TTNS:BOOT_SCHEMA=1 -->", boot)
        for name in ("ORIENTATION", "INVIOLABLE_CONSTRAINTS", "ACTIVE_ACTION_GUARDS", "STATUS", "NEXT_TASK"):
            block = re.search(rf"<!-- TTNS:BEGIN:{name} -->.*?<!-- TTNS:END:{name} -->", source, re.S).group()
            self.assertIn(block, boot)
        for included in ("## INVARIANTS", "## OPEN ISSUES", "### D2 — required", "Chosen choice.", "Because: exact evidence.", "required ground truth", "## Completeness", "EARLIER ENTRY POINTS", "DECISIONS D1", "ARTIFACT INDEX A2"):
            self.assertIn(included, boot)
        for omitted in ("### D1 — omitted", "Old choice.", "PRIVATE OMITTED DETAIL", "deferred material"):
            self.assertNotIn(omitted, boot)
        helper = load_helper()
        state = helper.parse_state(self.state)
        self.assertIn(helper.state_fingerprint(state.constraints.encode("utf-8")), boot)
        self.assertIn(helper.state_fingerprint(state.guards.encode("utf-8")), boot)
        self.assertIn(f"Boot characters: {len(boot)}/24000", boot)
        self.assertEqual(result.stdout, self.run_helper("boot", "--state", self.state).stdout)
        out = self.root / "03_boot.md"
        saved = self.run_helper("boot", "--state", self.state, "--out", out)
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertEqual(out.read_bytes(), result.stdout)

    def test_schema5_boot_is_bound_to_relay_and_checked_by_verify_and_emit(self):
        self.write_state_v2()
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        boot = self.root / "02_relay.boot.md"
        self.assertTrue(boot.is_file())
        helper = load_helper()
        self.assertIn(helper.state_fingerprint(boot.read_bytes()).encode(), self.relay.read_bytes())
        original = boot.read_bytes()
        for altered in (original.replace(b"Keep the threshold exactly", b"Change the threshold"), original.replace(b"\n", b"\r\n")):
            boot.write_bytes(altered)
            for command in ("verify", "emit"):
                check = self.run_helper(command, "--state", self.state, "--relay", self.relay)
                self.assertEqual(check.returncode, 4, check.stderr)
        boot.unlink()
        self.assertEqual(self.run_helper("verify", "--state", self.state, "--relay", self.relay).returncode, 4)
        boot.write_bytes(original)
        override = self.root / "03_moved_boot.md"
        boot.rename(override)
        check = self.run_helper("verify", "--state", self.state, "--relay", self.relay, "--boot", override)
        self.assertEqual(check.returncode, 0, check.stderr)
        custom = self.root / "04_custom_boot.md"
        result = self.run_helper("finalize", "--state", self.state, "--relay", self.relay, "--boot", custom)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(custom.is_file())
        self.assertIn(str(custom).encode(), self.relay.read_bytes())
        named = self.root / "ttns-relay-test.md"
        self.assertEqual(self.run_helper("finalize", "--state", self.state, "--relay", named).returncode, 0)
        self.assertTrue((self.root / "ttns-boot-test.md").is_file())

    def test_saved_schema4_relay_remains_verifiable(self):
        self.write_state_v2()
        helper = load_helper()
        self.relay.write_bytes(helper.render_relay(helper.parse_state(self.state), helper.load_relay_template_for_schema("4"), self.relay))
        for command in ("verify", "emit"):
            result = self.run_helper(command, "--state", self.state, "--relay", self.relay)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_section_warning_and_boot_budget_emergency(self):
        source = self.write_state_v2()
        source = re.sub(r"(?<=<!-- TTNS:BEGIN:STATUS -->\n).*?(?=\n<!-- TTNS:END:STATUS -->)", "x" * 2100, source, flags=re.S)
        self.state.write_text(source, encoding="utf-8")
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"[WARN] STATUS 2101 chars > 2000", result.stderr)
        source = source.replace("x" * 2100, "x" * 26000)
        self.state.write_text(source, encoding="utf-8")
        old = self.relay.read_bytes()
        for command, extra in (("boot", ()), ("finalize", ("--relay", self.relay))):
            result = self.run_helper(command, "--state", self.state, *extra)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"24000", result.stderr)
            self.assertIn(b"STATUS", result.stderr)
        self.assertEqual(self.relay.read_bytes(), old)
        emergency = self.run_helper("finalize", "--state", self.state, "--relay", self.relay, "--emergency")
        self.assertEqual(emergency.returncode, 0, emergency.stderr)
        boot = (self.root / "02_relay.boot.md").read_text(encoding="utf-8")
        marker = f"<!-- TTNS:BOOT_BUDGET=exceeded {len(boot)}/24000 -->"
        self.assertIn(marker, boot)
        self.assertIn(marker.encode(), self.relay.read_bytes())
        self.assertEqual(self.run_helper("verify", "--state", self.state, "--relay", self.relay).returncode, 0)
        self.assertEqual(self.run_helper("boot", "--state", self.state, "--emergency").stdout.decode(), boot)

    def test_required_decisions_are_optional_but_must_exist_when_named(self):
        source = self.write_state_v2()
        self.assertEqual(self.finalize().returncode, 0)
        for ids in ("D9", "D1, D1", "A1", "none\nRequired decision IDs: none"):
            self.state.write_text(source.replace("Required artifact IDs: A1", f"Required artifact IDs: A1\nRequired decision IDs: {ids}"), encoding="utf-8")
            self.assertEqual(self.finalize().returncode, 3)

    def test_all_section_budgets_warn_without_truncating_protected_text(self):
        source = self.write_state_v2()
        source = source.replace("## INVARIANTS\n", "## INVARIANTS\n" + "i" * 2100 + "\n")
        source = source.replace("## OPEN ISSUES\n", "## OPEN ISSUES\n" + "o" * 3100 + "\n")
        source = source.replace("Inspect A1", "n" * 1600 + " Inspect A1")
        source = source.replace("required ground truth", "a" * 450)
        self.state.write_text(source, encoding="utf-8")
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in (b"NEXT TASK", b"OPEN ISSUES", b"INVARIANTS", b"ARTIFACT INDEX A1"):
            self.assertIn(b"[WARN] " + name, result.stderr)
        constraint = "- **C1:** " + "c" * 25000
        self.write_state_v2(constraints=constraint)
        result = self.run_helper("boot", "--state", self.state)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertNotIn(b"INVIOLABLE", result.stderr)
        emergency = self.run_helper("boot", "--state", self.state, "--emergency")
        self.assertEqual(emergency.returncode, 0, emergency.stderr)
        self.assertIn(constraint.encode(), emergency.stdout)

    def test_boot_ignores_headings_inside_code_and_comments(self):
        source = self.write_state_v2()
        source = source.replace("## INVARIANTS\n", "## INVARIANTS\n```markdown\n## NOT A SECTION\n```\n<!--\n## ALSO NOT A SECTION\n-->\n")
        self.state.write_text(source, encoding="utf-8")
        result = self.run_helper("boot", "--state", self.state)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"## NOT A SECTION", result.stdout)
        self.assertNotIn(b"Omitted: NOT A SECTION", result.stdout)
        self.assertIn(b"Goal: preserve exact", result.stdout)

    def test_cross_machine_boot_locator_relocates_with_state(self):
        self.write_state_v2(target="cross-machine", state_locator="sync:fixture#01_state.md", portable_locator="state-relative:artifact.txt")
        self.assertEqual(self.finalize().returncode, 0)
        self.assertIn(b"TTNS:BOOT_LOCATOR=state-relative:02_relay.boot.md", self.relay.read_bytes())
        moved = self.root / "moved"
        moved.mkdir()
        for path in (self.state, self.relay, self.root / "02_relay.boot.md"):
            shutil.copy2(path, moved / path.name)
        result = self.run_helper("verify", "--state", moved / self.state.name, "--relay", moved / self.relay.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        fingerprint = load_helper().parse_state(self.state).fingerprint
        self.assertEqual(self.run_helper("verify", "--state", self.state, "--fingerprint", fingerprint).returncode, 0)

    def test_boot_fingerprint_marker_tampering_is_rejected(self):
        self.write_state_v2()
        self.assertEqual(self.finalize().returncode, 0)
        original = self.relay.read_bytes()
        tampered = re.sub(rb"(TTNS:BOOT_FINGERPRINT=sha256-lf:)[0-9a-f]{64}", rb"\g<1>" + b"0"*64, original)
        self.relay.write_bytes(tampered)
        self.assertEqual(self.run_helper("verify", "--state", self.state, "--relay", self.relay).returncode, 4)

    def test_liveness_tail_bound_and_ambiguous_or_malformed_records(self):
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(minutes=1)).isoformat()
        old = (now - timedelta(hours=2)).isoformat()
        path = self.root / "bounded.jsonl"
        recent_record = json.dumps({"type": "assistant", "timestamp": recent}) + "\n"
        # Invalid earlier bytes and an oversized body must never be read or quoted.
        path.write_bytes(b"not JSON\n" + b"x" * (256*1024) + b"\n" + recent_record.encode())
        result = self.run_helper("liveness", "--projects-dir", self.root, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["summary"]["running"], 1)
        for records in ([{"type": "user", "timestamp": old}],
                        [{"type": "user", "timestamp": recent}, {"type": "assistant", "timestamp": "bad"}],
                        [{"type": "assistant", "timestamp": old}, {"type": "cost-state", "startTime": 0, "totalDuration": 1}],
                        [{"type": "assistant", "timestamp": old}, {"type": "cost-state", "startTime": 0, "totalDuration": "bad"}]):
            path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
            result = self.run_helper("liveness", "--projects-dir", self.root, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["summary"]["unknown"], 1)
        failure = self.run_helper("liveness", "--projects-dir", self.root / "missing")
        self.assertEqual(failure.returncode, 5)
        self.assertEqual(failure.stdout, b"")

    def test_liveness_three_verdicts_self_exclusion_and_no_body_output(self):
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(minutes=2)).isoformat()
        old = (now - timedelta(hours=2)).isoformat()
        closed = now - timedelta(hours=1)
        project = self.root / "project"
        project.mkdir()
        samples = {
            "running": [{"type": "user", "timestamp": recent, "message": "NEVER PRINT THIS BODY"}],
            "exited": [{"type": "assistant", "timestamp": old}, {"type": "cost-state", "startTime": int((closed - timedelta(seconds=10)).timestamp()*1000), "totalDuration": 10000}],
            "unknown": [{"type": "progress", "timestamp": recent, "message": "NEVER PRINT THIS BODY"}],
        }
        for name, records in samples.items():
            (project / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        result = self.run_helper("liveness", "--projects-dir", self.root, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["summary"], {"running": 1, "exited": 1, "unknown": 1})
        self.assertNotIn(b"NEVER PRINT", result.stdout)
        self.assertTrue(next(r for r in data["sessions"] if r["verdict"] == "unknown")["reason"])
        plain = self.run_helper("liveness", "--projects-dir", self.root, "--self", "running")
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertNotIn(b"session=running", plain.stdout)
        self.assertIn(b"summary: running=0 exited=1 unknown=1", plain.stdout)
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "exited"}):
            env_self = self.run_helper("liveness", "--projects-dir", self.root)
        self.assertNotIn(b"session=exited", env_self.stdout)
        os.utime(project / "running.jsonl", (now.timestamp()-7200, now.timestamp()-7200))
        stale = self.run_helper("liveness", "--projects-dir", self.root, "--self", "exited", "--json")
        self.assertEqual(json.loads(stale.stdout)["summary"], {"running": 0, "exited": 0, "unknown": 1})

    def test_source_and_codex_helper_and_assets_are_byte_identical(self):
        if not CODEX_ROOT.is_dir():
            self.skipTest("standalone public package has no vendored Codex port")
        self.assertEqual(
            HELPER.read_bytes(),
            (CODEX_ROOT / "scripts" / "handoff.py").read_bytes(),
        )
        for name in (
            "state-file-template.md",
            "state-file-template-low-context.md",
            "relay-prompt-template.md",
            "relay-prompt-template-v1.md",
            "relay-prompt-template-v2.md",
            "relay-prompt-template-v3.md",
        ):
            self.assertEqual(
                (SKILL_ROOT / "assets" / name).read_bytes(),
                (CODEX_ROOT / "assets" / name).read_bytes(),
            )

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
    unittest.main(verbosity=2)
