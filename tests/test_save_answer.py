import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'project-handbook/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


answers = load('save_answer')
flow = load('build_flow')
EXAMPLE = json.loads((ROOT / 'project-handbook/assets/flow.example.json').read_text(encoding='utf-8'))


def saved(book):
    text = (book / 'answers.js').read_text(encoding='utf-8')
    match = re.fullmatch(r'window\.HANDBOOK_ANSWERS = (\[.*\]);\n', text, re.S)
    return json.loads(match[1])


class SaveAnswerTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp)
        self.book = self.temp / 'book'
        flow.build(EXAMPLE, self.book)

    def test_saves_and_replaces_by_id(self):
        answers.save(self.book, 'q-1', '库存不足会怎样？', '直接结束。', 'stock')
        answers.save(self.book, 'q-2', '整个流程多久？', '几秒。')
        answers.save(self.book, 'q-1', '库存不足会怎样？', '直接结束，不创建订单。', 'stock')
        values = saved(self.book)
        self.assertEqual([v['id'] for v in values], ['q-2', 'q-1'])
        self.assertEqual(values[1]['answer'], '直接结束，不创建订单。')
        self.assertEqual(values[1]['node'], 'stock')
        self.assertIsNone(values[0]['node'])

    def test_text_cannot_break_out_of_the_page(self):
        answers.save(self.book, 'q-1', 'x', 'a </script><script>alert(1)</script> "quoted"\nline')
        text = (self.book / 'answers.js').read_text(encoding='utf-8')
        self.assertNotIn('</script', text)
        self.assertEqual(saved(self.book)[0]['answer'], 'a </script><script>alert(1)</script> "quoted"\nline')

    def test_refuses_what_the_page_could_not_use(self):
        cases = [(self.temp, 'q-1', 'x', 'y', None, 'not a handbook folder'),
                 (self.book, 'q 1; rm', 'x', 'y', None, '问题编号'),
                 (self.book, 'q-1', ' ', 'y', None, 'must not be empty'),
                 (self.book, 'q-20261106-181100-wb01', 'q-20261106-181100-wb01', 'y', None, 'not the 问题编号'),
                 (self.book, 'q-1', 'x', 'y', 'nope', 'node "nope" is not in this handbook')]
        for book, entry_id, question, answer, node, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                answers.save(book, entry_id, question, answer, node)
        (self.book / 'answers.js').write_text('window.HANDBOOK_ANSWERS = [{"id": "q-0"', encoding='utf-8')
        with self.assertRaises(ValueError):
            answers.save(self.book, 'q-1', 'x', 'y')
        self.assertIn('q-0', (self.book / 'answers.js').read_text(encoding='utf-8'), 'a damaged file is left for repair')

    def test_works_for_a_page_built_without_python(self):
        book = self.temp / 'no-python'
        book.mkdir()
        shutil.copy(ROOT / 'project-handbook/assets/viewer/handbook.html', book)
        (book / 'flow-data.js').write_text('window.HANDBOOK_DATA = ' + json.dumps(EXAMPLE, ensure_ascii=False) + ';', encoding='utf-8')
        answers.save(book, 'q-1', 'x', 'y', 'pay')
        with self.assertRaisesRegex(ValueError, 'not in this handbook'):
            answers.save(book, 'q-2', 'x', 'y', 'nope')
        self.assertEqual(saved(book)[0]['node'], 'pay')


if __name__ == '__main__':
    unittest.main()
