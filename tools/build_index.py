#!/usr/bin/env python3
"""Regenerate index.json from topics/*.md. Run after every content change.

Use --check to verify index.json is up to date without writing it.
"""
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
NAME = re.compile(r"(\d{2})-([a-z0-9-]+)\.md")


def quiz_entry(topic_ids: set) -> dict:
    """Validates quiz.json and returns its index entry."""
    data = (ROOT / "quiz.json").read_bytes()
    quiz = json.loads(data)
    seen = set()
    for q in quiz["questions"]:
        label = f"quiz question '{q.get('id')}'"
        if q["id"] in seen:
            sys.exit(f"{label}: duplicate id")
        seen.add(q["id"])
        if q["topic"] not in topic_ids:
            sys.exit(f"{label}: unknown topic '{q['topic']}'")
        if not 2 <= len(q["options"]) <= 6:
            sys.exit(f"{label}: needs 2 to 6 options")
        if not 0 <= q["answer"] < len(q["options"]):
            sys.exit(f"{label}: answer is not an option index")
        if not q["question"] or not q["explanation"]:
            sys.exit(f"{label}: question and explanation are required")
    return {"path": "quiz.json", "sha256": hashlib.sha256(data).hexdigest()}


def build() -> str:
    topics, ids = [], set()
    for path in sorted((ROOT / "topics").glob("*.md")):
        match = NAME.fullmatch(path.name)
        if not match:
            sys.exit(f"{path.name}: expected NN-lower-case-slug.md")
        data = path.read_bytes()
        first = data.decode("utf-8").split("\n", 1)[0]
        if not first.startswith("# "):
            sys.exit(f"{path.name}: first line must be '# Title'")
        if match[2] in ids:
            sys.exit(f"{path.name}: duplicate topic id '{match[2]}'")
        ids.add(match[2])
        topics.append({
            "id": match[2],
            "number": int(match[1]),
            "title": first[2:].strip(),
            "path": f"topics/{path.name}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    if not topics:
        sys.exit("no topics found")
    index = {"schemaVersion": 1, "title": "Senior Android Developer Interview Prep Guide", "topics": topics, "quiz": quiz_entry(ids)}
    return json.dumps(index, indent=2) + "\n"


if __name__ == "__main__":
    target = ROOT / "index.json"
    text = build()
    if "--check" in sys.argv:
        if not target.exists() or target.read_text() != text:
            sys.exit("index.json is stale: run tools/build_index.py")
    else:
        target.write_text(text)
    print("index.json OK")
