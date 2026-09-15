#!/usr/bin/env python3
"""Compile a Project Handbook into a self-contained static site."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
HEADING_RE = re.compile(r"<(?P<tag>h2|h3)(?P<attrs>\s[^>]*)?>(?P<body>[\s\S]*?)</(?P=tag)>", re.I)
MERMAID_RE = re.compile(r"<(?:div|pre)\b[^>]*\bclass=[\"'][^\"']*\bmermaid\b[^\"']*[\"'][^>]*>", re.I)
UNSAFE_RE = re.compile(r"<\s*script\b|\bon[a-z]+\s*=|javascript\s*:", re.I)
SECRET_KEY_RE = re.compile(r"(?:api[_-]?key|access[_-]?token|secret|password)", re.I)


class HandbookError(Exception):
    """A user-fixable handbook input error."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handbook", type=Path)
    parser.add_argument("--draft", action="store_true", help="allow missing fragments for a labelled preview")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HandbookError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HandbookError(f"{path} must contain a JSON object")
    return value


def flatten_pages(book: dict[str, Any]) -> list[dict[str, Any]]:
    parts = book.get("parts")
    if not isinstance(parts, list) or not parts:
        raise HandbookError("book.json requires a non-empty parts array")
    pages: list[dict[str, Any]] = []
    seen: set[str] = set()
    home_count = 0
    for part_index, part in enumerate(parts):
        if not isinstance(part, dict) or not part.get("label"):
            raise HandbookError(f"parts[{part_index}] requires a label")
        part_pages = part.get("pages")
        if not isinstance(part_pages, list) or not part_pages:
            raise HandbookError(f"part {part.get('label', part_index)!r} requires pages")
        for page_index, page in enumerate(part_pages):
            if not isinstance(page, dict):
                raise HandbookError(f"parts[{part_index}].pages[{page_index}] must be an object")
            slug = page.get("slug")
            if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug) or (slug == "index" and not page.get("home")):
                raise HandbookError(f"invalid or reserved page slug {slug!r}")
            if slug in seen:
                raise HandbookError(f"duplicate page slug {slug!r}")
            for field in ("title", "lead"):
                if not isinstance(page.get(field), str) or not page[field].strip():
                    raise HandbookError(f"page {slug!r} requires non-empty {field}")
            page_home = bool(page.get("home"))
            home_count += int(page_home)
            seen.add(slug)
            pages.append({**page, "part_label": str(part["label"]), "part_icon": str(part.get("icon", "")), "_source_order": len(pages)})
    if home_count != 1:
        raise HandbookError(f"book.json requires exactly one home page; found {home_count}")
    pages.sort(key=lambda item: (item.get("order", item["_source_order"]), item["_source_order"]))
    for index, page in enumerate(pages):
        page["number"] = index
        page["url"] = "index.html" if page.get("home") else f"pages/{page['slug']}.html"
    return pages


def slugify_heading(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean).strip().lower()
    clean = re.sub(r"[^\w-]+", "-", clean, flags=re.UNICODE).strip("-")
    return clean or "section"


def process_headings(fragment: str) -> tuple[str, list[dict[str, Any]]]:
    headings: list[dict[str, Any]] = []
    used: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        tag = match.group("tag").lower()
        attrs = match.group("attrs") or ""
        body = match.group("body")
        explicit = re.search(r"\bid\s*=\s*([\"'])([^\"']+)\1", attrs)
        base = explicit.group(2) if explicit else slugify_heading(body)
        if explicit and not re.fullmatch(r"[A-Za-z][\w:.-]*", base):
            raise HandbookError(f"invalid heading id {base!r}")
        if explicit and base in used:
            raise HandbookError(f"duplicate explicit heading id {base!r}")
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        if not explicit:
            attrs += f' id="{html.escape(candidate, quote=True)}"'
        used.add(candidate)
        text = re.sub(r"<[^>]+>", "", body).strip()
        headings.append({"level": int(tag[1]), "id": candidate, "text": html.unescape(text)})
        anchor = f'<a class="anchor" href="#{html.escape(candidate, quote=True)}" aria-label="Link to section"></a>'
        return f"<{tag}{attrs}>{anchor}{body}</{tag}>"

    return HEADING_RE.sub(replace, fragment), headings


def plain_text(fragment: str) -> str:
    without_code = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", fragment, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", without_code)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def relative_url(from_url: str, to_url: str) -> str:
    from_parts = Path(from_url).parent.parts
    prefix = "../" * len(from_parts)
    return f"{prefix}{to_url}" if prefix else to_url


def e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def chat_config(book: dict[str, Any]) -> dict[str, Any]:
    """Validate the public, non-secret configuration embedded in each page."""
    raw = book.get("chat", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise HandbookError("book.json chat must be an object")
    secret_keys: list[str] = []

    def find_secret_keys(value: Any, path: str = "chat") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if SECRET_KEY_RE.search(str(key)):
                    secret_keys.append(child_path)
                else:
                    find_secret_keys(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                find_secret_keys(child, f"{path}[{index}]")

    find_secret_keys(raw)
    secret_keys = sorted(secret_keys)
    if secret_keys:
        raise HandbookError(
            "book.json chat cannot contain secrets; use the relay environment instead: "
            + ", ".join(secret_keys)
        )
    mode = raw.get("mode", "relay")
    if mode not in ("relay", "direct"):
        raise HandbookError("book.json chat.mode must be relay or direct")
    endpoint = raw.get("endpoint", "/api/chat" if mode == "relay" else "")
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise HandbookError("book.json chat.endpoint must be a non-empty string")
    parsed = urlsplit(endpoint)
    if parsed.scheme not in ("", "http", "https") or endpoint.startswith("//") or endpoint.lower().startswith("javascript:"):
        raise HandbookError("book.json chat.endpoint must be a relative, http, or https URL")
    model = raw.get("model", "")
    if not isinstance(model, str) or len(model) > 160:
        raise HandbookError("book.json chat.model must be a string of at most 160 characters")
    try:
        context_chars = int(raw.get("context_chars", 16000))
    except (TypeError, ValueError) as exc:
        raise HandbookError("book.json chat.context_chars must be an integer") from exc
    if not 1000 <= context_chars <= 100000:
        raise HandbookError("book.json chat.context_chars must be between 1000 and 100000")
    try:
        max_history = int(raw.get("max_history", 8))
    except (TypeError, ValueError) as exc:
        raise HandbookError("book.json chat.max_history must be an integer") from exc
    if not 0 <= max_history <= 20:
        raise HandbookError("book.json chat.max_history must be between 0 and 20")
    return {
        "enabled": bool(raw.get("enabled", True)),
        "mode": mode,
        "endpoint": endpoint.strip(),
        "model": model.strip(),
        "context_chars": context_chars,
        "max_history": max_history,
        "title": str(raw.get("title", "手册问答"))[:80],
        "placeholder": str(raw.get("placeholder", "输入问题，答案将附带来源…"))[:160],
    }


def visible_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in pages if not str(item.get("slug", "")).startswith("source-")]


def sidebar(page: dict[str, Any], pages: list[dict[str, Any]], book: dict[str, Any]) -> str:
    current = page["url"]
    nav = visible_pages(pages)
    chunks = [f'<a class="brand" href="{e(relative_url(current, "index.html"))}"><strong>{e(book["title"])}</strong><small>{e(book.get("subtitle", ""))}</small></a>', '<button class="sidebar-close" id="sidebar-close" type="button" aria-label="关闭导航" title="关闭导航">×</button>']
    for part_label in dict.fromkeys(item["part_label"] for item in nav):
        chunks.append(f'<section class="nav-group"><h2>{e(part_label)}</h2>')
        for item in nav:
            if item["part_label"] != part_label:
                continue
            href = relative_url(current, item["url"])
            active = " aria-current=\"page\"" if item["url"] == current else ""
            chunks.append(f'<a href="{e(href)}"{active}>{e(item["title"])}</a>')
        chunks.append("</section>")
    return "".join(chunks)


def toc(headings: list[dict[str, Any]]) -> str:
    if len(headings) < 2:
        return ""
    links = "".join(f'<li class="h{item["level"]}"><a href="#{e(item["id"])}">{e(item["text"])}</a></li>' for item in headings)
    return f'<aside class="toc"><p>本页目录</p><ol>{links}</ol></aside>'


def pager(page: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    nav = visible_pages(pages)
    try:
        index = nav.index(page)
    except ValueError:
        return "<nav class=\"pager\"><span class=\"pager-empty\"></span><span class=\"pager-empty\"></span></nav>"
    links: list[str] = []
    for direction, offset, label in (("prev", -1, "上一篇"), ("next", 1, "下一篇")):
        target_index = index + offset
        if target_index < 0 or target_index >= len(nav):
            links.append('<span class="pager-empty"></span>')
            continue
        target = nav[target_index]
        href = relative_url(page["url"], target["url"])
        links.append(f'<a class="{direction}" href="{e(href)}"><small>{label}</small><span>{e(target["title"])}</span></a>')
    return "<nav class=\"pager\">" + "".join(links) + "</nav>"


def chat_panel(chat: dict[str, Any]) -> str:
    if not chat["enabled"]:
        return ""
    return f'''<aside id="chat-panel" class="chat-panel" aria-label="{e(chat["title"])}">
  <header class="chat-header">
    <div><strong>{e(chat["title"])}</strong><small id="chat-status">等待连接</small></div>
    <button id="chat-clear" type="button" title="清空对话">清空</button>
  </header>
  <div id="chat-messages" class="chat-messages" role="log" aria-live="polite">
    <div class="chat-welcome"><strong>基于本项目手册提问</strong><p>我会优先引用当前整理出的代码与文档证据；证据不足时会明确说明。</p></div>
  </div>
  <details id="chat-settings" class="chat-settings">
    <summary>连接设置</summary>
    <label>回答方式<select id="chat-answer-mode"><option value="evidence">本地证据检索（不调用模型）</option><option value="model">模型问答（需配置接口）</option></select></label>
    <input id="chat-mode" type="hidden" value="relay">
    <label>接口地址<input id="chat-endpoint" type="url" spellcheck="false" placeholder="请输入完整接口地址，例如 https://你的域名/v1" value=""></label>
    <label id="chat-key-wrap">API Key（仅当前页面内存）<input id="chat-api-key" type="password" autocomplete="off"></label>
    <div class="chat-model-row">
      <label>模型<select id="chat-model"><option value="">先获取模型列表</option></select></label>
      <button id="chat-fetch-models" type="button">获取模型</button>
    </div>
    <p id="chat-fetch-note" class="chat-fetch-note" hidden></p>
    <p class="chat-security">填写接口地址和 API Key，点击获取模型后再提问。密钥只留在当前页面内存，不会写入 HTML、浏览器存储或 Git。双击 HTML 时浏览器会拦截外部模型接口，请用启动器打开 localhost。选择模型问答并发送后，会把当前问题与检索到的手册摘录发给所填接口。</p>
    <input id="chat-consent" type="checkbox" checked hidden>
  </details>
  <form id="chat-form" class="chat-form">
    <small id="chat-context">上下文：当前页面</small>
    <button id="chat-export" type="button">复制问题与证据到 agent</button>
    <textarea id="chat-input" rows="3" placeholder="{e(chat["placeholder"])}" maxlength="4000"></textarea>
    <div class="chat-form-foot"><small>Ctrl/⌘ + Enter 发送</small><button id="chat-send" type="submit">发送</button></div>
  </form>
</aside>'''


def shell(page: dict[str, Any], fragment: str, headings: list[dict[str, Any]], pages: list[dict[str, Any]], book: dict[str, Any], search: list[dict[str, Any]], chat: dict[str, Any]) -> str:
    base = "" if page.get("home") else "../"
    base_json = json.dumps(base).replace("<", "\\u003c")
    search_json = json.dumps(search, ensure_ascii=False).replace("<", "\\u003c")
    page_chat = dict(chat)
    page_chat['book_id'] = str(book.get('book_id', book['title']))
    page_chat['default_answer_mode'] = 'evidence'
    endpoint = page_chat["endpoint"]
    if not urlsplit(endpoint).scheme and not endpoint.startswith("/"):
        endpoint = relative_url(page["url"], endpoint)
    page_chat["endpoint"] = endpoint
    chat_json = json.dumps({**page_chat, "current_page": page["url"]}, ensure_ascii=False).replace("<", "\\u003c")
    chat_tags = "" if not chat["enabled"] else (
        f'<script id="chat-config" type="application/json">{chat_json}</script>\n'
        f'  <script src="{e(base)}assets/chat.js" defer></script>'
    )
    nav = visible_pages(pages)
    try:
        nav_index = nav.index(page)
        meta = f'阅读约 {e(page.get("time", ""))} 分钟 · 第 {nav_index + 1} / {len(nav)} 篇'
    except ValueError:
        meta = f'阅读约 {e(page.get("time", ""))} 分钟 · 来源证据'
    head = "" if page.get("home") else f'<header class="page-head"><p class="eyebrow">{e(page["part_label"])}</p><h1>{e(page["title"])}</h1><p class="lead">{e(page["lead"])}</p><p class="meta">{meta}</p></header>'
    search_button = '<button id="search-open" type="button">搜索 <kbd>Ctrl/⌘ K</kbd></button>'
    return f'''<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(page["title"])} · {e(book["title"])}</title>
  <meta name="description" content="{e(page["lead"])}">
  <link rel="stylesheet" href="{e(base)}assets/style.css">
</head>
<body class="{'atlas-book' if book.get('atlas') else ''}">
  <aside class="sidebar">{sidebar(page, pages, book)}</aside>
  <main>
    <header class="topbar"><button id="menu" type="button" aria-label="打开导航" aria-expanded="false">☰</button><span class="crumb">{e(page["part_label"])} / {e(page["title"])}</span>{search_button}<button id="theme" type="button" aria-label="切换主题">◐</button></header>
    <div class="content-wrap"><article class="article">{head}{fragment}{pager(page, pages)}</article>{toc(headings)}{chat_panel(page_chat)}</div>
  </main>
  <dialog id="search-dialog"><form method="dialog"><input id="search" placeholder="搜索页面与概念" autocomplete="off"><button aria-label="关闭">×</button></form><div id="results"></div></dialog>
  <script>window.HANDBOOK_BASE={base_json};</script>
  <script id="search-data" type="application/json">{search_json}</script>
  <script src="{e(base)}assets/app.js" defer></script>
  {('<script src="' + e(base) + 'assets/atlas.js" defer></script>') if book.get('atlas') else ''}
  {chat_tags}
</body>
</html>'''


def clean_previous(site: Path) -> None:
    manifest = site / ".generated.json"
    if not manifest.exists():
        return
    try:
        files = json.loads(manifest.read_text(encoding="utf-8")).get("files", [])
    except (OSError, json.JSONDecodeError):
        return
    for name in files:
        target = (site / name).resolve()
        if target.parent == site.resolve() or site.resolve() in target.parents:
            if target.is_file():
                target.unlink()


def prepare_pages(handbook: Path, pages: list[dict[str, Any]], draft: bool) -> tuple[list[tuple[dict[str, Any], str, str, list[dict[str, Any]]]], list[str]]:
    content_dir, asset_dir = handbook / "content", handbook / "assets"
    prepared: list[tuple[dict[str, Any], str, str, list[dict[str, Any]]]] = []
    missing: list[str] = []
    for page in pages:
        fragment_path = content_dir / f"{page['slug']}.html"
        if not fragment_path.is_file():
            missing.append(page["slug"])
            if not draft:
                continue
            fragment = f'<div class="callout warn"><div class="body"><strong>Draft placeholder</strong><p>Missing content/{e(page["slug"])}.html.</p></div></div>'
        else:
            fragment = fragment_path.read_text(encoding="utf-8")
        if UNSAFE_RE.search(fragment):
            raise HandbookError(f"unsafe script, inline handler, or javascript URL in {fragment_path}")
        if MERMAID_RE.search(fragment) and not (asset_dir / "mermaid.min.js").is_file():
            raise HandbookError(f"{fragment_path} uses Mermaid but assets/mermaid.min.js is missing")
        processed, headings = process_headings(fragment)
        prepared.append((page, fragment, processed, headings))
    if missing and not draft:
        raise HandbookError(f"missing content fragments: {', '.join(missing)}")
    return prepared, missing


def copy_assets(handbook: Path, site: Path, generated: list[str]) -> None:
    asset_dir = handbook / "assets"
    for asset in ("style.css", "app.js", "chat.js", "mermaid.min.js", "atlas.js"):
        source = asset_dir / asset
        if not source.is_file():
            continue
        target = site / "assets" / asset
        target.write_bytes(source.read_bytes())
        generated.append(target.relative_to(site).as_posix())


def build(handbook: Path, draft: bool) -> int:
    book = read_json(handbook / "book.json")
    pages = flatten_pages(book)
    chat = chat_config(book)
    asset_dir, site = handbook / "assets", handbook / "site"
    required_assets = ["style.css", "app.js"]
    if chat["enabled"]:
        required_assets.append("chat.js")
    for asset in required_assets:
        if not (asset_dir / asset).is_file():
            raise HandbookError(f"missing required local asset assets/{asset}")
    prepared, missing = prepare_pages(handbook, pages, draft)
    site.mkdir(exist_ok=True)
    (site / "pages").mkdir(exist_ok=True)
    (site / "assets").mkdir(exist_ok=True)
    clean_previous(site)
    search = [{"url": page["url"], "title": page["title"], "part": page["part_label"], "lead": page["lead"], "text": plain_text(fragment)} for page, fragment, _, _ in prepared]
    if book.get('atlas'):
        search = []
        for page, _, processed, headings in prepared:
            matches = list(HEADING_RE.finditer(processed))
            for i, match in enumerate(matches):
                end = matches[i+1].start() if i+1 < len(matches) else len(processed)
                section_html = processed[match.end():end].split('</section>', 1)[0]
                section_html = re.sub(r'<button\b[\s\S]*?</button>|<summary\b[\s\S]*?</summary>|<div class="node-actions"[\s\S]*?</div>', '', section_html, flags=re.I)
                section = plain_text(section_html)
                search.append({'url': page['url']+'#'+headings[i]['id'], 'title': page['title']+' / '+headings[i]['text'], 'part': page['part_label'], 'lead': page['lead'], 'text': section})
    generated: list[str] = []
    for page, fragment, processed, headings in prepared:
        output = site / ("index.html" if page.get("home") else f"pages/{page['slug']}.html")
        output.parent.mkdir(exist_ok=True)
        output.write_text(shell(page, processed, headings, pages, book, search, chat), encoding="utf-8")
        generated.append(output.relative_to(site).as_posix())
    copy_assets(handbook, site, generated)
    search_path = site / "assets" / "search-index.json"
    search_path.write_text(json.dumps(search, ensure_ascii=False, indent=2), encoding="utf-8")
    generated.append(search_path.relative_to(site).as_posix())
    (site / ".generated.json").write_text(json.dumps({"files": generated}, indent=2), encoding="utf-8")
    print(f"built {len(prepared)} page(s), {len(search)} search section(s) in {site}")
    if missing:
        print(f"draft placeholders: {', '.join(missing)}")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return build(args.handbook.resolve(), args.draft)
    except HandbookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
