#!/usr/bin/env python3
"""Contract tests for the deterministic to-the-next-session relay helper."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
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
        self.root = REPO.parent / f".ttns-test-{self.token}"
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.state = self.root / "01_state.md"
        self.relay = self.root / "02_relay.md"
        self.artifact = self.root / "artifact.txt"
        self.artifact.write_text("ground truth\n", encoding="utf-8")

    def state_text(
        self,
        *,
        status="active",
        target="same-machine",
        state_locator=None,
        superseded_by="none",
        portable_locator="—",
        required="A1",
        constraints=None,
        guards=None,
        next_task=None,
    ):
        if state_locator is None:
            state_locator = str(self.state)
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

_TTNS schema: 1_
_Handoff ID: fixture-001_
_Status: {status}_
_Target: {target}_
_State locator: {state_locator}_
_Last updated: 2026-07-11T12:00:00+09:00_
_Superseded by: {superseded_by}_

## START HERE
- Resume from the canonical state, never from `/compact`.

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
| A1 | `{self.artifact}` | required ground truth | read and compare | {portable_locator} |
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

    def test_source_and_codex_helper_and_assets_are_byte_identical(self):
        if not CODEX_ROOT.is_dir():
            self.skipTest("standalone public package has no vendored Codex port")
        self.assertEqual(
            HELPER.read_bytes(),
            (CODEX_ROOT / "scripts" / "handoff.py").read_bytes(),
        )
        for name in ("state-file-template.md", "relay-prompt-template.md"):
            self.assertEqual(
                (SKILL_ROOT / "assets" / name).read_bytes(),
                (CODEX_ROOT / "assets" / name).read_bytes(),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
