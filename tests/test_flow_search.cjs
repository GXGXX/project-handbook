const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const {test, before, after} = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');

const scripts = path.resolve(__dirname, '../project-handbook/scripts');
const term = '\u91d1\u989d';
const nodes = [
  {id: 'title-hit', title: term + '\u786e\u8ba4', lines: 'Order_Total', detail: 'First step'},
  {id: 'lines-hit', title: '\u8bf7\u6c42\u6821\u9a8c', lines: '\u68c0\u67e5' + term, detail: 'Second step'},
  {id: 'detail-hit', title: '\u8d26\u672c\u5199\u5165', lines: '\u4fdd\u6301\u4e00\u81f4', detail: '\u5ba1\u6838' + term},
  {id: 'later-hit', title: '\u5ba1\u6838\u786e\u8ba4', lines: term + '\u540c\u6b65', detail: 'Later section'},
  {id: 'last-hit', title: '\u5b8c\u6210', lines: '\u66f4\u65b0\u72b6\u6001', detail: term + '\u7559\u6863'}
].map((node, index) => ({...node, row: index < 3 ? index : index - 3, col: index === 4 ? 1 : 0, kind: 'process'}));
function graph(id, items) {
  return {id, title: id, source: 'demo', nodes: items, edges: items.slice(1).map((node, i) => ({a: items[i].id, b: node.id}))};
}
const manifest = {
  title: '\u8ba2\u5355\u6d41\u7a0b', summary: '',
  sources: [{id: 'demo', locator: 'Synthetic source', excerpt: 'source-only-token'}],
  graphs: [graph('first-section', nodes.slice(0, 3)), graph('later-section', nodes.slice(3))],
  examples: [{title: 'example-only-token', provenance: 'Synthetic', input: 'Input', trace: ['Step'], result: 'Result'}]
};
function python(code, data) {
  return spawnSync(process.env.PYTHON_EXECUTABLE || 'python', ['-B', '-X', 'utf8', '-c', code, scripts], {
    input: JSON.stringify(data), encoding: 'utf8', maxBuffer: 4e6
  });
}
let browser, temp, url;
const screenshots = process.argv[2] && path.resolve(process.argv[2]);
before(async () => {
  const rendered = python('import sys,json; sys.path.insert(0,sys.argv[1]); from build_flow import render; print(render(json.load(sys.stdin)))', manifest);
  assert.equal(rendered.status, 0, rendered.stderr);
  temp = fs.mkdtempSync(path.join(os.tmpdir(), 'handbook-search-'));
  const file = path.join(temp, 'handbook.html');
  fs.writeFileSync(file, rendered.stdout);
  url = pathToFileURL(file).href;
  if (screenshots) fs.mkdirSync(screenshots, {recursive: true});
  browser = await chromium.launch({headless: true, executablePath: process.env.BROWSER_EXECUTABLE || undefined});
});
after(async () => {
  if (browser) await browser.close();
  if (temp) fs.rmSync(temp, {recursive: true, force: true});
});
async function openPage(t, viewport = {width: 1440, height: 1100}) {
  const page = await browser.newPage({viewport, offline: true});
  const errors = [], requests = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('request', request => {if (/^https?:/.test(request.url())) requests.push(request.url());});
  t.after(async () => {
    await page.close();
    assert.deepEqual(errors, [], 'no browser errors');
    assert.deepEqual(requests, [], 'offline search must not request remote assets');
  });
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  return page;
}
async function state(page, count, currentId) {
  assert.equal(await page.locator('#search-count').count(), 1, 'live current/total output must exist');
  assert.equal(await page.locator('#search-count').textContent(), count);
  assert.deepEqual(await page.locator('.node.current-match').evaluateAll(items => items.map(node => node.id)), currentId ? [currentId] : []);
  assert.equal(await page.locator('.node.match').count(), Number(count.split('/')[1]));
  for (const id of ['search-prev', 'search-next']) assert.equal(await page.locator('#' + id).isDisabled(), count === '0/0');
}
async function contained(page, selector = '.node.current-match') {
  assert(await page.locator(selector).evaluateAll(items => {
    const viewport = document.getElementById('viewport'), v = viewport.getBoundingClientRect();
    return items.length > 0 && items.every(node => {
      const r = node.getBoundingClientRect();
      return r.left >= v.left + viewport.clientLeft - 1 && r.top >= v.top + viewport.clientTop - 1 &&
        r.right <= v.left + viewport.clientLeft + viewport.clientWidth + 1 && r.bottom <= v.top + viewport.clientTop + viewport.clientHeight + 1;
    });
  }), 'complete node bounds must fit inside the canvas viewport');
}
async function toolbarBounds(page) {
  return page.locator('.search-tools').evaluate(element => {
    const controls = [...element.querySelectorAll('input,output,button')].map(node => {
      const r = node.getBoundingClientRect();
      return {id: node.id, x: r.x, y: r.y, width: r.width, height: r.height};
    });
    for (let i = 0; i < controls.length; i++) {
      const a = controls[i];
      if (a.x < 0 || a.x + a.width > innerWidth || a.width <= 0) throw new Error(a.id + ' outside window');
      for (const b of controls.slice(i + 1)) {
        if (a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y) throw new Error(a.id + ' overlaps ' + b.id);
      }
    }
    if (document.documentElement.scrollWidth > innerWidth) throw new Error('horizontal page overflow');
    const next = document.querySelector('.legend').getBoundingClientRect();
    if (controls.some(r => r.y + r.height + 6 > next.top)) throw new Error('search focus ring overlaps legend');
    return controls;
  });
}
async function visibleCurrent(page) {
  const r = await page.locator('.node.current-match').boundingBox();
  assert(r.y >= 0 && r.y + r.height <= page.viewportSize().height, 'current match must be visible on screen, not only inside the scroll container');
}

test('live search spans titles, lines and details across sections with distinct current highlight', async t => {
  const page = await openPage(t);
  await state(page, '0/0');
  assert.equal(await page.locator('#locate').count(), 0);
  assert.equal(await page.locator('#search-count').getAttribute('aria-live'), 'polite');
  for (const [id, label, icon] of [
    ['search-prev', '\u4e0a\u4e00\u4e2a\u5339\u914d', 'chevron-up'],
    ['search-next', '\u4e0b\u4e00\u4e2a\u5339\u914d', 'chevron-down']
  ]) {
    const control = page.locator('#' + id);
    assert.equal(await control.getAttribute('title'), label);
    assert.equal(await control.getAttribute('aria-label'), label);
    assert.equal(await control.locator('svg').getAttribute('data-icon'), icon);
    assert.equal((await control.textContent()).trim(), '');
  }
  await page.locator('#search').pressSequentially(term);
  await state(page, '1/5', 'title-hit');
  await contained(page);
  assert.equal(await page.locator('#search').evaluate(el => el === document.activeElement), true);
  const outlines = await page.locator('.node.match').evaluateAll(items => items.map(el => getComputedStyle(el).outlineColor));
  assert.notEqual(outlines[0], outlines[1], 'current match must look different from other matches');
  const bounds = await toolbarBounds(page);
  await page.locator('#search').fill('  oRdEr_ToTaL  ');
  await state(page, '1/1', 'title-hit');
  assert.deepEqual(await toolbarBounds(page), bounds, 'counter changes must not shift controls');
  for (const query of ['', '   ', 'not-a-match', 'source-only-token', 'example-only-token']) {
    await page.locator('#search').fill(query);
    await state(page, '0/0');
  }
});

test('previous/next and Enter/Shift+Enter wrap while search focus stays in place', async t => {
  const page = await openPage(t);
  const search = page.locator('#search');
  await search.fill(term);
  await state(page, '1/5', 'title-hit');
  await page.locator('#search-prev').click();
  await state(page, '5/5', 'last-hit');
  await contained(page);
  await page.locator('#search-next').click();
  await state(page, '1/5', 'title-hit');
  await search.focus();
  for (const [count, id] of [['2/5', 'lines-hit'], ['3/5', 'detail-hit'], ['4/5', 'later-hit'], ['5/5', 'last-hit'], ['1/5', 'title-hit']]) {
    await search.press('Enter');
    await state(page, count, id);
    await contained(page);
    assert(await search.evaluate(el => el === document.activeElement));
  }
  await search.press('Shift+Enter');
  await state(page, '5/5', 'last-hit');
  assert(await search.evaluate(el => el === document.activeElement));
  await search.fill(term + '\u786e\u8ba4');
  await state(page, '1/1', 'title-hit');
  await search.press('Shift+Enter');
  await state(page, '1/1', 'title-hit');
});

test('IME confirmation and textarea Enter do not navigate search', async t => {
  const page = await openPage(t);
  const search = page.locator('#search');
  await search.fill(term);
  await state(page, '1/5', 'title-hit');
  for (const options of [{isComposing: true}, {keyCode: 229}]) {
    const prevented = await search.evaluate((el, options) => {
      const event = new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true, ...options});
      el.dispatchEvent(event);
      return event.defaultPrevented;
    }, options);
    assert.equal(prevented, false);
    await state(page, '1/5', 'title-hit');
  }
  await search.dispatchEvent('compositionstart');
  await search.press('Enter');
  await state(page, '1/5', 'title-hit');
  await search.dispatchEvent('compositionend');
  await search.press('Enter');
  await state(page, '2/5', 'lines-hit');
  await page.evaluate(() => {const draft = document.createElement('textarea'); draft.id = 'unrelated-draft'; document.body.append(draft);});
  const draft = page.locator('#unrelated-draft');
  await draft.fill('first');
  await draft.press('Enter');
  await draft.press('Shift+Enter');
  assert.equal(await draft.inputValue(), 'first\n\n');
  await state(page, '2/5', 'lines-hit');
});

for (const viewport of [{width: 1440, height: 1100}, {width: 390, height: 844}]) {
  test(`search toolbar and current bounds remain stable at ${viewport.width}px`, async t => {
    const page = await openPage(t, viewport);
    await state(page, '0/0');
    const initial = await toolbarBounds(page);
    await page.locator('a[href="#diagram"]').click();
    await page.locator('#search').fill(term);
    await state(page, '1/5', 'title-hit');
    await contained(page);
    const active = await toolbarBounds(page);
    assert.deepEqual(active.map(({id, width, height}) => ({id, width, height})), initial.map(({id, width, height}) => ({id, width, height})));
    if (screenshots) await page.screenshot({path: path.join(screenshots, `search-${viewport.width}.png`)});
    await page.locator('#search-prev').click();
    await state(page, '5/5', 'last-hit');
    await contained(page);
    await visibleCurrent(page);
    await toolbarBounds(page);
    if (screenshots) await page.screenshot({path: path.join(screenshots, `search-last-${viewport.width}.png`)});
    await page.locator('#last-hit span').evaluate(el => {el.textContent = 'Tall node\n'.repeat(100); window.dispatchEvent(new Event('resize'));});
    await page.locator('#search').press('Shift+Enter');
    await page.locator('#search').press('Enter');
    await contained(page);
    await page.setViewportSize({width: 390, height: 700});
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await contained(page);
    await toolbarBounds(page);
  });
}

test('offline full canvas retains wheel zoom, pan, fit and node details after searching', async t => {
  const page = await openPage(t);
  await page.locator('#search').fill(term);
  await state(page, '1/5', 'title-hit');
  await page.locator('.node.current-match').click();
  assert(await page.locator('#detail').isVisible());
  assert.equal(await page.locator('#detail-text').textContent(), 'First step');
  assert.equal(await page.locator('#detail-title').textContent(), term + '\u786e\u8ba4');
  await page.locator('.close').click();
  await page.locator('#zoom-reset').click();
  await page.locator('#viewport').evaluate(el => {el.scrollTop = 200;});
  const wheel = await page.locator('#viewport').evaluate(el => {
    const scale = () => new DOMMatrix(getComputedStyle(document.getElementById('canvas')).transform).a;
    const before = scale(), r = el.getBoundingClientRect();
    const zoom = new WheelEvent('wheel', {ctrlKey: true, deltaY: -120, clientX: r.left + 200, clientY: r.top + 200, cancelable: true});
    el.dispatchEvent(zoom);
    const scroll = new WheelEvent('wheel', {deltaY: 100, cancelable: true});
    el.dispatchEvent(scroll);
    return {before, after: scale(), zoomPrevented: zoom.defaultPrevented, scrollPrevented: scroll.defaultPrevented};
  });
  assert(wheel.after > wheel.before && wheel.zoomPrevented);
  assert.equal(wheel.scrollPrevented, false);
  const view = page.locator('#viewport');
  await view.scrollIntoViewIfNeeded();
  await view.evaluate(el => {el.scrollTop = 0;});
  const r = await view.boundingBox();
  await page.mouse.move(r.x + 8, r.y + 200);
  await page.mouse.down();
  await page.mouse.move(r.x + 8, r.y + 90, {steps: 5});
  await page.mouse.up();
  const pan = await view.evaluate(el => ({top: el.scrollTop, max: el.scrollHeight - el.clientHeight}));
  assert(pan.top >= 100, 'pan must move down from the top: ' + JSON.stringify(pan));
  await page.locator('#search').fill('');
  await page.locator('#zoom-fit').click();
  await contained(page, '.node');
  assert.equal(await page.locator('#edges>path').count(), 3);
});

test('explicit full-canvas view survives layout changes with an active search', async t => {
  const page = await openPage(t);
  await page.locator('#nodes').evaluate(el => {el.style.rowGap = '280px'; window.dispatchEvent(new Event('resize'));});
  await page.locator('#search').fill(term);
  await page.locator('#zoom-fit').click();
  const fit = await page.locator('#zoom-value').textContent();
  await page.evaluate(() => window.dispatchEvent(new Event('resize')));
  assert.equal(await page.locator('#zoom-value').textContent(), fit);
  await contained(page, '.node');
});

test('builder rejects search control IDs used by authored graphs or nodes', () => {
  const result = python([
    'import sys,json,copy',
    'sys.path.insert(0,sys.argv[1])',
    'from build_flow import validate',
    'data=json.load(sys.stdin)',
    'rejected=[]',
    'for ident in ["search-prev","search-next","search-count"]:',
    ' for target in ["graph","node"]:',
    '  d=copy.deepcopy(data)',
    '  if target=="graph": d["graphs"][0]["id"]=ident',
    '  else:',
    '   d["graphs"][0]["nodes"][0]["id"]=ident',
    '   d["graphs"][0]["edges"][0]["a"]=ident',
    '  try: validate(d)',
    '  except ValueError as e:',
    '   if "Invalid or duplicate ID" in str(e): rejected.append(ident+":"+target)',
    'print(json.dumps(rejected))'
  ].join('\n'), manifest);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), ['search-prev:graph', 'search-prev:node', 'search-next:graph', 'search-next:node', 'search-count:graph', 'search-count:node']);
});
