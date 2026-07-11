#!/usr/bin/env python3
"""Public-package contract tests."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class PublicPackageContractTests(unittest.TestCase):
    def test_release_version_and_public_entrypoints(self):
        skill = read("SKILL.md")
        self.assertRegex(skill, r"(?m)^  version: 0\.5\.0$")
        readme = read("README.md")
        self.assertIn("version-0.5.0", readme)
        self.assertIn("Status: **v0.5.0**", readme)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
