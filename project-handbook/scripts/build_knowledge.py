#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render reviewed knowledge JSON into a navigable visual handbook. No source execution."""
import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path
from build_handbook import build, HandbookError

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r'^[a-z][a-z0-9-]{0,44}$')
STATUS = {'verified', 'declared', 'partial', 'open'}
STATUS_LABELS = {'verified': '已核对', 'declared': '配置/文档声明', 'partial': '部分核对', 'open': '待补充'}
RESERVED_PAGES = {'index', 'reading-guide', 'architecture', 'flows', 'risks'}
STEP_KINDS = {'start', 'check', 'formula', 'end', 'exit', 'note'}
TONES = {'a', 'b', 'c', 'd', 'shared'}
LINE_TAGS = {'att', 'def', 'cond', 'both', 'base'}

def e(value):
    return html.escape(str(value), quote=True)

def validate_step_list(steps, source_ids, system_ids, where):
    if not isinstance(steps, list):
        raise ValueError(where + ' steps must be an array')
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError(where + ' steps must be objects')
        if step.get('status', 'partial') not in STATUS:
            raise ValueError('invalid flow step status')
        if step.get('kind') and step['kind'] not in STEP_KINDS:
            raise ValueError('invalid step kind: ' + str(step.get('kind')))
        if step.get('tone') and step['tone'] not in TONES:
            raise ValueError('invalid step tone: ' + str(step.get('tone')))
        for ref in step.get('systems', []):
            if ref not in system_ids:
                raise ValueError('unknown system: ' + ref)
        for ref in step.get('sources', []):
            if ref not in source_ids:
                raise ValueError('unknown source: ' + ref)
        for line in step.get('lines') or []:
            if not isinstance(line, dict) or not str(line.get('text', '')).strip():
                raise ValueError(where + ' line requires text')
            if line.get('tag') and line['tag'] not in LINE_TAGS:
                raise ValueError('invalid line tag: ' + str(line.get('tag')))
        for group in step.get('groups') or []:
            if not isinstance(group, dict):
                raise ValueError(where + ' groups must be objects')
            if group.get('tone') and group['tone'] not in TONES:
                raise ValueError('invalid group tone: ' + str(group.get('tone')))
            validate_step_list(group.get('steps', []), source_ids, system_ids, where + ' group')
        if step.get('branches'):
            if not isinstance(step['branches'], list):
                raise ValueError(where + ' branches must be an array')
            for branch in step['branches']:
                if not isinstance(branch, dict) or not str(branch.get('title', '')).strip():
                    raise ValueError(where + ' branch requires title')
                if branch.get('tone') and branch['tone'] not in TONES:
                    raise ValueError('invalid branch tone: ' + str(branch.get('tone')))
                validate_step_list(branch.get('steps', []), source_ids, system_ids, where + ' branch')

def validate(data):
    if not isinstance(data, dict) or not data.get('title') or not data.get('book_id'):
        raise ValueError('title and book_id required')
    systems = data.get('systems', [])
    sources = data.get('sources', [])
    if not systems: raise ValueError('systems required')
    ids = set()
    for item in systems + sources:
        key = item.get('id', '')
        if not ID.fullmatch(key) or key in ids or key in {'index', 'reading-guide'} or key.startswith('source-'):
            raise ValueError('invalid or duplicate id: ' + key)
        ids.add(key)
    source_ids = {s['id'] for s in sources}
    system_ids = {s['id'] for s in systems}
    for system in systems:
        node_ids = set()
        for node in system.get('nodes', []):
            key = node.get('id','')
            if not ID.fullmatch(key) or key in node_ids: raise ValueError('invalid or duplicate node id')
            node_ids.add(key)
            for ref in node.get('sources', []):
                if not isinstance(ref, str): raise ValueError('source reference must be a string')
                if ref not in source_ids: raise ValueError('unknown source: ' + ref)
            for ref in node.get('related', []):
                if ref not in system_ids: raise ValueError('unknown system: ' + ref)
    for rel in data.get('relations', []):
        if rel.get('from') not in system_ids or rel.get('to') not in system_ids:
            raise ValueError('unknown relation endpoint')
    project = data.get('project') or {}
    if not isinstance(project, dict): raise ValueError('project must be an object')
    for item in project.get('layers', []) + project.get('entrypoints', []) + project.get('runtime', []):
        if not isinstance(item, dict): raise ValueError('project items must be objects')
        if item.get('status', 'declared') not in STATUS: raise ValueError('invalid project status')
        for ref in item.get('sources', []):
            if ref not in source_ids: raise ValueError('unknown source: ' + ref)
    flow_ids = set()
    for flow in data.get('flows', []):
        key = flow.get('id', '')
        if not ID.fullmatch(key) or key in flow_ids or key in RESERVED_PAGES: raise ValueError('invalid or duplicate flow id: ' + key)
        flow_ids.add(key)
        if flow.get('status', 'partial') not in STATUS: raise ValueError('invalid flow status')
        if flow.get('tone') and flow['tone'] not in TONES: raise ValueError('invalid flow tone: ' + str(flow.get('tone')))
        validate_step_list(flow.get('steps', []), source_ids, system_ids, 'flow ' + key)
        lane_ids = set()
        for lane in flow.get('lanes') or []:
            if not isinstance(lane, dict): raise ValueError('flow lanes must be objects')
            lid = lane.get('id', '')
            if not ID.fullmatch(lid) or lid in lane_ids: raise ValueError('invalid or duplicate lane id: ' + lid)
            lane_ids.add(lid)
            if not str(lane.get('title', '')).strip(): raise ValueError('lane requires title: ' + lid)
            if lane.get('tone') and lane['tone'] not in TONES: raise ValueError('invalid lane tone: ' + str(lane.get('tone')))
            validate_step_list(lane.get('steps', []), source_ids, system_ids, 'lane ' + lid)
            for group in lane.get('groups') or []:
                if not isinstance(group, dict): raise ValueError('lane groups must be objects')
                if group.get('tone') and group['tone'] not in TONES: raise ValueError('invalid group tone')
                validate_step_list(group.get('steps', []), source_ids, system_ids, 'lane group')
        shared = flow.get('shared')
        if shared is not None:
            if not isinstance(shared, dict): raise ValueError('flow shared must be an object')
            if shared.get('tone') and shared['tone'] not in TONES: raise ValueError('invalid shared tone')
            validate_step_list(shared.get('steps', []), source_ids, system_ids, 'shared')
            for group in shared.get('groups') or []:
                if not isinstance(group, dict): raise ValueError('shared groups must be objects')
                if group.get('tone') and group['tone'] not in TONES: raise ValueError('invalid group tone')
                validate_step_list(group.get('steps', []), source_ids, system_ids, 'shared group')
    for risk in data.get('risks', []):
        if risk.get('status', 'open') not in STATUS: raise ValueError('invalid risk status')
        for ref in risk.get('sources', []):
            if ref not in source_ids: raise ValueError('unknown source: ' + ref)

def paragraph(text):
    return ''.join('<p>'+e(p)+'</p>' for p in str(text).split('\n') if p.strip())

def status_badge(status):
    value = status if status in STATUS else 'partial'
    return f'<span class="status-badge status-{value}">{STATUS_LABELS[value]}</span>'

def source_chips(refs, sources, origin='', prefix=''):
    return ''.join(
        f'<a class="evidence-chip" href="{prefix}source-{e(sid)}.html?from={e(origin)}">{e(sources[sid]["title"])} ↗</a>'
        for sid in refs if sid in sources
    )

TAG_LABELS = {'att': '入', 'def': '出', 'cond': '判断', 'both': '通用', 'base': '基'}

def short_label(text, limit=11):
    value = str(text).split('：')[0].strip()
    return value if len(value) <= limit else value[:limit - 1] + '…'

def system_status(system):
    kinds = [str(node.get('kind', '')) for node in system.get('nodes', [])]
    if kinds and all('待确认' in kind or '缺口' in kind for kind in kinds):
        return 'open'
    if kinds and any('待确认' in kind or '缺口' in kind for kind in kinds):
        return 'partial'
    if kinds and all('已核对' in kind for kind in kinds):
        return 'verified'
    return 'declared'

def primary_path_ids(flows, systems):
    path = []
    if not flows:
        return path
    def add_from(steps):
        for step in steps or []:
            for sid in step.get('systems', []):
                if sid in systems and sid not in path:
                    path.append(sid)
            for group in step.get('groups') or []:
                add_from(group.get('steps') or [])
            for branch in step.get('branches') or []:
                add_from(branch.get('steps') or [])
    flow = flows[0]
    add_from(flow.get('steps') or [])
    for group in flow.get('groups') or []:
        add_from(group.get('steps') or [])
    for lane in flow.get('lanes') or []:
        add_from(lane.get('steps') or [])
        for group in lane.get('groups') or []:
            add_from(group.get('steps') or [])
    shared = flow.get('shared') if isinstance(flow.get('shared'), dict) else {}
    add_from(shared.get('steps') or [])
    for group in shared.get('groups') or []:
        add_from(group.get('steps') or [])
    return path

def map_card(mid, kind, title, summary, status, href, extra='', visible=False):
    hidden = '' if visible else ' hidden'
    return (
        f'<article{hidden} class="map-card" data-map-card="{e(mid)}"><span class="section-kicker">{e(kind)}</span>'
        f'<h3>{e(title)} {status_badge(status)}</h3><p>{e(summary)}</p>{extra}'
        f'<a class="text-link" href="{e(href)}">打开详情 →</a></article>'
    )

def architecture_map(project, systems, relations, flows, page_href, layer_href):
    layers = list(project.get('layers') or [])
    path_ids = primary_path_ids(flows, systems)
    lead_flow = flows[0] if flows else {}
    col_w, node_w, node_h, pad_x = 292, 260, 70, 36
    layer_y, layer_h = 24, 64
    sys_y0 = 118 if layers else 24
    row_h = 108
    cols = max(len(layers), min(3, max(len(systems), 1)), 1)
    width = max(920, pad_x * 2 + cols * col_w)
    rows = (len(systems) + 2) // 3 if systems else 0
    height = sys_y0 + max(rows, 1) * row_h + 28
    def layer_id(item, index):
        return item.get('id') or f'layer-{index + 1}'

    layer_pos = {layer_id(item, i): (pad_x + i * col_w, layer_y) for i, item in enumerate(layers)}
    sys_pos = {key: (pad_x + (i % 3) * col_w, sys_y0 + (i // 3) * row_h) for i, key in enumerate(systems)}
    fills = {'verified': '#1f6b63', 'declared': '#2f5d68', 'partial': '#6a4e2c', 'open': '#7a3532'}
    svg = [
        f'<svg class="system-graph architecture-graph" viewBox="0 0 {width} {height}" role="group" aria-label="项目系统地图">'
        '<title>项目系统地图：点击节点查看职责和证据状态，主路径表示新人应先走的链路</title>'
        '<defs>'
        '<marker id="map-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7" fill="#7aa0a3"/></marker>'
        '<marker id="map-arrow-path" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7" fill="#e39a56"/></marker>'
        '</defs>'
    ]
    for rel in relations:
        if rel.get('from') not in sys_pos or rel.get('to') not in sys_pos:
            continue
        x, y = sys_pos[rel['from']]
        xx, yy = sys_pos[rel['to']]
        on_path = rel['from'] in path_ids and rel['to'] in path_ids
        cls = 'map-edge is-path' if on_path else 'map-edge'
        dash = '0' if on_path else '6 5'
        stroke = '#e39a56' if on_path else '#7aa0a3'
        width_n = '3' if on_path else '1.6'
        marker = 'map-arrow-path' if on_path else 'map-arrow'
        svg.append(
            f'<path class="{cls}" data-map-edge="{e(rel["from"])}:{e(rel["to"])}" d="M{x + node_w / 2} {y + node_h} C{x + node_w / 2} {y + node_h + 36}, {xx + node_w / 2} {yy - 28}, {xx + node_w / 2} {yy}" fill="none" stroke="{stroke}" stroke-width="{width_n}" stroke-dasharray="{dash}" marker-end="url(#{marker})"/>'
        )
    for a, b in zip(path_ids, path_ids[1:]):
        if any(rel.get('from') == a and rel.get('to') == b for rel in relations):
            continue
        if a not in sys_pos or b not in sys_pos:
            continue
        x, y = sys_pos[a]
        xx, yy = sys_pos[b]
        svg.append(
            f'<path class="map-edge is-path" data-map-edge="{e(a)}:{e(b)}" d="M{x + node_w / 2} {y + node_h} C{x + node_w / 2} {y + node_h + 36}, {xx + node_w / 2} {yy - 28}, {xx + node_w / 2} {yy}" fill="none" stroke="#e39a56" stroke-width="3" marker-end="url(#map-arrow-path)"/>'
        )
    for i, item in enumerate(layers):
        mid = layer_id(item, i)
        x, y = layer_pos[mid]
        status = item.get('status', 'declared')
        svg.append(
            f'<g class="map-node map-layer" tabindex="0" data-map-id="{e(mid)}" data-map-kind="layer" data-map-status="{e(status)}" role="button" aria-label="{e(item.get("title", mid))}">'
            f'<rect x="{x}" y="{y}" width="{node_w}" height="{layer_h}" rx="10" fill="{fills.get(status, "#2f5d68")}"/>'
            f'<text x="{x + 14}" y="{y + 22}" fill="#b7ddd8" font-size="11">LAYER {i + 1:02}</text>'
            f'<text x="{x + 14}" y="{y + 44}" fill="white" font-size="16">{e(short_label(item.get("title", mid)))}</text></g>'
        )
        if i + 1 < len(layers):
            nx, ny = layer_pos[layer_id(layers[i + 1], i + 1)]
            svg.append(f'<path class="map-edge map-layer-edge" d="M{x + node_w} {y + layer_h / 2} L{nx} {ny + layer_h / 2}" fill="none" stroke="#7aa0a3" stroke-width="1.8" marker-end="url(#map-arrow)"/>')
    for i, (key, sys_) in enumerate(systems.items()):
        x, y = sys_pos[key]
        status = system_status(sys_)
        on_path = '1' if key in path_ids else '0'
        path_mark = f' PATH {path_ids.index(key) + 1:02}' if key in path_ids else ''
        svg.append(
            f'<g class="map-node map-system" tabindex="0" data-map-id="{e(key)}" data-map-kind="system" data-map-status="{e(status)}" data-map-on-path="{on_path}" role="button" aria-label="{e(sys_["title"])}">'
            f'<rect x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="12" fill="{fills.get(status, "#2f5d68")}"/>'
            f'<text x="{x + 14}" y="{y + 24}" fill="#b7ddd8" font-size="11">{i + 1:02} / SYSTEM{path_mark}</text>'
            f'<text x="{x + 14}" y="{y + 48}" fill="white" font-size="15">{e(short_label(sys_["title"]))}</text></g>'
        )
    svg.append('</svg>')
    fallback = layer_href(0) if layers else (page_href(next(iter(systems))) if systems else '#')
    cards = [map_card('_default', 'SYSTEM MAP', '先看这一张图', project.get('purpose') or '先看分层、主路径和专题，再决定深入哪一页。', project.get('status', 'partial'), fallback, '<p>实线是新人主路径，虚线只是阅读关联，不是已验证调用。</p>', True)]
    for i, item in enumerate(layers):
        mid = layer_id(item, i)
        extra = f'<p>证据来源 {len(item.get("sources", []))} 个。这一层说明资料归属，不自动等于运行时调用。</p>'
        cards.append(map_card(mid, 'LAYER', item.get('title', mid), item.get('summary', ''), item.get('status', 'declared'), layer_href(i), extra))
    for key, sys_ in systems.items():
        extra = f'<p>{len(sys_.get("nodes", []))} 个节点。' + ('位于主路径。' if key in path_ids else '支线专题，主路径走完再看。') + '</p>'
        cards.append(map_card(key, 'SYSTEM', sys_['title'], sys_.get('summary', ''), system_status(sys_), page_href(key), extra))
    path_attr = ','.join(path_ids)
    default_lens = 'route' if path_ids else ('layers' if layers else 'domains')
    play = f'<button type="button" data-map-play>播放主路径</button>' if path_ids else ''
    flow_title = e(lead_flow.get('title', '主路径'))
    focus = path_ids[0] if path_ids else (layer_id(layers[0], 0) if layers else '')
    return (
        f'<section class="map-stage" data-map-stage data-lens="{default_lens}" data-map-path="{e(path_attr)}" data-map-focus="{e(focus)}">'
        f'<header class="map-toolbar"><div><span class="section-kicker">SYSTEM MAP</span><strong>{flow_title or "项目地图"}</strong></div>'
        f'<div class="map-lenses" role="group" aria-label="地图透镜">'
        f'<button type="button" data-map-lens="layers" aria-pressed="{str(default_lens == "layers").lower()}">分层</button>'
        f'<button type="button" data-map-lens="route" aria-pressed="{str(default_lens == "route").lower()}">主路径</button>'
        f'<button type="button" data-map-lens="domains" aria-pressed="{str(default_lens == "domains").lower()}">专题</button>'
        f'{play}</div></header>'
        f'<div class="map-shell"><div class="map-scroll">{"".join(svg)}</div>'
        f'<aside class="map-inspector" data-map-inspector>{"".join(cards)}</aside></div>'
        f'<p class="map-caption">默认透镜突出主路径。点击节点只聚焦，不跳页；打开详情后再进入专题。虚线是阅读关联，不是已验证调用链。</p></section>'
    )

def flow_arrow(label='', tone=''):
    cls = f' vf-arrow-label vf-tone-{e(tone)}' if tone else ' vf-arrow-label'
    extra = f'<div class="{cls.strip()}">{e(label)}</div>' if label else ''
    return f'<div class="vf-arrow" aria-hidden="true"><span class="vf-arrow-line"></span>{extra}<span class="vf-arrow-head"></span></div>'

def render_step_lines(step):
    lines = step.get('lines') or []
    if not lines:
        bits = []
        if step.get('action'):
            bits.append(f'<div class="vf-line"><span>{e(step["action"])}</span></div>')
        if step.get('output'):
            bits.append(f'<div class="vf-line"><span class="vf-op">得到：{e(step["output"])}</span></div>')
        return ''.join(bits)
    parts = []
    for line in lines:
        tag = line.get('tag') or ''
        label = line.get('label') or TAG_LABELS.get(tag, '')
        tag_html = f'<span class="vf-tag vf-tag-{e(tag)}">{e(label)}</span>' if label else ''
        note = f'<span class="vf-op">{e(line["note"])}</span>' if line.get('note') else ''
        parts.append(f'<div class="vf-line">{tag_html}<span>{e(line["text"])}</span>{note}</div>')
    return ''.join(parts)

def render_step_node(step, sources, origin, prefix=''):
    kind = step.get('kind') or 'formula'
    tone = step.get('tone') or 'shared'
    status = step.get('status', 'partial')
    title = step.get('label') or step.get('title') or ''
    phase = f'<div class="vf-phase">{e(step["phase"])}</div>' if step.get('phase') else ''
    chips = source_chips(step.get('sources', []), sources, origin, prefix)
    return (
        f'<article class="vf-node vf-{e(kind)} vf-tone-{e(tone)}">'
        f'{phase}<div class="vf-node-head"><strong>{e(title)}</strong> {status_badge(status)}</div>'
        f'{render_step_lines(step)}<div class="evidence-links">{chips}</div></article>'
    )

def render_groups(groups, sources, origin, prefix=''):
    parts = []
    for gi, group in enumerate(groups or []):
        tone = group.get('tone') or 'shared'
        title = group.get('title') or group.get('phase') or ''
        head = f'<div class="vf-phase">{e(title)}</div>' if title else ''
        inner = render_step_sequence(group.get('steps') or [], sources, f'{origin}.g{gi}', prefix)
        if gi:
            parts.append(flow_arrow(group.get('from_label') or ''))
        wide = ' vf-wide' if any(step.get('branches') for step in group.get('steps') or []) else ''
        parts.append(f'<div class="vf-group vf-tone-{e(tone)}{wide}">{head}{inner}</div>')
    return ''.join(parts)

def render_step_sequence(steps, sources, origin, prefix=''):
    parts = []
    for i, step in enumerate(steps or []):
        if i:
            parts.append(flow_arrow(step.get('from_label') or (steps[i - 1].get('handoff') or '')))
        node = render_step_node(step, sources, f'{origin}.{i}', prefix)
        parts.append(node)
        if step.get('groups'):
            inner = render_groups(step['groups'], sources, f'{origin}.{i}', prefix)
            if inner:
                parts.append(inner)
        if step.get('branches'):
            cols = []
            for branch in step['branches']:
                tone = branch.get('tone') or 'shared'
                inner = render_step_sequence(branch.get('steps') or [], sources, f'{origin}.{i}.{branch.get("id", "b")}', prefix)
                if not branch.get('steps'):
                    grouped = inner
                else:
                    grouped = f'<div class="vf-group vf-tone-{e(tone)}">{inner}</div>'
                cols.append(f'<div class="vf-branch-col"><div class="vf-branch-label vf-tone-{e(tone)}">{e(branch["title"])}</div>{grouped}</div>')
            parts.append(f'<div class="vf-branch-row">{"".join(cols)}</div>')
    return ''.join(parts)

def render_lane_body(item, sources, origin, prefix=''):
    chunks = []
    steps = item.get('steps') or []
    groups = item.get('groups') or []
    if item.get('start') and not (steps and steps[0].get('kind') == 'start'):
        tone = item.get('tone') or 'a'
        chunks.append(f'<div class="vf-node vf-start vf-tone-{e(tone)}">{e(item["start"])}</div>')
    if steps:
        if chunks:
            chunks.append(flow_arrow())
        chunks.append(render_step_sequence(steps, sources, origin, prefix))
    if groups:
        if chunks:
            chunks.append(flow_arrow())
        chunks.append(render_groups(groups, sources, origin, prefix))
    return ''.join(chunks)

def vertical_flow(flow, sources, prefix='pages/'):
    lanes = list(flow.get('lanes') or [])
    shared = flow.get('shared') if isinstance(flow.get('shared'), dict) else {}
    if not lanes:
        lanes = [{
            'id': 'main',
            'title': flow.get('title') or '主路径',
            'tone': flow.get('tone') or 'a',
            'start': '',
            'handoff': '',
            'steps': flow.get('steps') or [],
        }]
    buttons, panels, legend_items = [], [], []
    for i, lane in enumerate(lanes):
        lid = lane.get('id') or f'lane-{i + 1}'
        tone = lane.get('tone') or 'a'
        legend_items.append(f'<span class="vf-legend-item vf-tone-{e(tone)}">{e(lane.get("title", lid))}</span>')
        pressed = 'true' if i == 0 else 'false'
        hidden = '' if i == 0 else ' hidden'
        buttons.append(
            f'<button type="button" class="vf-toggle-btn vf-tone-{e(tone)}" data-flow-lane="{e(lid)}" aria-pressed="{pressed}">{e(lane.get("title", lid))}</button>'
        )
        chunks = [render_lane_body(lane, sources, f'flow.{flow.get("id", "main")}.{lid}', prefix)]
        if shared.get('steps') or shared.get('groups'):
            chunks.append(flow_arrow(lane.get('handoff') or '', lane.get('tone') or 'a'))
        panels.append(f'<div class="vf-lane" data-flow-panel="{e(lid)}"{hidden}>{"".join(chunks)}</div>')
    toggle = f'<div class="vf-toggle" role="tablist">{"".join(buttons)}</div>' if len(lanes) > 1 else ''
    shared_html = ''
    if shared.get('steps') or shared.get('groups'):
        legend_items.append(f'<span class="vf-legend-item vf-tone-shared">{e(shared.get("title") or "共用段")}</span>')
        banner = shared.get('banner') or shared.get('title') or '共用段'
        shared_title = shared.get('title') or '共用段'
        shared_origin = 'flow.' + str(flow.get('id', 'main')) + '.shared'
        shared_html = (
            f'<div class="vf-separator" aria-hidden="true"><span class="vf-separator-line"></span>'
            f'<span class="vf-separator-text">▼ 以下为 {e(shared_title)} 共用结算</span>'
            f'<span class="vf-separator-line"></span></div>'
            f'<div class="vf-shared" id="shared-flow">'
            f'<div class="vf-shared-banner">{e(banner)}</div>'
            f'{render_lane_body(shared, sources, shared_origin, prefix)}'
            f'</div>'
        )
    legend = f'<div class="vf-legend">{"".join(legend_items)}</div>' if legend_items else ''
    return (
        f'<section class="vf-stage" data-flow-stage>'
        f'{toggle}{legend}<div class="vf-chart">{"".join(panels)}{shared_html}</div>'
        f'</section>'
    )

def render_knowledge(data, output):
    validate(data)
    output = Path(output).resolve()
    if output.exists(): raise ValueError('output already exists; choose a new directory: ' + str(output))
    sources = {s['id']:s for s in data.get('sources',[])}
    systems = {s['id']:s for s in data['systems']}
    system_slugs = {key: (key if key not in RESERVED_PAGES else 'topic-' + key) for key in systems}
    project = data.get('project') or {}
    flows = data.get('flows') or []
    risks = data.get('risks') or []
    fragments = {}
    pages = []
    flow_source_parents = {}

    def add(slug, title, lead, body, home=False, part='专题参考'):
        pages.append({'slug':slug, 'title':title, 'lead':lead, 'home':home, 'time':5, '_part':part})
        fragments[slug] = body

    def reader_question(system):
        return str(system.get('question') or system.get('summary') or system['title']).strip()

    def page_link(system_id, from_slug='index'):
        prefix = 'pages/' if from_slug == 'index' else ''
        return f'{prefix}{e(system_slugs[system_id])}.html'

    cards = ''.join(
        f'<a class="atlas-card topic-card" href="{page_link(s["id"])}"><span class="atlas-number">Q{i+1:02}</span><strong>{e(reader_question(s))}</strong><p>{e(s["title"])}</p><small>{len(s.get("nodes",[]))} 个图解节点 · 展开专题 →</small></a>'
        for i, s in enumerate(systems.values())
    )
    relations = ''.join(
        f'<li><a href="{page_link(r["from"])}">{e(systems[r["from"]]["title"])}</a><span> → {e(r["label"])} → </span><a href="{page_link(r["to"])}">{e(systems[r["to"]]["title"])}</a><small> · {e(r.get("status","阅读关联"))}</small></li>'
        for r in data.get('relations',[])
    )
    first = max(systems, key=lambda k: len(systems[k].get('nodes',[])))
    first_title = systems[first]['title']
    if not flows:
        flows = [{'id': 'topic-deep-dive', 'title': f'先理解：{first_title}', 'goal': '按专题节点从入口读到边界。', 'status': 'partial', 'steps': [{'label': n['title'], 'action': n.get('body', ''), 'output': '继续阅读下一个节点。', 'systems': [first], 'sources': n.get('sources', []), 'status': 'partial'} for n in systems[first].get('nodes', [])]}]
    lead_flow = flows[0]
    flow_title = lead_flow.get('title') or f'沿“{first_title}”读一条主链'
    flow_goal = lead_flow.get('goal') or '从入口一路读到证据边界，先形成可复述的故事。'
    lead_risk = next((risk for risk in risks if risk.get('impact') == 'high'), risks[0] if risks else {})
    risk_title = lead_risk.get('title') or '资料边界仍需确认'
    purpose = project.get('purpose') or data.get('summary', '先建立项目骨架，再沿一条深链核对证据。')
    audience = project.get('audience') or '刚接手项目、需要快速判断入口和风险的新人。'
    layer_count = len(project.get('layers', []))
    flow_count = len(flows)
    risk_count = len(risks)
    home_flow = vertical_flow(lead_flow, sources, 'pages/') if lead_flow else ''
    home = (
        f'<div class="onboarding-hero"><p class="eyebrow">VERTICAL FLOW</p><h1>{e(data["title"])}</h1>'
        f'<p class="onboarding-purpose">{e(purpose)}</p><p class="onboarding-audience">适合：{e(audience)}</p>'
        f'<p class="hero-stats"><span>{flow_count or 1} 条主链路</span><span>{layer_count or len(systems)} 个证据层</span><span>{risk_count or 1} 个待确认边界</span></p>'
        f'<a class="btn primary" href="#question-flow">先看这一张图</a> <a href="pages/flows.html">打开步骤说明 →</a></div>'
        f'<h2 id="question-flow">{e(flow_title)}</h2><p class="map-next">{e(flow_goal)}</p>'
        f'{home_flow}'
        f'<p class="map-risk">当前最大缺口：<a href="pages/risks.html">{e(risk_title)}</a>。</p>'
        f'<details class="topic-index"><summary>{len(systems)} 个专题入口，用来定位重难点</summary><div class="atlas-grid">{cards}</div></details>'
        f'<details class="topic-index"><summary>跨系统阅读路线</summary><ul class="atlas-relations">{relations}</ul></details>'
        f'<div class="callout warn"><strong>证据边界</strong><p>这张竖向图只回答钉住的问题。声明节点不等于已核验运行代码；共用段里未入库的内层公式必须标成待补充。打开风险页可以看到下一步需要补什么。</p></div>'
    )
    add('index', data['title'], '先看一张竖向流程图，再沿证据核对声明与缺口。', home, True, '开始')

    project_layer_items = project.get('layers', [])
    def next_layer_link(index):
        if index + 1 >= len(project_layer_items):
            return ''
        return f'<a class="layer-next" href="#layer-{index + 2}">继续看下一层 →</a>'
    project_layers = ''.join(
        f'<li id="layer-{i + 1}"><strong>{e(item.get("title", item.get("id", "未命名")))}</strong> {status_badge(item.get("status", "declared"))}<p>{e(item.get("summary", ""))}</p>{source_chips(item.get("sources", []), sources, "architecture.layer")}{next_layer_link(i)}</li>'
        for i, item in enumerate(project_layer_items)
    ) or '<li id="layer-1"><strong>专题集合</strong> ' + status_badge('partial') + '<p>当前资料没有单独声明项目分层，先从专题和来源关系建立阅读骨架。</p></li>'
    entrypoints = ''.join(
        f'<li><strong>{e(item.get("title", "入口"))}</strong> {status_badge(item.get("status", "declared"))}<code>{e(item.get("path", ""))}</code><p>{e(item.get("summary", ""))}</p>{source_chips(item.get("sources", []), sources, "architecture.entry")}</li>'
        for item in project.get('entrypoints', [])
    ) or '<li>没有单独登记入口；需要从源码和旧文档补充启动、路由或模块入口。</li>'
    runtime = ''.join(
        f'<li><strong>{e(item.get("title", "运行方式"))}</strong> {status_badge(item.get("status", "declared"))}<pre>{e(item.get("command", ""))}</pre><p>{e(item.get("summary", ""))}</p></li>'
        for item in project.get('runtime', [])
    ) or '<li>没有运行命令证据。</li>'
    architecture_body = (
        f'<nav class="trail"><a href="../index.html">← 开始</a><span>/ 项目地图</span></nav>'
        f'<h2>项目由什么组成</h2><p>{e(purpose)}</p>'
        + architecture_map(
            project, systems, data.get('relations', []), flows,
            lambda key: page_link(key, 'architecture'),
            lambda i: f'#layer-{i + 1}',
        )
        + f'<h2>分层职责</h2><p class="map-caption">按资料归属排列：先看每层职责，再沿入口、链路和来源逐层确认。</p><ul class="map-list">{project_layers}</ul>'
        f'<h2>从哪里进入</h2><ul class="map-list">{entrypoints}</ul>'
        f'<h2>怎么运行</h2><ul class="map-list">{runtime}</ul>'
    )
    add('architecture', '项目地图', '看懂分层、入口、运行方式和证据状态。', architecture_body, False, '项目地图')

    def flatten_steps(steps):
        items = []
        for step in steps or []:
            items.append(step)
            for group in step.get('groups') or []:
                items.extend(flatten_steps(group.get('steps') or []))
            for branch in step.get('branches') or []:
                items.extend(flatten_steps(branch.get('steps') or []))
        return items

    def flatten_block(block):
        items = flatten_steps((block or {}).get('steps') or [])
        for group in (block or {}).get('groups') or []:
            items.extend(flatten_steps(group.get('steps') or []))
        return items

    def all_flow_steps(flow):
        items = flatten_block(flow)
        for lane in flow.get('lanes') or []:
            items.extend(flatten_block(lane))
        items.extend(flatten_block(flow.get('shared') if isinstance(flow.get('shared'), dict) else {}))
        return items

    def collect_flow_sources(block, origin_prefix, flow_id, flow_title):
        steps = (block or {}).get('steps') or []
        for i, step in enumerate(steps):
            origin = origin_prefix + '.' + str(i)
            for sid in step.get('sources', []):
                flow_source_parents.setdefault(sid, []).append((origin, flow_id, flow_title, step.get('label', '步骤 ' + str(i + 1))))
            for gi, group in enumerate(step.get('groups') or []):
                collect_flow_sources(group, origin + '.g' + str(gi), flow_id, flow_title)
            for branch in step.get('branches') or []:
                collect_flow_sources(branch, origin + '.' + str(branch.get('id', 'b')), flow_id, flow_title)
        for gi, group in enumerate((block or {}).get('groups') or []):
            collect_flow_sources(group, origin_prefix + '.g' + str(gi), flow_id, flow_title)

    flow_body = '<nav class="trail"><a href="../index.html">← 开始</a><span>/ 关键链路</span></nav><p>链路页回答“一个任务是怎么走的”。首页是可切换竖图；这里保留逐步说明和证据。</p>'
    for flow in flows:
        flow_body += f'<article class="flow-story" id="{e(flow["id"])}"><header><span class="section-kicker">FLOW</span><h2>{e(flow["title"])}</h2>{status_badge(flow.get("status", "partial"))}<p>{e(flow.get("goal", ""))}</p></header>'
        if flow.get('lanes') or flow.get('shared'):
            flow_body += vertical_flow(flow, sources, '')
        flow_body += '<ol class="flow-sequence">'
        collect_flow_sources(flow, 'flow.' + flow['id'], flow['id'], flow.get('title', ''))
        for lane in flow.get('lanes') or []:
            collect_flow_sources(lane, 'flow.' + flow['id'] + '.' + lane.get('id', 'lane'), flow['id'], flow.get('title', ''))
        shared = flow.get('shared') if isinstance(flow.get('shared'), dict) else {}
        collect_flow_sources(shared, 'flow.' + flow['id'] + '.shared', flow['id'], flow.get('title', ''))
        for i, step in enumerate(all_flow_steps(flow)):
            step_id = f'flow-{flow["id"]}-{i}'
            origin = f'flow.{flow["id"]}.{i}'
            system_links = ''.join(f'<a href="{page_link(sid, "flows")}">{e(systems[sid]["title"])}</a> ' for sid in step.get('systems', []) if sid in systems)
            action = step.get('action') or ' '.join(str(line.get('text', '')) for line in (step.get('lines') or []) if line.get('text'))
            flow_body += f'<li class="flow-sequence-step" id="{e(step_id)}"><span class="flow-step">{i+1:02}</span><div><h3>{e(step.get("label", f"步骤 {i+1}"))} {status_badge(step.get("status", "partial"))}</h3><p><strong>做什么：</strong>{e(action)}</p><p><strong>得到什么：</strong>{e(step.get("output", ""))}</p><p class="flow-systems">所属专题：{system_links or "待补充"}</p><div class="evidence-links">{source_chips(step.get("sources", []), sources, origin)}</div></div></li>'
        flow_body += '</ol></article>'
    add('flows', '关键链路', '用任务顺序理解入口、边界和输出，不把关系图误当调用链。', flow_body, False, '关键链路')

    risk_items = ''.join(
        f'<li class="risk-item risk-{e(risk.get("impact", "medium"))}"><div><h3>{e(risk.get("title", "待确认项"))} {status_badge(risk.get("status", "open"))}</h3><p>{e(risk.get("detail", ""))}</p><p><strong>下一步：</strong>{e(risk.get("next", "补充来源并重新核对。"))}</p><div class="evidence-links">{source_chips(risk.get("sources", []), sources, "risk")}</div></div></li>'
        for risk in risks
    ) or '<li class="risk-item"><div><h3>项目边界仍需确认 ' + status_badge('open') + '</h3><p>当前资料无法覆盖所有服务端、运行环境和线上状态。</p><p><strong>下一步：</strong>补充入口、链路和落库证据。</p></div></li>'
    add('risks', '风险与缺口', '明确哪些地方不能猜，以及接手后应该先补什么。', f'<nav class="trail"><a href="../index.html">← 开始</a><span>/ 风险与缺口</span></nav><h2>先看这些边界</h2><p>风险不是失败清单，而是新人接手时最需要确认的下一组问题。</p><ul class="risk-list">{risk_items}</ul>', False, '风险与缺口')

    for system in systems.values():
        nodes = system.get('nodes', [])
        kinds = list(dict.fromkeys(n.get('kind', '配置声明') for n in nodes))
        filters = '<div class="atlas-filters" role="group" aria-label="筛选证据类型"><button type="button" data-filter="all" aria-pressed="true">全部节点</button>' + ''.join(f'<button type="button" data-filter="{e(k)}" aria-pressed="false">{e(k)}</button>' for k in kinds) + '</div>'
        mini = '<nav class="flow-minimap" aria-label="本专题路线">' + ''.join(f'<a href="#{e(n["id"])}">{i+1}. {e(n["title"])}</a>' for i, n in enumerate(nodes)) + '</nav>'
        body = '<nav class="trail"><a href="../index.html">← 全局地图</a><span>/ {title}</span></nav>'.format(title=e(system['title'])) + paragraph(system.get('intro', system['summary'])) + mini + filters + '<div class="flow-stack">'
        for i, n in enumerate(nodes):
            refs = source_chips(n.get('sources', []), sources, f'{system["id"]}.{n["id"]}')
            related = ''.join(f'<a href="{page_link(s, system_slugs[system["id"]])}">继续：{e(systems[s]["title"])} →</a> ' for s in n.get('related', []) if s in systems)
            body += f'<section class="flow-node" data-kind="{e(n.get("kind", "配置声明"))}"><span class="flow-step">{i+1:02}</span><small class="evidence-kind">{e(n.get("kind", "配置声明"))}</small><h2 id="{e(n["id"])}">{e(n["title"])}</h2>{paragraph(n["body"])}'
            if n.get('details'): body += '<details><summary>展开字段、条件和分支</summary>' + paragraph(n['details']) + '</details>'
            if n.get('branches'):
                body += '<div class="branch-group"><p class="branch-prompt">选择一种情况，查看分支结果：</p><div class="branch-tabs">' + ''.join(f'<button type="button" data-branch="{i}" aria-pressed="{str(i == 0).lower()}">{e(b["title"])}</button>' for i, b in enumerate(n['branches'])) + '</div>'
                for i, b in enumerate(n['branches']):
                    body += f'<div class="branch-result" data-branch-panel="{i}" {"hidden" if i else ""}><strong>{e(b["title"])}</strong>{paragraph(b["body"])}</div>'
                body += '</div>'
            body += f'<div class="evidence-links">{refs}</div><div class="node-actions"><button type="button" data-ask="请解释{e(system["title"])}中的{e(n["title"])}，说明依据和未确认的部分。" data-node-title="{e(n["title"])}">问这个节点</button>{related}</div></section>'
        add(system_slugs[system['id']], system['title'], system['summary'], body + '</div>', False, '专题参考')

    for s in sources.values():
        system_parents = [(sys_, n) for sys_ in systems.values() for n in sys_.get('nodes', []) if s['id'] in n.get('sources', [])]
        flow_parents = flow_source_parents.get(s['id'], [])
        if system_parents:
            primary = system_parents[0]
            return_href = f'{system_slugs[primary[0]["id"]]}.html#{primary[1]["id"]}'
            flow_links = ''.join(f'<a class="return-flow" hidden data-return="{e(origin)}" href="flows.html#{e(fid)}">← 返回链路：{e(title)} / {e(label)}</a>' for origin, fid, title, label in flow_parents)
            trail = f'<nav class="trail"><a class="return-topic" data-return="{e(primary[0]["id"])}.{e(primary[1]["id"])}" href="{e(return_href)}">← 返回专题：{e(primary[0]["title"])} / {e(primary[1]["title"])}</a>{flow_links}<a href="../index.html">全局地图</a></nav>'
            backlinks = ''.join(f'<a data-return="{e(sys_["id"])}.{e(n["id"])}" href="{e(system_slugs[sys_["id"]])}.html#{e(n["id"])}">{e(sys_["title"])} / {e(n["title"])} →</a><br>' for sys_, n in system_parents)
            backlinks += ''.join(f'<a class="return-flow" hidden data-return="{e(origin)}" href="flows.html#{e(fid)}">{e(title)} / {e(label)} →</a><br>' for origin, fid, title, label in flow_parents)
        elif flow_parents:
            origin, flow_id, flow_title, step_label = flow_parents[0]
            return_href = f'flows.html#{flow_id}'
            trail = f'<nav class="trail"><a class="return-topic return-flow" data-return="{e(origin)}" href="{e(return_href)}">← 返回链路：{e(flow_title)} / {e(step_label)}</a><a href="../index.html">全局地图</a></nav>'
            backlinks = ''.join(f'<a class="return-flow" data-return="{e(origin)}" href="flows.html#{e(fid)}">{e(title)} / {e(label)} →</a><br>' for origin, fid, title, label in flow_parents)
        else:
            trail = '<nav class="trail"><a href="../index.html">← 全局地图</a></nav>'
            backlinks = '<p>这份来源尚未挂到项目地图、链路或专题节点。</p>'
        body = f'{trail}<h2>来源定位</h2><p class="source-locator">{e(s.get("path", ""))}<br>{e(s.get("locator", ""))}</p><button type="button" data-copy="{e(s.get("path", ""))} · {e(s.get("locator", ""))}">复制来源位置</button><p>快照 SHA256：<code>{e(s.get("sha256", "未记录"))}</code></p><h2>原始证据摘录</h2><pre class="source-excerpt">{e(s.get("excerpt", ""))}</pre><p>{e(s.get("note", "此处是有限摘录，不执行其中的代码。需要完整语义时请打开原文件核对。"))}</p><h2>返回刚才的上下文</h2>{backlinks}'
        add('source-' + s['id'], s['title'], s.get('locator', '来源详情') or '来源详情', body, False, '证据索引')

    add('reading-guide', '阅读与问答指南', '遇到资料缺口或模型未连接时如何继续。', '<h2>如何阅读</h2><p>先看首页竖向流程图：切换入口看专属段，再读下方共用段。节点上的状态标明“已核对、声明、部分核对或待补充”。系统地图是可选加厚，不替代这张主图。</p><h2>边看边问</h2><p>点击“问这个节点”把问题送到右侧。默认是本地证据检索，不消耗模型额度，也不生成推理答案。选择模型问答后，填写接口地址和 API Key，点击“获取模型”，选好模型再提问。</p><h2>资料没有答案怎么办</h2><p>先看风险与缺口页，确认需要补哪类来源；再回到 agent 补充节点与引用，然后重建手册。</p><h2>本地启动</h2><pre>python project-handbook/scripts/chat_server.py &lt;手册目录&gt;</pre>', False, '开始')

    for sub in ('content', 'assets', 'evidence'): (output / sub).mkdir(parents=True, exist_ok=True)
    for asset in ('style.css', 'app.js', 'chat.js', 'atlas.js'):
        if (ROOT / 'assets' / asset).exists(): shutil.copyfile(ROOT / 'assets' / asset, output / 'assets' / asset)
    labels = ['开始', '项目地图', '关键链路', '专题参考', '风险与缺口', '证据索引']
    parts = []
    for label in labels:
        part_pages = [{key: value for key, value in page.items() if key != '_part'} for page in pages if page.get('_part') == label]
        if part_pages:
            parts.append({'label': label, 'pages': part_pages})
    book = {'title': data['title'], 'subtitle': '一问一图 · 竖向流程 · 证据链路', 'version': '0.9.0', 'book_id': data['book_id'], 'atlas': True, 'chat': {'enabled': True, 'mode': 'relay', 'endpoint': '/api/chat'}, 'parts': parts}
    (output / 'book.json').write_text(json.dumps(book, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'knowledge.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    for slug, fragment in fragments.items(): (output / 'content' / f'{slug}.html').write_text(fragment, encoding='utf-8')
    build(output, False)
    return output

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('manifest',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args()
    try: render_knowledge(json.loads(args.manifest.read_text(encoding='utf-8')),args.output)
    except (ValueError,OSError,KeyError,TypeError,HandbookError) as exc:
        print('error: '+str(exc),file=sys.stderr); return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
