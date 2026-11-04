"""Score a generated flow.json against an answer key.

    python evals/score_flow.py evals/cases/spd-melee-damage.json path/to/flow.json
    python evals/score_flow.py evals/cases/spd-melee-damage.json path/to/flow.json --json
    python evals/score_flow.py --runs evals/runs

The key says what a correct answer must contain; the score says how much of it
the flow shows. It checks content, not layout: build_flow.py already checks the
structure. Matching is plain keyword search, so keys list both code names and
Chinese wording. A step counts as covered if any node mentions it; for order
checks its position is every node whose title or formula line names it (detail
only as a fallback), and branch targets skip pass-through terminal notes.

Checks and weights:
  concepts   40  each required step or statement appears in some node
  order      30  steps connect in the right direction; branch rules check where
                 each exit of a decision leads (one_branch_skips,
                 both_branches_reach), whatever its 是/否 wording
  decisions  10  branching steps are drawn as 是/否 decision nodes
  constants  10  key numbers appear in nodes or examples
  evidence   10  sources name the right files; one worked example walks the steps
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

WEIGHTS = {'concepts': 40, 'order': 30, 'decisions': 10, 'constants': 10, 'evidence': 10}


def _nodes(flow):
    return [node for graph in flow.get('graphs', []) for node in graph.get('nodes', [])]


def _text(node):
    return ' '.join(str(node.get(key, '')) for key in ('title', 'lines', 'detail')).lower()


def _matches(text, words):
    """Keyword search. A keyword that starts with an ASCII letter must not
    continue a longer identifier, so "Vulnerable" does not match inside
    "isInvulnerable" while "drRoll" still matches "enemy.drRoll()"."""
    for word in words:
        word = word.lower()
        if word[:1].isascii() and word[:1].isalpha():
            if re.search(r'(?<![a-z])' + re.escape(word), text):
                return True
        elif word in text:
            return True
    return False


def _graph(flow):
    edges = {}
    for graph in flow.get('graphs', []):
        for edge in graph.get('edges', []):
            edges.setdefault(edge['a'], set()).add(edge['b'])
    for edge in flow.get('connections', []):
        edges.setdefault(edge['a'], set()).add(edge['b'])
    return edges


def _reaches(edges, start, goal):
    seen, queue = {start}, deque([start])
    while queue:
        current = queue.popleft()
        for following in edges.get(current, ()):
            if following == goal:
                return True
            if following not in seen:
                seen.add(following)
                queue.append(following)
    return False


def _place(nodes, words):
    """Where a step sits: every node whose title or formula line names it.

    Only when no title or line names it do detail mentions count. Details often
    refer ahead ("dr 要到 defenseProc 之后才用"), so they must not place a step
    that has its own node. Titles and lines are both kept because generic words
    also appear in other titles ("通用死亡掉落处理结束" mentions 死亡); order
    checks pass if any placed node of one step leads to any of the other.
    """
    for fields in (('title', 'lines'), ('title', 'lines', 'detail')):
        found = [node['id'] for node in nodes
                 if _matches(' '.join(str(node.get(key, '')) for key in fields).lower(), words)]
        if found:
            return found
    return []


def _order(edges, first, then):
    """Some node of the earlier step must lead to some node of the later one."""
    if not first or not then:
        return 0.0, 'missing step'
    if any(a != b and _reaches(edges, a, b) for a in first for b in then):
        return 1.0, 'ok'
    if set(first) & set(then):
        return 0.5, 'both in one node; order not shown'
    return 0.0, 'wrong order or not connected'


def _branches(edges, deciders, targets, kind):
    """Check where each exit of a decision leads, whatever its 是/否 wording.

    both_branches_reach: every exit still arrives at the target step.
    one_branch_skips: one exit arrives at the target and another never does.
    """
    if not deciders:
        return 0.0, 'no decision node for this step'
    if not targets:
        return 0.0, 'missing target step'
    for decider in deciders:
        exits = sorted(edges.get(decider, ()))
        if len(exits) < 2:
            continue
        arrive = [any(t == goal or _reaches(edges, t, goal) for goal in targets) for t in exits]
        if kind == 'both_branches_reach' and all(arrive):
            return 1.0, 'ok'
        if kind == 'one_branch_skips' and any(arrive) and not all(arrive):
            return 1.0, 'ok'
    if kind == 'both_branches_reach':
        return 0.0, 'one exit never reaches the target'
    return 0.0, 'no exit skips the target'


def score(case, flow):
    nodes = _nodes(flow)
    texts = {node['id']: _text(node) for node in nodes}
    concepts = {concept['id']: concept for concept in case['concepts']}
    covering = {cid: [nid for nid, text in texts.items() if _matches(text, c['any'])]
                for cid, c in concepts.items()}
    edges = _graph(flow)
    results = {key: [] for key in WEIGHTS}

    for cid, concept in concepts.items():
        found = covering[cid]
        results['concepts'].append({'id': cid, 'label': concept['label'], 'score': 1.0 if found else 0.0,
                                    'nodes': found, 'trap': bool(concept.get('trap'))})

    kinds = {node['id']: node.get('kind') for node in nodes}
    placed = {cid: _place(nodes, concept['any']) for cid, concept in concepts.items()}
    # A step the key calls a decision is located by its decision node when one
    # exists, so a note such as "偷袭时命中值设为无限" cannot stand in for it.
    for cid in case.get('decisions', []):
        deciding = [nid for nid in placed[cid] if kinds[nid] == 'decision']
        if deciding:
            placed[cid] = deciding
    for rule in case.get('order', []):
        kind = rule.get('type', 'order')
        if kind == 'order':
            value, note = _order(edges, placed[rule['before']], placed[rule['after']])
            rule_id = rule['before'] + ' -> ' + rule['after']
        else:
            deciders = [nid for nid in covering[rule['decision']] if kinds[nid] == 'decision']
            targets = placed[rule['target']]
            # A terminal that only says "继续走财富戒分支" is a hand-off, not the
            # step itself; use the step's real node when the flow has one.
            working = [nid for nid in targets if kinds[nid] != 'terminal']
            value, note = _branches(edges, deciders, working or targets, kind)
            rule_id = rule['decision'] + ' ' + kind + ' ' + rule['target']
        results['order'].append({'id': rule_id, 'label': rule['why'], 'trap': bool(rule.get('trap')),
                                 'score': value, 'note': note})

    for cid in case.get('decisions', []):
        found = [nid for nid in covering[cid] if kinds[nid] == 'decision']
        results['decisions'].append({'id': cid, 'label': concepts[cid]['label'],
                                     'score': 1.0 if found else 0.0, 'nodes': found})

    example_text = ' '.join(
        ' '.join([ex.get('input', ''), ' '.join(ex.get('trace', [])), ex.get('result', '')])
        for ex in flow.get('examples', [])).lower()
    all_text = ' '.join(texts.values()) + ' ' + example_text
    for constant in case.get('constants', []):
        results['constants'].append({'id': constant['label'], 'label': constant['label'],
                                     'score': 1.0 if _matches(all_text, constant['any']) else 0.0})

    locators = ' '.join(str(source.get('locator', '')) for source in flow.get('sources', [])).lower()
    for name in case.get('evidence_files', []):
        results['evidence'].append({'id': 'source:' + name, 'label': 'a source names ' + name,
                                    'score': 1.0 if name.lower() in locators else 0.0})
    steps = max((len(ex.get('trace', [])) for ex in flow.get('examples', [])), default=0)
    minimum = case.get('min_example_steps', 3)
    results['evidence'].append({'id': 'example', 'label': f'a worked example with at least {minimum} steps',
                                'score': 1.0 if steps >= minimum else 0.0})

    total = 0.0
    for key, weight in WEIGHTS.items():
        rows = results[key]
        part = sum(row['score'] for row in rows) / len(rows) if rows else 1.0
        total += weight * part
    # A trap is either an order rule or a statement the flow must make, such as
    # "this falloff is configured but never called".
    traps = [row for key in ('concepts', 'order') for row in results[key] if row.get('trap')]
    return {'case': case['id'], 'score': round(total, 1),
            'traps_passed': sum(row['score'] == 1.0 for row in traps), 'traps': len(traps),
            'checks': results}


def report(result):
    lines = [f"{result['case']}: {result['score']} / 100  (traps {result['traps_passed']}/{result['traps']})"]
    for key, weight in WEIGHTS.items():
        rows = result['checks'][key]
        got = sum(row['score'] for row in rows)
        lines.append(f'  {key} ({weight}): {got:g}/{len(rows)}')
        for row in rows:
            if row['score'] < 1:
                mark = 'TRAP ' if row.get('trap') else ''
                note = ' [' + row['note'] + ']' if row.get('note') else ''
                lines.append(f"    - {mark}{row['id']}: {row['label']}{note}")
    return '\n'.join(lines)


def score_runs(runs, cases):
    """Score every runs/<case-id>/*.flow.json against cases/<case-id>.json."""
    rows = []
    for path in sorted(Path(runs).glob('*/*.flow.json')):
        case_path = Path(cases) / (path.parent.name + '.json')
        if not case_path.is_file():
            continue
        result = score(json.loads(case_path.read_text(encoding='utf-8')),
                       json.loads(path.read_text(encoding='utf-8')))
        rows.append((path.parent.name, path.name[:-len('.flow.json')], result))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('case', type=Path, nargs='?', help='answer key, e.g. evals/cases/spd-loot-drop.json')
    parser.add_argument('flow', type=Path, nargs='?', help='flow.json produced by the skill')
    parser.add_argument('--runs', type=Path, help='score every RUNS/<case-id>/<label>.flow.json')
    parser.add_argument('--json', action='store_true', help='print the full result as JSON')
    args = parser.parse_args(argv)
    if args.runs:
        rows = score_runs(args.runs, Path(__file__).resolve().parent / 'cases')
        if args.json:
            print(json.dumps([result for _, _, result in rows], ensure_ascii=False, indent=2))
        else:
            print(f'{"case":<20} {"run":<28} {"score":>6}  traps')
            for case_id, label, result in rows:
                print(f'{case_id:<20} {label:<28} {result["score"]:>6}  {result["traps_passed"]}/{result["traps"]}')
        return 0
    if not args.case or not args.flow:
        parser.error('give CASE and FLOW, or --runs DIR')
    case = json.loads(args.case.read_text(encoding='utf-8'))
    flow = json.loads(args.flow.read_text(encoding='utf-8'))
    result = score(case, flow)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else report(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
