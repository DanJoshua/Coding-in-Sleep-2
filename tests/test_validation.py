from __future__ import annotations

import unittest

from sleepcode.validation import Validator
from sleepcode.util import read_json, write_text

from tests.helpers import TempDirTestCase


class ValidationTests(TempDirTestCase, unittest.TestCase):
    def test_runs_candidate_sleepcode_tests_when_agent_created_them(self) -> None:
        write_text(self.root / ".sleepcode" / "tests" / "test_sample.py", "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n")

        result = Validator().run(self.root, self.root / "artifacts")

        self.assertEqual(result.status, "pass")
        self.assertEqual(result.metadata["kind"], "candidate_tests")
        self.assertEqual(read_json(self.root / "artifacts" / "validation.json")["status"], "pass")

    def test_python_without_candidate_tests_is_smoke_only(self) -> None:
        write_text(self.root / "app.py", "x = 1\n")

        result = Validator().run(self.root, self.root / "artifacts")

        self.assertEqual(result.status, "smoke")
        self.assertEqual(result.metadata["kind"], "smoke")

    def test_non_python_without_tests_is_unknown(self) -> None:
        write_text(self.root / "README.md", "hello\n")

        result = Validator().run(self.root, self.root / "artifacts")

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.metadata["kind"], "none")


if __name__ == "__main__":
    unittest.main()
