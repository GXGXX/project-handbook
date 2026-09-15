"""Validated offline newcomer walkthroughs. Never executes source material."""
import html
from html.parser import HTMLParser
from pathlib import Path
import re

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
ID = re.compile(r'^[a-z][a-z0-9-]{0,44}$')
STATUSES = {'verified': '已核对', 'declared': '资料声明', 'partial': '部分核对', 'open': '待补充'}
TYPES = {'architecture': '职责关系', 'workflow': '处理流程', 'sequence': '交互时序', 'lifecycle': '状态变化', 'calculation': '计算过程'}


def validate_learning(data):
    learning = data.get('learning')
    if not isinstance(learning, dict):
        raise ValueError('learning must be an object')
    source_ids = {s['id'] for s in data.get('sources', [])}

    def text(obj, *keys):
        for key in keys:
            if not isinstance(obj.get(key), str) or not obj[key].strip():
                raise ValueError('learning requires text: ' + key)

    def rows(obj, key, required=False):
        values = obj.get(key, [])
        if not isinstance(values, list) or (required and not values):
            raise ValueError(key + ' must be an array, nonempty when required')
        if any(not isinstance(row, dict) for row in values):
            raise ValueError(key + ' must contain objects')
        return values

    def identified(values):
        ids = set()
        for value in values:
            key = value.get('id')
            if not isinstance(key, str) or not ID.fullmatch(key) or key in ids:
                raise ValueError('invalid or duplicate learning id')
            ids.add(key)
        return ids

    def evidence(obj):
        refs = obj.get('sources', [])
        if not isinstance(refs, list) or any(not isinstance(s, str) or s not in source_ids for s in refs):
            raise ValueError('unknown learning source')
        if obj.get('status', 'partial') not in STATUSES:
            raise ValueError('invalid learning status')
        if obj.get('status') == 'verified' and not refs:
            raise ValueError('verified claims require sources')

    text(learning, 'question', 'interpretation', 'answer')
    evidence(learning)
    for key in ('scope', 'excluded'):
        values = learning.get(key, [])
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError(key + ' must contain text')
    diagram = learning.get('diagram')
    if not isinstance(diagram, dict) or diagram.get('type') not in TYPES:
        raise ValueError('invalid diagram type')
    nodes = rows(diagram, 'nodes', True)
    node_ids = identified(nodes)
    for node in nodes:
        text(node, 'title', 'body')
        evidence(node)
    for edge in rows(diagram, 'edges'):
        if edge.get('from') not in node_ids or edge.get('to') not in node_ids:
            raise ValueError('unknown diagram endpoint')
        text(edge, 'label')
        evidence(edge)
    steps = rows(learning, 'steps', True)
    step_ids = identified(steps)
    for step in steps:
        text(step, 'title', 'owner', 'input', 'action', 'output')
        if step.get('node') not in node_ids:
            raise ValueError('unknown step node')
        evidence(step)
    examples = rows(learning, 'examples', True)
    identified(examples)
    for example in examples:
        text(example, 'title', 'input', 'result')
        evidence(example)
        if example.get('kind') not in ('normal', 'boundary', 'exception'):
            raise ValueError('invalid example kind')
        if example.get('provenance') not in ('illustrative', 'observed'):
            raise ValueError('invalid example provenance')
        if example['provenance'] == 'observed' and not example.get('sources'):
            raise ValueError('observed examples require sources')
        if example['provenance'] == 'illustrative' and example.get('status') == 'verified':
            raise ValueError('illustrative examples cannot claim verified runtime')
        for trace in rows(example, 'trace', True):
            if trace.get('step') not in step_ids:
                raise ValueError('unknown example step')
            text(trace, 'value')
            evidence(trace)
    for action in rows(learning, 'actions', True):
        text(action, 'title', 'body')
        if action.get('step') not in step_ids:
            raise ValueError('unknown action step')
        evidence(action)
    for term in rows(learning, 'glossary'):
        text(term, 'term', 'meaning')
        if not isinstance(term.get('aliases', []), list) or any(not isinstance(v, str) for v in term.get('aliases', [])):
            raise ValueError('aliases must contain text')
    for coverage in rows(learning, 'coverage', True):
        text(coverage, 'area', 'checked', 'missing', 'next')


def e(value):
    return html.escape(str(value), quote=True)


def relationship_svg(diagram):
    """Show only authored edges; numbered key keeps long labels readable."""
    nodes = diagram['nodes']
    edges = diagram.get('edges', [])
    columns = min(3, len(nodes))
    rows = (len(nodes) + columns - 1) // columns
    width, height = columns * 270 + 80, rows * 160 + 80
    positions = {n['id']: (150 + (i % columns) * 270, 90 + (i // columns) * 160) for i, n in enumerate(nodes)}
    svg = f'<svg class="relationship-map" viewBox="0 0 {width} {height}" role="img" aria-label="职责节点与已声明关系；编号对应下方关系列表"><defs><marker id="relation-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="currentColor"/></marker></defs>'
    for i, edge in enumerate(edges):
        x1, y1 = positions[edge['from']]
        x2, y2 = positions[edge['to']]
        offset = 48 + (i % 3) * 20
        start_y, end_y = y1 + 28, y2 + 28
        curve = f'M{x1} {start_y} C{x1} {start_y+offset} {x2} {end_y+offset} {x2} {end_y}'
        if edge['from'] == edge['to']:
            curve = f'M{x1+80} {y1} C{x1+160} {y1-90} {x1+160} {y1+90} {x1+80} {y1+20}'
        dash = '' if edge.get('status') == 'verified' else ' stroke-dasharray="5 4"'
        svg += f'<path d="{curve}" fill="none" stroke="currentColor" stroke-width="1.6"{dash} marker-end="url(#relation-arrow)"/><text x="{(x1+x2)/2}" y="{(start_y+end_y)/2+offset*.75}" text-anchor="middle">{i+1}</text>'
    for node in nodes:
        x, y = positions[node['id']]
        radius = 24 if diagram['type'] == 'lifecycle' else 7
        title = node['title']
        label = title if len(title) <= 16 else title[:15] + '…'
        svg += f'<a href="#node-{e(node["id"])}"><rect x="{x-108}" y="{y-28}" width="216" height="56" rx="{radius}"/><text x="{x}" y="{y+5}" text-anchor="middle">{e(label)}</text><title>{e(title)}</title></a>'
    return svg + '</svg>'


def render_learning(data):
    validate_learning(data)
    learning = data['learning']
    sources = {s['id']: s for s in data.get('sources', [])}

    def badge(obj):
        status = obj.get('status', 'partial')
        return f'<span class="badge {status}">{STATUSES[status]}</span>'

    def refs(obj):
        return '<span class="refs">' + ' '.join(f'<a href="#evidence-{e(s)}">{e(sources[s]["title"])}</a>' for s in obj.get('sources', [])) + '</span>'

    def para(value):
        return f'<p>{e(value)}</p>'

    def section(key, number, title, body):
        return f'<section id="{key}" class="chapter"><header><span class="number">{number}</span><h2>{title}</h2></header>{body}</section>'

    route = [('answer', '先看答案'), ('overview', '看懂框架'), ('walkthrough', '走完流程'), ('examples', '跟着例子走'), ('glossary', '术语与细节'), ('actions', '回到实际工作')]
    nav = ''.join(f'<a href="#{key}"><span>0{i+1}</span>{title}</a>' for i, (key, title) in enumerate(route))
    body = section('answer', '01', '先看答案',
        f'<div class="answer">{para(learning["answer"])}{badge(learning)} {refs(learning)}</div>'
        f'<details><summary>本次问题的理解与范围</summary>{para(learning["interpretation"])}'
        f'<p><strong>涵盖：</strong>{e("；".join(learning.get("scope", [])))}</p>'
        f'<p><strong>不涵盖：</strong>{e("；".join(learning.get("excluded", [])))}</p></details>')
    diagram = learning['diagram']
    nodes = {n['id']: n for n in diagram['nodes']}
    node_cards = ''.join(f'<article id="node-{e(n["id"])}" class="component" data-node="{e(n["id"])}"><h3>{e(n["title"])}</h3>{para(n["body"])}{badge(n)} {refs(n)}</article>' for n in nodes.values())
    edges = ''.join(f'<li><a href="#node-{e(edge["from"])}">{e(nodes[edge["from"]]["title"])}</a><span class="edge-label"> → {e(edge["label"])} → </span><a href="#node-{e(edge["to"])}">{e(nodes[edge["to"]]["title"])}</a> {badge(edge)} {refs(edge)}</li>' for edge in diagram.get('edges', []))
    visual = relationship_svg(diagram) + f'<div class="components">{node_cards}</div><ol class="connections">{edges}</ol>'
    if diagram['type'] == 'sequence':
        participants = list(nodes)
        messages = ''
        for i, edge in enumerate(diagram.get('edges', [])):
            a, b = participants.index(edge['from']), participants.index(edge['to'])
            messages += f'<div class="message-row"><div class="message" style="grid-column:{min(a,b)+1} / {max(a,b)+2}"><span>{i+1}. {e(edge["label"])} {"→" if a <= b else "←"}</span><small>{e(nodes[edge["from"]]["title"])} → {e(nodes[edge["to"]]["title"])}</small>{badge(edge)} {refs(edge)}</div></div>'
        visual = f'<div class="sequence" style="--participants:{len(nodes)}"><div class="participants">{node_cards}</div>{messages}</div>'
    elif diagram['type'] == 'calculation':
        visual += '<div class="calculations">' + ''.join(f'<div><strong>{e(s["title"])}</strong><p>{e(s["input"])}</p><p>{e(s["action"])}</p><p>= {e(s["output"])}</p>{badge(s)}</div>' for s in learning['steps']) + '</div>'
    body += section('overview', '02', '看懂框架', f'<div class="diagram" data-diagram="{diagram["type"]}"><p class="diagram-label">{TYPES[diagram["type"]]}</p>{visual}</div>')
    steps = ''
    for i, step in enumerate(learning['steps']):
        steps += f'<article class="walk-step" id="step-{e(step["id"])}" data-step="{e(step["id"])}" data-owner-node="{e(step["node"])}"><header><span class="number">{i+1:02}</span><h3>{e(step["title"])}</h3>{badge(step)}</header><dl>'
        for key, label in [('owner', '谁负责'), ('input', '输入'), ('action', '做什么'), ('output', '得到什么')]:
            steps += f'<dt>{label}</dt><dd>{e(step[key])}</dd>'
        steps += f'</dl><a href="#node-{e(step["node"])}">{e(nodes[step["node"]]["title"])}</a> {refs(step)}'
        if step.get('details'):
            steps += f'<details><summary>条件、字段与分支</summary>{para(step["details"])}</details>'
        steps += '</article>'
    toolbar = '<div class="guide-controls"><button id="guide-start" type="button">开始理解</button><button id="guide-prev" type="button" aria-label="上一步">←</button><output id="guide-progress" aria-live="polite">完整流程</output><button id="guide-next" type="button" aria-label="下一步">→</button><button id="guide-reset" type="button" aria-label="结束导读">↺</button></div>'
    body += section('walkthrough', '03', '走完流程', toolbar + '<div class="steps">' + steps + '</div>')
    examples = ''
    step_names = {s['id']: s['title'] for s in learning['steps']}
    for example in learning['examples']:
        provenance = '演示数据，非运行实测' if example['provenance'] == 'illustrative' else '记录中的实际案例'
        kind = {'normal': '正常', 'boundary': '边界', 'exception': '异常'}[example['kind']]
        examples += f'<details class="example" id="example-{e(example["id"])}"><summary>{kind} · {e(example["title"])}</summary><p class="provenance">{provenance}</p>{badge(example)}<p><strong>初始条件：</strong>{e(example["input"])}</p><ol>'
        for trace in example['trace']:
            examples += f'<li><a href="#step-{e(trace["step"])}">{e(step_names[trace["step"]])}</a>{para(trace["value"])}{refs(trace)}</li>'
        examples += f'</ol><p><strong>最终结果：</strong>{e(example["result"])}</p>{refs(example)}</details>'
    body += section('examples', '04', '跟着例子走', examples)
    glossary = ''.join(f'<div class="term"><h3>{e(t["term"])}</h3><code>{e(" · ".join(t.get("aliases", [])))}</code>{para(t["meaning"])}</div>' for t in learning.get('glossary', []))
    body += section('glossary', '05', '术语与细节', glossary or '<p>本次没有额外术语。</p>')
    actions = ''.join(f'<article class="action"><h3>{e(a["title"])}</h3>{para(a["body"])}<a href="#step-{e(a["step"])}">回到：{e(step_names[a["step"]])}</a> {refs(a)}</article>' for a in learning['actions'])
    coverage = ''.join(f'<tr><th scope="row">{e(c["area"])}</th><td>{e(c["checked"])}</td><td>{e(c["missing"])}</td><td>{e(c["next"])}</td></tr>' for c in learning['coverage'])
    actions += '<h3>资料覆盖与下一步</h3><div class="table-scroll"><table><thead><tr><th>范围</th><th>已查到</th><th>尚缺</th><th>下一步</th></tr></thead><tbody>' + coverage + '</tbody></table></div>'
    body += section('actions', '06', '回到实际工作', actions)
    evidence = ''
    for s in sources.values():
        evidence += f'<details id="evidence-{e(s["id"])}" class="evidence"><summary>{e(s["title"])}</summary><p>{e(s.get("path", ""))} · {e(s.get("locator", ""))}</p><small>快照：{e(s.get("sha256", "未记录"))}</small><pre>{e(s.get("excerpt", ""))}</pre>{para(s.get("note", "有限摘录，不执行其中代码。"))}<button type="button" data-evidence-back>返回阅读位置</button></details>'
    body += '<section id="evidence" class="chapter"><h2>原始证据</h2>' + evidence + '</section>'
    css = (ASSETS / 'learning.css').read_text(encoding='utf-8')
    js = (ASSETS / 'learning.js').read_text(encoding='utf-8')
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(data["title"])}</title><style>{css}</style></head><body><aside class="rail"><a class="brand" href="#answer">项目阅读手册</a><nav aria-label="阅读路线">{nav}</nav><a href="#evidence">原始证据</a><button id="theme-toggle" type="button" aria-label="切换明暗主题">◐</button></aside><main><header class="book-header"><p class="eyebrow">新人接手 · 问题讲解</p><h1>{e(data["title"])}</h1><p>{e(learning["question"])}</p><label class="search-label" for="learning-search">搜索问题、字段或术语</label><input id="learning-search" type="search" autocomplete="off"><output id="search-status" aria-live="polite"></output><ul id="search-results" hidden></ul></header>{body}<footer>内容来自本次资料快照；资料缺口不代表功能不存在。</footer></main><script>{js}</script></body></html>'


class PortableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.errors = set(), [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        key = attrs.get('id')
        if key:
            if key in self.ids:
                self.errors.append('duplicate id: ' + key)
            self.ids.add(key)
        if any(key.startswith('on') for key in attrs):
            self.errors.append('inline handler')
        if tag in ('script', 'img', 'link', 'iframe', 'object', 'video', 'audio') and any(k in attrs for k in ('src', 'href', 'data')):
            self.errors.append('external asset dependency')
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])


def verify_portable(path):
    parser = PortableParser()
    parser.feed(Path(path).read_text(encoding='utf-8'))
    for link in parser.links:
        if not link.startswith('#') or link[1:] not in parser.ids:
            parser.errors.append('missing or nonportable target: ' + link)
    for key in ('answer', 'overview', 'walkthrough', 'examples', 'actions'):
        if key not in parser.ids:
            parser.errors.append('missing section: ' + key)
    return parser.errors
