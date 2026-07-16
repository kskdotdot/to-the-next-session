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

# Pinned SHA-256 digests of the frozen relay template assets, computed over
# canonical_utf8_lf() bytes (the runtime contract: load_relay_template always
# canonicalizes before use, so a CRLF working tree — e.g. core.autocrlf=true on
# Windows — must not break the guarantee). The guarantee is therefore
# "canonical UTF-8/LF-identical", not raw byte-identical.
# v1: pre-v0.6.0 blob (`git show a6c6fca:assets/relay-prompt-template.md`).
RELAY_V1_FROZEN_SHA256 = (
    "94076c029c21dd4a9e68174e0a61f2581f5510761865ac118b37cba285956ab9"
)
# v2: the v0.6.0 relay template file frozen at the v0.7.0 schema bump.
RELAY_V2_FROZEN_SHA256 = (
    "4cca481c2dbf970788a40e33585cb3c3a63958550e10412e4040d8ab9e90a1c2"
)
# v3: the verbose v0.7.0 relay template, frozen at the v0.8.0 lean-relay change so
# schema-3 relays (and schema-2 states rendered before v0.8.0) keep verifying.
RELAY_V3_FROZEN_SHA256 = (
    "5c7cc2a986dc8ba2b79af3e1e3b4c107d97fb98be5df59b64c6b338c1247693e"
)
FROZEN_RELAY_TEMPLATES = {
    "1": ("relay-prompt-template-v1.md", RELAY_V1_FROZEN_SHA256),
    "2": ("relay-prompt-template-v2.md", RELAY_V2_FROZEN_SHA256),
    "3": ("relay-prompt-template-v3.md", RELAY_V3_FROZEN_SHA256),
}

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
        self.assertRegex(skill, r"(?m)^  version: 0\.8\.0$")
        readme = read("README.md")
        self.assertIn("version-0.8.0", readme)
        self.assertIn("Status: **v0.8.0**", readme)
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
        for template in (
            "assets/state-file-template.md",
            "assets/state-file-template-low-context.md",
        ):
            with self.subTest(template=template):
                state = read(template)
                self.assertRegex(state, r"(?m)^_TTNS schema: 2_$")
                for marker in (
                    "ORIENTATION",
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
        self.assertIn("<!-- TTNS:RELAY_SCHEMA=4 -->", relay)
        tokens = set(re.findall(r"@@TTNS_[A-Z_]+@@", relay))
        # The lean relay carries only the pointer/orientation/guard/next tokens.
        self.assertEqual(len(tokens), 9)
        self.assertIn("@@TTNS_ORIENTATION@@", tokens)
        self.assertIn("@@TTNS_ACTIVE_ACTION_GUARDS@@", tokens)
        # It drops the verbose bodies that duplicate the canonical state file.
        for dropped in (
            "@@TTNS_INVIOLABLE_CONSTRAINTS@@",
            "@@TTNS_STATUS_TEXT@@",
            "@@TTNS_REQUIRED_ARTIFACTS@@",
            "@@TTNS_STATE_ABS_PATH@@",
            "@@TTNS_RELAY_ABS_PATH@@",
        ):
            self.assertNotIn(dropped, tokens)
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
        constraints=None,
        guards=None,
        next_task=None,
        start_here=None,
    ):
        if state_locator is None:
            state_locator = str(self.state)
        if start_here is None:
            if schema == "2":
                start_here = self.orientation()
            else:
                start_here = (
                    "- Resume from the canonical state, never from `/compact`."
                )
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

_TTNS schema: {schema}_
_Handoff ID: pkgtest-fixture_
_Status: {status}_
_Target: {target}_
_State locator: {state_locator}_
_Last updated: 2026-07-14T12:00:00+09:00_
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

    # 3. Shipped templates: every placeholder matches the FILL grammar; vocabulary
    # (`[unverified]`) and legitimate literals (`- None.`) are untouched.
    def test_shipped_state_template_placeholders_all_match_fill_grammar(self):
        for name in (
            "state-file-template.md",
            "state-file-template-low-context.md",
        ):
            with self.subTest(template=name):
                template = (ROOT / "assets" / name).read_text(encoding="utf-8")
                all_reserved = re.findall(r"@@TTNS_[A-Z0-9_]+@@", template)
                self.assertTrue(
                    all_reserved, "expected at least one @@TTNS_FILL_*@@ token"
                )
                for token in all_reserved:
                    self.assertRegex(token, r"^@@TTNS_FILL_[A-Z0-9_]+@@$")
        standard = (ROOT / "assets" / "state-file-template.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`[unverified]`", standard)
        self.assertNotIn("@@TTNS_FILL_UNVERIFIED@@", standard)
        self.assertIn("- None.", standard)

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

    # 8. Frozen relay assets: canonical UTF-8/LF hash matches the pin and each
    # asset declares its own schema. Hashing canonicalized bytes matches the
    # runtime contract (load happens after canonical_utf8_lf), so a CRLF working
    # tree cannot produce a false failure.
    def test_frozen_relay_assets_match_pinned_canonical_lf_hashes(self):
        helper = load_helper()
        for schema, (name, pin) in FROZEN_RELAY_TEMPLATES.items():
            with self.subTest(schema=schema):
                raw = (ROOT / "assets" / name).read_bytes()
                digest = hashlib.sha256(helper.canonical_utf8_lf(raw)).hexdigest()
                self.assertEqual(digest, pin)
                self.assertIn(
                    f"<!-- TTNS:RELAY_SCHEMA={schema} -->",
                    raw.decode("utf-8"),
                )

    # 9. The lean v4 render (schema-2 state) keeps orientation, the still-binding G#
    # guards, the next-task preview, and the recitation ack — and drops the verbose
    # bodies (C#, artifact rows, STATUS paragraph) that duplicate the state file.
    def test_v4_lean_relay_keeps_orientation_guards_drops_verbose_bodies(self):
        self.write_state(schema="2")
        result = self.finalize()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        relay = self.relay.read_text(encoding="utf-8")
        self.assertIn("<!-- TTNS:RELAY_SCHEMA=4 -->", relay)
        # Kept: orientation, active guards verbatim, bootstrap gate, ack.
        self.assertIn("Orientation — verbatim from the state", relay)
        self.assertIn("- **Goal:** Ship the fixture change end-to-end", relay)
        self.assertIn("- **Waiting on:** none", relay)
        self.assertIn(
            "Push and deploy remain forbidden until explicit user instruction", relay
        )
        self.assertIn("Bootstrap first", relay)
        self.assertIn("authorized only after bootstrap", relay)
        self.assertIn("Goal and Waiting on", relay)
        self.assertIn("proof of compliance", relay)
        # Dropped: C# bodies, the STATUS paragraph, and the artifact table rows.
        self.assertNotIn("Keep the threshold exactly", relay)
        self.assertNotIn("One phase is complete", relay)
        self.assertNotIn("required ground truth", relay)
        # The escape hatch that let work start before the state was read is gone.
        self.assertNotIn(
            "Read-only investigation and emergency repair may proceed", relay
        )

    # 10. A schema-2 state whose saved relay is schema 3 (rendered before the v0.8.0
    # lean change, from the frozen v3 template) still verifies and emits.
    def test_saved_schema3_relay_still_verifies_and_emits(self):
        self.write_state(schema="2")
        helper = load_helper()
        state = helper.parse_state(self.state)
        v3_template = helper.load_relay_template_for_schema("3")
        v3_rendered = helper.render_relay(state, v3_template, self.relay)
        self.assertIn(b"<!-- TTNS:RELAY_SCHEMA=3 -->\n", v3_rendered)
        self.relay.write_bytes(v3_rendered)

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
        self.assertEqual(emit_result.stdout, helper.copy_box(v3_rendered))

    # 11. The lean relay's length does not depend on how long the C# constraint set
    # or STATUS paragraph is: those bodies live only in the state file now.
    def test_lean_relay_length_is_independent_of_constraint_and_status_length(self):
        small = (
            "- **C1:** Keep the threshold exactly >= 80.\n"
            "- **C2:** Do NOT publish before explicit authorization."
        )
        self.write_state(schema="2", constraints=small)
        self.assertEqual(self.finalize().returncode, 0)
        small_len = self.relay.stat().st_size

        big = "\n".join(
            f"- **C{i}:** " + ("padding constraint body " * 30) for i in range(1, 9)
        )
        big_status = "Present reality. " * 60
        self.write_state(schema="2", constraints=big)
        self.state.write_text(
            self.state.read_text(encoding="utf-8").replace(
                "One phase is complete; the next phase has not started.", big_status
            ),
            encoding="utf-8",
            newline="\n",
        )
        self.assertEqual(self.finalize().returncode, 0)
        big_len = self.relay.stat().st_size

        self.assertEqual(small_len, big_len)
        self.assertNotIn("padding constraint body", self.relay.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
