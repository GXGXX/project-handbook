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


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
HEADING_RE = re.compile(r"<(?P<tag>h2|h3)(?P<attrs>\s[^>]*)?>(?P<body>[\s\S]*?)</(?P=tag)>", re.I)
MERMAID_RE = re.compile(r"<(?:div|pre)\b[^>]*\bclass=[\"'][^\"']*\bmermaid\b[^\"']*[\"'][^>]*>", re.I)
UNSAFE_RE = re.compile(r"<\s*script\b|\bon[a-z]+\s*=|javascript\s*:", re.I)


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


def sidebar(page: dict[str, Any], pages: list[dict[str, Any]], book: dict[str, Any]) -> str:
    current = page["url"]
    chunks = [f'<a class="brand" href="{e(relative_url(current, "index.html"))}"><strong>{e(book["title"])}</strong><small>{e(book.get("subtitle", ""))}</small></a>']
    for part_label in dict.fromkeys(item["part_label"] for item in pages):
        chunks.append(f'<section class="nav-group"><h2>{e(part_label)}</h2>')
        for item in pages:
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
    index = page["number"]
    links: list[str] = []
    for direction, offset, label in (("prev", -1, "上一篇"), ("next", 1, "下一篇")):
        target_index = index + offset
        if target_index < 0 or target_index >= len(pages):
            links.append('<span class="pager-empty"></span>')
            continue
        target = pages[target_index]
        href = relative_url(page["url"], target["url"])
        links.append(f'<a class="{direction}" href="{e(href)}"><small>{label}</small><span>{e(target["title"])}</span></a>')
    return "<nav class=\"pager\">" + "".join(links) + "</nav>"


def shell(page: dict[str, Any], fragment: str, headings: list[dict[str, Any]], pages: list[dict[str, Any]], book: dict[str, Any], search: list[dict[str, Any]]) -> str:
    base = "" if page.get("home") else "../"
    base_json = json.dumps(base).replace("<", "\\u003c")
    search_json = json.dumps(search, ensure_ascii=False).replace("<", "\\u003c")
    head = "" if page.get("home") else f'<header class="page-head"><p class="eyebrow">{e(page["part_label"])}</p><h1>{e(page["title"])}</h1><p class="lead">{e(page["lead"])}</p><p class="meta">阅读约 {e(page.get("time", ""))} 分钟 · 第 {page["number"] + 1} / {len(pages)} 篇</p></header>'
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
<body>
  <aside class="sidebar">{sidebar(page, pages, book)}</aside>
  <main>
    <header class="topbar"><button id="menu" type="button" aria-label="打开导航">☰</button><span class="crumb">{e(page["part_label"])} / {e(page["title"])}</span>{search_button}<button id="theme" type="button" aria-label="切换主题">◐</button></header>
    <div class="content-wrap"><article class="article">{head}{fragment}{pager(page, pages)}</article>{toc(headings)}</div>
  </main>
  <dialog id="search-dialog"><form method="dialog"><input id="search" placeholder="搜索页面与概念" autocomplete="off"><button aria-label="关闭">×</button></form><div id="results"></div></dialog>
  <script>window.HANDBOOK_BASE={base_json};</script>
  <script id="search-data" type="application/json">{search_json}</script>
  <script src="{e(base)}assets/app.js" defer></script>
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
    for asset in ("style.css", "app.js", "mermaid.min.js"):
        source = asset_dir / asset
        if not source.is_file():
            continue
        target = site / "assets" / asset
        target.write_bytes(source.read_bytes())
        generated.append(target.relative_to(site).as_posix())


def build(handbook: Path, draft: bool) -> int:
    book = read_json(handbook / "book.json")
    pages = flatten_pages(book)
    asset_dir, site = handbook / "assets", handbook / "site"
    for asset in ("style.css", "app.js"):
        if not (asset_dir / asset).is_file():
            raise HandbookError(f"missing required local asset assets/{asset}")
    prepared, missing = prepare_pages(handbook, pages, draft)
    site.mkdir(exist_ok=True)
    (site / "pages").mkdir(exist_ok=True)
    (site / "assets").mkdir(exist_ok=True)
    clean_previous(site)
    search = [{"url": page["url"], "title": page["title"], "part": page["part_label"], "lead": page["lead"], "text": plain_text(fragment)} for page, fragment, _, _ in prepared]
    generated: list[str] = []
    for page, fragment, processed, headings in prepared:
        output = site / ("index.html" if page.get("home") else f"pages/{page['slug']}.html")
        output.parent.mkdir(exist_ok=True)
        output.write_text(shell(page, processed, headings, pages, book, search), encoding="utf-8")
        generated.append(output.relative_to(site).as_posix())
    copy_assets(handbook, site, generated)
    search_path = site / "assets" / "search-index.json"
    search_path.write_text(json.dumps(search, ensure_ascii=False, indent=2), encoding="utf-8")
    generated.append(search_path.relative_to(site).as_posix())
    (site / ".generated.json").write_text(json.dumps({"files": generated}, indent=2), encoding="utf-8")
    print(f"built {len(search)} page(s) in {site}")
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
