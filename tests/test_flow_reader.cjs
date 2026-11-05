const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const {test, before, after} = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');

// Reading aids: readable first view, section titles and jumps, previous/next
// steps in node details, and an example's route drawn from its authored path.
const root = path.resolve(__dirname, '..');
const screenshots = process.argv[2] && path.resolve(process.argv[2]);
let browser, temp, url;

before(async () => {
  temp = fs.mkdtempSync(path.join(os.tmpdir(), 'handbook-reader-'));
  const out = path.join(temp, 'book');
  const built = spawnSync(process.env.PYTHON_EXECUTABLE || 'python', ['-B', '-X', 'utf8',
    path.join(root, 'project-handbook/scripts/build_flow.py'), path.join(root, 'project-handbook/assets/flow.example.json'), out], {encoding: 'utf8'});
  assert.equal(built.status, 0, built.stderr);
  url = pathToFileURL(path.join(out, 'handbook.html')).href;
  if (screenshots) fs.mkdirSync(screenshots, {recursive: true});
  browser = await chromium.launch({headless: true, executablePath: process.env.BROWSER_EXECUTABLE || undefined});
});
after(async () => {
  if (browser) await browser.close();
  if (temp) fs.rmSync(temp, {recursive: true, force: true});
});

async function openPage(t, viewport = {width: 1440, height: 1000}) {
  const page = await browser.newPage({viewport, offline: true});
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  t.after(async () => {await page.close(); assert.deepEqual(errors, [], 'no browser errors');});
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  return page;
}
const scaleOf = page => page.evaluate(() => new DOMMatrix(getComputedStyle(document.getElementById('canvas')).transform).a);

test('sections are titled on the canvas and can be jumped to', async t => {
  const page = await openPage(t, {width: 1440, height: 700});
  assert.deepEqual(await page.locator('#edges .section-label').allTextContents(), ['创建订单', '支付结果']);
  const chips = page.locator('#section-jump button');
  assert.deepEqual(await chips.allTextContents(), ['创建订单', '支付结果']);
  await chips.nth(1).click();
  const placed = await page.evaluate(() => {
    const view = document.getElementById('viewport'), v = view.getBoundingClientRect(), r = document.getElementById('callback').getBoundingClientRect();
    return {top: r.top - v.top, inside: r.left >= v.left && r.right <= v.right && r.bottom <= v.bottom,
            atEnd: view.scrollTop >= view.scrollHeight - view.clientHeight - 1, scrolled: view.scrollTop > 0};
  });
  assert(placed.inside && placed.scrolled && placed.top > 0 && (placed.top < 120 || placed.atEnd), 'jump brings the section to the top: ' + JSON.stringify(placed));
  if (screenshots) await page.screenshot({path: path.join(screenshots, 'reader-sections.png')});
});

test('node details list previous and next steps and walk the flow', async t => {
  const page = await openPage(t);
  await page.locator('#submit').click();
  assert.equal(await page.locator('#detail-from').textContent(), '这是流程起点');
  assert.deepEqual(await page.locator('#detail-to .step-link').allTextContents(), ['库存充足？']);
  await page.locator('#detail-to .step-link').click();
  assert.equal(await page.locator('#detail-title').textContent(), '库存充足？');
  assert(await page.locator('#detail').evaluate(d => d.open), 'dialog stays open while walking');
  const exits = await page.locator('#detail-to .step-link').evaluateAll(items => items.map(b => [b.querySelector('.step-label')?.textContent, b.dataset.node]));
  assert.deepEqual(exits.sort(), [['否', 'soldout'], ['是', 'created']]);
  await page.locator('#detail-to .step-link[data-node="created"]').click();
  await page.locator('#detail-to .step-link').click();
  assert.equal(await page.locator('#detail-title').textContent(), '发起支付');
  // A cross-section connection is a real next step too.
  assert.deepEqual(await page.locator('#detail-to .step-link').evaluateAll(items => items.map(b => b.dataset.node)), ['callback']);
  assert.equal(await page.locator('#detail-to .step-label').textContent(), '支付成功且通知校验通过');
  if (screenshots) await page.screenshot({path: path.join(screenshots, 'reader-detail.png')});
  await page.keyboard.press('Escape');
  assert.deepEqual(await page.locator('.node.selected').evaluateAll(items => items.map(n => n.id)), ['pay']);
  assert(await page.locator('#edges path.edge-active').count() >= 2, 'edges into and out of the selected node stand out');
  const visible = await page.evaluate(() => {
    const v = document.getElementById('viewport').getBoundingClientRect(), r = document.getElementById('pay').getBoundingClientRect();
    return r.top >= v.top && r.bottom <= v.bottom && r.left >= v.left && r.right <= v.right;
  });
  assert(visible, 'after walking, the canvas shows the step the reader stopped on');
});

test('an example route is numbered on the diagram and can be left', async t => {
  const page = await openPage(t);
  assert.equal(await page.locator('#route-bar').isVisible(), false);
  await page.locator('details.example').nth(1).locator('summary').click();
  await page.locator('details.example').nth(1).locator('.show-route').click();
  assert(await page.locator('#route-bar').isVisible());
  assert.equal(await page.locator('#route-title').textContent(), '异常：库存不足');
  const steps = await page.locator('.node[data-step]').evaluateAll(items => items.map(n => [n.id, n.dataset.step]));
  assert.deepEqual(steps, [['submit', '1'], ['stock', '2'], ['soldout', '3']]);
  assert.equal(await page.locator('.node.dim').count(), 7);
  assert.deepEqual(await page.locator('#edges path.edge-route').evaluateAll(items => items.map(p => p.dataset.from + '>' + p.dataset.to)), ['submit>stock', 'stock>soldout']);
  assert.equal(await page.locator('#edges path.edge-route').first().getAttribute('marker-end'), 'url(#route-arrow)');
  const shown = await page.evaluate(() => {
    const v = document.getElementById('viewport').getBoundingClientRect();
    return ['submit', 'stock', 'soldout'].every(id => {const r = document.getElementById(id).getBoundingClientRect(); return r.top >= v.top && r.bottom <= v.bottom && r.left >= v.left && r.right <= v.right;});
  });
  assert(shown, 'the whole route is in view');
  if (screenshots) await page.screenshot({path: path.join(screenshots, 'reader-route.png')});
  // Redrawing (resize) keeps the route.
  await page.setViewportSize({width: 1300, height: 1000});
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  assert.equal(await page.locator('#edges path.edge-route').count(), 2);
  await page.locator('#viewport').focus();
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#route-bar').isVisible(), false);
  assert.equal(await page.locator('.node.dim, .node[data-step], #edges .edge-dim').count(), 0);
  await page.locator('details.example').first().locator('summary').click();
  await page.locator('details.example').first().locator('.show-route').click();
  assert.equal(await page.locator('.node[data-step]').count(), 8);
  await page.locator('#route-clear').click();
  assert.equal(await page.locator('.node[data-step]').count(), 0);
});

test('opens readable, "/" finds, and narrow screens stay contained', async t => {
  const page = await openPage(t);
  const opening = await page.evaluate(() => {
    const v = document.getElementById('viewport'), c = document.getElementById('canvas');
    return {expected: Math.min(1, (v.clientWidth - 24) / c.offsetWidth), top: v.scrollTop};
  });
  assert(Math.abs(await scaleOf(page) - opening.expected) < .01 && opening.top === 0);
  await page.locator('body').click({position: {x: 5, y: 5}});
  await page.keyboard.press('/');
  assert.equal(await page.evaluate(() => document.activeElement.id), 'search');
  assert.equal(await page.locator('#search').inputValue(), '', 'the slash is not typed into the search');
  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  assert.equal(await page.locator('#section-jump').isVisible(), false, 'section chips hide on phones');
  await page.reload();
  await page.evaluate(() => document.fonts.ready);
  assert(Math.abs(await scaleOf(page) - Math.max(.55, Math.min(1, await page.evaluate(() => (document.getElementById('viewport').clientWidth - 24) / document.getElementById('canvas').offsetWidth)))) < .01, 'phones open legible, scrolling sideways when needed');
  assert(await page.locator('.mobile-hint').isVisible());
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'no sideways page scroll');
  await page.locator('#submit').click();
  const fits = await page.locator('#detail').evaluate(d => d.getBoundingClientRect().right <= innerWidth);
  assert(fits, 'details fit the phone width');
  if (screenshots) await page.screenshot({path: path.join(screenshots, 'reader-phone-detail.png')});
});

test('an offline copy keeps sections and routes but not the reader\'s temporary state', async t => {
  const page = await openPage(t);
  await page.locator('#section-jump button').nth(1).click();
  await page.locator('details.example').first().locator('summary').click();
  await page.locator('details.example').first().locator('.show-route').click();
  const [download] = await Promise.all([page.waitForEvent('download'), page.locator('.flow-qa-share').click()]);
  const copy = path.join(temp, 'copy.html');
  await download.saveAs(copy);
  const offline = await browser.newPage({viewport: {width: 1440, height: 1000}, offline: true});
  const errors = [];
  offline.on('pageerror', error => errors.push(String(error)));
  t.after(async () => {await offline.close(); assert.deepEqual(errors, []);});
  await offline.goto(pathToFileURL(copy).href);
  await offline.evaluate(() => document.fonts.ready);
  assert.equal(await offline.locator('#route-bar').isVisible(), false);
  assert.equal(await offline.locator('.node.dim, .node[data-step]').count(), 0);
  assert.equal(await offline.locator('#section-jump button').count(), 2);
  assert.deepEqual(await offline.locator('#edges .section-label').allTextContents(), ['创建订单', '支付结果']);
  await offline.evaluate(() => {document.querySelectorAll('details.example')[1].open = true;});
  await offline.locator('details.example').nth(1).locator('.show-route').click();
  assert.equal(await offline.locator('.node[data-step]').count(), 3);
});
