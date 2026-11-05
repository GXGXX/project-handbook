// Films the README demo video: drives a real handbook page inside stage.html
// and saves JPEG frames per scene, 30 fps, 1920x1080. Usage, from the repo root:
//   node docs/video/director.cjs OUT_DIR      (needs Playwright, Python and ffmpeg)
// then encode as described in docs/video/README.md.
const {chromium} = require('playwright');
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');
const {pathToFileURL} = require('url');

const REPO = path.resolve(__dirname, '../..');
const V = path.resolve(process.argv[2] || 'demo-video');
const BOOK = path.join(V, '流程手册-签到奖励');
const SHOWN_PATH = 'D:/资料/流程手册-签到奖励/handbook.html';
const FPS = 30;
const only = process.argv[3] ? process.argv[3].split(',') : null;

const ease = t => t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

(async () => {
  fs.mkdirSync(V, {recursive: true});
  if (!fs.existsSync(BOOK)) execFileSync('python3', ['-X', 'utf8', path.join(REPO, 'project-handbook/scripts/build_flow.py'),
    path.join(REPO, 'docs/examples/checkin.flow.json'), BOOK]);
  fs.rmSync(path.join(BOOK, 'answers.js'), {force: true});
  const browser = await chromium.launch();
  const context = await browser.newContext({viewport: {width: 1440, height: 810}, deviceScaleFactor: 4 / 3,
    permissions: ['clipboard-read', 'clipboard-write']});
  const page = await context.newPage();
  await page.goto(pathToFileURL(path.join(__dirname, 'stage.html')).href);
  await page.evaluate(src => { document.getElementById('book').src = src; }, pathToFileURL(path.join(BOOK, 'handbook.html')).href);
  await page.waitForTimeout(800);
  const frame = page.frames().find(f => f.url().endsWith('handbook.html'));
  await frame.evaluate(p => { window.pagePath = () => p; document.fonts.ready; }, SHOWN_PATH);
  await frame.evaluate(() => document.fonts.ready);
  const stage = (fn, ...args) => page.evaluate(([fn, args]) => window.stage[fn](...args), [fn, args]);

  let dir, count, cur = {x: 900, y: 600};
  const scenes = [];
  async function scene(name) {
    dir = path.join(V, 'frames', name); fs.rmSync(dir, {recursive: true, force: true}); fs.mkdirSync(dir, {recursive: true});
    count = 0; scenes.push(name);
  }
  async function snap(n = 1) {
    if (only && !only.includes(path.basename(dir))) { count += n; return; }
    const first = path.join(dir, String(++count).padStart(5, '0') + '.jpg');
    await page.screenshot({path: first, type: 'jpeg', quality: 92});
    for (let i = 1; i < n; i++) fs.linkSync(first, path.join(dir, String(++count).padStart(5, '0') + '.jpg'));
  }
  const hold = s => snap(Math.round(s * FPS));
  async function fade(from, to, s = .5) {
    const n = Math.round(s * FPS);
    for (let i = 1; i <= n; i++) { const t = ease(i / n); if (from) await stage('show', from, 1 - t); if (to) await stage('show', to, t); await snap(); }
  }
  async function move(x, y, s = .7) {
    const n = Math.round(s * FPS), x0 = cur.x, y0 = cur.y;
    for (let i = 1; i <= n; i++) { const t = ease(i / n); await stage('cursor', x0 + (x - x0) * t, y0 + (y - y0) * t); await snap(); }
    cur = {x, y};
  }
  async function click(after) {
    await page.mouse.click(cur.x, cur.y);
    if (after) await after();
    for (let i = 1; i <= 9; i++) { await stage('ring', cur.x, cur.y, i / 10); await snap(); }
    await stage('ring', cur.x, cur.y, 1);
  }
  async function centre(locator) { const b = await locator.boundingBox(); return [b.x + b.width / 2, b.y + b.height / 2]; }
  async function moveTo(locator, s, dx = 0, dy = 0) { const [x, y] = await centre(locator); await move(x + dx, y + dy, s); }
  let shown = null;
  async function caption(n, text, top = false) {
    if (!text) { // hide the current caption
      if (shown) for (let i = 7; i >= 0; i--) { await stage('cap', shown[0], shown[1], i / 8, top); await snap(); }
      shown = null; return;
    }
    for (let i = 1; i <= 8; i++) { await stage('cap', n, text, i / 8, top); await snap(); }
    shown = [n, text];
  }
  async function scrollFrame(target, s, el) {
    const n = Math.round(s * FPS);
    const from = await frame.evaluate(el => el ? document.querySelector(el).scrollTop : scrollY, el);
    for (let i = 1; i <= n; i++) {
      const y = from + (target - from) * ease(i / n);
      await frame.evaluate(([el, y]) => el ? document.querySelector(el).scrollTop = y : scrollTo(0, y), [el, y]);
      await snap();
    }
  }
  async function typeChat(text, s) {
    const n = Math.round(s * FPS);
    for (let i = 1; i <= n; i++) { await stage('input', text.slice(0, Math.ceil(text.length * i / n))); await snap(); }
  }

  // 0. Title
  await scene('00-title');
  await hold(2.6);

  // 1. Ask the AI in its chat
  await scene('01-ask');
  await fade('title', 'chat', .5);
  await caption('1', '在 AI 对话框里：说清资料在哪、想弄明白什么');
  const ask = '用 project-handbook 帮我梳理一下。\n资料在：D:/资料/签到活动\n问题：用户签到后，奖励是怎么判断和发放的？';
  await typeChat(ask, 2.2);
  await stage('cursor', 1215, 735, 0); cur = {x: 1215, y: 735};
  await hold(.3);
  await stage('input', ''); await stage('msg', 'me', '<span class="who">你</span>' + ask.replace(/\n/g, '<br>'));
  const thinking = await stage('msg', 'ai', '<span class="who">AI</span><span class="thinking">正在阅读资料，梳理流程…</span>');
  await hold(1.1);
  await stage('setMsg', thinking, '<span class="who">AI</span><b>结论：</b>每天限签 1 次；连续天数决定奖励，第 7 天发 100 金币 + 1 张抽奖券；新用户首签多 20 金币；发放失败会补发。<br><br>' +
    '<b>流程图已生成：</b><span class="path">D:/资料/流程手册-签到奖励/handbook.html</span><br>双击就能用浏览器打开。点任意一步可以看细节和依据；有看不懂的地方，点「问答」写下问题，点「复制给 AI」，再粘贴回这里发给我。');
  await hold(3.2);

  // 2. Open the page
  await scene('02-open');
  await caption('', '', false);
  await fade('chat', 'page', .6);
  await caption('2', '双击打开网页：整个流程在一张图上');
  await hold(.8);
  const diagramTop = await frame.evaluate(() => document.getElementById('diagram').getBoundingClientRect().top + scrollY - document.querySelector('nav').offsetHeight - 6);
  await scrollFrame(diagramTop, 1.0);
  await hold(.6);
  await scrollFrame(330, 1.4, '#viewport');
  await hold(.8);

  // 3. Click a step, walk to the next and back
  await scene('03-step');
  await caption('3', '点任意一步：看规则和原文依据，顺着「上一步 / 下一步」走');
  await stage('cursor', cur.x, cur.y, 1);
  await moveTo(frame.locator('#big'), .8, -40, -10);
  await click();
  await hold(1.4);
  await moveTo(frame.locator('#detail-to .step-link'), .7, -60);
  await click(() => frame.waitForTimeout(150));
  await hold(1.2);
  await moveTo(frame.locator('#detail-from .step-link[data-node="big"]'), .6, -60);
  await click(() => frame.waitForTimeout(150));
  await hold(.8);

  // 4. Ask in the page
  await scene('04-question');
  await caption('4', '有疑问就写下来，点「复制给 AI」');
  await moveTo(frame.getByRole('button', {name: '追问这个节点'}), .6);
  await click(() => frame.waitForTimeout(250));
  const panelTop = await frame.evaluate(() => document.querySelector('.flow-qa-panel').getBoundingClientRect().top + scrollY - document.querySelector('nav').offsetHeight - 10);
  await scrollFrame(panelTop, .6);
  await moveTo(frame.locator('.flow-qa-draft'), .5, -80);
  await click();
  const question = '第 7 天领完以后，第 8 天再签到算第几天？';
  const n = Math.round(1.3 * FPS);
  for (let i = 1; i <= n; i++) { await frame.locator('.flow-qa-draft').fill(question.slice(0, Math.ceil(question.length * i / n))); await snap(); }
  await moveTo(frame.locator('.flow-qa-send'), .5);
  await click(() => frame.waitForTimeout(300));
  await hold(1.6);
  const copied = await page.evaluate(() => navigator.clipboard.readText());

  // 5. Paste to the AI
  await scene('05-paste');
  await caption('', '', false);
  await stage('cursor', cur.x, cur.y, 0);
  await stage('clearMsgs');
  await fade('page', 'chat', .5);
  await caption('5', '粘贴给 AI：它用资料回答，并把答案存回网页');
  await hold(.3);
  await stage('input', copied); await hold(1.0);
  await stage('input', ''); await stage('msg', 'me', '<span class="who">你</span>' + copied.replace(/\n/g, '<br>'));
  const answering = await stage('msg', 'ai', '<span class="who">AI</span><span class="thinking">正在查资料回答…</span>');
  await hold(1.0);
  const id = copied.match(/问题编号：(\S+)/)[1];
  fs.writeFileSync(path.join(V, 'q.txt'), question);
  fs.writeFileSync(path.join(V, 'a.md'), '算**第 1 天**。\n\n领完第 7 天的大奖后，连续天数会重置为 0。第 8 天签到时昨天签过，所以 0 + 1 = 1：拿 10 金币，开始新一轮。');
  execFileSync('python3', ['-X', 'utf8', path.join(REPO, 'project-handbook/scripts/save_answer.py'), BOOK,
    '--id', id, '--node', 'big', '--question-file', path.join(V, 'q.txt'), '--answer-file', path.join(V, 'a.md')]);
  await stage('setMsg', answering, '<span class="who">AI</span>算 <b>第 1 天</b>。领完第 7 天的大奖后，连续天数会重置为 0；第 8 天签到时 0 + 1 = 1，拿 10 金币，开始新一轮。<br><br>已存回手册，回到网页几秒后会自动显示。');
  await hold(2.6);

  // 6. The answer is in the page
  await scene('06-answer');
  await caption('', '', false);
  await fade('chat', 'page', .5);
  await caption('6', '回到网页：回答已经出现，不用重新生成');
  await frame.locator('.flow-qa-entry-state').waitFor({state: 'detached', timeout: 15000});
  await frame.waitForTimeout(200);
  await frame.evaluate(() => { const box = document.querySelector('.flow-qa-transcript'), entries = box.querySelectorAll('.flow-qa-entry'); box.scrollTop = entries[entries.length - 1].offsetTop - box.offsetTop - 4; });
  await hold(2.6);

  // 7. Walk an example on the diagram
  await scene('07-route');
  await caption('7', '跟着数值例子，在图上走一遍');
  await stage('cursor', cur.x, cur.y, 1);
  await moveTo(frame.locator('.flow-qa-close'), .5);
  await click(() => frame.waitForTimeout(150));
  await frame.evaluate(() => { document.querySelector('details.example').open = true; });
  const exampleTop = await frame.evaluate(() => document.getElementById('examples').getBoundingClientRect().top + scrollY - 40);
  await scrollFrame(exampleTop, .8);
  await moveTo(frame.locator('.show-route').first(), .6);
  await click(() => frame.waitForTimeout(350));
  await stage('cursor', cur.x, cur.y, 0);
  await hold(2.8);

  // 8. Share
  await scene('08-share');
  await caption('8', '一键导出离线 HTML，发给同事双击就能看');
  await stage('cursor', cur.x, cur.y, 1);
  await moveTo(frame.locator('.flow-qa-share'), .7);
  await hold(1.6);

  // 9. End
  await scene('09-end');
  await caption('', '', false);
  await stage('cursor', cur.x, cur.y, 0);
  await fade('page', 'end', .6);
  await hold(3.4);

  fs.writeFileSync(path.join(V, 'frames', 'scenes.txt'), scenes.join('\n') + '\n');
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
