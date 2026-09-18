import json
import sys
import tempfile
import threading
import http.client
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'project-handbook/scripts'))
from build_flow import build
from flow_server import FlowServer, make_context, validate_source_roots


class FakeBackend:
    def __init__(self):
        self.prompts = []
        self.closed = False
        self.resets = []

    def status(self):
        return {'available': True, 'connected': True, 'model': 'test-model'}

    def ask(self, prompt, emit, cancel_event, schema=None):
        self.prompts.append(prompt)
        if 'REVISION_REQUEST' in prompt:
            return json.dumps({'summary': 'Reviewed synthetic explanation'})
        emit('First ')
        emit('answer.')
        return 'First answer.'

    def close(self):
        self.closed = True

    def reset_context(self):
        self.resets.append(len(self.prompts))


class FlowServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.book = Path(self.temp.name) / 'book'
        self.data = json.loads((ROOT / 'project-handbook/assets/damage.example.json').read_text(encoding='utf-8'))
        build(self.data, self.book)
        self.backend = FakeBackend()
        self.server = FlowServer(('127.0.0.1', 0), self.book, backend=self.backend)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)
        self.temp.cleanup()

    def request(self, path, data=None, token=True, origin=None):
        headers = {'Origin': origin or self.url}
        if token:
            headers['X-Flow-Token'] = self.server.token
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        with urlopen(Request(self.url + path, data=body, headers=headers), timeout=5) as r:
            return r.read().decode()

    def test_only_owned_pages_and_same_origin_apis(self):
        page = self.request('/')
        self.assertIn(self.server.token, page)
        self.assertNotIn(self.server.token, (self.book / 'handbook.html').read_text(encoding='utf-8'))
        for path in ('/flow.json', '/.flow-session.json', '/../../README.md'):
            with self.assertRaises(HTTPError) as cm:
                self.request(path)
            self.assertEqual(cm.exception.code, 404)
        with self.assertRaises(HTTPError) as cm:
            self.request('/api/state', token=False)
        self.assertEqual(cm.exception.code, 403)

    def test_session_recovery_is_same_origin_and_book_bound(self):
        session = json.loads(self.request('/api/session', token=False))
        self.assertEqual(session['token'], self.server.token)
        self.assertIn(session['book_id'], self.request('/'))
        for origin in ('https://evil.invalid', 'http://localhost:3000'):
            with self.assertRaises(HTTPError) as cm:
                self.request('/api/session', token=False, origin=origin)
            self.assertEqual(cm.exception.code, 403)
        with self.assertRaises(HTTPError) as cm:
            self.request('/api/ask', {'question': 'test'}, origin='https://evil.invalid')
        self.assertEqual(cm.exception.code, 403)

    def test_stream_history_and_export_do_not_regenerate_original(self):
        before = (self.book / 'handbook.html').read_bytes()
        events = [json.loads(line) for line in self.request('/api/ask', {'node_id': 'fixed-value', 'question': 'Why overwrite?'}).splitlines()]
        self.assertEqual([e['type'] for e in events], ['start', 'delta', 'delta', 'done'])
        entry = events[-1]['entry']
        self.assertEqual(entry['answer'], 'First answer.')
        self.assertIn('fixed-value', self.backend.prompts[0])
        state = json.loads(self.request('/api/state'))
        self.assertFalse(state['busy'])
        self.assertEqual(state['entries'][0]['id'], entry['id'])
        exported = json.loads(self.request('/api/export', {'entry_ids': [entry['id']], 'redact': True}))
        self.assertIn('First answer.', exported['html'])
        self.assertNotIn(self.server.token, exported['html'])
        self.assertNotIn('"runtime":', exported['html'])
        self.assertEqual(len(self.backend.prompts), 1)
        self.assertEqual(before, (self.book / 'handbook.html').read_bytes())
        saved = json.loads((self.book / '.flow-session.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['entries'][0]['id'], entry['id'])

    def test_compile_writes_new_offline_version(self):
        entry = json.loads(self.request('/api/ask', {'node_id': 'fixed-value', 'question': 'Why?'}).splitlines()[-1])['entry']
        before = (self.book / 'handbook.html').read_bytes()
        rows = [json.loads(x) for x in self.request('/api/compile', {'entry_ids': [entry['id']], 'redact': True}).splitlines()]
        self.assertEqual(rows[-1]['type'], 'compiled')
        result = self.request(rows[-1]['url'])
        self.assertIn('Reviewed synthetic explanation', result)
        self.assertIn('First answer.', result)
        self.assertNotIn(self.server.token, result)
        self.assertEqual(before, (self.book / 'handbook.html').read_bytes())
        self.assertEqual(self.backend.resets, [1, 2])

    def test_bad_inputs_and_busy_are_rejected(self):
        for body in ({'question': ''}, {'question': 'x', 'node_id': '../secret'}, {'question': 'x' * 4001}):
            with self.assertRaises(HTTPError) as cm:
                self.request('/api/ask', body)
            self.assertEqual(cm.exception.code, 400)
        with self.assertRaises(HTTPError):
            self.request('/api/export', {'entry_ids': ['not-existing']})
        with self.assertRaises(HTTPError):
            self.request('/api/compile', {'entry_ids': []})
        self.server.operation_lock.acquire()
        try:
            with self.assertRaises(HTTPError) as cm:
                self.request('/api/ask', {'question': 'busy'})
            self.assertEqual(cm.exception.code, 409)
        finally:
            self.server.operation_lock.release()

    def test_read_roots_and_context_are_bounded(self):
        roots = validate_source_roots([self.book, self.book])
        self.assertEqual(len(roots), 1)
        with self.assertRaises(ValueError):
            validate_source_roots([self.book / 'missing'])
        prompt = make_context(self.data, 'fixed-value', 'Explain', [])
        self.assertIn('固定伤害', prompt)
        self.assertLess(len(prompt), 45000)
        with self.assertRaises(ValueError):
            FlowServer(('0.0.0.0', 0), self.book, backend=self.backend)

    def test_dns_rebinding_host_is_rejected_before_serving_token(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        conn.request('GET', '/', headers={'Host': 'evil.invalid'})
        response = conn.getresponse()
        self.assertEqual(response.status, 403)
        self.assertNotIn(self.server.token, response.read().decode())
        conn.close()

    def test_cancel_persists_incomplete_answer_and_disallows_selection(self):
        started = threading.Event()
        def wait_for_cancel(prompt, emit, cancel_event, schema=None):
            emit('Partial text')
            started.set()
            cancel_event.wait(3)
            return 'Partial text'
        self.backend.ask = wait_for_cancel
        result = []
        worker = threading.Thread(target=lambda: result.append(self.request('/api/ask', {'question': 'Explain'})))
        worker.start()
        self.assertTrue(started.wait(2))
        self.request('/api/cancel', {})
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(json.loads(result[0].splitlines()[-1])['type'], 'error')
        state = json.loads(self.request('/api/state'))
        self.assertFalse(state['busy'])
        entry = state['entries'][0]
        self.assertEqual(entry['status'], 'cancelled')
        with self.assertRaises(HTTPError) as cm:
            self.request('/api/compile', {'entry_ids': [entry['id']]})
        self.assertEqual(cm.exception.code, 400)

    def test_backend_error_is_private_and_server_recovers(self):
        def fail(*args, **kwargs):
            raise RuntimeError('private-token C:/private/path')
        self.backend.ask = fail
        result = self.request('/api/ask', {'question': 'Explain'})
        self.assertNotIn('private-token', result)
        self.assertNotIn('C:/private', result)
        event = json.loads(result.splitlines()[-1])
        self.assertEqual(event['type'], 'error')
        self.assertIn('点重试', event['message'])
        state = json.loads(self.request('/api/state'))
        self.assertFalse(state['busy'])
        self.assertEqual(state['entries'][0]['status'], 'error')
        self.assertEqual(state['entries'][0]['error'], event['message'])
        self.assertNotIn('private-token', state['entries'][0]['error'])

    def test_signin_failure_explains_next_step(self):
        def fail(*args, **kwargs):
            raise RuntimeError('Sign in using the local Codex app or CLI, then retry.')
        self.backend.ask = fail
        self.backend.status = lambda: {'available': True, 'connected': False, 'message': 'Sign in using the local Codex app or CLI, then retry.'}
        event = json.loads(self.request('/api/ask', {'question': 'Explain'}).splitlines()[-1])
        self.assertEqual(event['type'], 'error')
        self.assertIn('登录', event['message'])
        self.assertNotIn('Sign in', event['message'])

    def test_general_question_can_be_exported(self):
        result = self.request('/api/ask', {'question': 'Explain the whole flow'})
        entry = json.loads(result.splitlines()[-1])['entry']
        exported = json.loads(self.request('/api/export', {'entry_ids': [entry['id']]}))
        self.assertIn('First answer.', exported['html'])

    def test_history_restored_with_new_connection_token(self):
        entry = json.loads(self.request('/api/ask', {'question': 'Explain'}).splitlines()[-1])['entry']
        self.server.shutdown()
        self.server.server_close()
        another = FlowServer(('127.0.0.1', 0), self.book, backend=FakeBackend())
        try:
            self.assertEqual(another.entries[0]['id'], entry['id'])
            self.assertNotEqual(another.token, self.server.token)
        finally:
            another.server_close()

    def test_second_server_for_same_book_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'already open'):
            FlowServer(('127.0.0.1', 0), self.book, backend=FakeBackend())

    def test_compiler_does_not_receive_unselected_saved_answers(self):
        self.server.data['qa'] = [{'id': 'unselected', 'question': 'private', 'answer': 'UNSELECTED_SENTINEL', 'node_id': None}]
        entry = json.loads(self.request('/api/ask', {'question': 'Explain'}).splitlines()[-1])['entry']
        self.request('/api/compile', {'entry_ids': [entry['id']]})
        self.assertNotIn('UNSELECTED_SENTINEL', self.backend.prompts[-1])

    def test_preexisting_offline_answers_are_selectable(self):
        data = self.data.copy()
        data['qa'] = [{'id': 'saved-answer', 'node_id': None, 'question': 'Saved question', 'answer': 'Saved answer'}]
        book = Path(self.temp.name) / 'revised-book'
        build(data, book)
        another = FlowServer(('127.0.0.1', 0), book, backend=FakeBackend())
        try:
            self.assertEqual(another.entries[0]['id'], 'saved-answer')
            self.assertEqual(another.entries[0]['status'], 'complete')
        finally:
            another.server_close()

    def test_only_missing_evidence_triggers_bounded_lookup(self):
        (self.book / 'combat.lua').write_text('local damage = 500', encoding='utf-8')
        self.server.roots = [self.book]
        prompts = []
        def answer(prompt, emit, cancel_event, schema=None):
            prompts.append(prompt)
            if len(prompts) == 1:
                emit('LOOKUP_')
                emit('REQUEST: damage')
                return 'LOOKUP_REQUEST: damage'
            emit('Based on combat.lua:1, damage is 500.')
            return 'Based on combat.lua:1, damage is 500.'
        self.backend.ask = answer
        result = self.request('/api/ask', {'question': 'What is actual damage?'})
        self.assertNotIn('LOOKUP_REQUEST', result)
        self.assertEqual(len(prompts), 2)
        self.assertIn('local damage = 500', prompts[1])
        self.assertEqual(json.loads(result.splitlines()[-1])['entry']['status'], 'complete')
