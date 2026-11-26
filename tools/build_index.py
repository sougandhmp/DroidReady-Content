#!/usr/bin/env python3
"""Regenerate the published files from topics/*.md and quiz.json.

Run after every content change. It writes:

  questions.json  everything the app needs, in one file
  version.json    a small file the app checks first; the version goes up by one
                  whenever questions.json changes
  index.json      used by older builds of the app

Use --check to verify the generated files are up to date without writing them.
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


HEADING = re.compile(r"(#{1,6}) +(.*)")
NUMBERED = re.compile(r"(\d+)\. +(.*)")
QUESTION = re.compile(r"\*\*(.+?)\*\*\s+(.+)")
LEVEL_TAG = re.compile(r" *\{(Easy|Medium|Hard)\}$")
DIVIDER = re.compile(r"\|?[ :|-]*-[ :|-]*\|?")
LEVELS = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}


def cells(row: str) -> list:
    """Splits a table row, keeping pipes that are escaped or inside inline code."""
    body = row.removeprefix("|").removesuffix("|")
    result, cell, in_code, i = [], "", False, 0
    while i < len(body):
        char = body[i]
        if char == "\\" and body[i + 1:i + 2] == "|":
            cell += "|"
            i += 1
        elif char == "|" and not in_code:
            result.append(cell.strip())
            cell = ""
        else:
            if char == "`":
                in_code = not in_code
            cell += char
        i += 1
    result.append(cell.strip())
    return result


def question_id(topic_id: str, text: str) -> str:
    """Stable while the topic slug and question text are unchanged."""
    return f"{topic_id}-{hashlib.sha256(text.encode()).hexdigest()[:12]}"


def questions_in(topic_id: str, markdown: str) -> list:
    found, section, in_code = {}, "", False

    def add(text, answer, level):
        key = question_id(topic_id, text)
        if key not in found:
            found[key] = {"id": key, "topic": topic_id, "text": text, "answer": answer, "level": level}

    lines = [line.strip() for line in markdown.split("\n")]
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            in_code = not in_code
        elif not in_code:
            heading = HEADING.fullmatch(line)
            numbered = NUMBERED.fullmatch(line)
            if heading:
                section = heading[2].lower()
            elif numbered and "interview questions" in section:
                text = numbered[2]
                tag = LEVEL_TAG.search(text)
                if tag:
                    text = text[:tag.start()]
                match = QUESTION.fullmatch(text)
                if match:
                    add(match[1], match[2], tag[1] if tag else None)
            elif (line.startswith("|") and "rapid-fire questions" in section
                  and i + 1 < len(lines) and DIVIDER.fullmatch(lines[i + 1])):
                i += 2
                while i < len(lines) and lines[i].startswith("|"):
                    row = cells(lines[i])
                    if len(row) >= 2:
                        level = LEVELS.get(row[2].lower()) if len(row) > 2 else None
                        add(row[0], row[1], level)
                    i += 1
                continue
        i += 1
    return list(found.values())


def to_json(value) -> str:
    return json.dumps(value, indent=1, ensure_ascii=False) + "\n"


def details_for(topic_id: str, questions: list) -> list:
    """Adds tracks, "why they ask" and the common mistake from details/<topic>.json."""
    path = ROOT / "details" / f"{topic_id}.json"
    details = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    unused = set(details) - {q["text"] for q in questions}
    if unused:
        sys.exit(f"details/{topic_id}.json: no question has the text {sorted(unused)[0]!r}")
    return [q | details.get(q["text"], {}) for q in questions]


def build_bundle(index: dict) -> dict:
    """Returns the contents of questions.json and version.json."""
    topics, questions = [], []
    for entry in index["topics"]:
        markdown = (ROOT / entry["path"]).read_text(encoding="utf-8")
        topics.append({key: entry[key] for key in ("id", "number", "title")} | {"notes": markdown})
        questions += details_for(entry["id"], questions_in(entry["id"], markdown))
    if not questions:
        sys.exit("no interview questions found")
    quiz = json.loads((ROOT / "quiz.json").read_text(encoding="utf-8"))["questions"]
    body = {"topics": topics, "questions": questions, "quiz": quiz}

    version = 0
    old_bundle, old_version = ROOT / "questions.json", ROOT / "version.json"
    unchanged = False
    if old_version.exists():
        version = json.loads(old_version.read_text())["version"]
    if old_bundle.exists():
        old = json.loads(old_bundle.read_text(encoding="utf-8"))
        unchanged = {key: old.get(key) for key in body} == body
    if not unchanged or version == 0:
        version += 1

    text = to_json({"schemaVersion": 1, "version": version} | body)
    pointer = {"schemaVersion": 1, "version": version,
               "sha256": hashlib.sha256(text.encode()).hexdigest()}
    return {"questions.json": text, "version.json": to_json(pointer)}


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


def main() -> None:
    index = build()
    outputs = {"index.json": index} | build_bundle(json.loads(index))
    if "--check" in sys.argv:
        stale = [name for name, text in outputs.items()
                 if not (ROOT / name).exists() or (ROOT / name).read_text(encoding="utf-8") != text]
        if stale:
            sys.exit(f"stale: {', '.join(stale)}. Run tools/build_index.py")
    else:
        for name, text in outputs.items():
            (ROOT / name).write_bytes(text.encode("utf-8"))
    version = json.loads(outputs["version.json"])["version"]
    bundle = json.loads(outputs["questions.json"])
    print(f"OK: version {version}, {len(bundle['topics'])} topics, "
          f"{len(bundle['questions'])} questions, {len(bundle['quiz'])} quiz questions")


if __name__ == "__main__":
    main()
