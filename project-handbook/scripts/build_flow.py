"""Build a portable, authored workflow: build_flow.py manifest.json NEW_OUTPUT."""
import argparse
import html
import json
import re
import copy
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'assets'


# Element IDs the page already uses; a node with one of these IDs would break it.
RESERVED_IDS = {'data', 'nodes', 'edges', 'canvas', 'diagram', 'examples', 'detail',
                'detail-title', 'detail-text', 'detail-formula', 'source', 'next',
                'search', 'graph-title', 'graph-note', 'arrow', 'amber-arrow',
                'viewport', 'stage', 'zoom-in', 'zoom-out', 'zoom-reset', 'zoom-fit',
                'zoom-value', 'search-prev', 'search-next', 'search-count'}
KINDS = ('process', 'decision', 'switch', 'terminal', 'merge')
MAX_COLUMNS = 4
MAX_SWITCH_EXITS = 6


def _fail(where, message):
    raise ValueError(f'{where}: {message}')


def _field(item, key, kind, where):
    """Return item[key] after checking it exists and has the expected type."""
    if not isinstance(item, dict):
        _fail(where, 'must be an object')
    if key not in item:
        _fail(where, f'missing "{key}"')
    value = item[key]
    if kind is int and (type(value) is not int):
        _fail(f'{where}.{key}', 'must be a whole number')
    if kind is not int and not isinstance(value, kind):
        _fail(f'{where}.{key}', 'must be ' + {str: 'text', list: 'a list', dict: 'an object'}[kind])
    return value


def validate(data):
    """Check an authored flow and explain the first problem in plain terms."""
    if not isinstance(data, dict):
        _fail('flow', 'must be an object')
    _field(data, 'title', str, 'flow')
    graphs = _field(data, 'graphs', list, 'flow')
    if not graphs:
        _fail('graphs', 'needs at least one section')
    sources = _field(data, 'sources', list, 'flow')
    source_ids = set()
    for index, source in enumerate(sources):
        where = f'sources[{index}]'
        source_id = _field(source, 'id', str, where)
        _field(source, 'locator', str, where)
        if source_id in source_ids:
            _fail(where, f'duplicate source id "{source_id}"')
        source_ids.add(source_id)
    used = set()

    def identifier(value, where):
        if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]*', value):
            _fail(where, f'id {value!r} must start with a letter and use only letters, digits, - and _')
        if value in RESERVED_IDS or value.startswith('flow-qa-'):
            _fail(where, f'id "{value}" is used by the page itself; choose another, such as "{value}-step"')
        if value in used:
            _fail(where, f'id "{value}" is already used by another section or node')
        used.add(value)

    def cited(value, where):
        if value not in source_ids:
            _fail(where, f'source "{value}" is not listed in sources')

    graph_ids = set()
    for g_index, graph in enumerate(graphs):
        gwhere = f'graphs[{g_index}]'
        identifier(_field(graph, 'id', str, gwhere), gwhere + '.id')
        graph_ids.add(graph['id'])
        cited(_field(graph, 'source', str, gwhere), gwhere + '.source')
        nodes = _field(graph, 'nodes', list, gwhere)
        if not nodes:
            _fail(gwhere, 'section has no nodes')
        occupied = {}
        for n_index, n in enumerate(nodes):
            where = f'{gwhere}.nodes[{n_index}]'
            identifier(_field(n, 'id', str, where), where + '.id')
            where = f'{gwhere}.nodes[{n_index}] ({n["id"]})'
            row, col = _field(n, 'row', int, where), _field(n, 'col', int, where)
            if row < 0 or not 0 <= col < MAX_COLUMNS:
                _fail(where, f'row must be 0 or more and col 0 to {MAX_COLUMNS - 1}')
            if (row, col) in occupied:
                _fail(where, f'same row and col as node "{occupied[(row, col)]}"')
            occupied[(row, col)] = n['id']
            if _field(n, 'kind', str, where) not in KINDS:
                _fail(where, 'kind must be one of ' + ', '.join(KINDS))
            for key in ('title', 'lines', 'detail'):
                _field(n, key, str, where)
            if 'sources' in n:
                if not isinstance(n['sources'], list) or not n['sources']:
                    _fail(where + '.sources', 'must be a non-empty list of source ids')
                for source in n['sources']:
                    cited(source, where + '.sources')
        ids = {n['id'] for n in nodes}
        seen = set()
        for e_index, edge in enumerate(_field(graph, 'edges', list, gwhere)):
            where = f'{gwhere}.edges[{e_index}]'
            a, b = _field(edge, 'a', str, where), _field(edge, 'b', str, where)
            for end in (a, b):
                if end not in ids:
                    _fail(where, f'"{end}" is not a node in this section; link sections with connections')
            if (a, b) in seen or a == b:
                _fail(where, 'duplicate edge or an edge to itself')
            seen.add((a, b))
            if edge.get('route', 'normal') not in ('normal', 'outer', 'bypass'):
                _fail(where + '.route', 'must be normal, outer or bypass')
            if 'label' in edge and not isinstance(edge['label'], str):
                _fail(where + '.label', 'must be text')
        for n in nodes:
            where = f'{gwhere} node "{n["id"]}"'
            exits = [e for e in graph['edges'] if e['a'] == n['id']]
            if n['kind'] == 'decision':
                labels = sorted(e.get('label', '').split(' ')[0] for e in exits)
                if labels != ['否', '是']:
                    _fail(where, 'a decision needs exactly one 是 edge and one 否 edge; '
                                 'use kind "switch" for three or more named outcomes')
            if n['kind'] == 'switch':
                labels = [e.get('label', '').strip() for e in exits]
                if not 2 <= len(exits) <= MAX_SWITCH_EXITS or not all(labels) or len(set(labels)) != len(labels):
                    _fail(where, f'a switch needs 2 to {MAX_SWITCH_EXITS} edges, each with its own label')
        reached = {nodes[0]['id']}
        for _ in nodes:
            reached.update(e['b'] for e in graph['edges'] if e['a'] in reached)
        if reached != ids:
            missing = ', '.join(sorted(ids - reached))
            _fail(gwhere, f'not reachable from the first node: {missing}')
    if data.get('common') and data['common'] not in graph_ids:
        _fail('common', 'is not a section id')
    all_nodes = {n['id']: n for g in graphs for n in g['nodes']}
    for index, edge in enumerate(data.get('connections', [])):
        where = f'connections[{index}]'
        a, b = _field(edge, 'a', str, where), _field(edge, 'b', str, where)
        if a not in all_nodes or b not in all_nodes or a == b:
            _fail(where, 'must join two different existing nodes')
        if all_nodes[a]['kind'] in ('decision', 'switch'):
            _fail(where, 'keep branch edges inside the section that owns the branch')
        if not edge.get('label'):
            _fail(where, 'needs a label saying when the flow crosses sections')
    for index, example in enumerate(data.get('examples', [])):
        where = f'examples[{index}]'
        for key in ('title', 'provenance', 'input', 'result'):
            _field(example, key, str, where)
        trace = _field(example, 'trace', list, where)
        if not all(isinstance(step, str) for step in trace):
            _fail(where + '.trace', 'must be a list of text steps')


def canvas_data(data):
    """Place all authored sections on one canvas; never infer connections."""
    result = copy.deepcopy(data)
    nodes, edges, occupied = [], [], set()
    next_row = 0
    for graph in result['graphs']:
        offset = graph.get('position', {'row': next_row, 'col': 0})
        if any(type(offset.get(k)) is not int or offset[k] < 0 for k in ('row', 'col')):
            raise ValueError('Invalid section position')
        for node in graph['nodes']:
            node['row'] += offset['row']
            node['col'] += offset['col']
            node['sources'] = list(node.get('sources') or [graph['source']])
            node['source'] = node['sources'][0]
            pos = node['row'], node['col']
            if pos in occupied:
                raise ValueError('Sections overlap on canvas')
            occupied.add(pos)
            nodes.append(node)
        edges.extend(graph['edges'])
        next_row = max(n['row'] for n in nodes) + 2
    edges.extend(result.get('connections', []))
    result['canvas'] = {'nodes': nodes, 'edges': edges}
    return result


def render(data):
    validate(data)
    data = canvas_data(data)
    esc = lambda value: html.escape(str(value), quote=True)
    header = '<header><span class="eyebrow">流程图解</span><h1>' + esc(data['title']) + '</h1><p>' + esc(data.get('summary', '')) + '</p></header>'
    nav = '<nav aria-label="阅读导航"><a href="#diagram" class="nav-active" aria-current="location">整体流程</a><a href="#examples">数值走一遍</a></nav>'
    examples = ''
    for ex in data.get('examples', []):
        examples += '<details class="example"><summary>' + esc(ex['title']) + '</summary><p>' + esc(ex['provenance']) + ' · ' + esc(ex['input']) + '</p><ol>'
        examples += ''.join('<li>' + esc(step) + '</li>' for step in ex['trace'])
        examples += '</ol><strong>' + esc(ex['result']) + '</strong></details>'
    replacements = {
        'TITLE': esc(data['title']), 'HEADER': header, 'NAV': nav, 'EXAMPLES': examples,
        'CSS': '\n'.join((ASSETS / name).read_text(encoding='utf-8') for name in ('flow.css', 'flow-assistant.css')),
        'JS': '\n;\n'.join((ASSETS / name).read_text(encoding='utf-8').replace('</script', '<\\/script')
                            for name in ('vendor/html2canvas.min.js', 'vendor/markdown-it.min.js', 'flow.js', 'flow-assistant.js')),
        'DATA': json.dumps(data, ensure_ascii=False).replace('<', '\\u003c'),
    }
    template = (ASSETS / 'flow-template.html').read_text(encoding='utf-8')
    return re.sub(r'@@([A-Z]+)@@', lambda m: replacements[m[1]], template)


def build(data, output):
    data = copy.deepcopy(data)
    data.pop('runtime', None)
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
