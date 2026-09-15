import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'project-handbook/scripts'))
from learning_handbook import render_learning, validate_learning, verify_portable


def fixture():
    return {
        'title': 'Reward walkthrough', 'book_id': 'learning-demo',
        'sources': [{'id': 'rules', 'title': 'Rules', 'path': 'config/rules.txt',
                     'locator': 'L1', 'excerpt': 'level >= 10', 'sha256': 'a' * 64}],
        'systems': [{'id': 'reward', 'title': 'Reward', 'summary': 'Grant once',
                     'nodes': [{'id': 'rule', 'title': 'Rule', 'body': 'Level 10', 'sources': ['rules']}]}],
        'learning': {
            'question': 'How do rewards work?', 'interpretation': 'Follow one claim.',
            'answer': 'Check eligibility before granting.', 'scope': ['Claim path'],
            'excluded': ['Purchases'], 'status': 'declared', 'sources': ['rules'],
            'diagram': {'type': 'workflow', 'nodes': [
                {'id': 'client', 'title': 'Client', 'body': 'Submit a claim', 'status': 'declared', 'sources': ['rules']},
                {'id': 'server', 'title': 'Server', 'body': 'Check eligibility', 'status': 'open', 'sources': []}],
                'edges': [{'from': 'client', 'to': 'server', 'label': 'claim', 'status': 'declared', 'sources': ['rules']}]},
            'steps': [{'id': 'check', 'title': 'Check level', 'node': 'server',
                       'owner': 'Server', 'input': 'level = 10', 'action': 'Compare with threshold',
                       'output': 'Eligible', 'details': 'The runtime implementation is missing.',
                       'status': 'declared', 'sources': ['rules']}],
            'examples': [{'id': 'normal', 'title': 'At threshold', 'kind': 'boundary',
                          'provenance': 'illustrative', 'input': 'level = 10',
                          'trace': [{'step': 'check', 'value': '10 >= 10', 'sources': ['rules']}],
                          'result': 'Eligibility only; no grant verified.', 'status': 'declared', 'sources': ['rules']}],
            'glossary': [{'term': 'Eligibility', 'aliases': ['unlock_level'], 'meaning': 'Whether a claim is allowed.'}],
            'actions': [{'title': 'Inspect handler', 'body': 'Find grant implementation.', 'step': 'check', 'sources': []}],
            'coverage': [{'area': 'Server', 'checked': 'Rule declaration', 'missing': 'Grant implementation', 'next': 'Read handler'}]
        }
    }


class LearningTest(unittest.TestCase):
    def test_portable_sections_and_escaped_evidence(self):
        data = fixture()
        data['sources'][0]['excerpt'] += '<script>alert(1)</script>'
        page = render_learning(data)
        for anchor in ['answer', 'overview', 'walkthrough', 'examples', 'glossary', 'actions', 'evidence-rules', 'step-check']:
            self.assertIn('id="' + anchor + '"', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('unlock_level', page)
        self.assertNotIn('<script src=', page)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'handbook.html'
            path.write_text(page, encoding='utf-8')
            self.assertEqual(verify_portable(path), [])

    def test_invalid_references_and_contract(self):
        mutations = [
            lambda x: x['learning']['steps'][0].update(node='unknown'),
            lambda x: x['learning']['examples'][0]['trace'][0].update(step='unknown'),
            lambda x: x['learning']['diagram']['edges'][0].update(to='unknown'),
            lambda x: x['learning'].update(sources=['unknown']),
            lambda x: x['learning']['diagram'].update(type='invented'),
            lambda x: x['learning']['steps'].append(copy.deepcopy(x['learning']['steps'][0])),
            lambda x: x['learning']['steps'][0].update(status='verified', sources=[]),
            lambda x: x['learning']['examples'][0].update(provenance='observed', sources=[]),
            lambda x: x['learning']['examples'][0].update(status='verified', provenance='illustrative'),
            lambda x: x['learning']['examples'][0].update(trace=[]),
        ]
        for mutate in mutations:
            data = fixture()
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate_learning(data)

    def test_all_diagram_types(self):
        for kind in ['architecture', 'workflow', 'sequence', 'lifecycle', 'calculation']:
            data = fixture()
            data['learning']['diagram']['type'] = kind
            self.assertIn('data-diagram="' + kind + '"', render_learning(data))

    def test_invalid_learning_preserves_absent_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = fixture()
            data['learning']['examples'][0]['trace'][0]['step'] = 'missing'
            manifest = root / 'input.json'
            manifest.write_text(json.dumps(data), encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT / 'project-handbook/scripts/build_knowledge.py'), str(manifest), str(root / 'book')], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / 'book').exists())

    def test_default_skill_contract_and_example(self):
        skill = (ROOT / 'project-handbook/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('Ask only when ambiguity changes scope', skill)
        self.assertIn('Directory import is discovery only', skill)
        self.assertIn('handbook.html', skill)
        data = json.loads((ROOT / 'project-handbook/assets/learning.example.json').read_text(encoding='utf-8'))
        validate_learning(data)
        self.assertEqual({e['kind'] for e in data['learning']['examples']}, {'normal', 'boundary', 'exception'})
        self.assertTrue(all(e['provenance'] == 'illustrative' for e in data['learning']['examples']))

    def test_build_integration_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'input.json'
            manifest.write_text(json.dumps(fixture()), encoding='utf-8')
            command = [sys.executable, str(ROOT / 'project-handbook/scripts/build_knowledge.py'), str(manifest), str(root / 'book')]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = root / 'book/handbook.html'
            self.assertTrue(page.exists())
            self.assertEqual(verify_portable(page), [])
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_portable_verifier_rejects_broken_link_remote_asset_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.html'
            path.write_text('<html><a href="#missing">x</a><img src="https://example.test/x"><p onclick="bad()">x</p></html>', encoding='utf-8')
            errors = verify_portable(path)
            self.assertTrue(any('missing' in e for e in errors))
            self.assertTrue(any('asset' in e for e in errors))
            self.assertTrue(any('handler' in e for e in errors))
