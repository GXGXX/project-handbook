#!/usr/bin/env python3
"""Create a portable Project Handbook workspace."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="handbook directory to create")
    parser.add_argument(
        "--force", action="store_true", help="replace only files created by this initializer"
    )
    return parser.parse_args()


def copy_template(source: Path, target: Path, force: bool) -> None:
    if target.exists() and not force:
        raise FileExistsError(f"refusing to overwrite {target}; use --force explicitly")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def write_sample_content(output: Path, force: bool) -> None:
    samples = {
        "index.html": """<div class=\"hero\">\n  <p class=\"eyebrow\">PROJECT HANDBOOK</p>\n  <h1>项目手册</h1>\n  <p class=\"tagline\">从代码与文档整理出可核验的离线导览。</p>\n  <p><a class=\"btn primary\" href=\"pages/overview.html\">开始阅读 →</a></p>\n</div>\n""",
        "overview.html": """<h2>这本手册回答什么</h2>\n<p>替换本页内容，说明项目定位、读者和事实来源。</p>\n<div class=\"callout note\"><div class=\"body\"><strong>示例内容</strong><p>这里的文件只是起步模板，交付前应换成项目事实。</p></div></div>\n""",
    }
    for name, content in samples.items():
        target = output / "content" / name
        if target.exists() and not force:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def create_workspace(output: Path, force: bool) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for directory in ("content", "assets", "evidence", "site"):
        (output / directory).mkdir(exist_ok=True)
    copy_template(ASSETS / "book.example.json", output / "book.json", force)
    copy_template(ASSETS / "style.css", output / "assets" / "style.css", force)
    copy_template(ASSETS / "app.js", output / "assets" / "app.js", force)
    write_sample_content(output, force)
    facts = output / "evidence" / "facts.json"
    if not facts.exists() or force:
        facts.write_text("{\n  \"facts\": []\n}\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        create_workspace(args.output.resolve(), args.force)
    except (FileExistsError, OSError) as exc:
        print(f"error: {exc}")
        return 1
    print(f"created handbook workspace: {args.output.resolve()}")
    print("next: edit book.json and content/*.html, then run build_handbook.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
