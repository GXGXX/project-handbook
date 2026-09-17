const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');

const assets = path.resolve(__dirname, '../project-handbook/assets');
const read = name => fs.existsSync(path.join(assets, name)) ? fs.readFileSync(path.join(assets, name), 'utf8') : '';
const token = 'synthetic-runtime-token-not-for-sharing';
const saved = {id: 'saved-1', node_id: 'entry', question: '已保存的问题', answer: '**已保存的答案**\n\n1. 先检查 `金额`。\n2. 再保存结果。\n\n/repository/private/module.py\n~/private/project\nhttps://internal.example/team\ncookie="session-private"\nBasic cHJpdmF0ZTpwYXNz\neyJhbGciOiJIUzI1NiJ9.eyJwcml2YXRlIjp0cnVlfQ.signature\nAKIA1234567890ABCDEF', status: 'complete', created_at: '2026-09-16T10:00:00Z'};
const failed = {id: 'failed-1', node_id: 'entry', question: '失败的问题', answer: '未完成的私人草稿', status: 'error'};
const nodes = [
  {id: 'entry', row: 0, col: 0, title: '提交订单', lines: '检查订单', detail: '来源 C:\\private\\orders.py，api_key=sk-test-private-value-123456', kind: 'process', source: 'demo'},
  {id: 'finish', row: 1, col: 0, title: '确认订单', lines: '保存结果', detail: '合成规则', kind: 'terminal', source: 'demo'}
];
const edges = [{a: 'entry', b: 'finish', label: '通过'}];

function fixture(runtime, qa = [saved, failed]) {
  const manifest = {
    title: '订单流程', summary: '合成问答测试', sources: [{id: 'demo', locator: 'C:\\private\\orders.py', excerpt: 'RAW-PRIVATE-SOURCE'}],
    graphs: [{id: 'order', title: '订单', source: 'demo', nodes, edges}], canvas: {nodes, edges}, examples: [], qa,
    filesystem: {root: 'C:\\private\\root'}, credentials: {password: 'hidden-password'}, runtime
  };
  const replacements = {
    TITLE: manifest.title, HEADER: '<header><h1>订单流程</h1></header>', NAV: '<nav><a href="#diagram">整体流程</a><a href="#examples">例子</a></nav>', EXAMPLES: '',
    DATA: JSON.stringify(manifest).replace(/</g, '\\u003c'), CSS: read('flow.css') + '\n' + read('flow-assistant.css'),
    JS: [read('vendor/html2canvas.min.js'), read('vendor/markdown-it.min.js'), read('flow.js'), read('flow-assistant.js')].join('\n;\n').replace(/<\/script/g, '<\\/script')
  };
  return read('flow-template.html').replace(/@@([A-Z]+)@@/g, (_, key) => replacements[key] || '');
}

async function until(check, message) {
  const end = Date.now() + 5000;
  while (Date.now() < end) {
    if (await check()) return;
    await new Promise(resolve => setTimeout(resolve, 30));
  }
  assert.fail(message);
}

(async () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'flow-assistant-test-'));
  const calls = [];
  let mode = 'success', stateEntries = [{...saved, answer: '仅在服务器历史中保存的答案'}, failed], backend = {available: true, connected: false, model: 'synthetic', message: 'Codex found; safety checks have not run.'}, pendingResponse;
  const json = (response, value, status = 200) => { response.writeHead(status, {'Content-Type': 'application/json'}); response.end(JSON.stringify(value)); };
  const server = http.createServer(async (request, response) => {
    const security = {'Content-Type': 'text/html; charset=utf-8', 'Content-Security-Policy': "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"};
    if (request.url === '/') { response.writeHead(200, security); response.end(fixture({api: '/api', token})); return; }
    if (request.url === '/versions/new/handbook.html') { response.writeHead(200, security); response.end(fixture(undefined, stateEntries.filter(entry => entry.id === 'new-1'))); return; }
    if (request.url === '/favicon.ico') { response.writeHead(204); response.end(); return; }
    let body = '';
    for await (const chunk of request) body += chunk;
    calls.push({url: request.url, headers: request.headers, body: body ? JSON.parse(body) : null});
    if (request.headers['x-flow-token'] !== token) { json(response, {message: 'missing token'}, 403); return; }
    if (request.url === '/api/state') { json(response, {entries: stateEntries, busy: false, backend}); return; }
    if (request.url === '/api/cancel') { if (pendingResponse && !pendingResponse.destroyed) pendingResponse.end(JSON.stringify({type: 'error', message: 'cancelled'}) + '\n'); json(response, {ok: true}); return; }
    if (request.url === '/api/export') {
      if (mode === 'disconnected') { response.destroy(); return; }
      json(response, {filename: 'shared.html', html: '<!doctype html><html lang="zh-CN"><body>SERVER-STATIC-EXPORT</body></html>'}); return;
    }
    if (request.url === '/api/ask' || request.url === '/api/compile') {
      if (mode === 'http-error') { json(response, {error: '服务暂不可用'}, 503); return; }
      response.writeHead(200, {'Content-Type': 'application/x-ndjson'});
      if (request.url === '/api/compile') {
        response.write(JSON.stringify({type: 'status', message: '正在生成新版本'}) + '\n');
        response.write(JSON.stringify({type: 'delta', text: '已校验流程'}) + '\n');
        response.end(JSON.stringify({type: 'compiled', url: mode === 'bad-url' ? 'https://example.com/steal' : '/versions/new/handbook.html'}) + '\n'); return;
      }
      const answerId = 'new-' + calls.filter(call => call.url === '/api/ask').length;
      response.write(JSON.stringify({type: 'start', id: answerId}) + '\n');
      if (mode === 'cancel') { pendingResponse = response; response.write(JSON.stringify({type: 'delta', text: '部分回答'}) + '\n'); return; }
      if (mode === 'broken') { response.end('{bad-json}\n'); return; }
      if (mode === 'truncated') { response.end(JSON.stringify({type: 'delta', text: '没有完成事件'}) + '\n'); return; }
      if (mode === 'stream-error') { response.end(JSON.stringify({type: 'error', message: '模型暂不可用'}) + '\n'); return; }
      if (mode === 'auth-error') {
        backend = {...backend, connected: false, message: 'Sign-in required. password:"synthetic secret phrase" https://internal.example/auth /data/private/auth.json'};
        response.end(JSON.stringify({type: 'error', message: '连接未建立'}) + '\n'); return;
      }
      response.write(JSON.stringify({type: 'status', message: '正在查阅来源 <b>只读</b> password:"synthetic secret phrase" https://internal.example/progress /data/private/progress.py'}) + '\n');
      const answer = '实时答案 <img src=x onerror=alert(1)> 第一段。第二段。';
      const delta = Buffer.from(JSON.stringify({type: 'delta', text: answer}) + '\r\n');
      const split = delta.indexOf(Buffer.from('答')) + 1;
      response.write(delta.subarray(0, split));
      setTimeout(() => {
        if (response.destroyed) return;
        response.write(delta.subarray(split));
        response.write(JSON.stringify({type: 'status', message: '正在核对来源'}) + '\n');
        setTimeout(() => {
          if (response.destroyed) return;
          const entry = {id: answerId, node_id: JSON.parse(body).node_id, question: JSON.parse(body).question, answer, status: 'complete', created_at: '2026-09-16T11:00:00Z'};
          backend = {...backend, connected: true, message: 'Connected: synthetic test connection.'};
          stateEntries = [saved, failed, entry];
          response.end(JSON.stringify({type: 'done', entry}));
        }, 250);
      }, 50);
      return;
    }
    response.writeHead(404); response.end();
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless: true, executablePath: process.env.BROWSER_EXECUTABLE || undefined});
  const errors = [];
  async function pageFor(url) {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, acceptDownloads: true});
    page.httpRequests = [];
    page.on('request', request => { if (/^https?:/.test(request.url())) page.httpRequests.push(request.url()); });
    page.on('pageerror', error => errors.push(String(error)));
    await page.goto(url);
    await page.evaluate(() => document.fonts.ready);
    return page;
  }
  async function download(page, selector) {
    const pending = page.waitForEvent('download');
    await page.locator(selector).click();
    const result = await pending;
    const file = path.join(temp, `${Date.now()}-${result.suggestedFilename()}`);
    await result.saveAs(file);
    return file;
  }
  try {
    const offlinePath = path.join(temp, 'offline.html');
    fs.writeFileSync(offlinePath, fixture(undefined));
    const offline = await pageFor(pathToFileURL(offlinePath).href);
    const requests = offline.httpRequests;
    assert.equal(await offline.getByRole('button', {name: '问答', exact: true}).count(), 1, 'assistant toolbar must be injected');
    await offline.getByRole('button', {name: '问答', exact: true}).click();
    assert(await offline.locator('#flow-qa-panel').isVisible());
    assert.match(await offline.locator('.flow-qa-status').textContent(), /离线/);
    assert(await offline.locator('.flow-qa-send').isDisabled());
    assert.equal(await offline.locator('.flow-qa-entry').count(), 2, 'all saved conversation, including incomplete answers, stays readable');
    assert.equal(await offline.locator('.flow-qa-entry input[type=checkbox]').count(), 1, 'only complete answers can be selected');
    await offline.locator('.flow-qa-close').click();
    await offline.locator('#entry').click();
    assert(await offline.locator('#detail').isVisible(), 'existing detail dialog remains modal');
    assert.match(await offline.locator('#detail-text').textContent(), /orders/);
    await offline.getByRole('button', {name: '追问这个节点', exact: true}).click();
    assert.equal(await offline.locator('#detail').evaluate(element => element.open), false);
    assert.match(await offline.locator('.flow-qa-context').textContent(), /提交订单/);
    await offline.locator('.flow-qa-entry input').check();
    await offline.locator('.flow-qa-draft').fill('UNSELECTED-PRIVATE-DRAFT');
    const exported = await download(offline, '.flow-qa-export');
    const html = fs.readFileSync(exported, 'utf8');
    assert(!html.includes('UNSELECTED-PRIVATE-DRAFT'));
    assert(!html.includes('RAW-PRIVATE-SOURCE'));
    assert(!html.includes('sk-test-private-value-123456'));
    assert(!html.includes('hidden-password'));
    assert(!html.includes('C:\\\\private'));
    for (const secret of ['repository/private', '~/private', 'internal.example', 'session-private', 'cHJpdmF0ZTpwYXNz', 'eyJhbGciOiJIUzI1NiJ9', 'AKIA1234567890ABCDEF']) assert(!html.includes(secret), `offline HTML leaked ${secret}`);
    const shared = await pageFor(pathToFileURL(exported).href);
    await shared.getByRole('button', {name: '问答', exact: true}).click();
    assert.equal(await shared.locator('.node').count(), 2, 'cloned exports must not duplicate generated nodes');
    assert.equal(await shared.locator('.flow-qa-entry').count(), 1);
    assert.match(await shared.locator('.flow-qa-entry').textContent(), /已保存的答案/);
    assert.equal(await shared.locator('.flow-qa-answer strong').textContent(), '已保存的答案');
    assert.equal(await shared.locator('.flow-qa-answer ol li').count(), 2);
    assert.equal(await shared.locator('.flow-qa-answer code').textContent(), '金额');
    assert(await shared.locator('.flow-qa-send').isDisabled());
    const data = await shared.locator('#data').textContent();
    assert.equal(JSON.parse(data).runtime, undefined);
    assert.equal(JSON.parse(data).filesystem, undefined);
    assert.equal(JSON.parse(data).qa.length, 1);
    assert.equal(await shared.locator('.flow-qa-draft').inputValue(), '');
    await shared.close();
    assert.deepEqual(requests, []);
    console.log('PASS offline: dialog handoff, saved history, complete-only selection, sanitized reusable HTML, no network');

    const redactionCases = [
      'password:"synthetic secret phrase"',
      'client_secret is \'another private phrase\'',
      'credential: "service user private phrase"',
      '"api_key": "quoted key phrase"',
      'session_key=opaque-session-value',
      'cookie="private cookie phrase"',
      'authorization: Basic cHJpdmF0ZTpwYXNz',
      'https://internal.example/private',
      'http://127.0.0.1:2367/private',
      '//private.example/team',
      'ssh://private.example/project',
      '/data/private/book.json',
      '/repository/another-private-module.py',
      'C:\\Private Folder\\private-book.json',
      '\\\\private-host\\private-share\\book.json',
      '~/private-project/config',
      'AKIA1234567890ABCDEF',
      'eyJhbGciOiJIUzI1NiJ9.eyJwcml2YXRlIjp0cnVlfQ.signature',
      '-----BEGIN RSA PRIVATE KEY-----\nsynthetic-private-key-material\n-----END RSA PRIVATE KEY-----'
    ];
    const fullFlow = {id: 'whole-flow-qa', node_id: null, question: '整个流程如何校验？', answer: '公开说明保留。\n' + redactionCases.join('\n')};
    const parityPath = path.join(temp, 'redaction-parity.html');
    fs.writeFileSync(parityPath, fixture(undefined, [fullFlow]));
    const parityPage = await pageFor(pathToFileURL(parityPath).href);
    const originalData = await parityPage.locator('#data').evaluate(element => JSON.parse(element.textContent));
    await parityPage.getByRole('button', {name: '问答', exact: true}).click();
    await parityPage.locator('.flow-qa-entry input').check();
    const parityExport = await download(parityPage, '.flow-qa-export');
    const parityShared = await pageFor(pathToFileURL(parityExport).href);
    const sharedData = await parityShared.locator('#data').evaluate(element => JSON.parse(element.textContent));
    assert(Object.hasOwn(sharedData.qa[0], 'node_id'), 'full-flow exports must retain the node_id key');
    assert.equal(sharedData.qa[0].node_id, null, 'whole-flow scope must remain null');
    assert.match(sharedData.qa[0].answer, /^公开说明保留。/);
    for (const secret of ['synthetic secret phrase', 'another private phrase', 'service user private phrase', 'quoted key phrase', 'opaque-session-value', 'private cookie phrase', 'cHJpdmF0ZTpwYXNz', 'internal.example', '127.0.0.1', 'private.example', '/data/private', 'another-private-module', 'Private Folder', 'private-host', 'private-project', 'AKIA1234567890ABCDEF', 'eyJhbGciOiJIUzI1NiJ9', 'synthetic-private-key-material']) {
      assert(!sharedData.qa[0].answer.includes(secret), `redaction parity fixture leaked ${secret}`);
    }
    const serverParity = spawnSync(process.env.PYTHON_EXECUTABLE || 'python', ['-c',
      'import sys,json; sys.path.insert(0,sys.argv[1]); from flow_exports import share_data; docs=json.load(sys.stdin); print(json.dumps([share_data(doc,doc["qa"])["qa"] for doc in docs],ensure_ascii=True))',
      path.resolve(assets, '../scripts')
    ], {input: JSON.stringify([originalData, sharedData]), encoding: 'utf8', env: {...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1'}});
    assert.equal(serverParity.status, 0, 'shared full-flow QA must validate through the server export helper: ' + (serverParity.stderr || serverParity.error || ''));
    const [serverOriginal, serverReused] = JSON.parse(serverParity.stdout);
    const normalizeRedaction = text => text.replace(/\[(?:redacted [^\]]+|已隐藏|路径已隐藏|链接已隐藏)\]/g, '[redacted]');
    assert.equal(normalizeRedaction(sharedData.qa[0].answer), normalizeRedaction(serverOriginal[0].answer), 'browser and server must redact the same credential, URL, and path spans');
    assert.equal(serverReused[0].node_id, null);
    assert.equal(serverReused[0].answer, sharedData.qa[0].answer);
    await parityPage.close(); await parityShared.close();
    console.log('PASS redaction parity: quoted credential phrases, all URLs, absolute paths, full-flow null scope and server reuse');

    const live = await pageFor(origin);
    await live.getByRole('button', {name: '问答', exact: true}).click();
    assert.equal(await live.locator('.flow-qa-draft').getAttribute('maxlength'), '4000');
    await until(() => live.locator('.flow-qa-entry').count().then(count => count === 2), 'server history not loaded');
    await until(() => live.locator('.flow-qa-entry').first().textContent().then(text => text.includes('仅在服务器历史')), 'history must come from the server, not just embedded data.qa');
    assert.doesNotMatch(await live.locator('.flow-qa-status').textContent(), /已连接/, 'executable discovery must not claim authentication or connection success');
    assert.match(await live.locator('.flow-qa-status').textContent(), /首个问题.*连接/, 'pending readiness should explain the first-question connection attempt');
    assert.match(await live.locator('.flow-qa-badge').textContent(), /待连接|未连接/);
    await live.locator('#entry').click();
    await live.getByRole('button', {name: '追问这个节点', exact: true}).click();
    await live.locator('.flow-qa-draft').fill('为什么检查订单？');
    assert(await live.locator('.flow-qa-send').isEnabled(), 'available but disconnected must permit the first question');
    await live.locator('.flow-qa-send').click();
    await until(() => live.locator('.flow-qa-status').textContent().then(text => /正在查阅来源|正在核对来源/.test(text)), 'source lookup status must not fail the ask stream');
    assert.equal(await live.locator('.flow-qa-status b').count(), 0, 'lookup status must remain plain text');
    assert.equal(await live.locator('.flow-qa-entry').last().locator('input').count(), 0, 'lookup status must not complete an answer');
    assert.equal(await live.locator('.flow-qa-draft').inputValue(), '为什么检查订单？');
    await until(() => live.locator('.flow-qa-entry').last().textContent().then(text => text.includes('第一段')), 'stream delta was not displayed before completion');
    assert.equal(await live.locator('.flow-qa-entry').last().locator('input').count(), 0, 'streaming answer must not be selectable');
    assert(await live.locator('.flow-qa-send').isDisabled());
    await until(() => live.locator('.flow-qa-entry input').count().then(count => count === 2), 'complete answer not selectable');
    await until(() => live.locator('.flow-qa-badge').textContent().then(text => text === '已连接'), 'first successful question should refresh confirmed connection readiness');
    assert.equal(await live.locator('.flow-qa-draft').inputValue(), '');
    assert.equal(await live.locator('.flow-qa-entry img').count(), 0, 'model output must be plain text');
    assert.equal(await live.locator('.flow-qa-entry').last().locator('.flow-qa-answer').textContent(), '实时答案 <img src=x onerror=alert(1)> 第一段。第二段。', 'status events must not enter the saved answer');
    const ask = calls.find(call => call.url === '/api/ask');
    assert.deepEqual(ask.body, {question: '为什么检查订单？', node_id: 'entry'});
    assert.equal(ask.headers['x-flow-token'], token);
    assert.equal(calls.filter(call => call.url === '/api/ask').length, 1);
    const restored = await pageFor(origin);
    await restored.getByRole('button', {name: '问答', exact: true}).click();
    await until(() => restored.locator('.flow-qa-entry').count().then(count => count === 3), 'server-saved conversation did not survive reopening');
    assert.match(await restored.locator('.flow-qa-entry').last().textContent(), /为什么检查订单/);
    await restored.close();
    await live.locator('.flow-qa-entry input').last().check();
    await live.locator('.flow-qa-compile').click();
    await until(() => live.locator('.flow-qa-result a').count().then(count => count === 1), 'compiled link not shown');
    assert.equal(await live.locator('.flow-qa-result a').getAttribute('href'), origin + '/versions/new/handbook.html');
    assert.equal(live.url(), origin + '/', 'compilation must not replace the open original');
    assert.deepEqual(calls.find(call => call.url === '/api/compile').body, {entry_ids: ['new-1'], redact: true});
    const popupPending = live.waitForEvent('popup');
    await live.locator('.flow-qa-result a').click();
    const compiled = await popupPending;
    await compiled.waitForLoadState('domcontentloaded');
    await compiled.getByRole('button', {name: '问答', exact: true}).click();
    assert(await compiled.locator('.flow-qa-send').isDisabled());
    assert.equal(await compiled.locator('.flow-qa-entry').count(), 1);
    assert.match(await compiled.locator('.flow-qa-entry').textContent(), /实时答案/);
    assert.equal(await compiled.locator('#data').evaluate(element => JSON.parse(element.textContent).runtime), undefined);
    await compiled.close();
    const liveExport = await download(live, '.flow-qa-export');
    assert.match(fs.readFileSync(liveExport, 'utf8'), /SERVER-STATIC-EXPORT/);
    assert.deepEqual(calls.find(call => call.url === '/api/export').body, {entry_ids: ['new-1'], redact: true});
    mode = 'disconnected';
    const fallback = await download(live, '.flow-qa-export');
    const fallbackHtml = fs.readFileSync(fallback, 'utf8');
    assert(!fallbackHtml.includes(token));
    assert(!fallbackHtml.includes('RAW-PRIVATE-SOURCE'));
    const fallbackPage = await pageFor(pathToFileURL(fallback).href);
    assert.equal(await fallbackPage.locator('#data').evaluate(element => JSON.parse(element.textContent).runtime), undefined);
    await fallbackPage.getByRole('button', {name: '问答', exact: true}).click();
    assert.equal(await fallbackPage.locator('.flow-qa-entry').count(), 1);
    assert.match(await fallbackPage.locator('.flow-qa-entry').textContent(), /实时答案/);
    assert(await fallbackPage.locator('.flow-qa-send').isDisabled());
    await fallbackPage.close();
    const screenshots = process.argv[2];
    if (screenshots) {
      fs.mkdirSync(screenshots, {recursive: true});
      await live.locator('#flow-qa-panel').scrollIntoViewIfNeeded();
      await live.screenshot({path: path.join(screenshots, 'flow-assistant-desktop.png')});
      await live.setViewportSize({width: 390, height: 844});
      await live.screenshot({path: path.join(screenshots, 'flow-assistant-mobile.png')});
      await live.setViewportSize({width: 1440, height: 1000});
    }
    console.log('PASS live: authenticated history, chunked UTF-8 NDJSON, plain-text answers, explicit compile and export');

    for (const failure of ['http-error', 'stream-error', 'broken', 'truncated']) {
      mode = failure;
      await live.locator('.flow-qa-draft').fill(`保留草稿 ${failure}`);
      await live.locator('.flow-qa-send').click();
      await until(() => live.locator('.flow-qa-send').isEnabled(), `${failure} left send stuck`);
      assert.equal(await live.locator('.flow-qa-draft').inputValue(), `保留草稿 ${failure}`);
      assert.equal(await live.locator('.flow-qa-entry').last().locator('input').count(), 0);
      assert.match(await live.locator('.flow-qa-status').textContent(), /失败|错误|中断|不可用/);
    }
    mode = 'cancel';
    await live.locator('.flow-qa-draft').fill('取消后保留');
    await live.locator('.flow-qa-send').click();
    await until(() => live.locator('.flow-qa-entry').last().textContent().then(text => text.includes('部分回答')), 'pending answer missing');
    await live.locator('.flow-qa-cancel').click();
    await until(() => live.locator('.flow-qa-send').isEnabled(), 'cancel did not release UI');
    assert.equal(await live.locator('.flow-qa-draft').inputValue(), '取消后保留');
    assert(calls.some(call => call.url === '/api/cancel' && call.headers['x-flow-token'] === token));
    assert.equal(await live.locator('.flow-qa-entry').last().locator('input').count(), 0);
    mode = 'bad-url';
    await live.locator('.flow-qa-compile').click();
    await until(() => live.locator('.flow-qa-compile').isEnabled(), 'invalid URL left compile stuck');
    assert.equal(await live.locator('.flow-qa-result a').count(), 0, 'unsafe compiled URLs must never become links');
    console.log('PASS failures: HTTP and stream errors, malformed/truncated NDJSON, cancellation, draft preservation, safe result URLs');

    backend = {available: false, connected: false, model: 'synthetic', message: 'Safety setup unavailable <b>read-only</b>. password:"synthetic secret phrase" https://internal.example/auth /data/private/auth.json'};
    const readiness = await pageFor(origin);
    await readiness.getByRole('button', {name: '问答', exact: true}).click();
    await until(() => readiness.locator('.flow-qa-status').textContent().then(text => text.includes('安全连接')), 'unavailable backend should show an understandable failure reason');
    assert.match(await readiness.locator('.flow-qa-badge').textContent(), /不可用/);
    await readiness.locator('.flow-qa-draft').fill('保留待连接的问题');
    await readiness.locator('.flow-qa-entry input').first().check();
    assert(await readiness.locator('.flow-qa-send').isDisabled());
    assert(await readiness.locator('.flow-qa-compile').isDisabled());
    assert(await readiness.locator('.flow-qa-export').isEnabled(), 'unavailable backend must preserve offline export');
    const readinessText = await readiness.locator('.flow-qa-status').textContent();
    for (const secret of ['synthetic secret phrase', 'internal.example', '/data/private']) assert(!readinessText.includes(secret), 'backend message leaked ' + secret);
    assert.equal(await readiness.locator('.flow-qa-status b').count(), 0, 'backend messages must use textContent');
    backend = {...backend, available: true, connected: false, message: 'Codex found; safety checks have not run.'};
    await readiness.locator('.flow-qa-refresh').click();
    await until(() => readiness.locator('.flow-qa-send').isEnabled(), 'discovered backend must allow a connection attempt without prior auth');
    assert.doesNotMatch(await readiness.locator('.flow-qa-status').textContent(), /已连接/);
    mode = 'auth-error';
    await readiness.locator('.flow-qa-send').click();
    await until(() => readiness.locator('.flow-qa-status').textContent().then(text => text.includes('登录')), 'failed first connection should explain how to restore sign-in');
    assert.doesNotMatch(await readiness.locator('.flow-qa-badge').textContent(), /已连接/);
    assert.equal(await readiness.locator('.flow-qa-draft').inputValue(), '保留待连接的问题');
    assert(await readiness.locator('.flow-qa-send').isEnabled(), 'failed authentication must permit retry after external sign-in');
    assert.equal(await readiness.locator('.flow-qa-entry').last().locator('input').count(), 0, 'readiness refresh must not replace the failed turn with old history');
    for (const secret of ['synthetic secret phrase', 'internal.example', '/data/private']) assert(!(await readiness.locator('.flow-qa-status').textContent()).includes(secret));
    backend = {...backend, connected: true, message: 'Connected: synthetic test connection.'};
    await readiness.locator('.flow-qa-refresh').click();
    await until(() => readiness.locator('.flow-qa-status').textContent().then(text => text === '已连接本地问答'), 'confirmed connection must be distinguishable from a pending attempt');
    assert.equal(await readiness.locator('.flow-qa-badge').textContent(), '已连接');
    await readiness.close();
    mode = 'success';
    console.log('PASS readiness: pending first connection, confirmed connection, unavailable backend, safe failure messages and auth retry');

    await offline.evaluate(() => {
      window.captureCalls = [];
      window.html2canvas = async (target, options) => {
        const clone = document.cloneNode(true);
        await options.onclone(clone);
        const canvas = clone.getElementById('canvas');
        window.captureCalls.push({target: target.id, width: options.width, height: options.height, transform: canvas.style.transform, overflow: clone.getElementById('stage').style.overflow, text: canvas.textContent, options: {allowTaint: options.allowTaint, useCORS: options.useCORS}, liveTransform: document.getElementById('canvas').style.transform});
        const image = document.createElement('canvas'); image.width = 16; image.height = 16;
        image.getContext('2d').fillRect(0, 0, 16, 16);
        return image;
      };
    });
    const transform = await offline.locator('#canvas').evaluate(element => element.style.transform);
    const fullPNG = await download(offline, '.flow-qa-png-full');
    assert.equal(fs.readFileSync(fullPNG).subarray(1, 4).toString(), 'PNG');
    await download(offline, '.flow-qa-png-view');
    const captures = await offline.evaluate(() => window.captureCalls);
    assert.equal(captures.length, 2);
    assert.equal(captures[0].transform, 'none', 'whole-canvas clone must not keep zoom transforms');
    assert.equal(captures[0].overflow, 'visible');
    assert.equal(captures[0].liveTransform, transform);
    assert.equal(captures[1].target, 'viewport');
    assert.equal(await offline.locator('#canvas').evaluate(element => element.style.transform), transform);
    assert.deepEqual(captures[0].options, {allowTaint: false, useCORS: false});
    await offline.locator('#canvas').evaluate(element => { element.style.height = '40000px'; });
    await offline.locator('.flow-qa-png-full').click();
    await until(() => offline.locator('.flow-qa-status').textContent().then(text => /过大|尺寸|大小/.test(text)), 'oversize PNG lacks an actionable error');
    assert.equal(await offline.evaluate(() => window.captureCalls.length), 2, 'oversized canvas must be rejected before rendering');
    await offline.locator('#canvas').evaluate(element => { element.style.height = ''; });
    console.log('PASS PNG: clone-only zoom reset, whole/viewport capture, size guard, PNG download');

    // Exercise the pinned renderer, including its SVG rasterization, under the server CSP.
    const pngPage = await pageFor(origin);
    await pngPage.locator('#entry span').evaluate(element => { element.textContent = 'C:\\private\\' + 'long-private-source-'.repeat(22); });
    await pngPage.evaluate(() => window.dispatchEvent(new Event('resize')));
    await pngPage.locator('#zoom-reset').click();
    await pngPage.evaluate(() => {
      window.realCaptures = [];
      window.cspFailures = [];
      document.addEventListener('securitypolicyviolation', event => window.cspFailures.push(event.violatedDirective));
      const native = window.html2canvas;
      window.html2canvas = async (target, options) => {
        const sourcePath = document.querySelector('#edges>path');
        const point = sourcePath.getPointAtLength(sourcePath.getTotalLength() / 4);
        const screen = point.matrixTransform(sourcePath.getScreenCTM());
        const rect = target.getBoundingClientRect();
        let geometry;
        const bitmap = await native(target, {...options, onclone: async (document, element) => {
          const boxes = () => [...document.querySelectorAll('.node')].map(node => ({id: node.id, top: node.offsetTop, left: node.offsetLeft, width: node.offsetWidth, height: node.offsetHeight}));
          const before = boxes();
          await options.onclone(document, element);
          geometry = {before, after: boxes(), text: document.getElementById('canvas').textContent};
        }});
        const pixels = bitmap.getContext('2d').getImageData(0, 0, bitmap.width, bitmap.height).data;
        let nonwhite = 0;
        for (let i = 0; i < pixels.length; i += 4) if (pixels[i + 3] && Math.min(pixels[i], pixels[i + 1], pixels[i + 2]) < 220) nonwhite++;
        const x = Math.round((target.id === 'canvas' ? point.x : screen.x - rect.left) * options.scale);
        const y = Math.round((target.id === 'canvas' ? point.y : screen.y - rect.top) * options.scale);
        let edgePixels = 0;
        for (let dx = -2; dx <= 2; dx++) for (let dy = -2; dy <= 2; dy++) {
          const i = ((y + dy) * bitmap.width + x + dx) * 4;
          if (pixels[i + 3] > 0 && pixels[i] < 210 && pixels[i + 1] < 220 && pixels[i + 2] < 230) edgePixels++;
        }
        window.realCaptures.push({width: bitmap.width, height: bitmap.height, nonwhite, edgePixels, geometry});
        return bitmap;
      };
    });
    const actualFull = await download(pngPage, '.flow-qa-png-full');
    const real = await pngPage.evaluate(() => window.realCaptures[0]);
    assert(real.width >= 560 && real.height > 300, 'full PNG should retain full-resolution canvas bounds');
    assert(real.nonwhite > 800, 'whole-canvas PNG is blank');
    assert(real.edgePixels >= 3, 'SVG connector pixels are missing from whole-canvas PNG');
    assert.deepEqual(real.geometry.after, real.geometry.before, 'redaction must not resize or move nodes relative to SVG edges');
    assert(!real.geometry.text.includes('long-private-source'));
    const actualView = await download(pngPage, '.flow-qa-png-view');
    const actualViewport = await pngPage.evaluate(() => window.realCaptures[1]);
    assert(actualViewport.nonwhite > 800 && actualViewport.edgePixels >= 3, 'viewport PNG must contain nodes and connectors');
    assert.deepEqual(await pngPage.evaluate(() => window.cspFailures), []);
    if (screenshots) {
      fs.copyFileSync(actualFull, path.join(screenshots, 'flow-assistant-full.png'));
      fs.copyFileSync(actualView, path.join(screenshots, 'flow-assistant-view.png'));
    }
    await pngPage.close();
    console.log(`PASS pinned html2canvas/CSP: full ${real.width}x${real.height}, ${real.nonwhite} nonwhite pixels, ${real.edgePixels} connector pixels; viewport ${actualViewport.width}x${actualViewport.height}, ${actualViewport.edgePixels} connector pixels`);

    const layout = await offline.evaluate(() => {
      const v = document.getElementById('viewport').getBoundingClientRect(), a = document.getElementById('flow-qa-panel').getBoundingClientRect();
      return {overlap: v.right > a.left + 1, overflow: document.documentElement.scrollWidth > innerWidth};
    });
    assert.equal(layout.overlap, false, 'desktop sidebar must sit beside the diagram');
    assert.equal(layout.overflow, false);
    await offline.setViewportSize({width: 390, height: 844});
    assert.equal(await offline.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    const drawer = await offline.locator('#flow-qa-panel').boundingBox();
    assert(drawer.x >= 0 && drawer.x + drawer.width <= 391 && drawer.y + drawer.height <= 845);
    await offline.keyboard.press('Escape');
    assert.equal(await offline.locator('#flow-qa-panel').isVisible(), false);
    console.log('PASS layout: desktop alongside canvas, mobile drawer, no document overflow, Escape close');

    for (const runtime of [{api: 'https://example.com/api', token}, {api: '/api/elsewhere', token}]) {
      const restricted = await browser.newPage();
      const outgoing = [];
      await restricted.route('**/*', route => { outgoing.push(route.request().url()); return route.abort(); });
      await restricted.setContent(fixture(runtime));
      await restricted.getByRole('button', {name: '问答', exact: true}).click();
      assert(await restricted.locator('.flow-qa-send').isDisabled());
      assert.deepEqual(outgoing, []);
      await restricted.close();
    }
    assert.deepEqual(errors, []);
    assert(calls.every(call => call.url.startsWith('/api/')), 'browser sent an unexpected request');
    console.log('PASS security: invalid runtime rejected, no page errors');
  } finally {
    await browser.close();
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    fs.rmSync(temp, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
