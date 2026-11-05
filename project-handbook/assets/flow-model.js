/* Flow checks and canvas placement, shared by the page and by tests.
 * Mirrors validate() and canvas_data() in scripts/build_flow.py so a page built
 * without Python is checked the same way; tests/flow_cases.json keeps them aligned. */
;(function (root) {
  'use strict';
  const RESERVED_IDS = ['data', 'nodes', 'edges', 'canvas', 'diagram', 'examples', 'detail',
    'detail-title', 'detail-text', 'detail-formula', 'source', 'next',
    'search', 'graph-title', 'graph-note', 'arrow', 'amber-arrow',
    'viewport', 'stage', 'zoom-in', 'zoom-out', 'zoom-reset', 'zoom-fit',
    'zoom-value', 'search-prev', 'search-next', 'search-count',
    'section-jump', 'route-bar', 'route-title', 'route-clear',
    'detail-links', 'detail-from', 'detail-to', 'detail-answers',
    'flow-title', 'flow-summary', 'example-list', 'flow-error', 'active-arrow', 'route-arrow'];
  const KINDS = ['process', 'decision', 'switch', 'terminal', 'merge'];
  const MAX_COLUMNS = 4, MAX_SWITCH_EXITS = 6;

  const fail = (where, message) => { throw new Error(where + ': ' + message); };
  const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  function field(item, key, kind, where) {
    if (!isObject(item)) fail(where, 'must be an object');
    if (!(key in item)) fail(where, 'missing "' + key + '"');
    const value = item[key];
    if (kind === 'int' && !(Number.isInteger(value) && typeof value === 'number')) fail(where + '.' + key, 'must be a whole number');
    if (kind === 'str' && typeof value !== 'string') fail(where + '.' + key, 'must be text');
    if (kind === 'list' && !Array.isArray(value)) fail(where + '.' + key, 'must be a list');
    if (kind === 'dict' && !isObject(value)) fail(where + '.' + key, 'must be an object');
    return value;
  }

  function validate(data) {
    if (!isObject(data)) fail('flow', 'must be an object');
    field(data, 'title', 'str', 'flow');
    const graphs = field(data, 'graphs', 'list', 'flow');
    if (!graphs.length) fail('graphs', 'needs at least one section');
    const sources = field(data, 'sources', 'list', 'flow');
    const sourceIds = new Set();
    sources.forEach((source, index) => {
      const where = 'sources[' + index + ']';
      const id = field(source, 'id', 'str', where);
      field(source, 'locator', 'str', where);
      if (sourceIds.has(id)) fail(where, 'duplicate source id "' + id + '"');
      sourceIds.add(id);
    });
    const used = new Set();
    const identifier = (value, where) => {
      if (typeof value !== 'string' || !/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(value))
        fail(where, 'id ' + JSON.stringify(value) + ' must start with a letter and use only letters, digits, - and _');
      if (RESERVED_IDS.includes(value) || value.startsWith('flow-qa-'))
        fail(where, 'id "' + value + '" is used by the page itself; choose another, such as "' + value + '-step"');
      if (used.has(value)) fail(where, 'id "' + value + '" is already used by another section or node');
      used.add(value);
    };
    const cited = (value, where) => { if (!sourceIds.has(value)) fail(where, 'source "' + value + '" is not listed in sources'); };
    const graphIds = new Set();
    graphs.forEach((graph, g) => {
      const gwhere = 'graphs[' + g + ']';
      identifier(field(graph, 'id', 'str', gwhere), gwhere + '.id');
      graphIds.add(graph.id);
      field(graph, 'title', 'str', gwhere);
      cited(field(graph, 'source', 'str', gwhere), gwhere + '.source');
      const nodes = field(graph, 'nodes', 'list', gwhere);
      if (!nodes.length) fail(gwhere, 'section has no nodes');
      const occupied = new Map();
      nodes.forEach((n, i) => {
        let where = gwhere + '.nodes[' + i + ']';
        identifier(field(n, 'id', 'str', where), where + '.id');
        where = gwhere + '.nodes[' + i + '] (' + n.id + ')';
        const row = field(n, 'row', 'int', where), col = field(n, 'col', 'int', where);
        if (row < 0 || col < 0 || col >= MAX_COLUMNS) fail(where, 'row must be 0 or more and col 0 to ' + (MAX_COLUMNS - 1));
        const cell = row + ',' + col;
        if (occupied.has(cell)) fail(where, 'same row and col as node "' + occupied.get(cell) + '"');
        occupied.set(cell, n.id);
        if (!KINDS.includes(field(n, 'kind', 'str', where))) fail(where, 'kind must be one of ' + KINDS.join(', '));
        for (const key of ['title', 'lines', 'detail']) field(n, key, 'str', where);
        if ('sources' in n) {
          if (!Array.isArray(n.sources) || !n.sources.length) fail(where + '.sources', 'must be a non-empty list of source ids');
          for (const source of n.sources) cited(source, where + '.sources');
        }
      });
      const ids = new Set(nodes.map(n => n.id)), seen = new Set();
      field(graph, 'edges', 'list', gwhere).forEach((edge, e) => {
        const where = gwhere + '.edges[' + e + ']';
        const a = field(edge, 'a', 'str', where), b = field(edge, 'b', 'str', where);
        for (const end of [a, b]) if (!ids.has(end)) fail(where, '"' + end + '" is not a node in this section; link sections with connections');
        if (seen.has(a + '\u0000' + b) || a === b) fail(where, 'duplicate edge or an edge to itself');
        seen.add(a + '\u0000' + b);
        if (!['normal', 'outer', 'bypass'].includes(edge.route === undefined ? 'normal' : edge.route)) fail(where + '.route', 'must be normal, outer or bypass');
        if ('label' in edge && typeof edge.label !== 'string') fail(where + '.label', 'must be text');
      });
      for (const n of nodes) {
        const where = gwhere + ' node "' + n.id + '"';
        const exits = graph.edges.filter(e => e.a === n.id);
        if (n.kind === 'decision') {
          const labels = exits.map(e => (e.label || '').split(' ')[0]).sort();
          if (labels.length !== 2 || labels[0] !== '否' || labels[1] !== '是')
            fail(where, 'a decision needs exactly one 是 edge and one 否 edge; use kind "switch" for three or more named outcomes');
        }
        if (n.kind === 'switch') {
          const labels = exits.map(e => (e.label || '').trim());
          if (exits.length < 2 || exits.length > MAX_SWITCH_EXITS || !labels.every(Boolean) || new Set(labels).size !== labels.length)
            fail(where, 'a switch needs 2 to ' + MAX_SWITCH_EXITS + ' edges, each with its own label');
        }
      }
      const reached = new Set([nodes[0].id]);
      for (let i = 0; i < nodes.length; i++) for (const e of graph.edges) if (reached.has(e.a)) reached.add(e.b);
      const missing = [...ids].filter(id => !reached.has(id)).sort();
      if (missing.length) fail(gwhere, 'not reachable from the first node: ' + missing.join(', '));
    });
    if (data.common && !graphIds.has(data.common)) fail('common', 'is not a section id');
    for (const key of ['connections', 'examples']) if (key in data && !Array.isArray(data[key])) fail('flow.' + key, 'must be a list');
    const allNodes = new Map(graphs.flatMap(g => g.nodes).map(n => [n.id, n]));
    const linked = new Set(graphs.flatMap(g => g.edges).map(e => e.a + '\u0000' + e.b));
    const connections = data.connections || [];
    for (const e of connections) if (isObject(e)) linked.add(e.a + '\u0000' + e.b);
    connections.forEach((edge, index) => {
      const where = 'connections[' + index + ']';
      const a = field(edge, 'a', 'str', where), b = field(edge, 'b', 'str', where);
      if (!allNodes.has(a) || !allNodes.has(b) || a === b) fail(where, 'must join two different existing nodes');
      if (['decision', 'switch'].includes(allNodes.get(a).kind)) fail(where, 'keep branch edges inside the section that owns the branch');
      if (!edge.label) fail(where, 'needs a label saying when the flow crosses sections');
    });
    (data.examples || []).forEach((example, index) => {
      const where = 'examples[' + index + ']';
      for (const key of ['title', 'provenance', 'input', 'result']) field(example, key, 'str', where);
      const trace = field(example, 'trace', 'list', where);
      if (!trace.every(step => typeof step === 'string')) fail(where + '.trace', 'must be a list of text steps');
      if ('path' in example) checkPath(example.path, allNodes, linked, where + '.path');
    });
  }

  function checkPath(path, nodes, linked, where) {
    if (!Array.isArray(path) || path.length < 2 || !path.every(id => typeof id === 'string'))
      fail(where, 'must list at least two node ids in the order the example walks them');
    for (const id of path) if (!nodes.has(id)) fail(where, '"' + id + '" is not a node');
    for (let i = 1; i < path.length; i++)
      if (!linked.has(path[i - 1] + '\u0000' + path[i]))
        fail(where, 'no edge from "' + path[i - 1] + '" to "' + path[i] + '"; list every node the example passes, in order');
  }

  // Place every section on one canvas. Connections are only the authored ones.
  function prepare(data) {
    const result = JSON.parse(JSON.stringify(data));
    const nodes = [], edges = [], occupied = new Set(), sections = [];
    let nextRow = 0;
    for (const graph of result.graphs) {
      const offset = graph.position || {row: nextRow, col: 0};
      if (!['row', 'col'].every(k => Number.isInteger(offset[k]) && offset[k] >= 0)) throw new Error('Invalid section position');
      for (const authored of graph.nodes) {
        // A copy, so graphs keep their own coordinates and can be placed again.
        const node = Object.assign({}, authored, {row: authored.row + offset.row, col: authored.col + offset.col});
        node.sources = (node.sources && node.sources.length ? node.sources : [graph.source]).slice();
        node.source = node.sources[0];
        const cell = node.row + ',' + node.col;
        if (occupied.has(cell)) throw new Error('Sections overlap on canvas');
        occupied.add(cell); nodes.push(node);
      }
      edges.push(...graph.edges);
      sections.push({id: graph.id, title: graph.title, nodes: graph.nodes.map(n => n.id)});
      nextRow = Math.max(...nodes.map(n => n.row)) + 2;
    }
    edges.push(...(result.connections || []));
    result.canvas = {nodes, edges, sections};
    return result;
  }

  const api = {validate, prepare, RESERVED_IDS, KINDS};
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.FlowModel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
