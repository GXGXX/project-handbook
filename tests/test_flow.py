import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('flow_builder', ROOT / 'project-handbook/scripts/build_flow.py')
flow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flow)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'project-handbook/assets/flow.example.json').read_text(encoding='utf-8'))

    def test_portable_and_no_review(self):
        page = flow.render(self.data)
        self.assertNotIn('@@', page)
        self.assertNotIn('id="review"', page)
        self.assertNotIn('href="#review"', page)
        self.assertIn('activateNavigation', page)
        self.assertIn('nav-active', page)

    def test_reject_invalid_graphs(self):
        changes = [lambda d: d['graphs'][0]['edges'].pop(1),
                   lambda d: d['graphs'][0]['edges'][0].update(b='missing'),
                   lambda d: d['graphs'][0]['nodes'][1].update(row=0),
                   lambda d: d['graphs'][0]['nodes'][0].update(id='detail'),
                   lambda d: d.update(common='missing')]
        for change in changes:
            d = copy.deepcopy(self.data)
            change(d)
            with self.assertRaises(ValueError):
                flow.validate(d)

    def test_safe_text(self):
        self.data['title'] = '<script>alert(1)</script>'
        self.data['sources'][0]['excerpt'] = '</script><script>alert(2)</script>'
        page = flow.render(self.data)
        self.assertNotIn('<script>alert', page)
        self.assertIn('\\u003c/script>', page)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'book'
            flow.build(self.data, output)
            self.assertTrue((output / 'handbook.html').is_file())
            with self.assertRaises(FileExistsError):
                flow.build(self.data, output)
