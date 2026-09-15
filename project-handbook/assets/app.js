(function () {
  "use strict";
  var root = document.documentElement;
  var get = function (key) { try { return localStorage.getItem(key); } catch (error) { console.warn("theme preference unavailable", error); return null; } };
  var set = function (key, value) { try { localStorage.setItem(key, value); } catch (error) { console.warn("theme preference was not saved", error); return false; } return true; };
  var saved = get("project-handbook-theme");
  if (saved) root.dataset.theme = saved;
  document.getElementById("theme").addEventListener("click", function () {
    var theme = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = theme; set("project-handbook-theme", theme);
  });
  var sidebar = document.querySelector(".sidebar");
  var menu = document.getElementById("menu");
  var setSidebarState = function (open) {
    sidebar.classList.toggle("open", open);
    menu.setAttribute("aria-expanded", open ? "true" : "false");
    menu.setAttribute("aria-label", open ? "关闭导航" : "打开导航");
  };
  var closeSidebar = function () {
    setSidebarState(false);
  };
  menu.addEventListener("click", function () {
    setSidebarState(!sidebar.classList.contains("open"));
  });
  var closeButton = document.getElementById("sidebar-close");
  if (closeButton) closeButton.addEventListener("click", closeSidebar);
  sidebar.querySelectorAll("a").forEach(function (link) { link.addEventListener("click", closeSidebar); });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeSidebar();
  });
  var dialog = document.getElementById("search-dialog");
  var input = document.getElementById("search");
  var results = document.getElementById("results");
  var base = window.HANDBOOK_BASE || "";
  var data = document.getElementById("search-data");
  var index = data ? JSON.parse(data.textContent || "[]") : [];
  var esc = function (value) { return String(value).replace(/[&<>\"]/g, function (ch) { return { "&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;" }[ch]; }); };
  function show(items) {
    results.innerHTML = items.map(function (item) {
      return '<a href="' + base + esc(item.url) + '"><strong>' + esc(item.title) + '</strong><br><small>' + esc(item.lead) + '</small></a>';
    }).join("") || "<p>没有匹配内容。</p>";
  }
  document.getElementById("search-open").addEventListener("click", function () {
    dialog.showModal(); input.value = ""; show([]); input.focus();
  });
  input.addEventListener("input", function () {
    var query = input.value.trim().toLowerCase();
    show(index.filter(function (item) { return !query || (item.title + item.lead + item.text).toLowerCase().indexOf(query) >= 0; }).slice(0, 20));
  });
  document.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); document.getElementById("search-open").click(); }
  });
}());
