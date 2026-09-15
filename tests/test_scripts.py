from __future__ import annotations

import json
import os
os.environ['PYTHONUTF8'] = '1'
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "project-handbook"
INIT = ROOT / "scripts" / "init_handbook.py"
BUILD = ROOT / "scripts" / "build_handbook.py"
VERIFY = ROOT / "scripts" / "verify_handbook.py"
IMPORT = ROOT / "scripts" / "import_project.py"


def run(script: Path, folder: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), str(folder), *args],
        text=True,
        encoding='utf-8',
        capture_output=True,
        check=False,
    )


class HandbookScriptsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name) / "handbook"
        self.assertEqual(run(INIT, self.folder).returncode, 0)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_build_and_verify(self) -> None:
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        result = run(VERIFY, self.folder)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.folder / "site" / "pages" / "overview.html").exists())
        index = (self.folder / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="search-data"', index)
        self.assertIn('id="chat-panel"', index)
        self.assertIn('id="chat-config"', index)
        self.assertIn('id="chat-fetch-models"', index)
        self.assertIn('id="chat-fetch-note"', index)
        self.assertNotIn('浏览器直连', index)
        self.assertIn('id="chat-endpoint"', index)
        self.assertIn('请输入完整接口地址，例如 https://你的域名/v1', index)
        self.assertNotIn('https://api.openai.com/v1 或 /api/chat', index)
        self.assertIn('id="chat-consent"', index)
        self.assertNotIn('我确认允许将相关证据', index)
        self.assertIn('sidebar-close', index)
        self.assertTrue((self.folder / "site" / "assets" / "chat.js").exists())
        self.assertIn("项目总览", index)

    def test_missing_fragment_fails_without_partial_pages(self) -> None:
        (self.folder / "content" / "overview.html").unlink()
        result = run(BUILD, self.folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.folder / "site" / "index.html").exists())

    def test_unsafe_fragment_fails(self) -> None:
        (self.folder / "content" / "overview.html").write_text('<script>alert("x")</script>', encoding="utf-8")
        result = run(BUILD, self.folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe", result.stderr)

    def test_broken_link_is_reported(self) -> None:
        content = self.folder / "content" / "overview.html"
        content.write_text('<p><a href="pages/missing.html">broken</a></p>', encoding="utf-8")
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        result = run(VERIFY, self.folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("broken internal link", result.stdout)

    def test_fact_presence_is_checked(self) -> None:
        facts = {"facts": [{"id": "port", "value": "9030", "page": "overview", "source": "config.py"}]}
        (self.folder / "evidence" / "facts.json").write_text(json.dumps(facts), encoding="utf-8")
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        result = run(VERIFY, self.folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fact 'port'", result.stdout)

    def test_chat_secret_is_rejected(self) -> None:
        config = json.loads((self.folder / "book.json").read_text(encoding="utf-8"))
        config["chat"]["api_key"] = "must-not-be-embedded"
        (self.folder / "book.json").write_text(json.dumps(config), encoding="utf-8")
        result = run(BUILD, self.folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot contain secrets", result.stderr)

    def test_chat_can_be_disabled_without_chat_asset(self) -> None:
        config = json.loads((self.folder / "book.json").read_text(encoding="utf-8"))
        config["chat"]["enabled"] = False
        (self.folder / "book.json").write_text(json.dumps(config), encoding="utf-8")
        (self.folder / "assets" / "chat.js").unlink()
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        result = run(VERIFY, self.folder)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        index = (self.folder / "site" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('id="chat-config"', index)

    def test_chat_relay_serves_site_and_explains_missing_key(self) -> None:
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        scripts = ROOT / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            import chat_server

            index = json.loads((self.folder / "site" / "assets" / "search-index.json").read_text(encoding="utf-8"))
            server = chat_server.HandbookServer(
                ("127.0.0.1", 0),
                chat_server.HandbookHandler,
                site=self.folder / "site",
                index=index,
                provider_url="https://example.invalid/v1/chat/completions",
                api_key="",
                api_key_env="OPENAI_API_KEY",
                model="demo-model",
                context_chars=16000,
                max_history=8,
                timeout=10,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                root = f"http://127.0.0.1:{server.server_port}"
                with urlopen(root + "/index.html", timeout=5) as response:
                    self.assertEqual(response.status, 200)
                with self.assertRaises(HTTPError) as models_error:
                    urlopen(root + "/api/models", timeout=5)
                self.assertIn("OPENAI_API_KEY", json.loads(models_error.exception.read().decode("utf-8"))["error"])
                request = Request(
                    root + "/api/chat",
                    data=json.dumps({"query": "项目总览", "consent": True}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request, timeout=5)
                payload = json.loads(raised.exception.read().decode("utf-8"))
                self.assertIn("OPENAI_API_KEY", payload["error"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        finally:
            sys.path.remove(str(scripts))

    def test_chat_relay_passes_context_to_mock_model_and_returns_sources(self) -> None:
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        scripts = ROOT / "scripts"
        sys.path.insert(0, str(scripts))

        class MockModelHandler(BaseHTTPRequestHandler):
            received = None

            def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
                length = int(self.headers.get("Content-Length", "0"))
                MockModelHandler.received = json.loads(self.rfile.read(length).decode("utf-8"))
                body = json.dumps({"choices": [{"message": {"content": "手册证据显示这是一个示例回答。[1]"}}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        provider = ThreadingHTTPServer(("127.0.0.1", 0), MockModelHandler)
        provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
        provider_thread.start()
        try:
            import chat_server

            index = json.loads((self.folder / "site" / "assets" / "search-index.json").read_text(encoding="utf-8"))
            relay = chat_server.HandbookServer(
                ("127.0.0.1", 0),
                chat_server.HandbookHandler,
                site=self.folder / "site",
                index=index,
                provider_url=f"http://127.0.0.1:{provider.server_port}/v1/chat/completions",
                api_key="test-key",
                api_key_env="TEST_KEY",
                model="demo-model",
                context_chars=16000,
                max_history=8,
                timeout=10,
            )
            relay_thread = threading.Thread(target=relay.serve_forever, daemon=True)
            relay_thread.start()
            try:
                request = Request(
                    f"http://127.0.0.1:{relay.server_port}/api/chat",
                    data=json.dumps({"query": "项目总览", "consent": True}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertIn("示例回答", payload["answer"])
                self.assertTrue(payload["sources"])
                self.assertIsNotNone(MockModelHandler.received)
                system = MockModelHandler.received["messages"][0]["content"]
                self.assertIn("handbook_context", system)
                self.assertIn("项目总览", system)
            finally:
                relay.shutdown()
                relay.server_close()
                relay_thread.join(timeout=5)
        finally:
            provider.shutdown()
            provider.server_close()
            provider_thread.join(timeout=5)
            sys.path.remove(str(scripts))

    def test_chat_relay_lists_models_from_provider(self) -> None:
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        scripts = ROOT / "scripts"
        sys.path.insert(0, str(scripts))

        class MockModelHandler(BaseHTTPRequestHandler):
            auth = ""

            def do_GET(self) -> None:  # noqa: N802
                if self.path.split("?", 1)[0] != "/v1/models":
                    self.send_error(404)
                    return
                MockModelHandler.auth = self.headers.get("Authorization", "")
                MockModelHandler.ua = self.headers.get("User-Agent", "")
                body = json.dumps({"data": [{"id": "gpt-test"}, {"id": "gpt-other"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        provider = ThreadingHTTPServer(("127.0.0.1", 0), MockModelHandler)
        provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
        provider_thread.start()
        try:
            import chat_server

            index = json.loads((self.folder / "site" / "assets" / "search-index.json").read_text(encoding="utf-8"))
            relay = chat_server.HandbookServer(
                ("127.0.0.1", 0),
                chat_server.HandbookHandler,
                site=self.folder / "site",
                index=index,
                provider_url=f"http://127.0.0.1:{provider.server_port}/v1/chat/completions",
                api_key="test-key",
                api_key_env="TEST_KEY",
                model="demo-model",
                context_chars=16000,
                max_history=8,
                timeout=10,
            )
            relay_thread = threading.Thread(target=relay.serve_forever, daemon=True)
            relay_thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{relay.server_port}/api/models", timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(payload["models"], ["gpt-test", "gpt-other"])
                self.assertEqual(MockModelHandler.auth, "Bearer test-key")
                self.assertIn("Mozilla/5.0", MockModelHandler.ua)
                request = Request(
                    f"http://127.0.0.1:{relay.server_port}/api/models",
                    data=json.dumps({
                        "base_url": f"http://127.0.0.1:{provider.server_port}/v1",
                        "api_key": "posted-key",
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    posted = json.loads(response.read().decode("utf-8"))
                self.assertEqual(posted["models"], ["gpt-test", "gpt-other"])
                self.assertEqual(MockModelHandler.auth, "Bearer posted-key")
            finally:
                relay.shutdown()
                relay.server_close()
                relay_thread.join(timeout=5)
        finally:
            provider.shutdown()
            provider.server_close()
            provider_thread.join(timeout=5)
            sys.path.remove(str(scripts))

    def test_evidence_only_get_models_is_refused(self) -> None:
        self.assertEqual(run(BUILD, self.folder).returncode, 0)
        scripts = ROOT / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            import chat_server

            index = json.loads((self.folder / "site" / "assets" / "search-index.json").read_text(encoding="utf-8"))
            server = chat_server.HandbookServer(
                ("127.0.0.1", 0),
                chat_server.HandbookHandler,
                site=self.folder / "site",
                index=index,
                provider_url="https://example.invalid/v1/chat/completions",
                api_key="",
                api_key_env="OPENAI_API_KEY",
                model="demo-model",
                context_chars=16000,
                max_history=8,
                timeout=10,
                evidence_only=True,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaises(HTTPError) as raised:
                    urlopen(f"http://127.0.0.1:{server.server_port}/api/models", timeout=5)
                error = json.loads(raised.exception.read().decode("utf-8"))["error"]
                self.assertIn("仅证据", error)
                self.assertIn("供应商", error)
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/models",
                    data=json.dumps({"base_url": "https://example.invalid/v1"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as posted:
                    urlopen(request, timeout=5)
                posted_error = json.loads(posted.exception.read().decode("utf-8"))["error"]
                self.assertIn("API Key", posted_error)
                self.assertNotIn("仅证据", posted_error)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        finally:
            sys.path.remove(str(scripts))

    def test_import_project_builds_from_client_and_docs_roots(self) -> None:
        client = Path(self.temp.name) / "client"
        docs = Path(self.temp.name) / "docs"
        output = Path(self.temp.name) / "imported"
        client.mkdir()
        docs.mkdir()
        (client / "main.py").write_text("print('client entry')\n", encoding="utf-8")
        (docs / "技能说明.txt").write_text("技能入口与配置字段\n", encoding="utf-8")
        (docs / "活动.xls").write_bytes(b"legacy workbook")
        result = subprocess.run(
            [sys.executable, str(IMPORT), "--client", str(client), "--docs", str(docs), "--output", str(output)],
            text=True,
            encoding='utf-8',
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((output / "site" / "index.html").exists())
        self.assertTrue((output / "evidence" / "import-manifest.json").exists())
        self.assertTrue((output / "evidence" / "project-draft.json").exists())
        draft = json.loads((output / "evidence" / "project-draft.json").read_text(encoding="utf-8"))
        self.assertEqual(draft["status"], "partial")
        self.assertEqual([layer["id"] for layer in draft["layers"]], ["client", "docs"])
        book = json.loads((output / "book.json").read_text(encoding="utf-8"))
        self.assertEqual([part["label"] for part in book["parts"]][:3], ["开始", "项目地图", "资料索引"])
        index_fragment = (output / "content" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-map-stage', index_fragment)
        self.assertIn('pages/architecture.html#layer-1', index_fragment)
        self.assertIn('服务端运行待补充', index_fragment)
        self.assertIn('layer-state', index_fragment)
        self.assertIn('待补充', index_fragment)
        self.assertNotIn('orientation-board', index_fragment)
        self.assertNotIn('class="layer-map"', index_fragment)
        reading_guide = (output / "content" / "reading-guide.html").read_text(encoding="utf-8")
        self.assertIn("15 分钟", reading_guide)
        self.assertGreaterEqual(reading_guide.count('class="route-copy"'), 3)
        imported_index = (output / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('sidebar-close', imported_index)
        self.assertIn('<body class="atlas-book">', imported_index)
        self.assertIn("client entry", (output / "content" / "client-source.html").read_text(encoding="utf-8"))
        architecture = (output / "content" / "architecture.html").read_text(encoding="utf-8")
        self.assertIn('id="layer-3"', architecture)
        self.assertIn('服务端运行待补充', architecture)
        self.assertIn('status-open', architecture)
        self.assertNotIn('<table>', architecture.split('<h2>候选入口', 1)[0])

    def test_import_project_refuses_output_inside_source_root(self) -> None:
        client = Path(self.temp.name) / "client"
        docs = Path(self.temp.name) / "docs"
        client.mkdir()
        docs.mkdir()
        result = subprocess.run(
            [sys.executable, str(IMPORT), "--client", str(client), "--docs", str(docs), "--output", str(client / "handbook")],
            text=True,
            encoding='utf-8',
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不能位于客户端或文档源目录内", result.stderr)

    def test_import_project_accepts_optional_backend_root(self) -> None:
        client = Path(self.temp.name) / "client-backend-client"
        backend = Path(self.temp.name) / "backend"
        docs = Path(self.temp.name) / "backend-docs"
        output = Path(self.temp.name) / "with-backend"
        client.mkdir()
        backend.mkdir()
        docs.mkdir()
        (client / "main.ts").write_text("export const app = true\n", encoding="utf-8")
        (backend / "server.py").write_text("def handle(): pass\n", encoding="utf-8")
        (docs / "run.md").write_text("启动说明\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(IMPORT), "--client", str(client), "--backend", str(backend), "--docs", str(docs), "--output", str(output)],
            text=True,
            encoding='utf-8',
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        manifest = json.loads((output / "evidence" / "import-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["backend"]["root"], str(backend.resolve()))
        draft = json.loads((output / "evidence" / "project-draft.json").read_text(encoding="utf-8"))
        self.assertEqual([layer["id"] for layer in draft["layers"]], ["client", "backend", "docs"])
        self.assertTrue((output / "content" / "backend-source.html").exists())
        limits = (output / "content" / "evidence-limits.html").read_text(encoding="utf-8")
        self.assertIn(str(backend.resolve()), limits)
        catalog = (output / "content" / "data-catalog.html").read_text(encoding="utf-8")
        self.assertIn("服务端扩展名", catalog)


if __name__ == "__main__":
    unittest.main()
