"""Tests for the validator: each kind of broken content must be rejected."""
import copy
import hashlib
import json
import unittest

from validate_content import validate_bundle, validate_markdown, validate_version_change

BUNDLE = {
    "schemaVersion": 1,
    "version": 2,
    "topics": [{"id": "kotlin", "number": 1, "title": "Kotlin", "notes": "# Kotlin"}],
    "questions": [{"id": "q1", "topic": "kotlin", "text": "Why?", "answer": "Because.",
                   "level": "Easy", "tracks": ["junior"], "why": "W.", "mistake": "M."}],
    "quiz": [{"id": "z1", "topic": "kotlin", "question": "Which?", "options": ["a", "b"],
              "answer": 1, "explanation": "b.", "why": "W.", "mistake": "M.", "tracks": ["senior"]}],
}


def encode(bundle, **pointer_changes):
    data = json.dumps(bundle).encode()
    pointer = {"schemaVersion": 1, "version": bundle.get("version"),
               "sha256": hashlib.sha256(data).hexdigest()} | pointer_changes
    return json.dumps(pointer).encode(), data


class BundleTest(unittest.TestCase):
    def errors_after(self, change):
        bundle = copy.deepcopy(BUNDLE)
        change(bundle)
        return validate_bundle(*encode(bundle))

    def test_valid_content_passes(self):
        self.assertEqual([], validate_bundle(*encode(BUNDLE)))

    def test_level_and_code_may_be_missing(self):
        self.assertEqual([], self.errors_after(lambda b: b["questions"][0].pop("level")))

    def test_broken_structures_fail(self):
        changes = {
            "missing field": lambda b: b["questions"][0].pop("answer"),
            "misspelt field": lambda b: b["questions"][0].update(levle="Easy"),
            "number as text": lambda b: b["topics"][0].update(number="1"),
            "true as a number": lambda b: b["quiz"][0].update(answer=True),
            "empty title": lambda b: b["topics"][0].update(title=" "),
            "topics not a list": lambda b: b.update(topics={}),
            "no topics": lambda b: b.update(topics=[]),
            "no questions": lambda b: b.update(questions=[]),
            "duplicate id": lambda b: b["questions"].append(b["questions"][0]),
            "unknown question topic": lambda b: b["questions"][0].update(topic="x"),
            "unknown quiz topic": lambda b: b["quiz"][0].update(topic="x"),
            "unknown level": lambda b: b["questions"][0].update(level="Expert"),
            "one option": lambda b: b["quiz"][0].update(options=["a"], answer=0),
            "option not text": lambda b: b["quiz"][0].update(options=["a", 2]),
            "answer out of range": lambda b: b["quiz"][0].update(answer=2),
            "wrong schema": lambda b: b.update(schemaVersion=2),
            "item not an object": lambda b: b["questions"].append("text"),
            "no why": lambda b: b["questions"][0].pop("why"),
            "follow-up not text": lambda b: b["questions"][0].update(followUp=["x"]),
            "empty mistake": lambda b: b["questions"][0].update(mistake=" "),
            "no tracks": lambda b: b["questions"][0].update(tracks=[]),
            "badly written track": lambda b: b["questions"][0].update(tracks=["System Design"]),
            "quiz without tracks": lambda b: b["quiz"][0].pop("tracks"),
            "quiz without why": lambda b: b["quiz"][0].pop("why"),
            "quiz with a blank mistake": lambda b: b["quiz"][0].update(mistake=" "),
            "unknown kind": lambda b: b["quiz"][0].update(kind="riddle"),
            "bug lines on a concept question": lambda b: b["quiz"][0].update(bugLines=[1]),
            "bug line past the code": lambda b: b["quiz"][0].update(
                kind="bug", code="a\nb", bugLines=[3]),
            "bug line that is blank": lambda b: b["quiz"][0].update(
                kind="bug", code="a\n\nb", bugLines=[2]),
            "no bug lines listed": lambda b: b["quiz"][0].update(
                kind="bug", code="a", bugLines=[]),
            "bug line not a number": lambda b: b["quiz"][0].update(
                kind="bug", code="a", bugLines=[True]),
            "code question without code": lambda b: b["quiz"][0].update(kind="output"),
            "badly written review date":
                lambda b: b["questions"][0].update(reviewed="27/11/2026"),
            "review date in the future":
                lambda b: b["questions"][0].update(reviewed="2999-01-01"),
        }
        for name, change in changes.items():
            with self.subTest(name):
                self.assertTrue(self.errors_after(change))

    def test_new_tracks_and_past_review_dates_are_allowed(self):
        self.assertEqual([], self.errors_after(
            lambda b: b["questions"][0].update(tracks=["acme-set-1"], reviewed="2026-01-31")))

    def test_checksum_and_version_must_match(self):
        self.assertTrue(validate_bundle(*encode(BUNDLE, sha256="0" * 64)))
        self.assertTrue(validate_bundle(*encode(BUNDLE, version=3)))

    def test_invalid_json_fails(self):
        pointer, _ = encode(BUNDLE)
        self.assertTrue(validate_bundle(pointer, b"{ not json"))
        self.assertTrue(validate_bundle(b'{"version":1,"version":2}', b"{}"))


class MarkdownTest(unittest.TestCase):
    def check(self, body):
        return validate_markdown("t.md", "# T\n\n" + body)

    def test_supported_markdown_passes(self):
        self.assertEqual([], self.check(
            "### Interview questions\n\n1. **Why?** Because `a{}`. {Hard}\n2. **How?** So.\n\n"
            "```\n  - not a list\n> not a quote\n```\n\n"
            "### Rapid-fire questions\n\n| Q | A | Level |\n| - | - | - |\n| a? | b | Easy |\n"))

    def test_mistakes_that_would_lose_content_fail(self):
        bad = {
            "no bold question": "### Interview questions\n\n1. Why? Because.",
            "no answer": "### Interview questions\n\n1. **Why?**",
            "bad level tag": "### Interview questions\n\n1. **Why?** So. {easy}",
            "wrapped answer": "### Interview questions\n\n1. **Why?** One\ntwo.",
            "bulleted question": "### Interview questions\n\n- **Why?** So.",
            "repeated question": "### Interview questions\n\n1. **A?** x\n2. **A?** y",
            "empty rapid-fire answer":
                "### Rapid-fire questions\n\n| Q | A |\n| - | - |\n| a? |  |",
            "bad rapid-fire level":
                "### Rapid-fire questions\n\n| Q | A | L |\n| - | - | - |\n| a? | b | Hrd |",
            "nested list": "- a\n  - b",
            "image": "![x](y.png)",
            "quote": "> x",
            "unclosed code": "```kotlin\nval a = 1",
        }
        for name, body in bad.items():
            with self.subTest(name):
                self.assertTrue(self.check(body))

    def test_title_is_required(self):
        self.assertTrue(validate_markdown("t.md", "text"))


class VersionChangeTest(unittest.TestCase):
    def change(self, version, answer="Because."):
        old = encode(BUNDLE)
        bundle = copy.deepcopy(BUNDLE)
        bundle["version"] = version
        bundle["questions"][0]["answer"] = answer
        return validate_version_change(*encode(bundle), *old)

    def test_changed_content_needs_a_higher_version(self):
        self.assertTrue(self.change(2, "New."))
        self.assertTrue(self.change(1, "New."))
        self.assertEqual([], self.change(3, "New."))

    def test_unchanged_content_keeps_its_version(self):
        self.assertEqual([], self.change(2))
        self.assertTrue(self.change(3))


if __name__ == "__main__":
    unittest.main()
