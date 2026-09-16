import sys
import os
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'project-handbook/scripts'))
from flow_sources import lookup_sources


class SourceLookupTests(unittest.TestCase):
    def test_relevant_lines_have_relative_citations_and_no_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'combat.lua').write_text('local damage = 500\nshield = 100\napi_key=sk-private-test123456\n', encoding='utf-8')
            (root / '.env').write_text('damage=SECRET', encoding='utf-8')
            (root / 'irrelevant.txt').write_text('unrelated text', encoding='utf-8')
            result = lookup_sources([root], 'damage shield', threading.Event())
            self.assertIn('combat.lua:1', result)
            self.assertIn('damage = 500', result)
            self.assertNotIn('sk-private', result)
            self.assertNotIn('SECRET', result)
            self.assertNotIn(str(root), result)

    def test_does_not_follow_links_outside_authorized_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / 'allowed'
            root.mkdir()
            secret = parent / 'private.txt'
            secret.write_text('damage=PRIVATE_OUTSIDE_ROOT', encoding='utf-8')
            try:
                (root / 'combat.txt').symlink_to(secret)
            except OSError:
                self.skipTest('Symlink permission unavailable')
            self.assertNotIn('PRIVATE_OUTSIDE_ROOT', lookup_sources([root], 'damage', threading.Event()))

    def test_sensitive_directories_are_not_searched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'auth').mkdir()
            (root / 'auth/settings.json').write_text('{"damage":"PRIVATE_AUTH_VALUE"}', encoding='utf-8')
            self.assertNotIn('PRIVATE_AUTH_VALUE', lookup_sources([root], 'damage', threading.Event()))

    def test_checks_the_open_handle_before_reading(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / 'allowed'
            root.mkdir()
            allowed = root / 'combat.lua'
            allowed.write_text('damage = 10', encoding='utf-8')
            outside = base / 'outside.lua'
            outside.write_text('damage = PRIVATE_OUTSIDE_HANDLE', encoding='utf-8')
            original_open = Path.open
            def changed_open(path, *args, **kwargs):
                return original_open(outside if path == allowed else path, *args, **kwargs)
            with patch.object(Path, 'open', changed_open):
                self.assertNotIn('PRIVATE_OUTSIDE_HANDLE', lookup_sources([root], 'damage', threading.Event()))

    @unittest.skipUnless(os.name == 'nt', 'Windows junction behavior')
    def test_junction_cannot_disguise_a_sensitive_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hidden = root / 'auth'
            hidden.mkdir()
            (hidden / 'settings.json').write_text('{"damage":"PRIVATE_JUNCTION_VALUE"}', encoding='utf-8')
            link = root / 'ordinary'
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(hidden)],
                                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                self.skipTest('Junction creation unavailable')
            self.assertNotIn('PRIVATE_JUNCTION_VALUE', lookup_sources([root], 'damage', threading.Event()))

    def test_empty_roots_and_cancel_do_not_claim_full_search(self):
        self.assertIn('No authorized', lookup_sources([], 'damage', threading.Event()))
        cancel = threading.Event()
        cancel.set()
        self.assertIn('cancelled', lookup_sources([ROOT], 'damage', cancel))


if __name__ == '__main__':
    unittest.main()
