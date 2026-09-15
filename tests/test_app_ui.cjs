const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

class ClassList {
  constructor() { this.values = new Set(); }
  toggle(name, force) {
    const next = force === undefined ? !this.values.has(name) : force;
    if (next) this.values.add(name); else this.values.delete(name);
    return next;
  }
  contains(name) { return this.values.has(name); }
}

class El {
  constructor() {
    this.value = '';
    this.textContent = '';
    this.innerHTML = '';
    this.listeners = {};
    this.attributes = {};
    this.classList = new ClassList();
    this.children = [];
    this.hidden = false;
  }
  addEventListener(event, callback) { (this.listeners[event] ??= []).push(callback); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key]; }
  querySelectorAll(selector) { return selector === 'a' ? this.children : []; }
  fire(event, payload = {}) { for (const callback of this.listeners[event] || []) callback({ preventDefault() {}, target: this, ...payload }); }
  focus() {}
  showModal() { this.open = true; }
}

function setup() {
  const ids = {};
  for (const id of ['theme', 'menu', 'search-dialog', 'search', 'results', 'search-open', 'search-data']) ids[id] = new El();
  ids['search-data'].textContent = '[]';
  const sidebar = new El();
  const close = new El();
  const link = new El();
  sidebar.children = [link];
  const documentListeners = {};
  const storage = {};
  const localStorage = { getItem: key => storage[key] ?? null, setItem: (key, value) => { storage[key] = value; } };
  const sandbox = {
    document: {
      documentElement: { dataset: {} },
      getElementById: id => ids[id] || (id === 'sidebar-close' ? close : null),
      querySelector: selector => selector === '.sidebar' ? sidebar : null,
      addEventListener: (event, callback) => { (documentListeners[event] ??= []).push(callback); },
    },
    window: { HANDBOOK_BASE: '' },
    localStorage,
    console,
  };
  vm.runInNewContext(fs.readFileSync('project-handbook/assets/app.js', 'utf8'), sandbox);
  return { ids, sidebar, close, link, documentListeners };
}

const app = setup();
app.ids.menu.fire('click');
assert(app.sidebar.classList.contains('open'));
assert.equal(app.ids.menu.getAttribute('aria-expanded'), 'true');
assert.equal(app.ids.menu.getAttribute('aria-label'), '关闭导航');
app.close.fire('click');
assert(!app.sidebar.classList.contains('open'));
assert.equal(app.ids.menu.getAttribute('aria-expanded'), 'false');
app.ids.menu.fire('click');
app.link.fire('click');
assert(!app.sidebar.classList.contains('open'));
app.ids.menu.fire('click');
for (const listener of app.documentListeners.keydown || []) listener({ key: 'Escape', preventDefault() {} });
assert(!app.sidebar.classList.contains('open'));
console.log('PASS: sidebar close button, navigation links, Escape, and aria state');
