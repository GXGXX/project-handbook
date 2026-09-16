/* Lucide icon paths: ISC License, Copyright (c) Lucide Contributors.
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION
 * OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
 * CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */
;(() => {
  'use strict';
  function initialize() {
    const source = document.getElementById('data');
    const viewportElement = document.getElementById('viewport');
    const toolbar = document.querySelector('.canvas-tools');
    if (!source || !viewportElement || !toolbar || document.querySelector('.flow-qa-shell')) return;
    let book;
    try { book = JSON.parse(source.textContent); } catch (_) { return; }
    const runtime = book.runtime;
    const live = location.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)
      && runtime && runtime.api === '/api' && typeof runtime.token === 'string' && runtime.token.length > 0;
    const authoredNodes = book.canvas?.nodes || (book.graphs || []).flatMap(graph => graph.nodes || []);
    const selected = new Set();
    let entries = normalizeEntries(book.qa, true), nodeId = null, active = null, externalBusy = false;
    let available = !!live, loading = !!live, exporting = false, polling = null, refreshing = false;
    let connected = false, backendMessage = '';
    let returnFocus = null, localCounter = 0;
    const icons = {
      chat: ['M21 15a4 4 0 0 1-4 4H7l-4 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z'],
      close: ['M18 6 6 18', 'm6 6 12 12'],
      send: ['m22 2-7 20-4-9-9-4Z', 'M22 2 11 13'],
      download: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'm7 10 5 5 5-5', 'M12 15V3'],
      image: ['M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z', 'm21 15-5-5L5 21', 'M8.5 8.5h.01'],
      scan: ['M4 9V5a1 1 0 0 1 1-1h4', 'M15 4h4a1 1 0 0 1 1 1v4', 'M20 15v4a1 1 0 0 1-1 1h-4', 'M9 20H5a1 1 0 0 1-1-1v-4', 'M8 12h8'],
      refresh: ['M3 12a9 9 0 0 1 15.36-6.36L21 8', 'M21 3v5h-5', 'M21 12a9 9 0 0 1-15.36 6.36L3 16', 'M8 16H3v5'],
      compile: ['M12 3v12', 'm8 11 4 4 4-4', 'M5 17v4h14v-4'],
      stop: ['M6 6h12v12H6z']
    };
    function element(tag, className, text) {
      const result = document.createElement(tag);
      if (className) result.className = className;
      if (text !== undefined) result.textContent = text;
      return result;
    }
    function icon(name) {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      for (const [key, value] of Object.entries({viewBox: '0 0 24 24', width: 18, height: 18, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true'})) svg.setAttribute(key, value);
      for (const d of icons[name]) {
        const path = document.createElementNS(svg.namespaceURI, 'path'); path.setAttribute('d', d); svg.append(path);
      }
      return svg;
    }
    function button(className, label, image, text = false) {
      const result = element('button', 'flow-qa-button ' + className);
      result.type = 'button'; result.title = label; result.setAttribute('aria-label', label);
      if (image) result.append(icon(image));
      if (text) result.append(element('span', '', label));
      return result;
    }
    function normalizeEntries(values, authored = false) {
      const found = new Set();
      return (Array.isArray(values) ? values : []).filter(value => value && typeof value.question === 'string' && typeof value.answer === 'string').map((value, index) => ({
        id: typeof value.id === 'string' && value.id ? value.id : `authored-${index}`,
        node_id: typeof value.node_id === 'string' ? value.node_id : null,
        question: value.question, answer: value.answer,
        status: value.status || (authored ? 'complete' : 'error'),
        created_at: typeof value.created_at === 'string' ? value.created_at : ''
      })).filter(value => { if (found.has(value.id)) return false; found.add(value.id); return true; });
    }

    const tools = element('div', 'flow-qa-tools');
    tools.dataset.flowQaUi = '';
    const toggle = button('flow-qa-toggle', '问答', 'chat', true);
    const share = button('flow-qa-share', '导出离线 HTML', 'download');
    const pngFull = button('flow-qa-png-full', '导出全图 PNG', 'image');
    const pngView = button('flow-qa-png-view', '导出当前视图 PNG', 'scan');
    tools.append(toggle, share, pngFull, pngView); toolbar.append(tools);
    const shell = element('div', 'flow-qa-shell');
    viewportElement.before(shell); shell.append(viewportElement);
    const aside = element('aside', 'flow-qa-panel');
    aside.id = 'flow-qa-panel'; aside.hidden = true; aside.setAttribute('aria-label', '流程问答');
    toggle.setAttribute('aria-controls', aside.id); toggle.setAttribute('aria-expanded', 'false');
    const head = element('div', 'flow-qa-header');
    const heading = element('div', 'flow-qa-heading');
    const badge = element('span', 'flow-qa-badge', live ? '检查中' : '离线副本');
    heading.append(element('h3', '', '流程问答'), badge);
    const refresh = button('flow-qa-refresh', '刷新连接与历史', 'refresh'); refresh.hidden = !live;
    const close = button('flow-qa-close', '关闭问答', 'close');
    head.append(heading, refresh, close);
    const context = element('div', 'flow-qa-context');
    const contextText = element('span', '', '整个流程');
    const clearContext = button('flow-qa-clear-context', '取消节点限定', 'close'); clearContext.hidden = true;
    context.append(element('span', 'flow-qa-context-label', '当前范围'), contextText, clearContext);
    const transcript = element('div', 'flow-qa-transcript');
    transcript.setAttribute('role', 'log'); transcript.setAttribute('aria-label', '问答记录'); transcript.tabIndex = 0;
    const result = element('div', 'flow-qa-result'); result.hidden = true;
    const status = element('p', 'flow-qa-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    const form = element('form', 'flow-qa-form');
    const draft = element('textarea', 'flow-qa-draft');
    draft.rows = 3; draft.maxLength = 4000; draft.placeholder = '有什么疑问？'; draft.setAttribute('aria-label', '问题');
    const actions = element('div', 'flow-qa-actions');
    const send = button('flow-qa-send flow-qa-primary', '发送', 'send', true); send.type = 'submit';
    const cancel = button('flow-qa-cancel', '停止', 'stop', true); cancel.hidden = true;
    actions.append(cancel, send); form.append(draft, actions);
    const footer = element('div', 'flow-qa-footer');
    const count = element('span', 'flow-qa-selection');
    const exportButton = button('flow-qa-export', '离线 HTML', 'download', true);
    const compile = button('flow-qa-compile', '整理新版本', 'compile', true);
    compile.title = '将选中的回答整理成完整版本，保留原版';
    const footerActions = element('div', 'flow-qa-footer-actions'); footerActions.append(exportButton, compile);
    footer.append(count, footerActions); aside.append(head, context, transcript, result, status, form, footer); shell.append(aside);
    const dialog = document.getElementById('detail');
    if (dialog) {
      const askNode = button('flow-qa-ask-node flow-qa-primary', '追问这个节点', 'chat', true);
      askNode.dataset.flowQaUi = ''; dialog.append(askNode);
      askNode.addEventListener('click', () => { dialog.close(); openPanel(askNode); draft.focus({preventScroll: true}); });
    }
    function setStatus(message, error = false) {
      status.textContent = message;
      status.classList.toggle('flow-qa-error', error);
    }
    function updateReadiness(backend) {
      available = backend.available === true;
      connected = available && backend.connected === true;
      backendMessage = typeof backend.message === 'string' ? redactText(backend.message).slice(0, 240) : '';
      badge.textContent = !available ? '不可用' : connected ? '已连接' : '待连接';
      badge.dataset.state = !available ? 'unavailable' : connected ? 'connected' : 'pending';
      badge.title = connected ? '' : backendMessage;
    }
    function readinessSummary() {
      if (connected) return '已连接本地问答';
      const summary = available ? 'Codex 可用；首个问题将尝试连接' : '问答暂不可用；可阅读与导出';
      return summary + (backendMessage ? '。' + backendMessage : '');
    }
    function updateControls() {
      const busy = !!active || externalBusy;
      send.disabled = !live || !available || loading || busy || !draft.value.trim();
      compile.disabled = !live || !available || loading || busy || !selected.size;
      cancel.hidden = !live || !busy;
      cancel.disabled = !!active?.cancelling;
      refresh.disabled = !!active || refreshing;
      exportButton.disabled = share.disabled = exporting;
      pngFull.disabled = pngView.disabled = exporting;
      count.textContent = `已选 ${selected.size} 条完整回答`;
      transcript.setAttribute('aria-busy', active?.kind === 'ask' ? 'true' : 'false');
    }
    function openPanel(trigger = toggle) {
      if (!aside.hidden) return;
      returnFocus = trigger;
      aside.hidden = false; shell.classList.add('flow-qa-open'); toggle.setAttribute('aria-expanded', 'true');
      window.dispatchEvent(new Event('resize'));
    }
    function closePanel() {
      if (aside.hidden) return;
      aside.hidden = true; shell.classList.remove('flow-qa-open'); toggle.setAttribute('aria-expanded', 'false');
      window.dispatchEvent(new Event('resize'));
      const target = returnFocus?.isConnected && !returnFocus.closest('dialog') ? returnFocus : toggle;
      target.focus({preventScroll: true});
    }
    function setNode(id) {
      const node = authoredNodes.find(item => item.id === id);
      nodeId = node ? node.id : null;
      contextText.textContent = node ? node.title : '整个流程'; clearContext.hidden = !node;
    }
    function renderEntries(scroll = false) {
      const nearBottom = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 90;
      const oldScroll = transcript.scrollTop;
      transcript.replaceChildren();
      if (!entries.length) transcript.append(element('p', 'flow-qa-empty', '暂无问答'));
      for (const entry of entries) {
        const article = element('article', 'flow-qa-entry'); article.dataset.entryId = entry.id;
        const meta = element('div', 'flow-qa-entry-meta');
        const node = authoredNodes.find(item => item.id === entry.node_id);
        meta.append(element('span', '', node ? node.title : '整个流程'));
        if (entry.status === 'complete') {
          const label = element('label', 'flow-qa-pick');
          const checkbox = element('input'); checkbox.type = 'checkbox'; checkbox.checked = selected.has(entry.id);
          checkbox.setAttribute('aria-label', '选择回答：' + entry.question);
          checkbox.addEventListener('change', () => { if (checkbox.checked) selected.add(entry.id); else selected.delete(entry.id); updateControls(); });
          label.append(checkbox, element('span', '', '选用')); meta.append(label);
        } else {
          meta.append(element('span', 'flow-qa-entry-state', entry.status === 'streaming' ? '回答中' : entry.status === 'cancelled' ? '已停止' : '未完成'));
        }
        article.append(meta, element('h4', 'flow-qa-question', entry.question), element('div', 'flow-qa-answer', entry.answer || (entry.status === 'streaming' ? '…' : '暂无回答')));
        transcript.append(article);
      }
      transcript.scrollTop = scroll || nearBottom ? transcript.scrollHeight : oldScroll;
      updateControls();
    }
    toggle.addEventListener('click', () => { if (aside.hidden) { openPanel(); draft.focus({preventScroll: true}); } else closePanel(); });
    close.addEventListener('click', closePanel);
    clearContext.addEventListener('click', () => setNode(null));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !aside.hidden && !dialog?.open) { event.preventDefault(); closePanel(); }
    });
    // Listen on window so either document- or window-dispatched renderer events work.
    window.addEventListener('flow:node-selected', event => setNode(event.detail?.id));
    document.addEventListener('flow:node-selected', event => setNode(event.detail?.id));
    draft.addEventListener('input', updateControls);
    draft.addEventListener('keydown', event => {
      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !event.isComposing) { event.preventDefault(); if (!send.disabled) form.requestSubmit(); }
    });

    async function request(endpoint, body, signal) {
      if (!live) throw new Error('离线副本无法连接问答');
      const response = await fetch(runtime.api + endpoint, {
        method: body === undefined ? 'GET' : 'POST',
        headers: {'X-Flow-Token': runtime.token, ...(body === undefined ? {} : {'Content-Type': 'application/json'})},
        body: body === undefined ? undefined : JSON.stringify(body),
        signal, credentials: 'same-origin', cache: 'no-store', redirect: 'error'
      });
      if (!response.ok) {
        let message = `请求失败（${response.status}）`;
        try { const value = await response.json(); message = value.message || value.error || message; } catch (_) { /* HTTP status is the fallback. */ }
        if (response.status === 409) { externalBusy = true; schedulePoll(); }
        throw new Error(typeof message === 'string' ? message : '请求失败');
      }
      return response;
    }
    function schedulePoll() {
      if (!live || polling) return;
      polling = setTimeout(() => { polling = null; if (!active) refreshState(true); else schedulePoll(); }, 1800);
    }
    async function refreshState(quiet = false, readinessOnly = false) {
      if (!live || active || refreshing) return;
      refreshing = true; updateControls();
      try {
        const value = await (await request('/state', undefined, AbortSignal.timeout(10000))).json();
        if (active) return;
        if (!Array.isArray(value.entries) || !value.backend || typeof value.busy !== 'boolean'
          || typeof value.backend.available !== 'boolean' || typeof value.backend.connected !== 'boolean') throw new Error('历史记录格式错误');
        if (!readinessOnly) {
          const history = normalizeEntries(value.entries);
          // Retain local failed turns and authored QAs that the server does not own.
          const known = new Set(history.map(entry => entry.id));
          entries = [...entries.filter(entry => !known.has(entry.id)), ...history];
        }
        externalBusy = value.busy;
        updateReadiness(value.backend);
        if (readinessOnly) {
          if (!connected && backendMessage && status.classList.contains('flow-qa-error')) setStatus(status.textContent + '；' + backendMessage, true);
        } else {
          if (!quiet || !externalBusy) setStatus(externalBusy ? '已有任务正在处理' : readinessSummary(), !available);
          renderEntries();
        }
        if (externalBusy) schedulePoll();
      } catch (error) {
        connected = false; backendMessage = '';
        badge.textContent = '状态未知'; badge.dataset.state = 'unknown'; badge.title = '';
        if (!readinessOnly) setStatus('连接检查失败；可重试，已有问答仍可阅读与导出', true);
      } finally { loading = false; refreshing = false; updateControls(); }
    }
    refresh.addEventListener('click', () => refreshState());
    async function stream(endpoint, payload, operation, receive) {
      const response = await request(endpoint, payload, operation.controller.signal);
      if (!response.body) throw new Error('浏览器无法读取实时回答');
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8', {fatal: true});
      let buffer = '', total = 0;
      function consume(line) {
        if (!line.trim()) return;
        let event;
        try { event = JSON.parse(line); } catch (_) { throw new Error('回答数据格式错误'); }
        if (!event || typeof event.type !== 'string') throw new Error('回答数据格式错误');
        if (event.type === 'error') throw new Error(typeof event.message === 'string' ? event.message : '回答失败');
        receive(event);
      }
      try {
        while (true) {
          const {value, done} = await reader.read();
          if (operation.cancelling || operation.controller.signal.aborted) throw new DOMException('Stopped', 'AbortError');
          if (done) { buffer += decoder.decode(); break; }
          total += value.byteLength;
          if (total > 4 * 1024 * 1024) throw new Error('回答过大，请缩小问题范围');
          buffer += decoder.decode(value, {stream: true});
          let index;
          while ((index = buffer.indexOf('\n')) !== -1) { const line = buffer.slice(0, index); buffer = buffer.slice(index + 1); consume(line); }
        }
        if (buffer.trim()) consume(buffer);
        if (!operation.complete) throw new Error('回答中断，未收到完成结果');
      } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
    }
    function newOperation(kind) {
      const operation = {kind, controller: new AbortController(), cancelling: false, complete: false};
      active = operation; result.replaceChildren(); result.hidden = true; updateControls();
      return operation;
    }
    async function finishOperation(operation) {
      if (operation.cancelPromise) await operation.cancelPromise;
      if (active === operation) active = null;
      updateControls();
      await refreshState(true, true);
    }
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (send.disabled || active) return;
      const question = draft.value.trim();
      const originalDraft = draft.value;
      const operation = newOperation('ask');
      const entry = {id: `local-${Date.now()}-${++localCounter}`, node_id: nodeId, question, answer: '', status: 'streaming'};
      entries.push(entry); renderEntries(true); setStatus('正在回答…');
      try {
        await stream('/ask', {question, node_id: entry.node_id}, operation, event => {
          if (operation.complete) throw new Error('完成结果之后出现多余数据');
          if (event.type === 'start') {
            if (typeof event.id !== 'string' || !event.id) throw new Error('回答标识格式错误');
            entry.id = event.id;
          } else if (event.type === 'status') {
            if (typeof event.message !== 'string') throw new Error('进度数据格式错误');
            setStatus(redactText(event.message).slice(0, 240));
            return;
          } else if (event.type === 'delta') {
            if (typeof event.text !== 'string') throw new Error('回答数据格式错误');
            entry.answer += event.text;
          } else if (event.type === 'done') {
            const final = normalizeEntries([event.entry])[0];
            if (!final || final.status !== 'complete' || final.question !== question || final.node_id !== entry.node_id) throw new Error('完成结果格式错误');
            Object.assign(entry, final); operation.complete = true;
          } else { throw new Error('未知回答事件'); }
          renderEntries();
        });
        if (draft.value === originalDraft) draft.value = '';
        setStatus('回答已保存');
      } catch (error) {
        selected.delete(entry.id);
        entry.status = operation.cancelling ? 'cancelled' : 'error';
        setStatus(operation.cancelling ? '已停止；草稿已保留' : '回答失败：' + safeMessage(error), !operation.cancelling);
        renderEntries();
      } finally { await finishOperation(operation); }
    });
    function safeMessage(error) {
      return redactText(String(error?.message || '请求中断')).slice(0, 240);
    }
    cancel.addEventListener('click', async () => {
      if (!live || active?.cancelling) return;
      const operation = active;
      if (operation) { operation.cancelling = true; operation.controller.abort(); }
      cancel.disabled = true; setStatus('正在停止…');
      const cancellation = (async () => {
        try { await (await request('/cancel', {})).json(); externalBusy = false; }
        catch (error) { externalBusy = true; setStatus('停止请求失败；正在检查任务状态', true); schedulePoll(); }
      })();
      if (operation) operation.cancelPromise = cancellation;
      await cancellation;
      if (!operation) { setStatus(externalBusy ? '任务状态待确认' : '已发送停止请求'); updateControls(); }
    });
    function safeResultUrl(value) {
      if (typeof value !== 'string' || !value || value.startsWith('//') || /[\\\u0000-\u0020]/.test(value)) throw new Error('新版本链接无效');
      const url = new URL(value, location.href);
      if (url.origin !== location.origin || !/^\/versions\/[^/]+\/handbook\.html$/.test(url.pathname) || url.search || url.hash || url.username || url.password) throw new Error('新版本链接无效');
      return url.href;
    }
    compile.addEventListener('click', async () => {
      if (compile.disabled || active) return;
      const ids = [...selected];
      const operation = newOperation('compile'); setStatus(`正在编入 ${ids.length} 条回答…`);
      try {
        let finalUrl;
        await stream('/compile', {entry_ids: ids, redact: true}, operation, event => {
          if (operation.complete) throw new Error('新版本完成后出现多余数据');
          if (event.type === 'compiled') { finalUrl = safeResultUrl(event.url); operation.complete = true; }
          else if (event.type === 'status' || event.type === 'delta') setStatus(redactText(String(event.message || event.text || '正在生成新版本…')).slice(-240));
          else if (event.type !== 'start') throw new Error('未知新版本事件');
        });
        const link = element('a', '', '打开新版本'); link.href = finalUrl; link.target = '_blank'; link.rel = 'noopener noreferrer';
        result.append(link); result.hidden = false; setStatus('新版本已生成；原版本未改动');
      } catch (error) { setStatus(operation.cancelling ? '已停止生成；原版本未改动' : '生成失败：' + safeMessage(error), !operation.cancelling); }
      finally { await finishOperation(operation); }
    });

    function redactText(value) {
      let text = String(value ?? '');
      if (runtime?.token) text = text.split(runtime.token).join('[已隐藏]');
      return text
        .replace(/-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----[\s\S]*?(?:-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----|$)/g, '[已隐藏]')
        .replace(/(?<![\w-])["']?(?:[a-z0-9]+[_-])*(?:(?:api|secret|private)[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|session[_-]?(?:id|key)|cookie|password|passwd|pwd|secret|token|authorization|credential)["']?(?:\s*[:=]\s*|\s+is\s+)(?:(?:bearer|basic)\s+)?(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;<>]+)/gi, '[已隐藏]')
        .replace(/\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+/gi, '[已隐藏]')
        .replace(/\b(?:sk-[A-Za-z0-9_-]{8,}|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{8,}|xox[baprs]-[A-Za-z0-9-]{8,}|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b/g, '[已隐藏]')
        .replace(/(?:\b[a-z][a-z0-9+.-]*:\/\/|(?<![\w:/])\/\/)[^\s<>"']+/gi, '[链接已隐藏]')
        .replace(/(?<![\w/<])(?:[A-Za-z]:[\\/]|\\\\|~[/\\]|\/(?![/\s<>]))[^\r\n<>"'|,;，。；）)\]}]*/g, '[路径已隐藏]');
    }
    function pick(value, fields) {
      const result = {};
      for (const key of fields) {
        if (typeof value?.[key] === 'string') result[key] = redactText(value[key]);
        else if (typeof value?.[key] === 'number' && Number.isFinite(value[key])) result[key] = value[key];
      }
      return result;
    }
    function shareData() {
      const value = pick(book, ['title', 'summary', 'common']);
      const cleanNode = node => pick(node, ['id', 'row', 'col', 'title', 'lines', 'detail', 'kind', 'source']);
      const cleanEdge = edge => pick(edge, ['a', 'b', 'label', 'route']);
      value.sources = (book.sources || []).map(item => ({...pick(item, ['id', 'locator']), excerpt: ''}));
      value.graphs = (book.graphs || []).map(graph => ({...pick(graph, ['id', 'title', 'source', 'summary', 'note']), ...(graph.position ? {position: pick(graph.position, ['row', 'col'])} : {}), nodes: (graph.nodes || []).map(cleanNode), edges: (graph.edges || []).map(cleanEdge)}));
      value.connections = (book.connections || []).map(cleanEdge);
      value.examples = (book.examples || []).map(example => ({...pick(example, ['title', 'provenance', 'input', 'result']), trace: (example.trace || []).map(redactText)}));
      value.canvas = {nodes: authoredNodes.map(cleanNode), edges: (book.canvas?.edges || []).map(cleanEdge)};
      value.qa = entries.filter(entry => entry.status === 'complete' && selected.has(entry.id)).map(entry => ({...pick(entry, ['id', 'question', 'answer']), node_id: entry.node_id || null}));
      return value;
    }
    function sanitizeDom(root) {
      const owner = root.ownerDocument || root;
      const walker = owner.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let text;
      while ((text = walker.nextNode())) {
        if (!text.parentElement?.closest('script,style')) text.textContent = redactText(text.textContent);
      }
      for (const node of root.querySelectorAll('*')) {
        for (const attribute of [...node.attributes]) {
          if (/^on/i.test(attribute.name) || attribute.name === 'srcdoc') { node.removeAttribute(attribute.name); continue; }
          if (['src', 'srcset', 'poster'].includes(attribute.name) && !attribute.value.startsWith('data:')) { node.removeAttribute(attribute.name); continue; }
          if (attribute.name === 'href' && !/^(#|data:)/.test(attribute.value)) { node.removeAttribute(attribute.name); continue; }
          if (attribute.name.startsWith('data-')) node.removeAttribute(attribute.name);
          else if (['title', 'alt', 'placeholder', 'value', 'aria-label'].includes(attribute.name)) node.setAttribute(attribute.name, redactText(attribute.value));
        }
      }
    }
    function offlineHtml() {
      // Clone the authored document, not the current conversation or generated canvas.
      const clone = document.documentElement.cloneNode(true);
      clone.querySelectorAll('[data-flow-qa-ui],.flow-qa-panel').forEach(node => node.remove());
      const clonedShell = clone.querySelector('.flow-qa-shell');
      if (clonedShell) clonedShell.replaceWith(clonedShell.querySelector('#viewport'));
      clone.querySelectorAll('script[src],iframe,object,embed,link[rel=preload],link[rel=stylesheet],base').forEach(node => node.remove());
      clone.querySelector('#nodes')?.replaceChildren(); clone.querySelector('#edges')?.replaceChildren();
      const closedDialog = clone.querySelector('#detail');
      if (closedDialog) closedDialog.removeAttribute('open');
      for (const id of ['detail-title', 'detail-formula', 'detail-text', 'source']) clone.querySelector('#' + id)?.replaceChildren();
      clone.querySelectorAll('textarea,input').forEach(node => { node.removeAttribute('value'); node.removeAttribute('checked'); if (node.tagName === 'TEXTAREA') node.textContent = ''; });
      const dataElement = clone.querySelector('#data');
      dataElement.textContent = JSON.stringify(shareData()).replace(/</g, '\\u003c');
      sanitizeDom(clone);
      return '<!doctype html>\n' + clone.outerHTML;
    }
    function saveBlob(blob, filename) {
      const url = URL.createObjectURL(blob);
      const anchor = element('a'); anchor.href = url; anchor.download = filename; anchor.hidden = true;
      document.body.append(anchor); anchor.click(); anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    }
    async function exportHtml() {
      if (exporting) return;
      openPanel(); exporting = true; updateControls(); setStatus('正在导出离线副本…');
      try {
        let html, fallback = false, filename = 'handbook-offline.html';
        if (live) {
          try {
            const result = await (await request('/export', {entry_ids: [...selected], redact: true}, AbortSignal.timeout(10000))).json();
            if (typeof result.html !== 'string' || !result.html) throw new Error('导出文件为空');
            html = result.html;
            if (typeof result.filename === 'string') filename = result.filename.replace(/[^\p{L}\p{N}._-]/gu, '_').slice(0, 120);
          } catch (_) { html = offlineHtml(); fallback = true; }
        } else html = offlineHtml();
        if (!filename.endsWith('.html')) filename += '.html';
        saveBlob(new Blob([html], {type: 'text/html;charset=utf-8'}), filename);
        setStatus(`${fallback ? '连接不可用，已从本页' : '已'}导出 ${selected.size} 条回答；敏感信息已隐藏`);
      } catch (error) { setStatus('导出失败：' + safeMessage(error), true); }
      finally { exporting = false; updateControls(); }
    }
    share.addEventListener('click', () => { openPanel(share); exportHtml(); });
    exportButton.addEventListener('click', exportHtml);
    async function exportPng(whole) {
      if (exporting) return;
      exporting = true; updateControls();
      try {
        if (typeof window.html2canvas !== 'function') throw new Error('此副本未包含图片组件，请导出离线 HTML');
        await document.fonts.ready;
        const canvasElement = document.getElementById('canvas');
        const width = Math.ceil(whole ? canvasElement.offsetWidth : viewportElement.clientWidth);
        const height = Math.ceil(whole ? canvasElement.offsetHeight : viewportElement.clientHeight);
        const scale = Math.min(2, window.devicePixelRatio || 1);
        if (!width || !height || width * scale > 16384 || height * scale > 16384 || width * height * scale * scale > 32 * 1024 * 1024) throw new Error('图片尺寸过大；请导出当前视图或离线 HTML');
        const target = whole ? canvasElement : viewportElement;
        const scrollLeft = viewportElement.scrollLeft, scrollTop = viewportElement.scrollTop;
        const nodeSizes = new Map([...canvasElement.querySelectorAll('.node')].map(node => {
          const style = getComputedStyle(node);
          return [node.id, {width: style.width, height: style.height}];
        }));
        setStatus('正在生成图片…');
        const image = await window.html2canvas(target, {
          width, height, scale, backgroundColor: '#ffffff', useCORS: false, allowTaint: false, logging: false,
          imageTimeout: 1500,
          ignoreElements: node => ['IFRAME', 'OBJECT', 'EMBED'].includes(node.tagName) || !!node.closest?.('.flow-qa-panel'),
          onclone: clonedDocument => {
            const canvas = clonedDocument.getElementById('canvas'), stage = clonedDocument.getElementById('stage'), view = clonedDocument.getElementById('viewport');
            // Redacted text may be shorter; preserve authored boxes and connector geometry.
            for (const node of canvas.querySelectorAll('.node')) {
              const size = nodeSizes.get(node.id);
              if (size) Object.assign(node.style, {width: size.width, height: size.height, minHeight: size.height, maxHeight: size.height, overflow: 'hidden'});
            }
            sanitizeDom(canvas);
            if (whole) {
              // Only the cloned wrappers are expanded. Node geometry and edge routes stay intact.
              canvas.style.transform = 'none'; canvas.style.position = 'relative'; canvas.style.left = '0'; canvas.style.top = '0';
              canvas.style.width = width + 'px'; canvas.style.height = height + 'px';
              for (const parent of [stage, view]) { parent.style.width = width + 'px'; parent.style.height = height + 'px'; parent.style.overflow = 'visible'; parent.style.maxHeight = 'none'; parent.style.maxWidth = 'none'; }
              view.scrollLeft = 0; view.scrollTop = 0;
            } else {
              view.scrollLeft = scrollLeft; view.scrollTop = scrollTop;
              view.style.width = width + 'px'; view.style.height = height + 'px';
              view.style.minHeight = '0'; view.style.overflow = 'hidden';
            }
          }
        });
        const blob = await new Promise(resolve => image.toBlob(resolve, 'image/png'));
        if (!blob) throw new Error('浏览器未能生成图片，请缩小视图');
        saveBlob(blob, whole ? 'handbook-full.png' : 'handbook-view.png'); setStatus('图片已导出；敏感路径已隐藏');
      } catch (error) { openPanel(); setStatus('图片导出失败：' + safeMessage(error), true); }
      finally { exporting = false; updateControls(); }
    }
    pngFull.addEventListener('click', () => exportPng(true));
    pngView.addEventListener('click', () => exportPng(false));
    renderEntries();
    setStatus(live ? '正在检查本地问答…' : '离线副本；可阅读与导出已有问答');
    if (live) refreshState();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, {once: true});
  else initialize();
})();
