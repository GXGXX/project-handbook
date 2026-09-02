from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "project-handbook"
INIT = ROOT / "scripts" / "init_handbook.py"
BUILD = ROOT / "scripts" / "build_handbook.py"
VERIFY = ROOT / "scripts" / "verify_handbook.py"


def run(script: Path, folder: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), str(folder), *args],
        text=True,
        capture_output=True,
        check=False,
    )


class HandbookScriptsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name) / "handbook"
        self.assertEqual(run(INIT, self.folder).returncode, 0)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_build_and_verify(self) -> None:
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        result = run(VERIFY, self.folder)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.folder / "site" / "pages" / "overview.html").exists())
        index = (self.folder / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="search-data"', index)
        self.assertIn("项目总览", index)

    def test_missing_fragment_fails_without_partial_pages(self) -> None:
        (self.folder / "content" / "overview.html").unlink()
        result = run(BUILD, self.folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.folder / "site" / "index.html").exists())

    def test_unsafe_fragment_fails(self) -> None:
        (self.folder / "content" / "overview.html").write_text('<script>alert("x")</script>', encoding="utf-8")
        result = run(BUILD, self.folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe", result.stderr)

    def test_broken_link_is_reported(self) -> None:
        content = self.folder / "content" / "overview.html"
        content.write_text('<p><a href="pages/missing.html">broken</a></p>', encoding="utf-8")
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        result = run(VERIFY, self.folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("broken internal link", result.stdout)

    def test_fact_presence_is_checked(self) -> None:
        facts = {"facts": [{"id": "port", "value": "9030", "page": "overview", "source": "config.py"}]}
        (self.folder / "evidence" / "facts.json").write_text(json.dumps(facts), encoding="utf-8")
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        result = run(VERIFY, self.folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fact 'port'", result.stdout)


if __name__ == "__main__":
    unittest.main()
