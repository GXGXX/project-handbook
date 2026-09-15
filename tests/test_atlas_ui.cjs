const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

class ClassList {
  constructor() { this.values = new Set(); }
  toggle(name, force) {
    const next = force === undefined ? !this.values.has(name) : !!force;
    if (next) this.values.add(name); else this.values.delete(name);
    return next;
  }
  contains(name) { return this.values.has(name); }
}

class El {
  constructor(attrs = {}) {
    this.attrs = Object.fromEntries(Object.entries(attrs).map(([k, v]) => [k, String(v)]));
    this.children = [];
    this.parent = null;
    this.hidden = false;
    this.classList = new ClassList();
    this.listeners = {};
  }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  getAttribute(key) { return Object.prototype.hasOwnProperty.call(this.attrs, key) ? this.attrs[key] : null; }
  appendChild(child) { child.parent = this; this.children.push(child); return child; }
  closest(selector) {
    let node = this;
    while (node) {
      if (matches(node, selector)) return node;
      node = node.parent;
    }
    return null;
  }
  querySelectorAll(selector) { return collect(this).filter(node => matches(node, selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

function collect(node) {
  const out = [];
  for (const child of node.children) {
    out.push(child, ...collect(child));
  }
  return out;
}

function matches(node, selector) {
  if (selector.startsWith('.')) return node.classList.contains(selector.slice(1));
  const attr = /^\[([^\]]+)\]$/.exec(selector);
  if (!attr) return false;
  const [key, value] = attr[1].split('=');
  if (value === undefined) return node.getAttribute(key) !== null;
  return node.getAttribute(key) === value.replace(/^"|"$/g, '');
}

function setupFlow() {
  const stage = new El({'data-flow-stage': ''});
  const a = new El({'data-flow-lane': 'path-a', 'aria-pressed': 'true'});
  const b = new El({'data-flow-lane': 'path-b', 'aria-pressed': 'false'});
  const panelA = new El({'data-flow-panel': 'path-a'});
  const panelB = new El({'data-flow-panel': 'path-b'});
  panelB.hidden = true;
  stage.appendChild(a);
  stage.appendChild(b);
  stage.appendChild(panelA);
  stage.appendChild(panelB);
  return { stage, a, b, panelA, panelB };
}

function setup() {
  const stage = new El({'data-map-stage': '', 'data-lens': 'route', 'data-map-path': 'growth,combat', 'data-map-focus': 'growth'});
  const layers = new El({'data-map-lens': 'layers', 'aria-pressed': 'false'});
  const route = new El({'data-map-lens': 'route', 'aria-pressed': 'true'});
  const play = new El({'data-map-play': ''});
  const growth = new El({'data-map-id': 'growth', 'data-map-on-path': '1'});
  const combat = new El({'data-map-id': 'combat', 'data-map-on-path': '1'});
  const growthCard = new El({'data-map-card': 'growth'});
  const combatCard = new El({'data-map-card': 'combat'});
  const defaultCard = new El({'data-map-card': '_default'});
  growth.classList.values.add('map-node');
  combat.classList.values.add('map-node');
  stage.appendChild(layers);
  stage.appendChild(route);
  stage.appendChild(play);
  stage.appendChild(growth);
  stage.appendChild(combat);
  stage.appendChild(growthCard);
  stage.appendChild(combatCard);
  stage.appendChild(defaultCard);
  const flow = setupFlow();
  const documentListeners = {};
  const sandbox = {
    document: {
      querySelectorAll: selector => selector === '[data-map-stage]' ? [stage] : selector === '[data-flow-stage]' ? [flow.stage] : [],
      addEventListener: (event, callback) => { (documentListeners[event] ??= []).push(callback); },
      getElementById: () => null,
    },
    window: {
      addEventListener() {},
      matchMedia: () => ({ matches: true }),
    },
    location: { hash: '', search: '' },
    URLSearchParams,
    navigator: {},
    WeakMap,
    setInterval,
    clearInterval,
    console,
  };
  vm.runInNewContext(fs.readFileSync('project-handbook/assets/atlas.js', 'utf8'), sandbox);
  return { stage, layers, route, play, growth, combat, growthCard, combatCard, defaultCard, documentListeners, flow };
}

const app = setup();
assert.equal(app.growthCard.hidden, false);
assert.equal(app.combatCard.hidden, true);
assert(app.growth.classList.contains('is-focus'));
for (const listener of app.documentListeners.click) listener({ target: app.layers, closest(sel) { return this.target.closest(sel); } });
assert.equal(app.stage.getAttribute('data-lens'), 'layers');
assert.equal(app.layers.getAttribute('aria-pressed'), 'true');
for (const listener of app.documentListeners.click) listener({ target: app.combat, closest(sel) { return this.target.closest(sel); } });
assert.equal(app.stage.getAttribute('data-map-focus'), 'combat');
assert.equal(app.combatCard.hidden, false);
assert.equal(app.growthCard.hidden, true);
assert(app.combat.classList.contains('is-focus'));
for (const listener of app.documentListeners.click) listener({ target: app.play, closest(sel) { return this.target.closest(sel); } });
assert.equal(app.stage.getAttribute('data-lens'), 'route');
assert.equal(app.growthCard.hidden, false);
assert.equal(app.flow.panelA.hidden, false);
assert.equal(app.flow.panelB.hidden, true);
for (const listener of app.documentListeners.click) listener({ target: app.flow.b, closest(sel) { return this.target.closest(sel); } });
assert.equal(app.flow.a.getAttribute('aria-pressed'), 'false');
assert.equal(app.flow.b.getAttribute('aria-pressed'), 'true');
assert.equal(app.flow.panelA.hidden, true);
assert.equal(app.flow.panelB.hidden, false);
console.log('PASS: map lens, node focus, path playback, and flow switch');
