# DroidReady content

Study material for the DroidReady Android app. The app reads `index.json` from the
`main` branch, then downloads the Markdown files it lists. Changing content here
does not need an app release.

## Website

<https://sougandh.dev/DroidReady-Content/> shows the same content in a
browser. GitHub Pages serves it from the root of `main`, with no build step:
`index.html` and `assets/` read `index.json`, `topics/` and `quiz.json` directly,
so pushing content to `main` updates the site too. Progress and bookmarks are
saved in each visitor's browser and don't sync with the app.

To preview locally, run `python3 -m http.server` and open <http://localhost:8000>.

## Update content

1. Edit or add files in `topics/`, or edit `quiz.json`. Name them `NN-slug.md`; the first line is `# Title`.
2. Run `python3 tools/build_index.py`.
3. Commit the Markdown and `index.json` together, then push to `main`.

The app checks each file against the SHA-256 in `index.json`. If you skip step 2,
the app rejects the update and keeps showing its saved copy. GitHub's raw file
cache can delay a change by a few minutes.

- The slug (`kotlin` in `01-kotlin.md`) identifies a topic. Renaming it resets
  that topic's "done" mark. Changing only the number reorders topics.
- Keep line endings as LF.

## Supported Markdown

Headings, paragraphs, `-` bullets, `1.` numbered lists, `- [ ]` checklists, pipe
tables, fenced code blocks, and inline bold, italic, code and links. Lists are
single level. Images, nested lists, block quotes and HTML are not rendered.

## Interview questions

The app builds its question list from two patterns:

- Under a heading containing `Interview questions`, each numbered item written as
  `1. **Question?** Answer. {Medium}`
- Under a heading containing `Rapid-fire questions`, each table row:
  `| question | answer | Level |`

The level is `Easy`, `Medium` or `Hard`, and is optional. Editing a question's
text makes it a new question, so its progress and bookmark reset. Changing only
the answer or level keeps them.

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
  "explanation": "Shown after the user answers."
}
```

`topic` is a topic slug and `answer` is the zero-based index of the right option.

The difficulty levels and the first set of quiz questions were drafted with AI
help from the study notes. Review them and edit as you see fit.
