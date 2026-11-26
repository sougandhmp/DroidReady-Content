# DroidReady content

Study material for the DroidReady Android app, served by GitHub Pages. Changing
content here does not need an app release.

## Website

<https://sougandh.dev/DroidReady-Content/> shows the same content in a
browser. GitHub Pages serves it from the root of `develop`, with no build step:
`index.html` and `assets/` read `questions.json`, the same file as the app, so
merging content into `develop` updates the site too. Progress and bookmarks are
saved in each visitor's browser and don't sync with the app.

To preview locally, run `python3 -m http.server` and open <http://localhost:8000>.

## Update content

1. Edit or add files in `topics/`, or edit `quiz.json`. Name them `NN-slug.md`; the first line is `# Title`.
2. Run `python3 tools/build_index.py`.
3. Commit your changes **and the generated files** together on a new branch.
4. Open a pull request into `develop`. Direct pushes are blocked.
5. Merge once the **validate-content** check passes. Merging publishes the change.

The script writes `questions.json`, `version.json` and `index.json`. Don't edit
them by hand.

The app reads the small `version.json` first, and downloads `questions.json` only
when the version is higher than the one it has. It then checks the file against
the SHA-256 in `version.json`. Two consequences:

- If you skip step 2, the app doesn't see your change.
- To undo a change, revert it and run the script again. That publishes the old
  text under a **new, higher** version. Never lower the version.

GitHub Pages can take a few minutes to serve a change. `index.json` is only for
older builds of the app, which read this repository's raw files.

- The slug (`kotlin` in `01-kotlin.md`) identifies a topic. Renaming it resets
  that topic's "done" mark. Changing only the number reorders topics.
- Keep line endings as LF.

## Pull request checks

CI runs `tools/validate_content.py` and blocks the merge if:

- `questions.json` or `version.json` doesn't match the structure the app reads:
  a missing or misspelt field, a wrong type, a duplicate id, an unknown topic or
  level, a quiz answer that isn't one of its options, or a wrong checksum.
- Content changed without a higher version, so apps would never download it.
- The Markdown would silently lose content, for example a badly formatted
  interview question, or uses something the app can't show.
- The generated files are out of date.

Run the same checks before you push:

```sh
python3 -m unittest discover -s tools -p 'test_*.py'
python3 tools/validate_content.py --base-ref origin/develop
python3 tools/build_index.py --check
```

If another pull request merges first, update your branch and run
`tools/build_index.py` again. If `version.json` or `questions.json` conflicts,
take the version from `develop`, then run the script.

The rules follow the app's `data/remote/Dtos.kt` and `ContentMapper.kt`. Change
the validator whenever the app's structure changes.

## Supported Markdown

Headings, paragraphs, `-` bullets, `1.` numbered lists, `- [ ]` checklists, pipe
tables, fenced code blocks, and inline bold, italic, code and links. Lists are
single level. Images, nested lists, block quotes and HTML are not rendered.

## Interview questions

The script builds the question list from two patterns:

- Under a heading containing `Interview questions`, each numbered item written as
  `1. **Question?** Answer. {Medium}`
- Under a heading containing `Rapid-fire questions`, each table row:
  `| question | answer | Level |`

The level is `Easy`, `Medium` or `Hard`, and is optional. Editing a question's
text makes it a new question, so its progress and bookmark reset. Changing only
the answer or level keeps them.

Run the build script before previewing a change, so that `questions.json` includes it.

## Question details

Every interview question also needs an entry in `details/<topic-slug>.json`, keyed by
the question's exact text. CI fails if one is missing, or if an entry matches no
question (usually after the question was reworded).

```json
{
  "Is `onDestroy` always called?": {
    "tracks": ["junior"],
    "why": "Why an interviewer asks this.",
    "mistake": "A common wrong answer.",
    "followUp": "What the interviewer may ask next.",
    "code": "fun example() = Unit"
  }
}
```

- `tracks` drives the filters in the app: `junior`, `senior` and `system-design`. Any
  other lower-case value, such as a company set, appears as a new filter without an app
  update. Quiz questions need `tracks` too.
- `followUp` and `code` are optional. `code` is Kotlin shown under the answer; compile it
  before you publish it.
- "Last reviewed" in the app and on the website is set by the build script: **the day the
  question's answer or details last changed**. A new or edited question gets that day's
  date, and unchanged questions keep theirs. It does not by itself mean the answer was
  fact-checked. To set a date by hand, for example after checking an unchanged answer,
  add `"reviewed": "YYYY-MM-DD"` to its entry. Remove that line the next time you edit
  the question, or the old date stays.

The first set of tracks, reasons, common mistakes, follow-ups and code samples was drafted with AI help.

## Quiz

`quiz.json` holds the multiple-choice questions used by Daily 5 and topic quizzes:

```json
{
  "id": "unique-id",
  "topic": "kotlin",
  "question": "What does this print?",
  "code": "optional code sample",
  "options": ["A", "B"],
  "answer": 0,
  "explanation": "Shown after the user answers.",
  "tracks": ["junior"],
  "kind": "output"
}
```

`kind` is optional: `output` for "What does this print?" and `bug` for "find the bug".
Both need `code`. Run an `output` snippet before you publish it.

`topic` is a topic slug and `answer` is the zero-based index of the right option.

The difficulty levels and the first set of quiz questions were drafted with AI
help from the study notes. Review them and edit as you see fit.
