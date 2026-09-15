"""Build a portable, authored workflow: build_flow.py manifest.json NEW_OUTPUT."""
import argparse
import html
import json
import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'assets'


def validate(data):
    graphs = data['graphs']
    if not graphs:
        raise ValueError('At least one graph is required')
    used = {'data', 'nodes', 'edges', 'canvas', 'diagram', 'examples', 'detail',
            'detail-title', 'detail-text', 'detail-formula', 'source', 'next',
            'search', 'graph-title', 'graph-note', 'arrow', 'amber-arrow'}
    def identifier(value):
        if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]*', value) or value in used:
            raise ValueError('Invalid or duplicate ID: ' + str(value))
        used.add(value)
    source_ids = {s['id'] for s in data.get('sources', [])}
    graph_ids = set()
    for graph in graphs:
        identifier(graph['id'])
        graph_ids.add(graph['id'])
        if graph.get('source') not in source_ids:
            raise ValueError('Missing graph source')
        nodes = graph['nodes']
        if not nodes:
            raise ValueError('Empty graph')
        occupied = set()
        for n in nodes:
            identifier(n['id'])
            if type(n['row']) is not int or n['row'] < 0 or n['col'] not in (0, 1):
                raise ValueError('Invalid node position')
            pos = n['row'], n['col']
            if pos in occupied:
                raise ValueError('Overlapping node positions')
            occupied.add(pos)
            if n['kind'] not in ('process', 'decision', 'terminal', 'merge'):
                raise ValueError('Invalid node kind')
            for field in ('title', 'lines', 'detail'):
                if not isinstance(n[field], str):
                    raise ValueError('Node text must be a string')
        ids = {n['id'] for n in nodes}
        seen = set()
        for edge in graph['edges']:
            if edge['a'] not in ids or edge['b'] not in ids:
                raise ValueError('Unknown edge endpoint')
            pair = edge['a'], edge['b']
            if pair in seen or edge['a'] == edge['b']:
                raise ValueError('Duplicate edge or self-loop')
            seen.add(pair)
            if edge.get('route', 'normal') not in ('normal', 'outer', 'bypass'):
                raise ValueError('Invalid route')
        for n in nodes:
            if n['kind'] == 'decision':
                labels = [e.get('label', '').split(' ')[0] for e in graph['edges'] if e['a'] == n['id']]
                if sorted(labels) != ['否', '是']:
                    raise ValueError('Decision requires exactly one 是 and one 否 branch')
        reached = {nodes[0]['id']}
        for _ in nodes:
            reached.update(e['b'] for e in graph['edges'] if e['a'] in reached)
        if reached != ids:
            raise ValueError('Unreachable nodes')
    if data.get('common') and data['common'] not in graph_ids:
        raise ValueError('Unknown common graph')


def render(data):
    validate(data)
    esc = lambda value: html.escape(str(value), quote=True)
    header = '<header><span class="eyebrow">流程图解</span><h1>' + esc(data['title']) + '</h1><p>' + esc(data.get('summary', '')) + '</p></header>'
    nav = '<nav aria-label="流程选择">' + ''.join(
        '<button data-tab="' + esc(g['id']) + '" aria-pressed="' + str(i == 0).lower() + '">' + esc(g['title']) + '</button>'
        for i, g in enumerate(data['graphs'])) + '<a href="#examples">数值走一遍</a></nav>'
    examples = ''
    for ex in data.get('examples', []):
        examples += '<details class="example"><summary>' + esc(ex['title']) + '</summary><p>' + esc(ex['provenance']) + ' · ' + esc(ex['input']) + '</p><ol>'
        examples += ''.join('<li>' + esc(step) + '</li>' for step in ex['trace'])
        examples += '</ol><strong>' + esc(ex['result']) + '</strong></details>'
    replacements = {
        'TITLE': esc(data['title']), 'HEADER': header, 'NAV': nav, 'EXAMPLES': examples,
        'CSS': (ASSETS / 'flow.css').read_text(encoding='utf-8'),
        'JS': (ASSETS / 'flow.js').read_text(encoding='utf-8'),
        'DATA': json.dumps(data, ensure_ascii=False).replace('<', '\\u003c'),
    }
    template = (ASSETS / 'flow-template.html').read_text(encoding='utf-8')
    return re.sub(r'@@([A-Z]+)@@', lambda m: replacements[m[1]], template)


def build(data, output):
    page = render(data)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'handbook.html').write_text(page, encoding='utf-8')
    (output / 'flow.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(json.loads(args.manifest.read_text(encoding='utf-8')), args.output)
