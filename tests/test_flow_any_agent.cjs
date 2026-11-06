const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const {test, before, after} = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');

// Works with any agent: a page built without Python (viewer + flow-data.js),
// and questions copied from the page, answered by the agent into answers.js.
const root = path.resolve(__dirname, '..');
const viewer = path.join(root, 'project-handbook/assets/viewer/handbook.html');
const example = fs.readFileSync(path.join(root, 'project-handbook/assets/flow.example.json'), 'utf8');
const screenshots = process.argv[2] && path.resolve(process.argv[2]);
let browser, temp;

before(async () => {
  temp = fs.mkdtempSync(path.join(os.tmpdir(), 'handbook-any-agent-'));
  if (screenshots) fs.mkdirSync(screenshots, {recursive: true});
  browser = await chromium.launch({headless: true, executablePath: process.env.BROWSER_EXECUTABLE || undefined});
});
after(async () => {
  if (browser) await browser.close();
  if (temp) fs.rmSync(temp, {recursive: true, force: true});
});

// Build the way an agent without Python does: copy the page, write the data.
function noPythonBook(name, dataText) {
  const dir = path.join(temp, name);
  fs.mkdirSync(dir);
  fs.copyFileSync(viewer, path.join(dir, 'handbook.html'));
  if (dataText !== undefined) fs.writeFileSync(path.join(dir, 'flow-data.js'), dataText);
  return dir;
}
async function open(t, dir, {expectErrors = false} = {}) {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, permissions: ['clipboard-read', 'clipboard-write'], acceptDownloads: true});
  const page = await context.newPage();
  const errors = [], requests = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('request', request => { if (!request.url().startsWith('file:')) requests.push(request.url()); });
  t.after(async () => {
    await context.close();
    if (!expectErrors) assert.deepEqual(errors, [], 'no browser errors');
    assert.deepEqual(requests, [], 'nothing leaves the computer');
  });
  await page.goto(pathToFileURL(path.join(dir, 'handbook.html')).href);
  await page.evaluate(() => document.fonts.ready);
  page.errors = errors;
  return page;
}

test('a page built without Python draws the same flow', async t => {
  const dir = noPythonBook('no-python', 'window.HANDBOOK_DATA = ' + JSON.stringify({...JSON.parse(example), project: 'D:/资料/订单'}) + ';\n');
  const page = await open(t, dir);
  assert.equal(await page.title(), '订单支付是怎样完成的？');
  assert.equal(await page.locator('#flow-title').textContent(), '订单支付是怎样完成的？');
  assert.equal(await page.locator('.node').count(), 10);
  assert.equal(await page.locator('details.example').count(), 3);
  assert.deepEqual(await page.locator('#edges .section-label').allTextContents(), ['创建订单', '支付结果']);
  assert.equal(await page.locator('#flow-error').isVisible(), false);
  await page.locator('#stock').click();
  assert.equal(await page.locator('#detail-title').textContent(), '库存充足？');
});

test('a flow with a problem says what is wrong and how to get it fixed', async t => {
  const broken = JSON.parse(example);
  broken.graphs[0].edges[1].label = '可能';
  const dir = noPythonBook('broken', 'window.HANDBOOK_DATA = ' + JSON.stringify(broken) + ';');
  const page = await open(t, dir, {expectErrors: true});
  assert(await page.locator('#flow-error').isVisible());
  assert.equal(await page.locator('main').isVisible(), false);
  assert.match(await page.locator('#flow-error pre').textContent(), /graphs\[0\] node "stock": a decision needs exactly one 是 edge and one 否 edge/);
  await page.locator('#flow-error button').click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  assert.match(copied, /^这份流程图页面打不开，请用 project-handbook 技能修好数据后重新生成。/);
  assert(copied.includes(path.join(dir, 'handbook.html').replace(/\\/g, '/')), 'the copied text says which page');
  assert.match(await page.locator('#flow-error button').textContent(), /已复制/);
  if (screenshots) await page.screenshot({path: path.join(screenshots, 'any-agent-error.png')});

  const missing = await open(t, noPythonBook('missing'), {expectErrors: true});
  assert.match(await missing.locator('#flow-error pre').textContent(), /没有找到流程数据/);
  const garbled = await open(t, noPythonBook('garbled', 'window.HANDBOOK_DATA = {"title": ;'), {expectErrors: true});
  assert(await garbled.locator('#flow-error').isVisible(), 'a syntax error in flow-data.js still explains itself');
});

test('a question is copied for the AI and its saved answer appears in the page', async t => {
  const built = spawnSync(process.env.PYTHON_EXECUTABLE || 'python', ['-B', '-X', 'utf8', path.join(root, 'project-handbook/scripts/build_flow.py'),
    path.join(root, 'project-handbook/assets/flow.example.json'), path.join(temp, 'relay')], {encoding: 'utf8'});
  assert.equal(built.status, 0, built.stderr);
  const dir = path.join(temp, 'relay');
  const page = await open(t, dir);
  await page.locator('#stock').click();
  await page.getByRole('button', {name: '追问这个节点', exact: true}).click();
  assert.equal(await page.locator('.flow-qa-badge').textContent(), '交给 AI 回答');
  const send = page.locator('.flow-qa-send');
  assert.equal(await send.textContent(), '复制给 AI');
  assert(await send.isDisabled(), 'nothing to copy yet');
  await page.locator('.flow-qa-draft').fill('库存不足时订单会保留多久？');
  await send.click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  const lines = copied.split('\n');
  assert.equal(lines[0], '请用 project-handbook 技能回答我在流程手册里的这个问题，并把回答存回手册。');
  assert.equal(lines[1], '手册：' + path.join(dir, 'handbook.html').replace(/\\/g, '/'));
  assert.match(lines[2], /^问题编号：q-\d{8}-\d{6}-[a-z0-9]{1,4}$/);
  assert.equal(lines[3], '针对：库存充足？（节点 stock）');
  assert.equal(lines[4], '问题：库存不足时订单会保留多久？');
  assert.equal(await page.locator('.flow-qa-relay').textContent(), copied, 'the text is also shown for manual copying');
  assert.deepEqual(await page.locator('.flow-qa-entry-state').allTextContents(), ['等 AI 回答']);
  assert.equal(await page.locator('.flow-qa-draft').inputValue(), '');

  // Still waiting after closing and reopening the page.
  await page.reload();
  await page.evaluate(() => document.fonts.ready);
  await page.getByRole('button', {name: '问答', exact: true}).click();
  assert.deepEqual(await page.locator('.flow-qa-entry-state').allTextContents(), ['等 AI 回答']);

  // The agent saves its answer with save_answer.py; the page shows it without a refresh.
  const id = lines[2].slice('问题编号：'.length);
  fs.writeFileSync(path.join(temp, 'q.txt'), '库存不足时订单会保留多久？');
  fs.writeFileSync(path.join(temp, 'a.md'), '不会保留。**库存不足**时直接结束，不创建订单。\n\n| 情况 | 结果 |\n|---|---|\n| 不足 | 结束 |');
  const saved = spawnSync(process.env.PYTHON_EXECUTABLE || 'python', ['-B', '-X', 'utf8', path.join(root, 'project-handbook/scripts/save_answer.py'),
    dir, '--id', id, '--node', 'stock', '--question-file', path.join(temp, 'q.txt'), '--answer-file', path.join(temp, 'a.md')], {encoding: 'utf8'});
  assert.equal(saved.status, 0, saved.stderr);
  await page.locator('.flow-qa-entry-state').waitFor({state: 'detached', timeout: 10000});
  assert.equal(await page.locator('.flow-qa-answer strong').first().textContent(), '库存不足');
  assert.equal(await page.locator('.flow-qa-answer table').count(), 1);
  assert.match(await page.locator('.flow-qa-entry-meta').textContent(), /库存充足？/);
  assert.equal(await page.locator('.flow-qa-role-assistant').textContent(), 'AI');
  assert.match(await page.locator('.flow-qa-status').textContent(), /已存回手册/);
  assert.equal(await page.locator('.flow-qa-relay').count(), 0, 'the copied text makes way for the answer');
  assert(await page.locator('.flow-qa-answer table').isVisible(), 'the answer is in view');
  if (screenshots) await page.screenshot({path: path.join(screenshots, 'any-agent-answered.png')});

  // Ask the AI to fold the answer into a new version.
  await page.locator('.flow-qa-compile').click();
  const compile = await page.evaluate(() => navigator.clipboard.readText());
  assert.match(compile, /^请用 project-handbook 技能，把这份流程手册里下面这些已回答的问题整理进流程图，生成新版本（原版保留）。\n手册：.+\n问题编号：q-/);
  assert(compile.includes(id));

  // A copy sent to someone else keeps the answer but cannot ask.
  const [download] = await Promise.all([page.waitForEvent('download'), page.locator('.flow-qa-export').click()]);
  const copy = path.join(temp, 'shared.html');
  await download.saveAs(copy);
  const html = fs.readFileSync(copy, 'utf8');
  assert(!html.includes('<script src="answers.js">') && !html.includes('<script src="flow-data.js">'), 'the shared file stands alone');
  const shared = await browser.newPage();
  await shared.goto(pathToFileURL(copy).href);
  await shared.getByRole('button', {name: '问答', exact: true}).click();
  assert.equal(await shared.locator('.flow-qa-badge').textContent(), '分享副本');
  assert.equal(await shared.locator('.flow-qa-entry').count(), 1);
  assert(await shared.locator('.flow-qa-send').isDisabled());
  await shared.close();
});

test('a question can be withdrawn and copied again', async t => {
  const dir = noPythonBook('withdraw', 'window.HANDBOOK_DATA = ' + example + ';');
  const page = await open(t, dir);
  await page.getByRole('button', {name: '问答', exact: true}).click();
  await page.locator('.flow-qa-draft').fill('整个流程最长要多久？');
  await page.locator('.flow-qa-draft').press('Enter');
  const first = await page.evaluate(() => navigator.clipboard.readText());
  assert.match(first, /针对：整个流程\n问题：整个流程最长要多久？$/);
  await page.evaluate(() => navigator.clipboard.writeText(''));
  await page.locator('.flow-qa-copy-again').click();
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), first);
  await page.locator('.flow-qa-drop').click();
  assert.equal(await page.locator('.flow-qa-entry').count(), 0);
  await page.reload();
  await page.getByRole('button', {name: '问答', exact: true}).click();
  assert.equal(await page.locator('.flow-qa-entry').count(), 0, 'withdrawn questions stay gone');
});

test('answers written by hand in the documented form are shown', async t => {
  const dir = noPythonBook('by-hand', 'window.HANDBOOK_DATA = ' + example + ';');
  // Exactly the shape references/answers.md shows, with a line break inside the answer.
  fs.writeFileSync(path.join(dir, 'answers.js'), 'window.HANDBOOK_ANSWERS = [\n {"id": "q-20261105-093321-04hp", "node": "stock", "question": "库存不足会怎样？", "answer": "直接结束。\\n\\n- **不**创建订单", "time": "2026-11-05 10:12"},\n {"id": "q-20261105-093400-zzzz", "node": null, "question": "整个流程多久？", "answer": "几秒。", "time": "2026-11-05 10:13"}\n];\n');
  const page = await open(t, dir);
  await page.getByRole('button', {name: '问答', exact: true}).click();
  assert.equal(await page.locator('.flow-qa-entry').count(), 2);
  assert.deepEqual(await page.locator('.flow-qa-entry-meta').allTextContents(), ['库存充足？', '整个流程']);
  assert.equal(await page.locator('.flow-qa-answer li strong').textContent(), '不');
  const doc = fs.readFileSync(path.join(root, 'project-handbook/references/answers.md'), 'utf8');
  assert(doc.includes('window.HANDBOOK_ANSWERS = ['), 'the documented form is the one tested here');
});

test('several questions go to the AI in one paste', async t => {
  const dir = noPythonBook('batch', 'window.HANDBOOK_DATA = ' + example + ';');
  const page = await open(t, dir);
  await page.locator('#stock').click();
  await page.getByRole('button', {name: '追问这个节点', exact: true}).click();
  await page.locator('.flow-qa-draft').fill('库存不足时订单会保留多久？');
  await page.locator('.flow-qa-send').click();
  await page.locator('.flow-qa-clear-context').click();
  await page.locator('.flow-qa-draft').fill('整个流程最长要多久？');
  await page.locator('.flow-qa-send').click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  const lines = copied.split('\n');
  assert.equal(lines[0], '请用 project-handbook 技能回答我在流程手册里的这 2 个问题，并把回答存回手册。');
  const ids = [...copied.matchAll(/问题编号：(\S+)/g)].map(m => m[1]);
  assert.equal(ids.length, 2);
  assert.match(copied, /\n\n1\. 问题编号：q-\S+\n针对：库存充足？（节点 stock）\n问题：库存不足时订单会保留多久？\n\n2\. 问题编号：q-\S+\n针对：整个流程\n问题：整个流程最长要多久？$/);
  assert.match(await page.locator('.flow-qa-status').textContent(), /已复制 2 个问题/);
  assert.deepEqual(await page.locator('.flow-qa-entry-state').allTextContents(), ['等 AI 回答', '等 AI 回答']);

  // The AI saves the first answer; the next copy carries only the one still waiting.
  fs.writeFileSync(path.join(dir, 'answers.js'), 'window.HANDBOOK_ANSWERS = [' + JSON.stringify({id: ids[0], node: 'stock', question: 'x', answer: '不保留。'}) + '];');
  await page.waitForFunction(() => document.querySelectorAll('.flow-qa-entry-state').length === 1, null, {timeout: 10000});
  await page.locator('.flow-qa-copy-again').click();
  const again = await page.evaluate(() => navigator.clipboard.readText());
  assert.match(again, /^请用 project-handbook 技能回答我在流程手册里的这个问题/);
  assert(again.includes(ids[1]) && !again.includes(ids[0]));

  // A model that saves the 问题编号 as the question still shows the reader's words, also after a reload.
  fs.writeFileSync(path.join(dir, 'answers.js'), 'window.HANDBOOK_ANSWERS = [' + [
    {id: ids[0], node: 'stock', question: 'x', answer: '不保留。'}, {id: ids[1], node: null, question: ids[1], answer: '几秒。'}
  ].map(value => JSON.stringify(value)).join(',') + '];');
  await page.waitForFunction(() => document.querySelectorAll('.flow-qa-entry-state').length === 0, null, {timeout: 10000});
  assert.deepEqual(await page.locator('.flow-qa-question').allTextContents(), ['x', '整个流程最长要多久？']);
  await page.reload();
  await page.locator('.flow-qa-toggle').click();
  assert.deepEqual(await page.locator('.flow-qa-question').allTextContents(), ['x', '整个流程最长要多久？']);
});
