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
        self.assertNotIn('data-tab=', page)
        self.assertNotIn('id="next"', page)
        self.assertIn('id="zoom-fit"', page)

    def test_reject_invalid_graphs(self):
        changes = [lambda d: d['graphs'][0]['edges'].pop(1),
                   lambda d: d['graphs'][0]['edges'][0].update(b='missing'),
                   lambda d: d['graphs'][0]['nodes'][1].update(row=0),
                   lambda d: d['graphs'][0]['nodes'][0].update(id='detail'),
                   lambda d: d['connections'][0].update(b='missing')]
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

    def test_canvas_keeps_all_nodes_and_explicit_connections(self):
        data = flow.canvas_data(self.data)
        self.assertEqual(len(data['canvas']['nodes']), 10)
        self.assertEqual(len(data['canvas']['edges']), 9)
        self.assertIn({'a': 'pay', 'b': 'callback', 'label': '支付成功且通知校验通过'}, data['canvas']['edges'])
        self.assertEqual(self.data['graphs'][1]['nodes'][0]['row'], 0)
        self.data.pop('connections')
        self.assertEqual(len(flow.canvas_data(self.data)['canvas']['edges']), 8)

    def test_node_sources_survive_combining_sections(self):
        self.data['sources'].append({'id':'second','locator':'Second source','excerpt':'Second evidence'})
        self.data['graphs'][1]['source'] = 'second'
        flow.validate(self.data)
        nodes = {n['id']:n for n in flow.canvas_data(self.data)['canvas']['nodes']}
        self.assertEqual(nodes['created']['source'], 'demo')
        self.assertEqual(nodes['callback']['source'], 'second')

    def test_canvas_rejects_overlapping_sections(self):
        self.data['graphs'][1]['position'] = {'row':0, 'col':0}
        with self.assertRaises(ValueError):
            flow.render(self.data)

    def test_sanitized_damage_example(self):
        text = (ROOT / 'project-handbook/assets/damage.example.json').read_text(encoding='utf-8')
        data = json.loads(text)
        page = flow.render(data)
        self.assertIn('教学数据', data['summary'])
        self.assertIn('非项目代码摘录', data['sources'][0]['locator'])
        self.assertNotRegex(text, r'https?://|[A-Za-z]:[\\/]|m_[A-Z]')
        self.assertEqual(len(data['examples']), 3)
        self.assertNotIn('@@', page)
        base = max(1600 - 600, 1)
        reduced = base * 2 * 80 // 100
        normal = max(reduced - 100, 0)
        fixed = max(500 - 100, 0)
        self.assertEqual((base, reduced, normal, fixed, min(200, normal)), (1000, 1600, 1500, 400, 200))
        for example, result in zip(data['examples'], (normal, fixed, 200)):
            self.assertIn(str(result), ' '.join(example['trace']))
