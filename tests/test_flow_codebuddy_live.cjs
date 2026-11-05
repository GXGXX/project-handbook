const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const {test, before, after} = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn, spawnSync} = require('node:child_process');

// Direct answers in the page through WorkBuddy's command line (CodeBuddy CLI),
// with a stand-in CLI that streams a fixed answer the way stream-json does.
const root = path.resolve(__dirname, '..');
const python = process.env.PYTHON_EXECUTABLE || 'python';
let browser, temp, server, url, logFile;

const FAKE = `#!/usr/bin/env python3
import json, os, sys
prompt = sys.stdin.read()
open(os.environ['FAKE_CODEBUDDY_LOG'], 'a', encoding='utf-8').write(json.dumps({'argv': sys.argv[1:], 'prompt': prompt}, ensure_ascii=False) + '\\n')
say = lambda e: print(json.dumps(e, ensure_ascii=False), flush=True)
for part in ['不会保留。', '库存不足时', '直接结束。']:
    say({'type': 'stream_event', 'event': {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': part}}})
say({'type': 'result', 'subtype': 'success', 'result': '不会保留。库存不足时直接结束。'})
`;

before(async () => {
  temp = fs.mkdtempSync(path.join(os.tmpdir(), 'handbook-codebuddy-'));
  const fake = path.join(temp, 'codebuddy');
  fs.writeFileSync(fake, FAKE, {mode: 0o755});
  logFile = path.join(temp, 'calls.jsonl');
  const book = path.join(temp, 'book');
  const built = spawnSync(python, ['-B', '-X', 'utf8', path.join(root, 'project-handbook/scripts/build_flow.py'),
    path.join(root, 'project-handbook/assets/flow.example.json'), book], {encoding: 'utf8'});
  assert.equal(built.status, 0, built.stderr);
  server = spawn(python, ['-B', '-X', 'utf8', path.join(root, 'project-handbook/scripts/flow_server.py'), book,
    '--agent', 'codebuddy', '--codebuddy-bin', fake], {env: {...process.env, FAKE_CODEBUDDY_LOG: logFile}, stdio: ['ignore', 'pipe', 'pipe']});
  url = await new Promise((resolve, reject) => {
    let out = '', err = '';
    server.stdout.on('data', chunk => { out += chunk; const m = out.match(/http:\/\/127\.0\.0\.1:\d+/); if (m) resolve(m[0]); });
    server.stderr.on('data', chunk => { err += chunk; });
    server.on('exit', code => reject(new Error('server exited ' + code + ': ' + err)));
    setTimeout(() => reject(new Error('server did not start: ' + err)), 15000);
  });
  browser = await chromium.launch({headless: true, executablePath: process.env.BROWSER_EXECUTABLE || undefined});
});
after(async () => {
  if (browser) await browser.close();
  if (server) server.kill();
  if (temp) fs.rmSync(temp, {recursive: true, force: true});
});

test('a question is answered in the page by the CodeBuddy CLI', async () => {
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(url + '/handbook.html');
  await page.locator('#stock').click();
  await page.getByRole('button', {name: '追问这个节点', exact: true}).click();
  const send = page.locator('.flow-qa-send');
  assert.equal(await send.textContent(), '发送', 'connected pages answer directly, no copying');
  await page.locator('.flow-qa-draft').fill('库存不足时订单会保留多久？');
  await send.click();
  await page.locator('.flow-qa-answer').filter({hasText: '库存不足时直接结束'}).waitFor({timeout: 15000});
  assert.equal(await page.locator('.flow-qa-role-assistant').last().textContent(), 'CodeBuddy · AI');
  assert.equal(await page.locator('.flow-qa-badge').textContent(), '已连接');
  const calls = fs.readFileSync(logFile, 'utf8').trim().split('\n').map(line => JSON.parse(line));
  assert.deepEqual(calls[0].argv, ['-p', '--output-format', 'stream-json']);
  assert.match(calls[0].prompt, /库存不足时订单会保留多久？/);
  assert.match(calls[0].prompt, /库存充足？/, 'the selected step is in the prompt');
  assert.deepEqual(errors, []);
  await page.close();
});
