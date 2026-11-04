import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evals'))
sys.path.insert(0, str(ROOT / 'project-handbook/scripts'))
from build_flow import validate
from score_flow import score

CASES = sorted((ROOT / 'evals/cases').glob('*.json'))


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def gold(case_path):
    return load(ROOT / 'evals/gold' / (case_path.stem + '.flow.json'))


def rewire(flow, edges):
    flow = copy.deepcopy(flow)
    flow['graphs'][0]['edges'] = [dict(zip(('a', 'b', 'label'), edge)) if len(edge) == 3
                                  else {'a': edge[0], 'b': edge[1]} for edge in edges]
    return flow


def failed(result):
    return {row['id'] for rows in result['checks'].values() for row in rows if row['score'] < 1}


class AnswerKeyTests(unittest.TestCase):
    def test_keys_are_well_formed(self):
        self.assertGreaterEqual(len(CASES), 3)
        sources = load(ROOT / 'evals/sources.json')
        for path in CASES:
            with self.subTest(case=path.name):
                case = load(path)
                self.assertEqual(case['id'], path.stem)
                self.assertIn(case['source'], sources)
                ids = [concept['id'] for concept in case['concepts']]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertTrue(all(concept['any'] for concept in case['concepts']))
                self.assertTrue(set(case['decisions']) <= set(ids))
                for rule in case['order']:
                    kind = rule.get('type', 'order')
                    self.assertIn(kind, ('order', 'one_branch_skips', 'both_branches_reach'))
                    refs = (rule['before'], rule['after']) if kind == 'order' else (rule['decision'], rule['target'])
                    self.assertTrue(set(refs) <= set(ids), rule)
                    if kind != 'order':
                        self.assertIn(rule['decision'], case['decisions'])
                self.assertTrue(any(rule.get('trap') for rule in case['order']))
                self.assertTrue(case['evidence'] and case['evidence_files'])

    def test_gold_answers_build_and_score_full_marks(self):
        for path in CASES:
            with self.subTest(case=path.name):
                flow = gold(path)
                validate(flow)
                result = score(load(path), flow)
                self.assertEqual(result['score'], 100.0, failed(result))
                self.assertEqual(result['traps_passed'], result['traps'])


class TrapTests(unittest.TestCase):
    def test_armor_before_multipliers_is_caught(self):
        case = load(ROOT / 'evals/cases/spd-melee-damage.json')
        flow = gold(ROOT / 'evals/cases/spd-melee-damage.json')
        wrong = rewire(flow, [
            ('start', 'invul'), ('invul', 'invul-end', '是'), ('invul', 'hit', '否'),
            ('hit', 'armor-roll', '是'), ('hit', 'miss-end', '否'), ('armor-roll', 'damage-roll'),
            ('damage-roll', 'armor-subtract'), ('armor-subtract', 'multipliers'),
            ('multipliers', 'defense-proc'), ('defense-proc', 'negative'),
            ('negative', 'vulnerable', '是'), ('negative', 'skip', '否'), ('skip', 'apply'),
            ('vulnerable', 'attack-proc'), ('attack-proc', 'apply'), ('apply', 'end')])
        validate(wrong)
        result = score(case, wrong)
        self.assertEqual(result['traps_passed'], 1)
        self.assertIn('multipliers -> armor-subtract', failed(result))
        self.assertIn('defense-proc -> armor-subtract', failed(result))
        self.assertLess(result['score'], 95)

    def test_infinite_accuracy_checked_first_is_caught(self):
        case = load(ROOT / 'evals/cases/spd-hit-check.json')
        flow = gold(ROOT / 'evals/cases/spd-hit-check.json')
        wrong = rewire(flow, [
            ('start', 'skills'), ('skills', 'overrides'), ('overrides', 'inf-acc'),
            ('inf-acc', 'hit-all', '是'), ('inf-acc', 'inf-eva', '否'),
            ('inf-eva', 'dodge-all', '是'), ('inf-eva', 'acc-roll', '否'),
            ('acc-roll', 'def-roll'), ('def-roll', 'compare'),
            ('compare', 'hit-roll', '是'), ('compare', 'dodge-roll', '否')])
        validate(wrong)
        result = score(case, wrong)
        self.assertIn('infinite-evasion -> infinite-accuracy', failed(result))
        self.assertLess(result['traps_passed'], result['traps'])

    def test_stolen_ending_all_drops_is_caught(self):
        case = load(ROOT / 'evals/cases/spd-loot-drop.json')
        flow = gold(ROOT / 'evals/cases/spd-loot-drop.json')
        edges = [(e['a'], e['b'], e['label']) if 'label' in e else (e['a'], e['b'])
                 for e in flow['graphs'][0]['edges']]
        wrong = rewire(flow, [('stolen', 'not-enemy', '是') if edge[:2] == ('stolen', 'wealth') else edge
                              for edge in edges])
        validate(wrong)
        result = score(case, wrong)
        self.assertIn('stolen both_branches_reach wealth-bonus', failed(result))
        self.assertEqual(result['traps_passed'], 2)

    def test_level_cap_that_still_grants_ring_drops_is_caught(self):
        case = load(ROOT / 'evals/cases/spd-loot-drop.json')
        flow = gold(ROOT / 'evals/cases/spd-loot-drop.json')
        edges = [(e['a'], e['b'], e['label']) if 'label' in e else (e['a'], e['b'])
                 for e in flow['graphs'][0]['edges']]
        wrong = rewire(flow, [('level', 'wealth', '是') if edge[:2] == ('level', 'too-high') else edge
                              for edge in edges] + [('too-high', 'end')])
        result = score(case, wrong)
        self.assertIn('level-cap one_branch_skips wealth-bonus', failed(result))


class RunsTests(unittest.TestCase):
    def test_scores_each_run_against_its_case(self):
        import tempfile
        from score_flow import score_runs
        with tempfile.TemporaryDirectory() as temp:
            for path in CASES:
                folder = Path(temp) / path.stem
                folder.mkdir()
                (folder / 'gold.flow.json').write_text(json.dumps(gold(path)), encoding='utf-8')
            (Path(temp) / 'unknown-case').mkdir()
            (Path(temp) / 'unknown-case' / 'x.flow.json').write_text('{}', encoding='utf-8')
            rows = score_runs(temp, ROOT / 'evals/cases')
        self.assertEqual([(case, label) for case, label, _ in rows], [(p.stem, 'gold') for p in CASES])
        self.assertTrue(all(result['score'] == 100.0 for _, _, result in rows))


class ScoringRuleTests(unittest.TestCase):
    def setUp(self):
        self.case = {'id': 'mini', 'concepts': [
            {'id': 'a', 'label': 'A', 'any': ['alpha']}, {'id': 'b', 'label': 'B', 'any': ['beta']},
            {'id': 'd', 'label': 'D', 'any': ['gate']}],
            'decisions': ['d'], 'order': [{'before': 'a', 'after': 'b', 'why': 'a first'}],
            'constants': [{'label': 'x', 'any': ['1.5']}], 'evidence_files': ['rules.py'],
            'min_example_steps': 2}

    def flow(self, nodes, edges):
        return {'sources': [{'id': 's', 'locator': 'src/rules.py:1'}],
                'graphs': [{'id': 'g', 'source': 's', 'nodes': nodes, 'edges': edges}],
                'examples': [{'input': '', 'trace': ['1', '2'], 'result': ''}]}

    def test_steps_in_one_node_get_half_credit_for_order(self):
        nodes = [{'id': 'n', 'kind': 'process', 'title': 'alpha then beta ×1.5'},
                 {'id': 'g', 'kind': 'decision', 'title': 'gate?'}]
        result = score(self.case, self.flow(nodes, [{'a': 'n', 'b': 'g'}]))
        self.assertEqual(result['checks']['order'][0]['score'], 0.5)

    def test_reverse_order_and_missing_decision_fail(self):
        nodes = [{'id': 'b', 'kind': 'process', 'title': 'beta'}, {'id': 'a', 'kind': 'process', 'title': 'alpha'},
                 {'id': 'g', 'kind': 'process', 'title': 'gate'}]
        result = score(self.case, self.flow(nodes, [{'a': 'b', 'b': 'a'}, {'a': 'a', 'b': 'g'}]))
        self.assertEqual(result['checks']['order'][0]['score'], 0)
        self.assertEqual(result['checks']['decisions'][0]['score'], 0)
        self.assertEqual(result['checks']['constants'][0]['score'], 0)

    def test_generic_word_in_a_later_title_does_not_move_the_step(self):
        # Codex wrote "通用死亡掉落处理结束" at the end; death is still the entry.
        case = {**self.case, 'concepts': [{'id': 'a', 'label': 'A', 'any': ['die(', '死亡']},
                                          {'id': 'b', 'label': 'B', 'any': ['敌对']},
                                          {'id': 'd', 'label': 'D', 'any': ['gate']}]}
        nodes = [{'id': 'hp', 'kind': 'terminal', 'title': '生命值归零', 'lines': '调用 die(cause)'},
                 {'id': 'enemy', 'kind': 'decision', 'title': '是敌对阵营吗？'},
                 {'id': 'end', 'kind': 'terminal', 'title': '通用死亡掉落处理结束'}]
        edges = [{'a': 'hp', 'b': 'enemy'}, {'a': 'enemy', 'b': 'end'}]
        result = score(case, self.flow(nodes, edges))
        self.assertEqual(result['checks']['order'][0]['score'], 1.0)

    def test_keywords_do_not_match_inside_longer_identifiers(self):
        case = {**self.case, 'concepts': [{'id': 'a', 'label': 'A', 'any': ['Vulnerable']},
                                          {'id': 'b', 'label': 'B', 'any': ['drRoll']},
                                          {'id': 'd', 'label': 'D', 'any': ['gate']}]}
        nodes = [{'id': 'n', 'kind': 'process', 'title': 'x', 'lines': 'isInvulnerable() then enemy.drRoll()'}]
        result = score(case, self.flow(nodes, []))
        self.assertEqual([row['score'] for row in result['checks']['concepts']], [0.0, 1.0, 0.0])

    def test_pass_through_terminal_is_not_the_branch_target(self):
        case = {**self.case, 'concepts': [{'id': 'd', 'label': 'D', 'any': ['被偷']},
                                          {'id': 'w', 'label': 'W', 'any': ['财富戒']}],
                'decisions': ['d'], 'constants': [],
                'order': [{'type': 'both_branches_reach', 'decision': 'd', 'target': 'w', 'why': 'w'}]}
        nodes = [{'id': 'd', 'kind': 'decision', 'title': '被偷了吗？'},
                 {'id': 'note', 'kind': 'terminal', 'title': '结束', 'lines': '不再走财富戒'},
                 {'id': 'roll', 'kind': 'process', 'title': '掷普通掉落'},
                 {'id': 'w', 'kind': 'process', 'title': '财富戒额外掉落'}]
        edges = [{'a': 'd', 'b': 'note', 'label': '是'}, {'a': 'd', 'b': 'roll', 'label': '否'},
                 {'a': 'roll', 'b': 'w'}]
        result = score(case, self.flow(nodes, edges))
        self.assertEqual(result['checks']['order'][0]['score'], 0.0)

    def test_evidence_needs_named_file_and_long_enough_example(self):
        nodes = [{'id': 'a', 'kind': 'process', 'title': 'alpha'}]
        flow = self.flow(nodes, [])
        flow['sources'][0]['locator'] = 'somewhere else'
        flow['examples'][0]['trace'] = ['only one']
        result = score(self.case, flow)
        self.assertEqual([row['score'] for row in result['checks']['evidence']], [0, 0])


if __name__ == '__main__':
    unittest.main()
