"""Tests for how "reviewed" dates are set."""
import datetime
import json
import pathlib
import tempfile
import unittest

from build_index import date_questions

TODAY = datetime.date.today().isoformat()


def question(answer="A.", **extra):
    return {"id": "q1", "answer": answer} | extra


class ReviewDateTest(unittest.TestCase):
    def dated(self, new, old=None):
        with tempfile.TemporaryDirectory() as folder:
            bundle = pathlib.Path(folder) / "questions.json"
            if old is not None:
                bundle.write_text(json.dumps({"questions": [old]}))
            date_questions([new], bundle)
        return new["reviewed"]

    def test_a_new_question_gets_today(self):
        self.assertEqual(TODAY, self.dated(question()))

    def test_an_unchanged_question_keeps_its_date(self):
        self.assertEqual("2026-01-31", self.dated(question(), question(reviewed="2026-01-31")))

    def test_a_changed_question_gets_today(self):
        self.assertEqual(TODAY, self.dated(question("New."), question(reviewed="2026-01-31")))

    def test_a_question_without_a_date_gets_today(self):
        self.assertEqual(TODAY, self.dated(question(), question()))

    def test_a_written_date_wins(self):
        self.assertEqual("2026-02-01", self.dated(question(reviewed="2026-02-01"), question()))


if __name__ == "__main__":
    unittest.main()
