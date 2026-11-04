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
        self.assertNotRegex(page, r'@@[A-Z]+@@')
        self.assertNotIn('id="review"', page)
        self.assertNotIn('href="#review"', page)
        self.assertIn('activateNavigation', page)
        self.assertIn('nav-active', page)
        self.assertNotIn('data-tab=', page)
        self.assertNotIn('id="next"', page)
        self.assertIn('id="zoom-fit"', page)

    def test_assistant_and_local_capture_are_embedded(self):
        page = flow.render(self.data)
        self.assertIn('flow:node-selected', page)
        self.assertIn('html2canvas', page)
        self.assertIn('markdownit', page)
        self.assertIn('flow-qa-panel', page)
        self.assertNotRegex(page, r'<script[^>]+src="https?://')

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

    def test_build_never_saves_live_runtime(self):
        self.data['runtime'] = {'token': 'ephemeral-secret', 'api': '/api'}
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'book'
            flow.build(self.data, output)
            for filename in ('handbook.html', 'flow.json'):
                self.assertNotIn('ephemeral-secret', (output / filename).read_text(encoding='utf-8'))
        self.assertIn('runtime', self.data)

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

    def switch_flow(self, labels):
        nodes = [{'id': 'start', 'row': 0, 'col': 0, 'kind': 'switch', 'title': '伤害来源？', 'lines': '', 'detail': ''}]
        edges = []
        for index, label in enumerate(labels):
            nodes.append({'id': f'way{index}', 'row': 1, 'col': index, 'kind': 'terminal',
                          'title': label or 'x', 'lines': '', 'detail': ''})
            edges.append({'a': 'start', 'b': f'way{index}', 'label': label})
        return {'title': 'Switch', 'sources': [{'id': 'code', 'locator': 'Damage.cs'}],
                'graphs': [{'id': 'damage', 'title': 'Damage', 'source': 'code', 'nodes': nodes, 'edges': edges}]}

    def test_switch_takes_two_to_six_named_outcomes_in_up_to_four_columns(self):
        flow.validate(self.switch_flow(['普攻', '技能', 'Buff']))
        page = flow.render(self.switch_flow(['普攻', '技能', 'Buff', '反伤']))
        self.assertIn('"kind": "switch"', page)
        for labels in (['普攻'], ['普攻', '普攻', 'Buff'], ['普攻', '', 'Buff'], ['a', 'b', 'c', 'd', 'e']):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                flow.validate(self.switch_flow(labels))

    def test_errors_name_the_place_and_the_fix(self):
        cases = [
            (lambda d: d['graphs'][0]['nodes'][1].pop('kind'), 'graphs[0].nodes[1]', 'missing "kind"'),
            (lambda d: d['graphs'][0]['nodes'][0].update(id='source'), 'graphs[0].nodes[0]', 'used by the page'),
            (lambda d: d['graphs'][0]['nodes'][0].update(id='next'), 'graphs[0].nodes[0]', '"next-step"'),
            (lambda d: d['graphs'][0]['nodes'][1].update(col=4), 'graphs[0].nodes[1]', 'col 0 to 3'),
            (lambda d: d['graphs'][0]['nodes'][0].update(sources=['missing']), '.sources', 'not listed in sources'),
            (lambda d: d['examples'][0].pop('result'), 'examples[0]', 'missing "result"'),
        ]
        for change, where, hint in cases:
            d = copy.deepcopy(self.data)
            change(d)
            with self.subTest(hint=hint), self.assertRaises(ValueError) as caught:
                flow.validate(d)
            self.assertIn(where, str(caught.exception))
            self.assertIn(hint, str(caught.exception))
        d = copy.deepcopy(self.data)
        decision = next(n for n in d['graphs'][0]['nodes'] if n['kind'] == 'decision')
        next(e for e in d['graphs'][0]['edges'] if e['a'] == decision['id'] and e['label'].startswith('否'))['label'] = '其他'
        with self.assertRaises(ValueError) as caught:
            flow.validate(d)
        self.assertIn('use kind "switch"', str(caught.exception))

    def test_nodes_can_cite_their_own_sources(self):
        self.data['sources'].append({'id': 'formula', 'locator': 'Formula.cs:10', 'excerpt': 'damage * 1.5'})
        first = self.data['graphs'][0]['nodes'][0]
        first['sources'] = ['formula', 'demo']
        flow.validate(self.data)
        nodes = {n['id']: n for n in flow.canvas_data(self.data)['canvas']['nodes']}
        self.assertEqual(nodes[first['id']]['sources'], ['formula', 'demo'])
        self.assertEqual(nodes[first['id']]['source'], 'formula')
        other = self.data['graphs'][0]['nodes'][1]['id']
        self.assertEqual(nodes[other]['sources'], [self.data['graphs'][0]['source']])
        self.assertNotIn('sources', self.data['graphs'][0]['nodes'][1])

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
        self.assertNotRegex(page, r'@@[A-Z]+@@')
        base = max(1600 - 600, 1)
        reduced = base * 2 * 80 // 100
        normal = max(reduced - 100, 0)
        fixed = max(500 - 100, 0)
        self.assertEqual((base, reduced, normal, fixed, min(200, normal)), (1000, 1600, 1500, 400, 200))
        for example, result in zip(data['examples'], (normal, fixed, 200)):
            self.assertIn(str(result), ' '.join(example['trace']))
