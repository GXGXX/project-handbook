#!/usr/bin/env python3
"""Import a client source tree and a documentation/config tree into a handbook."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {
    ".bat", ".cfg", ".cpp", ".csv", ".h", ".hpp", ".ini", ".js", ".json", ".lua",
    ".lst", ".log", ".md", ".proto", ".py", ".sql", ".ts", ".tsv", ".txt", ".xml",
    ".xmlp", ".yaml", ".yml",
}
SPREADSHEET_EXTENSIONS = {".csv", ".tsv", ".xls", ".xlsx"}
SKIP_DIRS = {".git", ".svn", ".hg", ".codex_work", "__pycache__", "node_modules"}
SENSITIVE_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|password|secret|authorization)\s*([:=])\s*([^\s,;]+)"
)


class ImportError_(Exception):
    """A user-fixable import error."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True, type=Path, help="client source directory")
    parser.add_argument("--docs", required=True, type=Path, help="documentation/config directory")
    parser.add_argument("--output", required=True, type=Path, help="new handbook directory")
    parser.add_argument("--sample-files", type=int, default=80, help="files shown per source in the handbook")
    parser.add_argument("--max-excerpt-bytes", type=int, default=16000, help="maximum text bytes read per sample")
    parser.add_argument("--force", action="store_true", help="replace a previous generated handbook directory")
    parser.add_argument("--no-build", action="store_true", help="write source material without compiling site/")
    return parser.parse_args()


def scrub(value: str) -> str:
    """Redact common credential-shaped values before they reach generated HTML."""
    return SENSITIVE_RE.sub(lambda match: f"{match.group(1)}{match.group(2)} [REDACTED]", value)


def h(value: Any) -> str:
    return html.escape(str(value), quote=True)


def is_skipped(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return any(part in SKIP_DIRS for part in parts)


def safe_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_text(path: Path, max_bytes: int) -> str:
    try:
        raw = path.read_bytes()[:max_bytes]
    except OSError as exc:
        return f"[读取失败: {exc}]"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gb18030", errors="replace")
    if len(raw) == max_bytes:
        text += "\n…（片段已截断，原文件未复制到手册）"
    return scrub(text)


def xlsx_summary(path: Path) -> str:
    """Read workbook sheet names and dimensions without requiring Excel/openpyxl."""
    try:
        with ZipFile(path) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = ["".join(node.itertext()) for node in root.findall(".//{*}si")]
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            names = [node.get("name", "") for node in workbook.findall(".//{*}sheet")]
            sheet_files = sorted(name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
            dimensions: list[str] = []
            headers: list[str] = []
            for sheet_file in sheet_files[:12]:
                sheet = ET.fromstring(archive.read(sheet_file))
                dimension = sheet.find(".//{*}dimension")
                if dimension is not None and dimension.get("ref"):
                    dimensions.append(dimension.get("ref", ""))
                first_row = sheet.find(".//{*}sheetData/{*}row")
                if first_row is not None and not headers:
                    for cell in first_row.findall("{*}c")[:12]:
                        value = cell.find("{*}v")
                        if value is None or value.text is None:
                            continue
                        text = value.text
                        if cell.get("t") == "s" and text.isdigit() and int(text) < len(shared):
                            text = shared[int(text)]
                        headers.append(scrub(text)[:80])
            sheet_text = "、".join(name for name in names if name) or "未读取到工作表名"
            detail = f"工作表 {len(names)} 个：{sheet_text}"
            if dimensions:
                detail += f"；首个表维度：{dimensions[0]}"
            if headers:
                detail += f"；首行字段：{'、'.join(headers)}"
            return detail
    except (OSError, BadZipFile, ET.ParseError, KeyError) as exc:
        return f"XLSX 元数据读取失败：{exc}"


def file_summary(path: Path, root: Path, max_excerpt_bytes: int) -> dict[str, Any]:
    suffix = path.suffix.lower() or "[无扩展名]"
    try:
        stat = path.stat()
        size = stat.st_size
        modified = stat.st_mtime
    except OSError:
        size, modified = 0, 0
    record: dict[str, Any] = {
        "path": safe_rel(path, root),
        "absolute_path": str(path),
        "extension": suffix,
        "size": size,
        "modified": modified,
        "excerpt": "",
        "summary": "",
    }
    if suffix == ".xlsx":
        record["summary"] = xlsx_summary(path)
    elif suffix == ".xls":
        record["summary"] = "旧版 Excel 工作簿；本次只记录文件元数据，未尝试改写或读取单元格。"
    elif suffix in TEXT_EXTENSIONS:
        excerpt = read_text(path, max_excerpt_bytes)
        record["excerpt"] = excerpt
        record["summary"] = f"文本片段 {len(excerpt)} 字符"
    else:
        record["summary"] = "二进制/资源文件；本次只记录元数据。"
    return record


def sample_score(path: Path, root: Path, category: str) -> tuple[int, str]:
    relative = safe_rel(path, root).lower()
    suffix = path.suffix.lower()
    score = 0
    if suffix in TEXT_EXTENSIONS:
        score += 12
    if category == "docs" and suffix in SPREADSHEET_EXTENSIONS:
        score += 8
    if category == "client" and suffix in {".py", ".lua", ".json", ".bat", ".xml", ".txt"}:
        score += 8
    for word in ("config", "cfg", "skill", "task", "item", "help", "guide", "activity", "reward", "system", "main"):
        if word in relative:
            score += 3
    if any(part in SKIP_DIRS for part in Path(relative).parts):
        score -= 40
    score -= len(Path(relative).parts)
    return score, relative


def inventory(root: Path, category: str, sample_limit: int, max_excerpt_bytes: int) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise ImportError_(f"目录不存在或不可读取: {root}")
    files: list[Path] = []
    skipped = 0
    for path in root.rglob("*"):
        if is_skipped(path, root):
            if path.is_file():
                skipped += 1
            continue
        if path.is_file():
            files.append(path)
    files.sort(key=lambda path: safe_rel(path, root).lower())
    extensions = Counter(path.suffix.lower() or "[无扩展名]" for path in files)
    candidates = sorted(files, key=lambda path: sample_score(path, root, category), reverse=True)[:max(0, sample_limit)]
    records = [file_summary(path, root, max_excerpt_bytes) for path in candidates]
    total_bytes = sum(path.stat().st_size for path in files if path.exists())
    return {
        "root": str(root),
        "category": category,
        "total_files": len(files),
        "total_bytes": total_bytes,
        "skipped_files": skipped,
        "extensions": dict(extensions.most_common()),
        "samples": records,
    }


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{h(cell)}</th>" for cell in headers)
    body = "".join("<tr>" + "".join(f"<td>{h(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<div class=\"table-wrap\"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def extension_rows(data: dict[str, Any], limit: int = 18) -> list[list[Any]]:
    rows = []
    for extension, count in list(data["extensions"].items())[:limit]:
        rows.append([extension, count, "可读取文本/表格" if extension in TEXT_EXTENSIONS else "仅元数据"])
    return rows


def file_rows(data: dict[str, Any]) -> list[list[Any]]:
    rows = []
    for record in data["samples"]:
        rows.append([record["path"], record["extension"], record["size"], record["summary"]])
    return rows


def excerpts(data: dict[str, Any], limit: int = 12) -> str:
    blocks: list[str] = []
    for record in data["samples"]:
        excerpt = record.get("excerpt", "").strip()
        if not excerpt:
            continue
        blocks.append(
            f"<details><summary>{h(record['path'])}</summary><pre><code>{h(excerpt[:4000])}</code></pre></details>"
        )
        if len(blocks) >= limit:
            break
    return "".join(blocks) or "<p>本次抽样没有可直接展示的文本片段；请查看文件清单和元数据。</p>"


def make_content(client: dict[str, Any], docs: dict[str, Any]) -> dict[str, str]:
    client_root = h(client["root"])
    docs_root = h(docs["root"])
    overview = f"""<div class=\"hero\"><p class=\"eyebrow\">IMPORTED PROJECT HANDBOOK</p>
<h1>客户端与配置资料导览</h1><p class=\"tagline\">从真实客户端代码树和策划/配置目录建立可核验的第一版知识入口。</p>
<p><a class=\"btn primary\" href=\"pages/client-source.html\">查看客户端 →</a></p></div>
<h2>本次导入范围</h2><p>客户端目录：<code>{client_root}</code><br>文档与配置目录：<code>{docs_root}</code></p>
{table(['来源','文件数','抽样展示','被跳过的版本控制/缓存文件'], [['客户端', client['total_files'], len(client['samples']), client['skipped_files']], ['文档与配置', docs['total_files'], len(docs['samples']), docs['skipped_files']]])}
<div class=\"callout note\"><div class=\"body\"><strong>阅读提示</strong><p>这是一份由导入器生成的证据索引，不等于完整业务逆向。先从“客户端代码”了解入口和工具，再从“配置文档”定位表格，最后用右侧问答追问具体事实。</p></div></div>"""
    client_page = f"""<h2>客户端目录画像</h2><p>扫描根目录：<code>{client_root}</code>。本次跳过 SVN 元数据、缓存和依赖目录中的文件，避免把构建产物误当成业务事实。</p>
{table(['相对路径','类型','大小（字节）','导入摘要'], file_rows(client))}
<h2>文本抽样</h2>{excerpts(client)}
<div class=\"callout warn\"><div class=\"body\"><strong>如何继续核对</strong><p>看到入口脚本后，应回到源码确认调用链、配置加载位置和运行参数；抽样片段可能被截断，不能代替原文件。</p></div></div>"""
    docs_page = f"""<h2>文档与配置目录画像</h2><p>扫描根目录：<code>{docs_root}</code>。Excel 文件默认只读取工作簿名称、维度和首行字段；旧版 `.xls` 保留元数据，避免无意修改业务配置。</p>
{table(['相对路径','类型','大小（字节）','导入摘要'], file_rows(docs))}
<h2>可直接阅读的片段</h2>{excerpts(docs)}"""
    catalog_page = f"""<h2>文件类型与检索边界</h2><p>类型统计用于回答“资料在哪里”，不是对配置值的完整解释。优先从高频扩展名和文件名定位专题，再打开原始工作簿复核。</p>
<h3>客户端扩展名</h3>{table(['扩展名','数量','处理方式'], extension_rows(client))}
<h3>文档与配置扩展名</h3>{table(['扩展名','数量','处理方式'], extension_rows(docs))}
<h2>抽样策略</h2><p>导入器优先抽取脚本、JSON/XML、文本和名称包含 config、skill、task、item、help、activity、reward 的文件。大型资源、编译产物和版本控制目录只计数，不复制。</p>"""
    limits_page = f"""<h2>证据与限制</h2><p>本手册由以下两个根目录生成：</p><ul><li><code>{client_root}</code></li><li><code>{docs_root}</code></li></ul>
<h2>已经做的安全处理</h2><ul><li>不会把 API Key、Token、密码或 Secret 写入 book.json 或 HTML；文本抽样会对明显的凭据格式做脱敏。</li><li>不会修改客户端和文档源目录，也不会把原始 Excel 文件复制进输出目录。</li><li>右侧问答只使用生成的搜索索引；模型无法看到未被导入的文件。</li></ul>
<h2>下一步建议</h2><ol><li>针对要改动的玩法，补充一页带来源路径的事实说明。</li><li>对关键配置表指定“表名—字段—版本—生效端”，不要只依赖文件名。</li><li>启动本地 relay 后，先问一个手册中明确存在的问题，再问一个不存在的问题，确认回答会引用来源或明确拒答。</li></ol>
<div class=\"callout warn\"><div class=\"body\"><strong>服务器代码暂未纳入</strong><p>本次只导入客户端和文档/配置目录，因此不能据此判断服务端校验、落库、广播或最终生效逻辑。</p></div></div>"""
    return {
        "index.html": overview,
        "client-source.html": client_page,
        "docs-config.html": docs_page,
        "data-catalog.html": catalog_page,
        "evidence-limits.html": limits_page,
    }


def write_handbook(output: Path, client: dict[str, Any], docs: dict[str, Any], force: bool) -> None:
    source_roots = [Path(client["root"]).resolve(), Path(docs["root"]).resolve()]
    if any(output == root or root in output.parents for root in source_roots):
        raise ImportError_("输出目录不能位于客户端或文档源目录内；请使用独立的新目录")
    if output.exists():
        if not force:
            raise ImportError_(f"输出目录已存在：{output}；如确认覆盖请加 --force")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for directory in ("content", "assets", "evidence"):
        (output / directory).mkdir()
    for asset in ("style.css", "app.js", "chat.js"):
        shutil.copyfile(ROOT / "assets" / asset, output / "assets" / asset)
    book = {
        "title": "御剑客户端与配置手册",
        "subtitle": "Imported Project Handbook",
        "version": "0.2.0",
        "chat": {"enabled": True, "mode": "relay", "endpoint": "/api/chat", "model": "", "context_chars": 16000, "max_history": 8, "title": "手册问答", "placeholder": "输入关于客户端、配置或文档的问题…"},
        "parts": [
            {"id": "start", "label": "项目导览", "icon": "◆", "pages": [{"slug": "index", "title": "封面与范围", "home": True, "time": 3, "lead": "本次导入了客户端代码与配置/策划资料，服务器代码暂不在范围内。"}]},
            {"id": "client", "label": "客户端代码", "icon": "◇", "pages": [{"slug": "client-source", "title": "客户端代码画像", "time": 10, "lead": "客户端目录结构、抽样文件和可核对的文本入口。"}]},
            {"id": "docs", "label": "配置与文档", "icon": "▣", "pages": [{"slug": "docs-config", "title": "配置与策划资料", "time": 12, "lead": "Excel、脚本和策划资料的抽样清单与可读片段。"}, {"slug": "data-catalog", "title": "数据目录与检索边界", "time": 8, "lead": "文件类型统计、抽样策略和表格读取边界。"}]},
            {"id": "evidence", "label": "证据与边界", "icon": "○", "pages": [{"slug": "evidence-limits", "title": "证据、限制与下一步", "time": 6, "lead": "哪些结论可以回答，哪些问题必须回到源文件或等待服务器代码。"}]},
        ],
    }
    (output / "book.json").write_text(json.dumps(book, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, content in make_content(client, docs).items():
        (output / "content" / name).write_text(content, encoding="utf-8")
    facts = {
        "facts": [
            {"id": "client-root", "value": client["root"], "page": "index", "source": "import manifest"},
            {"id": "docs-root", "value": docs["root"], "page": "index", "source": "import manifest"},
            {"id": "client-file-count", "value": str(client["total_files"]), "page": "index", "source": "import manifest"},
            {"id": "docs-file-count", "value": str(docs["total_files"]), "page": "index", "source": "import manifest"},
        ]
    }
    (output / "evidence" / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"client": client, "docs": docs, "generator": "project-handbook/import_project.py"}
    (output / "evidence" / "import-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_tool(script: Path, handbook: Path) -> None:
    result = subprocess.run([sys.executable, str(script), str(handbook)], text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise ImportError_(f"{script.name} 执行失败")


def main() -> int:
    args = parse_args()
    try:
        if args.sample_files < 0 or args.max_excerpt_bytes < 100:
            raise ImportError_("sample-files 必须非负，max-excerpt-bytes 至少为 100")
        client = inventory(args.client, "client", args.sample_files, args.max_excerpt_bytes)
        docs = inventory(args.docs, "docs", args.sample_files, args.max_excerpt_bytes)
        output = args.output.resolve()
        write_handbook(output, client, docs, args.force)
        print(f"imported client files: {client['total_files']} (samples: {len(client['samples'])})")
        print(f"imported docs/config files: {docs['total_files']} (samples: {len(docs['samples'])})")
        print(f"wrote handbook source: {output}")
        if not args.no_build:
            run_tool(ROOT / "scripts" / "build_handbook.py", output)
            run_tool(ROOT / "scripts" / "verify_handbook.py", output)
    except (ImportError_, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
