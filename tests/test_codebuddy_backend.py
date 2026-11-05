import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'project-handbook/scripts'
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backend_module = load('codebuddy_backend')
server_module = load('flow_server')

# A stand-in for `codebuddy -p --output-format stream-json`: records how it was
# called, then replays the events named by FAKE_CODEBUDDY_MODE.
FAKE = r'''#!/usr/bin/env python3
import json, os, sys, time
prompt = sys.stdin.read()
with open(os.environ['FAKE_CODEBUDDY_LOG'], 'w', encoding='utf-8') as log:
    json.dump({'argv': sys.argv[1:], 'prompt': prompt, 'cwd': os.getcwd(), 'files': os.listdir('.')}, log, ensure_ascii=False)
mode = os.environ.get('FAKE_CODEBUDDY_MODE', 'stream')
say = lambda event: print(json.dumps(event, ensure_ascii=False), flush=True)
say({'type': 'system', 'subtype': 'init', 'tools': []})
if mode == 'stream':
    for part in ['算', '第 1 ', '天。']:
        say({'type': 'stream_event', 'event': {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': part}}})
    say({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': '算第 1 天。'}]}})
    say({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': '算第 1 天。'})
elif mode == 'whole':
    say({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': '第一段。'}]}})
    say({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': '第一段。第二段。'}]}})
    say({'type': 'result', 'subtype': 'success', 'result': '第一段。第二段。'})
elif mode == 'login':
    # What codebuddy 2.100.0 printed when not signed in.
    say({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Authentication required. Please use /login command to sign in to your account'}], 'role': 'assistant'}})
    say({'type': 'result', 'subtype': 'error_during_execution', 'is_error': True, 'num_turns': 2})
elif mode == 'error-result':
    say({'type': 'result', 'subtype': 'error_during_execution', 'is_error': True, 'result': 'quota exceeded'})
elif mode == 'slow':
    say({'type': 'stream_event', 'event': {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': '开始'}}})
    time.sleep(30)
elif mode == 'json':
    say({'type': 'result', 'subtype': 'success', 'result': '```json\n{"title": "新标题"}\n```'})
'''


class CodeBuddyBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.binary = self.temp / 'codebuddy'
        self.binary.write_text(FAKE, encoding='utf-8')
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IEXEC)
        self.log = self.temp / 'call.json'
        os.environ['FAKE_CODEBUDDY_LOG'] = str(self.log)
        self.addCleanup(os.environ.pop, 'FAKE_CODEBUDDY_MODE', None)
        self.backend = backend_module.CodeBuddyBackend(binary=str(self.binary), model='glm-4.6')
        self.addCleanup(self.backend.close)

    def ask(self, mode, prompt='第 8 天算第几天？', cancel=None, schema=None):
        os.environ['FAKE_CODEBUDDY_MODE'] = mode
        parts = []
        answer = self.backend.ask(prompt, parts.append, cancel or threading.Event(), schema=schema)
        return answer, parts, json.loads(self.log.read_text(encoding='utf-8'))

    @unittest.skipIf(os.name == 'nt', 'the fake CLI is a POSIX script')
    def test_streams_an_answer_without_tools_or_files(self):
        self.assertEqual(self.backend.status()['name'], 'CodeBuddy')
        self.assertFalse(self.backend.status()['connected'], 'not known to be signed in before a question')
        answer, parts, call = self.ask('stream')
        self.assertEqual(answer, '算第 1 天。')
        self.assertEqual(''.join(parts), '算第 1 天。', 'whole messages do not repeat streamed text')
        self.assertEqual(call['argv'], ['-p', '--output-format', 'stream-json', '--include-partial-messages',
                                        '--tools', '', '--strict-mcp-config', '--model', 'glm-4.6'])
        self.assertNotIn('-y', call['argv'], 'no permission is granted to anything left')
        self.assertEqual(call['prompt'], '第 8 天算第几天？', 'the prompt goes on stdin, not the command line')
        self.assertEqual(call['files'], [], 'it runs in an empty folder')
        self.assertTrue(self.backend.status()['connected'])

    @unittest.skipIf(os.name == 'nt', 'the fake CLI is a POSIX script')
    def test_whole_messages_show_only_new_text(self):
        answer, parts, _ = self.ask('whole')
        self.assertEqual(answer, '第一段。第二段。')
        self.assertEqual(parts, ['第一段。', '第二段。'])

    @unittest.skipIf(os.name == 'nt', 'the fake CLI is a POSIX script')
    def test_sign_in_and_other_failures_are_named(self):
        with self.assertRaisesRegex(RuntimeError, 'sign-in required'):
            self.ask('login')
        status = self.backend.status()
        self.assertFalse(status['connected'])
        self.assertIn('codebuddy', server_module.public_ask_failure(self.backend))
        self.assertIn('登录', server_module.public_ask_failure(self.backend))
        with self.assertRaisesRegex(RuntimeError, 'request failed'):
            self.ask('error-result')

    @unittest.skipIf(os.name == 'nt', 'the fake CLI is a POSIX script')
    def test_cancel_stops_the_cli(self):
        cancel = threading.Event()
        threading.Timer(.5, cancel.set).start()
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            self.ask('slow', cancel=cancel)

    @unittest.skipIf(os.name == 'nt', 'the fake CLI is a POSIX script')
    def test_structured_output_asks_for_json(self):
        answer, _, call = self.ask('json', prompt='REVISION_REQUEST', schema={'type': 'object'})
        self.assertIn('Return only the JSON object', call['prompt'])
        self.assertIn('"type": "object"', call['prompt'])
        self.assertIn('```json', answer, 'the server strips fences before parsing')

    def test_missing_cli_is_reported_without_starting_anything(self):
        missing = backend_module.CodeBuddyBackend(binary=str(self.temp / 'nope'))
        self.assertFalse(missing.status()['available'])
        self.assertIn('没有找到本机 CodeBuddy', server_module.public_ask_failure(missing))

    def test_agent_choice(self):
        self.assertEqual(server_module.make_backend('codebuddy', binary=str(self.binary), cwd=self.temp).name, 'CodeBuddy')
        self.assertEqual(server_module.make_backend('codex', binary=str(self.temp / 'nope'), cwd=self.temp).name, 'Codex')
        with self.assertRaises(ValueError):
            server_module.make_backend('other')


if __name__ == '__main__':
    unittest.main()
