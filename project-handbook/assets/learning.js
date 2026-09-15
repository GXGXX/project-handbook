(function () {
  'use strict';
  var steps = Array.from(document.querySelectorAll('[data-step]'));
  var nodes = Array.from(document.querySelectorAll('[data-node]'));
  var cursor = -1;
  var previous = document.getElementById('guide-prev');
  var next = document.getElementById('guide-next');
  var progress = document.getElementById('guide-progress');
  function select(index, scroll) {
    cursor = index < 0 ? -1 : Math.min(index, steps.length - 1);
    steps.forEach(function (step, i) { step.classList.toggle('active', i === cursor); });
    nodes.forEach(function (node) { node.classList.toggle('active', cursor >= 0 && node.dataset.node === steps[cursor].dataset.ownerNode); });
    previous.disabled = cursor <= 0;
    next.disabled = cursor === steps.length - 1;
    progress.textContent = cursor < 0 ? '完整流程' : (cursor + 1) + ' / ' + steps.length;
    if (scroll && cursor >= 0) steps[cursor].scrollIntoView({block: 'start'});
  }
  document.getElementById('guide-start').addEventListener('click', function () { select(0, true); });
  previous.addEventListener('click', function () { select(Math.max(0, cursor - 1), true); });
  next.addEventListener('click', function () { select(cursor + 1, true); });
  document.getElementById('guide-reset').addEventListener('click', function () { select(-1, false); });
  select(-1, false);
  function reveal(id) {
    var target = document.getElementById(id);
    if (!target) return;
    var parent = target;
    while (parent) {
      if (parent.tagName === 'DETAILS') parent.open = true;
      parent = parent.parentElement;
    }
    var index = steps.indexOf(target);
    if (index >= 0) select(index, false);
  }
  var evidenceOrigin = null;
  document.addEventListener('click', function (event) {
    var back = event.target.closest('[data-evidence-back]');
    if (back && evidenceOrigin) {
      evidenceOrigin.focus();
      evidenceOrigin.scrollIntoView({block: 'center'});
      return;
    }
    var link = event.target.closest('a[href^="#"]');
    if (!link) return;
    var id = link.getAttribute('href').slice(1);
    if (id.indexOf('evidence-') === 0) evidenceOrigin = link;
    reveal(id);
  });
  function fromHash() {
    try { reveal(decodeURIComponent(window.location.hash.slice(1))); } catch (_) {}
  }
  window.addEventListener('hashchange', fromHash);
  fromHash();
  var search = document.getElementById('learning-search');
  var results = document.getElementById('search-results');
  var searchStatus = document.getElementById('search-status');
  var candidates = Array.from(document.querySelectorAll('.walk-step,.component,.example,.term,.action,.evidence'));
  candidates.forEach(function (item, i) { if (!item.id) item.id = 'search-item-' + i; });
  search.addEventListener('input', function () {
    results.textContent = '';
    var query = search.value.trim().toLocaleLowerCase();
    results.hidden = !query;
    if (!query) { searchStatus.textContent = ''; return; }
    var matches = candidates.filter(function (item) { return item.textContent.toLocaleLowerCase().indexOf(query) >= 0; });
    searchStatus.textContent = matches.length ? matches.length + ' 处匹配' : '没有匹配的内容';
    matches.slice(0, 30).forEach(function (item) {
      var li = document.createElement('li');
      var link = document.createElement('a');
      link.href = '#' + item.id;
      var heading = item.querySelector('h3,summary');
      link.textContent = heading ? heading.textContent : item.textContent.slice(0, 80);
      li.appendChild(link);
      results.appendChild(li);
    });
  });
  document.getElementById('theme-toggle').addEventListener('click', function () {
    var root = document.documentElement;
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
  });
}());
