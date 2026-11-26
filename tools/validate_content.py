#!/usr/bin/env python3
"""Checks that the content can be read, in full, by the DroidReady app.

The rules for questions.json and version.json mirror the app's code:
data/remote/Dtos.kt, data/remote/ContentMapper.kt and
data/repository/ContentRepositoryImpl.kt. Change them together.

It also catches Markdown mistakes that tools/build_index.py would skip without an
error, which would make content silently disappear from the app.

Usage: validate_content.py [--base-ref REF] [--root DIR]
With --base-ref, it also checks that the content version moved correctly since REF.
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import re
import subprocess
import sys

SCHEMA_VERSION = 1
MAX_BYTES = 8 * 1024 * 1024  # RetrofitContentDataSource.MAX_BYTES
MAX_INT = 2**31 - 1  # Kotlin Int
LEVELS = ("Easy", "Medium", "Hard")
KINDS = ("output", "bug")
# Lower-case words joined by hyphens, so a new track needs no change to the app.
TRACK = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


class Optional:
    """A field the app allows to be missing or null."""

    def __init__(self, kind):
        self.kind = kind


# field -> type. These are the app's data transfer objects.
VERSION = {"schemaVersion": int, "version": int, "sha256": str}
BUNDLE = {"schemaVersion": int, "version": int, "topics": list, "questions": list, "quiz": list}
TOPIC = {"id": str, "number": int, "title": str, "notes": str}
QUESTION = {"id": str, "topic": str, "text": str, "answer": str, "level": Optional(str),
            "tracks": list, "why": str, "mistake": str, "reviewed": Optional(str),
            "followUp": Optional(str), "code": Optional(str)}
QUIZ = {"id": str, "topic": str, "question": str, "code": Optional(str),
        "options": list, "answer": int, "explanation": str, "why": str, "mistake": str,
        "tracks": list, "kind": Optional(str)}


def load_json(data: bytes, name: str, errors: list):
    def no_duplicate_keys(pairs):
        keys = [key for key, _ in pairs]
        for key in sorted({k for k in keys if keys.count(k) > 1}):
            errors.append(f"{name}: key '{key}' appears twice in one object")
        return dict(pairs)

    def no_constants(value):
        raise ValueError(f"{value} is not valid JSON")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicate_keys,
                          parse_constant=no_constants)
    except (UnicodeDecodeError, ValueError) as error:
        errors.append(f"{name}: not valid UTF-8 JSON: {error}")
        return None


def check_object(value, shape: dict, where: str, errors: list) -> bool:
    """True if [value] has exactly the fields and types of [shape]."""
    if not isinstance(value, dict):
        errors.append(f"{where}: must be an object")
        return False
    before = len(errors)
    for key in value.keys() - shape.keys():
        errors.append(f"{where}: unknown field '{key}' (the app would ignore it; is it a typo?)")
    for key, kind in shape.items():
        optional = isinstance(kind, Optional)
        if optional:
            kind = kind.kind
        item = value.get(key)
        if item is None:
            if not optional:
                errors.append(f"{where}: '{key}' is required")
        # bool is a subclass of int in Python, but not a number to the app.
        elif not isinstance(item, kind) or isinstance(item, bool):
            errors.append(f"{where}: '{key}' must be {kind.__name__}, not {type(item).__name__}")
        elif kind is int and not -MAX_INT - 1 <= item <= MAX_INT:
            errors.append(f"{where}: '{key}' is too large")
        elif kind is str and not item.strip() and not optional:
            errors.append(f"{where}: '{key}' must not be empty")
    return len(errors) == before


def check_items(items, shape: dict, name: str, errors: list) -> list:
    """Returns the well-formed items, after reporting bad ones and repeated ids."""
    good, seen = [], set()
    for position, item in enumerate(items):
        identifier = item.get("id") if isinstance(item, dict) else None
        where = f"questions.json {name}[{position}]" + (f" ({identifier})" if identifier else "")
        if check_object(item, shape, where, errors):
            if item["id"] in seen:
                errors.append(f"{where}: duplicate id")
            seen.add(item["id"])
            good.append(item)
    return good


def check_tracks(tracks: list, where: str, errors: list) -> None:
    if not tracks or not all(isinstance(t, str) and TRACK.fullmatch(t) for t in tracks):
        errors.append(f"{where}: tracks needs at least one value such as 'junior', "
                      "'senior' or 'system-design'")
    elif len(set(tracks)) != len(tracks):
        errors.append(f"{where}: a track is listed twice")


def check_reviewed(value, where: str, errors: list) -> None:
    """A review date is a promise to readers, so it must be a real day that has happened."""
    try:
        day = datetime.date.fromisoformat(value)
    except ValueError:
        errors.append(f"{where}: reviewed must be a date like 2026-11-27")
        return
    # A day of slack for authors ahead of the CI server's time zone.
    if day.isoformat() != value or day > datetime.date.today() + datetime.timedelta(days=1):
        errors.append(f"{where}: reviewed must be written YYYY-MM-DD and not be in the future")


def validate_bundle(version_bytes: bytes, bundle_bytes: bytes) -> list:
    errors = []
    pointer = load_json(version_bytes, "version.json", errors)
    bundle = load_json(bundle_bytes, "questions.json", errors)
    if pointer is None or bundle is None:
        return errors
    pointer_ok = check_object(pointer, VERSION, "version.json", errors)
    bundle_ok = check_object(bundle, BUNDLE, "questions.json", errors)
    if len(bundle_bytes) > MAX_BYTES:
        errors.append(f"questions.json: larger than the app's limit of {MAX_BYTES} bytes")
    if pointer_ok:
        if pointer["schemaVersion"] != SCHEMA_VERSION:
            errors.append(f"version.json: schemaVersion must be {SCHEMA_VERSION}, "
                          "or the app asks users to update")
        if pointer["version"] < 1:
            errors.append("version.json: version must be 1 or more")
        if pointer["sha256"] != hashlib.sha256(bundle_bytes).hexdigest():
            errors.append("version.json: sha256 does not match questions.json")
    if not bundle_ok:
        return errors
    if bundle["schemaVersion"] != SCHEMA_VERSION:
        errors.append(f"questions.json: schemaVersion must be {SCHEMA_VERSION}")
    if pointer_ok and bundle["version"] != pointer["version"]:
        errors.append("questions.json: version differs from version.json")

    if not bundle["topics"]:
        errors.append("questions.json: there are no topics")
    if not bundle["questions"]:
        errors.append("questions.json: there are no questions")
    topics = check_items(bundle["topics"], TOPIC, "topics", errors)
    topic_ids = {topic["id"] for topic in topics}

    for question in check_items(bundle["questions"], QUESTION, "questions", errors):
        if question["topic"] not in topic_ids:
            errors.append(f"question {question['id']}: unknown topic '{question['topic']}'")
        if question.get("level") is not None and question["level"] not in LEVELS:
            errors.append(f"question {question['id']}: level must be one of {', '.join(LEVELS)}")
        check_tracks(question["tracks"], f"question {question['id']}", errors)
        if question.get("reviewed") is not None:
            check_reviewed(question["reviewed"], f"question {question['id']}", errors)

    for quiz in check_items(bundle["quiz"], QUIZ, "quiz", errors):
        label = f"quiz {quiz['id']}"
        check_tracks(quiz["tracks"], label, errors)
        if quiz.get("kind") is not None:
            if quiz["kind"] not in KINDS:
                errors.append(f"{label}: kind must be one of {', '.join(KINDS)}")
            elif not (quiz.get("code") or "").strip():
                errors.append(f"{label}: a '{quiz['kind']}' question needs code")
        if quiz["topic"] not in topic_ids:
            errors.append(f"{label}: unknown topic '{quiz['topic']}'")
        options = quiz["options"]
        if len(options) < 2 or not all(isinstance(o, str) and o.strip() for o in options):
            errors.append(f"{label}: needs at least 2 options, all non-empty text")
        elif len(set(options)) != len(options):
            errors.append(f"{label}: two options are the same")
        if not 0 <= quiz["answer"] < len(options):
            errors.append(f"{label}: answer must be the zero-based position of an option")
    return errors


def validate_markdown(name: str, text: str) -> list:
    """Finds Markdown the app cannot show, and questions that would be skipped."""
    # Imported here so that the bundle checks work without the build script.
    from build_index import DIVIDER, HEADING, LEVEL_TAG, NUMBERED, QUESTION as ITEM, cells

    errors = []
    lines = text.split("\n")
    if not lines[0].startswith("# "):
        errors.append(f"{name}:1: the first line must be '# Title'")
    section, fence_line, after_item, rapid_header, seen = "", None, False, False, set()

    def remember(question, where):
        if question in seen:
            errors.append(f"{where}: this question appears twice, so one copy would be dropped")
        seen.add(question)

    for number, raw in enumerate(lines, 1):
        line, where = raw.strip(), f"{name}:{number}"
        if line.startswith("```"):
            fence_line = None if fence_line else number
            after_item = False
            continue
        if fence_line:
            continue
        heading = HEADING.fullmatch(line)
        if heading:
            section, after_item, rapid_header = heading[2].lower(), False, False
            continue
        if re.match(r"\s+([-*]|\d+\.) ", raw):
            errors.append(f"{where}: nested lists are not supported")
        if line.startswith(">"):
            errors.append(f"{where}: block quotes are not supported")
        if re.search(r"!\[[^\]]*\]\(", re.sub(r"`[^`]*`", "", line)):
            errors.append(f"{where}: images are not supported")

        if "interview questions" in section:
            numbered = NUMBERED.fullmatch(line)
            if numbered:
                body, tag = numbered[2], LEVEL_TAG.search(numbered[2])
                if tag:
                    body = body[:tag.start()]
                elif re.search(r"\{[^{}`]*\}$", body):
                    errors.append(f"{where}: the level tag must be exactly "
                                  "{Easy}, {Medium} or {Hard}")
                match = ITEM.fullmatch(body)
                if match:
                    remember(match[1], where)
                else:
                    errors.append(f"{where}: write it as '1. **Question?** Answer. {{Medium}}', "
                                  "or the app will not list it")
            elif line and after_item:
                errors.append(f"{where}: an answer must stay on one line, "
                              "or the rest of it is left out of the question")
            elif re.match(r"([-*] |\*\*)", line):
                errors.append(f"{where}: interview questions must be a numbered list")
            after_item = bool(numbered)
        elif "rapid-fire questions" in section:
            if not line.startswith("|"):
                rapid_header = False
            elif DIVIDER.fullmatch(line):
                rapid_header = True
            elif rapid_header:
                row = cells(line)
                if len(row) not in (2, 3) or not row[0] or not row[1]:
                    errors.append(f"{where}: a row needs a question, an answer "
                                  "and an optional level")
                else:
                    if len(row) == 3 and row[2] and row[2] not in LEVELS:
                        errors.append(f"{where}: level must be one of {', '.join(LEVELS)}")
                    remember(row[0], where)
    if fence_line:
        errors.append(f"{name}:{fence_line}: this code block is never closed")
    return errors


def validate_version_change(new_version: bytes, new_bundle: bytes,
                            old_version: bytes, old_bundle: bytes) -> list:
    """The app downloads only a higher version, so changed content needs one."""
    new, old = json.loads(new_version), json.loads(old_version)
    new_body, old_body = json.loads(new_bundle), json.loads(old_bundle)
    new_body.pop("version", None)
    old_body.pop("version", None)
    if new_body != old_body and new["version"] <= old["version"]:
        return [f"version.json: the content changed, so the version must be higher than "
                f"{old['version']}, or installed apps never download it. "
                "Update your branch, then run tools/build_index.py"]
    if new_body == old_body and new["version"] != old["version"]:
        return [f"version.json: the content did not change, so the version must stay "
                f"{old['version']}"]
    return []


def file_at(root: pathlib.Path, ref: str, path: str):
    result = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{path}"],
                            capture_output=True)
    return result.stdout if result.returncode == 0 else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base-ref", help="the commit or branch the change will be merged into")
    parser.add_argument("--root", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    root = args.root

    errors = []
    topics = sorted((root / "topics").glob("*.md"))
    if not topics:
        errors.append("topics/: no Markdown files")
    for path in topics:
        try:
            errors += validate_markdown(f"topics/{path.name}", path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            errors.append(f"topics/{path.name}: not UTF-8 text")

    missing = [n for n in ("version.json", "questions.json") if not (root / n).is_file()]
    if missing:
        errors += [f"{n}: missing. Run tools/build_index.py" for n in missing]
    else:
        version = (root / "version.json").read_bytes()
        bundle = (root / "questions.json").read_bytes()
        bundle_errors = validate_bundle(version, bundle)
        errors += bundle_errors
        if args.base_ref and not bundle_errors:
            # A typo in the ref must not silently skip the version check.
            if subprocess.run(["git", "-C", str(root), "cat-file", "-e",
                               f"{args.base_ref}^{{commit}}"]).returncode != 0:
                errors.append(f"cannot find base ref '{args.base_ref}'")
            else:
                old_version = file_at(root, args.base_ref, "version.json")
                old_bundle = file_at(root, args.base_ref, "questions.json")
                # The first publication has nothing to compare with.
                if old_version and old_bundle:
                    errors += validate_version_change(version, bundle, old_version, old_bundle)

    if errors:
        for error in errors:
            # GitHub shows lines in this form as annotations on the pull request.
            print(f"::error::{error}")
        sys.exit(f"{len(errors)} problem(s) found")
    print(f"Content is valid: {len(topics)} topic files, questions.json and version.json")


if __name__ == "__main__":
    main()
