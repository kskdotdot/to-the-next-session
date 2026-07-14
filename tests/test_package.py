#!/usr/bin/env python3
"""Public-package contract tests."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "handoff.py"

# Pinned SHA-256 of assets/relay-prompt-template-v1.md, computed once from the
# pre-v0.6.0 blob (`git show a6c6fca:assets/relay-prompt-template.md | sha256sum`).
# This is the machine proof (F7) that the v1 frozen asset is byte-identical to the
# relay template as it existed immediately before this refactor.
RELAY_V1_FROZEN_SHA256 = (
    "94076c029c21dd4a9e68174e0a61f2581f5510761865ac118b37cba285956ab9"
)

# Pinned fingerprint for a fixed sample. canonical_utf8_lf/state_fingerprint were not
# touched by the v0.6.0 change; this guards against silent future drift in either.
FINGERPRINT_SAMPLE = (
    b"to-the-next-session v0.6.0 fingerprint pin sample\r\nsecond line\r\n"
)
FINGERPRINT_PIN = (
    "sha256-lf:a851bd7f56013abd47815d1d81c17a42ee076148f0db710932f9f7ad87ebbded"
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def load_helper():
    spec = importlib.util.spec_from_file_location("ttns_handoff_pkgtest", HELPER)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load helper: {HELPER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PublicPackageContractTests(unittest.TestCase):
    def test_release_version_and_public_entrypoints(self):
        skill = read("SKILL.md")
        self.assertRegex(skill, r"(?m)^  version: 0\.6\.0$")
        readme = read("README.md")
        self.assertIn("version-0.6.0", readme)
        self.assertIn("Status: **v0.6.0**", readme)
        self.assertIn("scripts/handoff.py", readme)
        self.assertNotIn("markdown-only", readme.casefold())

    def test_skill_preserves_the_two_product_cores(self):
        skill = read("SKILL.md")
        for required in (
            "/compact",
            "STATE FILE",
            "RELAY PROMPT",
            "scripts/handoff.py",
            "sole source of truth",
        ):
            self.assertIn(required, skill)
        self.assertRegex(skill, r"final fenced\s+block")
        self.assertNotIn("saved relay file is canonical", skill.casefold())

    def test_state_and_relay_schema_tokens_are_complete(self):
        state = read("assets/state-file-template.md")
        for marker in (
            "INVIOLABLE_CONSTRAINTS",
            "ACTIVE_ACTION_GUARDS",
            "STATUS",
            "NEXT_TASK",
        ):
            self.assertEqual(state.count(f"TTNS:BEGIN:{marker}"), 1)
            self.assertEqual(state.count(f"TTNS:END:{marker}"), 1)
        self.assertIn("Required artifact IDs:", state)
        self.assertIn(
            "| ID | Locator on this machine | What it is | "
            "Cheapest safe verification | Portable locator |",
            state,
        )

        relay = read("assets/relay-prompt-template.md")
        tokens = set(re.findall(r"@@TTNS_[A-Z_]+@@", relay))
        self.assertEqual(len(tokens), 13)
        for token in tokens:
            self.assertGreaterEqual(relay.count(token), 1)

    def test_openai_metadata_is_install_ready(self):
        metadata = read("agents/openai.yaml")
        short = re.search(r'(?m)^  short_description: "([^"]+)"$', metadata)
        prompt = re.search(r'(?m)^  default_prompt: "([^"]+)"$', metadata)
        self.assertIsNotNone(short)
        self.assertIsNotNone(prompt)
        self.assertTrue(25 <= len(short.group(1)) <= 64)
        self.assertIn("$to-the-next-session", prompt.group(1))
        self.assertIn("/compact", prompt.group(1))
        self.assertIn("fenced", prompt.group(1).casefold())


class FillTokenAndRelaySchemaTests(unittest.TestCase):
    """v0.6.0 additions: @@TTNS_FILL_*@@ two-stage reject, schema-aware verify,
    the v2 ack block, and the frozen v1 asset's machine-verified identity."""

    maxDiff = None

    def setUp(self):
        self.token = uuid.uuid4().hex
        self.root = ROOT.parent / f".ttns-pkgtest-{self.token}"
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
        constraints=None,
        guards=None,
        next_task=None,
    ):
        if state_locator is None:
            state_locator = str(self.state)
        if constraints is None:
            constraints = (
                "- **C1:** Keep the threshold exactly >= 80.\n"
                "- **C2:** Do NOT publish before explicit authorization."
            )
        if guards is None:
            guards = (
                "- **G1:** Push and deploy remain forbidden until explicit "
                "user instruction."
            )
        if next_task is None:
            next_task = (
                "Inspect A1 and perform exactly one deterministic continuation "
                "step.\nRequired artifact IDs: A1"
            )
        return f"""# TO THE NEXT SESSION — fixture

_TTNS schema: 1_
_Handoff ID: pkgtest-fixture_
_Status: {status}_
_Target: {target}_
_State locator: {state_locator}_
_Last updated: 2026-07-14T12:00:00+09:00_
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
One phase is complete; the next phase has not started.
<!-- TTNS:END:STATUS -->

## NEXT TASK
<!-- TTNS:BEGIN:NEXT_TASK -->
{next_task}
<!-- TTNS:END:NEXT_TASK -->

## ARTIFACT INDEX
| ID | Locator on this machine | What it is | Cheapest safe verification | Portable locator |
|---|---|---|---|---|
| A1 | `{self.artifact}` | required ground truth | read and compare | {portable_locator} |

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

    # 1. FILL residue: reject lists the unfilled tokens by name.
    def test_finalize_rejects_unfilled_fill_tokens_and_lists_them(self):
        template_text = (
            ROOT / "assets" / "state-file-template.md"
        ).read_text(encoding="utf-8")
        self.state.write_text(template_text, encoding="utf-8", newline="\n")
        result = self.finalize()
        self.assertEqual(result.returncode, 3)
        stderr = result.stderr.decode("utf-8")
        self.assertIn("unfilled", stderr.lower())
        self.assertIn("@@TTNS_FILL_TASK_NAME@@", stderr)
        self.assertIn("@@TTNS_FILL_HANDOFF_ID@@", stderr)
        # More than one distinct token must be listed, not just the first hit.
        self.assertGreaterEqual(stderr.count("@@TTNS_FILL_"), 2)

    # 2. A non-FILL reserved @@TTNS_*@@ token is a separate, distinct error.
    def test_finalize_rejects_non_fill_reserved_token_with_distinct_message(self):
        self.write_state(
            constraints=(
                "- **C1:** Preserve this literal @@TTNS_STATUS_TEXT@@ verbatim.\n"
                "- **C2:** Do NOT publish before explicit authorization."
            )
        )
        result = self.finalize()
        self.assertEqual(result.returncode, 3)
        stderr = result.stderr.decode("utf-8")
        self.assertIn("reserved", stderr.lower())
        self.assertIn("@@TTNS_STATUS_TEXT@@", stderr)
        self.assertNotIn("unfilled", stderr.lower())

    # 3. Shipped template: every placeholder matches the FILL grammar; vocabulary
    # (`[unverified]`) and legitimate literals (`- None.`) are untouched.
    def test_shipped_state_template_placeholders_all_match_fill_grammar(self):
        template = (
            ROOT / "assets" / "state-file-template.md"
        ).read_text(encoding="utf-8")
        all_reserved = re.findall(r"@@TTNS_[A-Z0-9_]+@@", template)
        self.assertTrue(all_reserved, "expected at least one @@TTNS_FILL_*@@ token")
        for token in all_reserved:
            self.assertRegex(token, r"^@@TTNS_FILL_[A-Z0-9_]+@@$")
        self.assertIn("`[unverified]`", template)
        self.assertNotIn("@@TTNS_FILL_UNVERIFIED@@", template)
        self.assertIn("- None.", template)

    # 4. A saved schema-1 relay, rendered from the frozen v1 template, still
    # verifies and emits correctly (backward-compat verify).
    def test_v1_schema_relay_still_verifies_against_frozen_template(self):
        self.write_state()
        helper = load_helper()
        state = helper.parse_state(self.state)
        v1_template = helper.load_relay_template_v1()
        v1_rendered = helper.render_relay(state, v1_template, self.relay)
        self.assertIn(b"<!-- TTNS:RELAY_SCHEMA=1 -->\n", v1_rendered)
        self.relay.write_bytes(v1_rendered)

        result = self.run_helper(
            "verify", "--state", self.state, "--relay", self.relay
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

        emit_result = self.run_helper(
            "emit", "--state", self.state, "--relay", self.relay
        )
        self.assertEqual(
            emit_result.returncode, 0, emit_result.stderr.decode(errors="replace")
        )
        self.assertEqual(emit_result.stdout, helper.copy_box(v1_rendered))

    # 5. Missing / duplicated / unrecognized TTNS:RELAY_SCHEMA are explicit errors.
    def test_relay_schema_missing_duplicate_and_unknown_are_explicit_errors(self):
        self.write_state()
        self.assertEqual(self.finalize().returncode, 0)
        base = self.relay.read_bytes()
        self.assertIn(b"<!-- TTNS:RELAY_SCHEMA=2 -->\n", base)

        cases = {
            "missing": base.replace(b"<!-- TTNS:RELAY_SCHEMA=2 -->\n", b""),
            "duplicate": base.replace(
                b"<!-- TTNS:RELAY_SCHEMA=2 -->\n",
                b"<!-- TTNS:RELAY_SCHEMA=2 -->\n<!-- TTNS:RELAY_SCHEMA=2 -->\n",
            ),
            # Malformed value: not a recognized schema number at all.
            "invalid_value": base.replace(
                b"<!-- TTNS:RELAY_SCHEMA=2 -->", b"<!-- TTNS:RELAY_SCHEMA=abc -->"
            ),
            # Well-formed but unrecognized version number.
            "unknown_value": base.replace(
                b"<!-- TTNS:RELAY_SCHEMA=2 -->", b"<!-- TTNS:RELAY_SCHEMA=99 -->"
            ),
        }
        for label, mutated in cases.items():
            with self.subTest(label=label):
                self.relay.write_bytes(mutated)
                result = self.run_helper(
                    "verify", "--state", self.state, "--relay", self.relay
                )
                self.assertEqual(result.returncode, 4)
                stderr = result.stderr.decode("utf-8")
                self.assertIn("TTNS_RELAY_STALE", stderr)
                if label in ("invalid_value", "unknown_value"):
                    self.assertIn("unsupported_schema", stderr)
                else:
                    self.assertIn("RELAY_SCHEMA", stderr)

    # 6. The v2 render carries the TTNS:SKILL= line and every ack element.
    def test_v2_relay_has_skill_meta_line_and_all_ack_elements(self):
        self.write_state()
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        relay = self.relay.read_text(encoding="utf-8")
        self.assertIn("<!-- TTNS:SKILL=to-the-next-session -->", relay)
        self.assertIn("<!-- TTNS:RELAY_SCHEMA=2 -->", relay)
        self.assertIn("Handoff ID", relay)
        self.assertRegex(relay, r"verify\s+result")
        self.assertIn("C# and G# ID list", relay)
        self.assertIn("STATUS in one line", relay)
        self.assertIn("the single NEXT TASK", relay)
        self.assertIn("Last updated", relay)
        self.assertIn("not proof of compliance", relay)

    # 7. Fingerprint algorithm non-regression against a pinned v0.5.1-era digest.
    def test_fingerprint_algorithm_matches_pinned_digest(self):
        helper = load_helper()
        self.assertEqual(
            helper.state_fingerprint(FINGERPRINT_SAMPLE), FINGERPRINT_PIN
        )

    # 8. The frozen v1 asset's bytes match the pinned pre-refactor blob hash.
    def test_v1_frozen_asset_matches_pinned_pre_refactor_blob_hash(self):
        v1_path = ROOT / "assets" / "relay-prompt-template-v1.md"
        digest = hashlib.sha256(v1_path.read_bytes()).hexdigest()
        self.assertEqual(digest, RELAY_V1_FROZEN_SHA256)


if __name__ == "__main__":
    unittest.main(verbosity=2)
