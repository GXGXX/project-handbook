#!/usr/bin/env python3
"""Verify a built Project Handbook and its evidence manifest."""

from __future__ import annotations

import argparse
import html
import json
import posixpath
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from build_handbook import HandbookError, UNSAFE_RE, flatten_pages, read_json


TAG_RE = re.compile(r"<(?P<tag>script|link|a|img)\b(?P<attrs>[^>]*)>", re.I)
ATTR_RE = re.compile(r"\b(?:href|src)\s*=\s*([\"'])(.*?)\1", re.I)
ID_RE = re.compile(r"\bid\s*=\s*([\"'])([^\"']+)\1", re.I)
HEADING_RE = re.compile(r"<h[23]\b([^>]*)>", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handbook", type=Path)
    return parser.parse_args()


def expected_files(pages: list[dict[str, Any]]) -> dict[str, str]:
    return {("index.html" if page.get("home") else f"pages/{page['slug']}.html"): page["slug"] for page in pages}


def local_target(current: str, url: str) -> str | None:
    parts = urlsplit(url)
    if parts.scheme or parts.netloc:
        return None
    target = parts.path
    if not target:
        return current
    return posixpath.normpath(posixpath.join(posixpath.dirname(current), target))


def visible_text(source: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", source))


def verify_links(source: str, relative: str, expected: dict[str, str], site: Path) -> list[str]:
    errors: list[str] = []
    for tag_match in TAG_RE.finditer(source):
        tag = tag_match.group("tag").lower()
        attr_match = ATTR_RE.search(tag_match.group("attrs"))
        if not attr_match:
            continue
        url = attr_match.group(2)
        if url.startswith("#") or url.startswith(("mailto:", "tel:")):
            continue
        parsed = urlsplit(url)
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            errors.append(f"unsupported URL scheme in {relative}: {url}")
            continue
        if parsed.scheme in ("http", "https"):
            if tag in ("script", "link", "img"):
                errors.append(f"remote asset in {relative}: {url}")
            continue
        target = local_target(relative, url)
        if target in expected:
            continue
        if target and target.startswith("assets/") and (site / target).is_file():
            continue
        if target and target.startswith("assets/"):
            errors.append(f"missing local asset in {relative}: {url}")
        elif target and target not in expected:
            errors.append(f"broken internal link in {relative}: {url}")
    return errors


def verify_page_file(path: Path, relative: str, expected: dict[str, str], site: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if any(marker in source for marker in ("Draft placeholder", "Missing content/", "[TODO:")):
        errors.append(f"scaffold placeholder remains in {relative}")
    content_only = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", source, flags=re.I)
    if UNSAFE_RE.search(content_only):
        errors.append(f"unsafe script or inline handler in {relative}")
    ids = [match.group(2) for match in ID_RE.finditer(source)]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"duplicate HTML id(s) in {relative}: {', '.join(duplicates)}")
    article_match = re.search(r'<article class="article">([\s\S]*?)</article>', source, re.I)
    article = article_match.group(1) if article_match else source
    for heading in HEADING_RE.finditer(article):
        if not re.search(r"\bid\s*=", heading.group(1), re.I):
            errors.append(f"heading without id in {relative}")
            break
    errors.extend(verify_links(source, relative, expected, site))
    return errors


def verify_pages(handbook: Path, pages: list[dict[str, Any]]) -> list[str]:
    site = handbook / "site"
    expected = expected_files(pages)
    errors: list[str] = []
    for relative in expected:
        path = site / relative
        if not path.is_file():
            errors.append(f"missing generated page {relative}")
            continue
        errors.extend(verify_page_file(path, relative, expected, site))
    extra = [item.relative_to(site).as_posix() for item in (site / "pages").glob("*.html") if item.is_file() and f"pages/{item.name}" not in expected]
    errors.extend(f"stale generated page {name}" for name in extra)
    return errors


def verify_assets(handbook: Path) -> list[str]:
    site_assets = handbook / "site" / "assets"
    errors: list[str] = []
    for name in ("style.css", "app.js", "search-index.json"):
        if not (site_assets / name).is_file():
            errors.append(f"missing generated asset site/assets/{name}")
    index_path = site_assets / "search-index.json"
    if index_path.is_file():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(index, list):
                errors.append("search-index.json must contain an array")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid search-index.json: {exc}")
    return errors


def verify_facts(handbook: Path, pages: list[dict[str, Any]]) -> list[str]:
    facts_path = handbook / "evidence" / "facts.json"
    if not facts_path.is_file():
        return []
    try:
        data = read_json(facts_path)
    except HandbookError as exc:
        return [str(exc)]
    facts = data.get("facts", [])
    if not isinstance(facts, list):
        return ["evidence/facts.json facts must be an array"]
    known = {page["slug"] for page in pages}
    errors: list[str] = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict) or not fact.get("value") or not fact.get("page"):
            errors.append(f"fact {index} requires value and page")
            continue
        page = str(fact["page"])
        if page not in known:
            errors.append(f"fact {index} references unknown page {page!r}")
            continue
        output = handbook / "site" / ("index.html" if page == "index" else f"pages/{page}.html")
        if output.is_file() and str(fact["value"]) not in visible_text(output.read_text(encoding="utf-8")):
            errors.append(f"fact {fact.get('id', index)!r} value is absent from page {page}")
    return errors


def verify(handbook: Path) -> int:
    try:
        pages = flatten_pages(read_json(handbook / "book.json"))
    except HandbookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    errors = verify_pages(handbook, pages) + verify_assets(handbook) + verify_facts(handbook, pages)
    if errors:
        print(f"verification failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"verified {len(pages)} page(s), local assets, links, IDs, and evidence")
    return 0


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(verify(args.handbook.resolve()))
