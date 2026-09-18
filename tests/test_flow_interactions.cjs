const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {spawnSync} = require('node:child_process');

(async () => {
  const root = path.resolve(__dirname, '..');
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'handbook-interactions-'));
  const data = JSON.parse(fs.readFileSync(path.join(root, 'project-handbook/assets/damage.example.json'), 'utf8'));
  data.qa = [{id: 'saved', node_id: 'fixed-value', question: '固定伤害为什么是覆盖？', answer: '**实际扣血是 400。**\n\n先用固定值替换前面的计算结果：\n\n1. 固定值为 `500`。\n2. 再扣除护盾 `100`。\n\n```lua\ndamage = 500 - 100\n```\n\n| 项目 | 数值 |\n| --- | --- |\n| 扣血 | 400 |\n\n![private](https://invalid.example/private.png)\n\n<script>window.pwned=1</script>\n\n[bad](javascript:alert(1))'}];
  const manifest = path.join(temp, 'input.json');
  fs.writeFileSync(manifest, JSON.stringify(data));
  const scripts = path.join(root, 'project-handbook/scripts');
  const rendered = spawnSync(process.env.PYTHON_EXECUTABLE || 'python', ['-X', 'utf8', '-c', 'import sys,json; sys.path.insert(0,sys.argv[1]); from build_flow import render; d=json.load(open(sys.argv[2],encoding="utf-8")); d["runtime"]={"api":"/api","token":"test-token"}; print(render(d))', scripts, manifest], {encoding: 'utf8', maxBuffer: 4e6});
  assert.equal(rendered.status, 0, rendered.stderr);
  const calls = [];
  const server = http.createServer(async (req, res) => {
    if (req.url === '/') {res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(rendered.stdout); return;}
    if (req.url === '/favicon.ico') {res.writeHead(204); res.end(); return;}
    if (req.url === '/api/state') {res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({entries: [], busy: false, backend: {available: true, connected: false, message: 'Codex found; safety checks have not run.'}})); return;}
    if (req.url === '/api/ask') {
      let body = ''; for await (const part of req) body += part;
      calls.push(JSON.parse(body));
      res.setHeader('Content-Type', 'application/x-ndjson');
      const entry = {...calls.at(-1), id: 'answer-' + calls.length, answer: '**答案已收到。**', status: 'complete'};
      res.end(JSON.stringify({type: 'start', id: entry.id}) + '\n' + JSON.stringify({type: 'done', entry}) + '\n'); return;
    }
    res.writeHead(404); res.end();
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({headless: true, executablePath: process.env.BROWSER_EXECUTABLE || undefined});
  const page = await browser.newPage({viewport: {width: 1520, height: 1100}});
  const errors = [], external = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('request', request => {if (request.url().includes('invalid.example')) external.push(request.url());});
  try {
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.locator('#zoom-reset').click();
    for (let i = 0; i < 3; i++) await page.locator('#zoom-in').click();
    const view = page.locator('#viewport');
    await view.evaluate(el => {el.scrollTop = 350; el.scrollLeft = 80;});
    const zoomed = await view.evaluate(el => {
      const bounds = el.getBoundingClientRect(), canvas = document.getElementById('canvas');
      const scale = () => new DOMMatrix(getComputedStyle(canvas).transform).a;
      const x = 300, y = 300;
      const before = {scale: scale(), x: (el.scrollLeft + x) / scale(), y: (el.scrollTop + y) / scale()};
      const event = new WheelEvent('wheel', {ctrlKey: true, deltaY: -120, clientX: bounds.left + el.clientLeft + x, clientY: bounds.top + el.clientTop + y, cancelable: true, bubbles: true});
      el.dispatchEvent(event);
      return {before, after: {scale: scale(), x: (el.scrollLeft + x) / scale(), y: (el.scrollTop + y) / scale()}, prevented: event.defaultPrevented};
    });
    assert(zoomed.prevented && zoomed.after.scale > zoomed.before.scale, 'Ctrl+wheel must zoom the canvas, not the browser');
    assert(Math.abs(zoomed.after.x - zoomed.before.x) < 2 && Math.abs(zoomed.after.y - zoomed.before.y) < 2, 'the point under the cursor should stay anchored');
    const normal = await view.evaluate(el => {const event = new WheelEvent('wheel', {deltaY: 100, cancelable: true}); el.dispatchEvent(event); return event.defaultPrevented;});
    assert.equal(normal, false, 'ordinary wheel remains scrolling');
    const point = await view.boundingBox();
    const beforeWheel = await page.locator('#zoom-value').textContent();
    await page.mouse.move(point.x + 250, point.y + 200);
    await page.keyboard.down('Control'); await page.mouse.wheel(0, 120); await page.keyboard.up('Control');
    await page.waitForFunction(before => document.getElementById('zoom-value').textContent !== before, beforeWheel);
    assert(Number.parseInt(await page.locator('#zoom-value').textContent()) < Number.parseInt(beforeWheel), 'real Ctrl+wheel can zoom out');
    const limits = await view.evaluate(el => {
      const apply = deltaY => {for (let i = 0; i < 30; i++) el.dispatchEvent(new WheelEvent('wheel', {ctrlKey: true, deltaY, cancelable: true})); return new DOMMatrix(getComputedStyle(document.getElementById('canvas')).transform).a;};
      return {max: apply(-300), min: apply(300)};
    });
    assert.equal(limits.max, 2); assert(limits.min > 0 && limits.min <= .1);
    console.log('PASS cursor-anchored Ctrl+wheel and ordinary scroll');

    await page.locator('.flow-qa-toggle').click();
    const panel = page.locator('.flow-qa-panel');
    assert((await panel.boundingBox()).width >= 500, 'desktop Q&A starts wide enough to read');
    assert.equal(await page.locator('.flow-qa-entry').first().locator('.flow-qa-role-user').textContent(), '你');
    assert.match(await page.locator('.flow-qa-entry').first().locator('.flow-qa-role-assistant').textContent(), /Codex.*AI/);
    assert.equal(await page.locator('.flow-qa-answer').first().locator('strong').textContent(), '实际扣血是 400。');
    assert.equal(await page.locator('.flow-qa-answer').first().locator('ol li').count(), 2);
    assert.equal(await page.locator('.flow-qa-answer').first().locator('pre code').count(), 1);
    assert.equal(await page.locator('.flow-qa-answer').first().locator('table').count(), 1);
    assert.equal(await page.locator('.flow-qa-answer img,.flow-qa-answer script,.flow-qa-answer a').count(), 0);
    assert.equal(await page.evaluate(() => window.pwned), undefined);
    assert.doesNotMatch(await page.locator('.flow-qa-status').textContent(), /safety checks|Codex found/);
    assert.equal(await page.locator('.flow-qa-png-view').count(), 0);
    assert.match(await page.locator('.flow-qa-footer .flow-qa-hint').textContent(), /整理新版本|离线 HTML/);

    await panel.scrollIntoViewIfNeeded();
    const before = await panel.boundingBox();
    const handle = await page.locator('.flow-qa-resize-width').boundingBox();
    await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
    await page.mouse.down(); await page.mouse.move(handle.x - 130, handle.y + handle.height / 2, {steps: 5}); await page.mouse.up();
    assert((await panel.boundingBox()).width > before.width + 100, 'dragging left edge widens Q&A');
    const beforeHeight = (await panel.boundingBox()).height;
    await page.locator('.flow-qa-resize-corner').focus();
    await page.keyboard.press('ArrowDown');
    assert((await panel.boundingBox()).height > beforeHeight, 'resize handle supports keyboard height adjustment');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);

    const draft = page.locator('.flow-qa-draft');
    await draft.fill('第一行'); await draft.press('Shift+Enter'); await draft.type('第二行');
    assert.equal(await draft.inputValue(), '第一行\n第二行');
    await draft.evaluate(el => el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', isComposing: true, bubbles: true, cancelable: true})));
    assert.equal(calls.length, 0, 'IME confirmation does not send');
    await draft.press('Enter');
    await page.waitForFunction(() => document.querySelector('.flow-qa-draft').value === '');
    assert.equal(calls.length, 1);
    assert.equal(calls[0].question, '第一行\n第二行');
    await draft.press('Enter');
    assert.equal(calls.length, 1, 'empty Enter does not send again');
    console.log('PASS readable Markdown, roles, safer icons, desktop resize, Enter/Shift+Enter and IME');

    if (process.argv[2]) {fs.mkdirSync(process.argv[2], {recursive: true}); await panel.screenshot({path: path.join(process.argv[2], 'qa-resized.png')});}
    await page.setViewportSize({width: 390, height: 844});
    const mobileBefore = await panel.boundingBox();
    const top = await page.locator('.flow-qa-resize-top').boundingBox();
    await page.mouse.move(top.x + top.width / 2, top.y + top.height / 2); await page.mouse.down();
    await page.mouse.move(top.x + top.width / 2, top.y - 50, {steps: 5}); await page.mouse.up();
    const mobileAfter = await panel.boundingBox();
    assert(mobileAfter.height > mobileBefore.height + 30 && mobileAfter.y >= 0, 'mobile top handle resizes inside viewport');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    if (process.argv[2]) await page.screenshot({path: path.join(process.argv[2], 'qa-mobile.png')});
    await page.setViewportSize({width: 740, height: 480});
    const shortBefore = (await panel.boundingBox()).height;
    await page.locator('.flow-qa-resize-top').focus();
    await page.keyboard.press('ArrowDown');
    const shortAfter = await panel.boundingBox();
    assert(shortAfter.height < shortBefore && shortAfter.y >= 0, 'short mobile viewport must honor the resize handle');
    await page.setViewportSize({width: 1520, height: 1100});
    assert((await panel.boundingBox()).width > before.width + 100, 'desktop width is retained across mobile layout');
    assert.deepEqual(errors, []); assert.deepEqual(external, []);
    console.log('PASS mobile resize bounds and no external content execution or requests');
  } finally {await browser.close(); await new Promise(resolve => server.close(resolve)); fs.rmSync(temp, {recursive: true, force: true});}
})().catch(error => {console.error(error); process.exitCode = 1;});
