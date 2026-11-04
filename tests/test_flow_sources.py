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

    def test_reads_files_whose_names_do_not_match(self):
        # The old lookup read 400 files chosen by file name; Mob.java lost.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(450):
                (root / f'a{index:03}_loot.java').write_text('class A { float lootChance = 0.1f; }', encoding='utf-8')
            (root / 'zz').mkdir()
            (root / 'zz/Mob.java').write_text('float dropBonus = ring();\nreturn lootChance * dropBonus;\n',
                                               encoding='utf-8')
            result = lookup_sources([root], 'dropBonus lootChance', threading.Event())
            first = result.splitlines()[1]
            self.assertEqual(first, 'root-1/zz/Mob.java:1')
            self.assertIn('read 451 of 451', result)

    def test_import_lines_do_not_count_as_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'A.java').write_text('import game.items.RingOfWealth;\nimport game.Mob;\nclass A {}\n', encoding='utf-8')
            (root / 'B.java').write_text('class B {\n  float bonus = RingOfWealth.dropChanceMultiplier(hero);\n}\n',
                                         encoding='utf-8')
            result = lookup_sources([root], 'RingOfWealth Mob', threading.Event())
            self.assertIn('B.java:1', result)
            self.assertNotIn('A.java', result)

    def test_rare_terms_and_definitions_rank_first(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(20):
                (root / f'use{index}.lua').write_text('local damage = 1\nprint(damage)\n', encoding='utf-8')
            (root / 'rules.lua').write_text('\n' * 30 + 'local function critFactor(damage)\n  return damage * 1.5\nend\n',
                                            encoding='utf-8')
            result = lookup_sources([root], 'damage critFactor', threading.Event())
            self.assertEqual(result.splitlines()[1], 'root-1/rules.lua:27')

    def test_code_comments_are_not_redacted_as_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Char.java').write_text('//vulnerable applies after armor\nx *= 1.33f; // see //cdn.example.com/a\n',
                                            encoding='utf-8')
            result = lookup_sources([root], 'vulnerable armor', threading.Event())
            self.assertIn('//vulnerable applies after armor', result)
            self.assertNotIn('cdn.example.com', result)

    def test_spreadsheet_cells_are_searched_with_sheet_and_row(self):
        import zipfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
            rel = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
            with zipfile.ZipFile(root / 'skill.xlsx', 'w') as book:
                book.writestr('xl/workbook.xml', f'<workbook {ns} {rel}><sheets>'
                              '<sheet name="技能表" sheetId="1" r:id="rId1"/></sheets></workbook>')
                book.writestr('xl/_rels/workbook.xml.rels',
                              '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                              '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
                book.writestr('xl/sharedStrings.xml', f'<sst {ns}><si><t>暴击倍率</t></si><si><t>crit</t></si></sst>')
                book.writestr('xl/worksheets/sheet1.xml', f'<worksheet {ns}><sheetData>'
                              '<row r="1"><c r="A1" t="s"><v>1</v></c><c r="B1" t="s"><v>0</v></c></row>'
                              '<row r="7"><c r="A7"><v>101</v></c><c r="B7"><v>1.5</v></c></row>'
                              '</sheetData></worksheet>')
            result = lookup_sources([root], '暴击倍率', threading.Event())
            self.assertIn('root-1/skill.xlsx:1', result)
            self.assertIn('技能表!1: A=crit, B=暴击倍率', result)
            self.assertIn('技能表!7: A=101, B=1.5', result)


if __name__ == '__main__':
    unittest.main()
