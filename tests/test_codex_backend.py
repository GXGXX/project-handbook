"""The fake peer runs over real pipes; it never contacts a model or reads auth."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'project-handbook/scripts'))


def fake_codex():
    scenario = os.environ.get('FAKE_CODEX_SCENARIO', '')
    if 'generate-json-schema' in sys.argv:
        output = Path(sys.argv[sys.argv.index('--out') + 1]) / 'v2'
        output.mkdir(parents=True, exist_ok=True)
        access = {'oneOf': [{'properties': {
            'type': {'enum': ['restricted']},
            'includePlatformDefaults': {'type': 'boolean'},
            'readableRoots': {'type': 'array', 'items': {'type': 'string'}},
        }}]}
        readonly = {'properties': {'type': {'enum': ['readOnly']},
                                   'networkAccess': {'type': 'boolean'}}}
        if scenario not in ('old-sandbox', 'tool-less'):
            readonly['properties']['access'] = {'$ref': '#/definitions/ReadOnlyAccess'}
        schema = {'properties': {'sandboxPolicy': {'$ref': '#/definitions/SandboxPolicy'}},
                  'definitions': {'SandboxPolicy': {'oneOf': [readonly]}, 'ReadOnlyAccess': access}}
        thread = {'properties': {}}
        if scenario != 'old-sandbox':
            schema['properties']['environments'] = {'type': ['array', 'null']}
            thread['properties']['environments'] = {'type': ['array', 'null']}
        (output / 'TurnStartParams.json').write_text(json.dumps(schema), encoding='utf-8')
        (output / 'ThreadStartParams.json').write_text(json.dumps(thread), encoding='utf-8')
        return

    def send(message):
        print(json.dumps(message), flush=True)

    def reply(request, result):
        send({'id': request['id'], 'result': result})

    def event(method, params):
        send({'method': method, 'params': params})

    config = {'mcp_servers': {}, 'plugins': {}, 'features': {}}
    if scenario == 'inherited-tools':
        config = {'mcp_servers': {'external.with.dots': {'enabled': True}},
                  'plugins': {'synthetic@marketplace': {'enabled': True}},
                  'features': {'inherited_action': True}}
    for index, arg in enumerate(sys.argv):
        if arg == '-c':
            key, raw = sys.argv[index + 1].split('=', 1)
            if key in ('mcp_servers', 'plugins') and raw != '{}':
                value = {json.loads(name): {'enabled': False} for name in
                         re.findall(r'("(?:\\.|[^"\\])*")=\{enabled=false\}', raw)}
            else:
                value = json.loads(raw)
            target = config
            parts = [json.loads(part) if part.startswith('"') else part
                     for part in re.findall(r'"(?:\\.|[^"\\])*"|[^.]+', key)]
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            if isinstance(value, dict) and isinstance(target.get(parts[-1]), dict):
                target[parts[-1]].update(value)
            else:
                target[parts[-1]] = value
    if scenario == 'mcp-enabled':
        config['mcp_servers'] = {'external': {'url': 'https://invalid.example', 'enabled': True}}
    if scenario == 'tools-enabled':
        config['features']['apps'] = True
    if scenario == 'unverified-config':
        config.pop('features', None)
    turns = 0
    pending = None
    history = []
    for line in sys.stdin:
        request = json.loads(line)
        with open(os.environ['FAKE_CODEX_LOG'], 'a', encoding='utf-8') as log:
            log.write(json.dumps(request) + '\n')
        method = request.get('method')
        if not method:
            continue
        if method == 'initialize':
            reply(request, {'userAgent': 'synthetic-codex'})
        elif method == 'initialized':
            pass
        elif method == 'config/read':
            reply(request, {'config': config, 'origins': {}, 'layers': None})
        elif method == 'experimentalFeature/list':
            features = [{'name': name, 'enabled': enabled, 'defaultEnabled': False, 'stage': 'stable'}
                        for name, enabled in config.get('features', {}).items()]
            features.append({'name': 'guardianv2.thread_context', 'enabled': False,
                             'defaultEnabled': False, 'stage': 'underDevelopment'})
            features.append({'name': 'legacy_metadata', 'enabled': True,
                             'defaultEnabled': True, 'stage': 'removed'})
            if scenario in ('engine-selected', 'effective-shell-enabled'):
                features = [item for item in features if item['name'] != 'unified_exec']
                features.append({'name': 'unified_exec', 'enabled': True,
                                 'defaultEnabled': True, 'stage': 'stable'})
                if scenario == 'effective-shell-enabled':
                    features = [item for item in features if item['name'] != 'shell_tool']
                    features.append({'name': 'shell_tool', 'enabled': True,
                                     'defaultEnabled': True, 'stage': 'stable'})
            if scenario == 'effective-tool-enabled':
                features.append({'name': 'unstoppable_action', 'enabled': True,
                                 'defaultEnabled': True, 'stage': 'stable'})
            reply(request, {'data': features, 'nextCursor': None})
        elif method == 'account/read':
            reply(request, {'account': None if scenario == 'unauthenticated' else
                  {'type': 'chatgpt', 'email': 'PRIVATE_EMAIL', 'planType': 'pro'},
                  'requiresOpenaiAuth': True})
        elif method == 'thread/start':
            if scenario == 'raw-error':
                send({'id': request['id'], 'error': {'code': -32000,
                      'message': 'PRIVATE_CREDENTIAL sk-private C:\\private\\auth.json'}})
                continue
            reply(request, {'thread': {'id': 'dedicated-thread'}, 'model': 'fake-model',
                            'approvalPolicy': 'never', 'sandbox': {'type': 'readOnly'}})
        elif method == 'turn/start':
            turns += 1
            turn = 'turn-' + str(turns)
            pending = turn
            params = {'threadId': 'dedicated-thread', 'turnId': turn, 'itemId': 'answer'}
            if scenario == 'early-events':
                event('item/agentMessage/delta', {**params, 'delta': 'early '})
            reply(request, {'turn': {'id': turn, 'status': 'inProgress', 'items': [], 'error': None}})
            if scenario == 'memory':
                answer = '|'.join(history) or 'FRESH'
                history.append(request['params']['input'][0]['text'])
                item = {'type': 'agentMessage', 'id': 'answer', 'text': answer, 'phase': 'final_answer'}
                event('item/agentMessage/delta', {**params, 'delta': answer})
                event('turn/completed', {'threadId': 'dedicated-thread',
                      'turn': {'id': turn, 'status': 'completed', 'items': [item], 'error': None}})
                continue
            if scenario in ('commentary-only', 'late-commentary', 'mixed-phases', 'commentary-legacy'):
                commentary = {'type': 'agentMessage', 'id': 'progress', 'text': 'Checking evidence.',
                              'phase': 'commentary'}
                progress_params = {**params, 'itemId': 'progress'}
                if scenario != 'late-commentary':
                    event('item/started', {'threadId': 'dedicated-thread', 'turnId': turn,
                                          'item': {**commentary, 'text': ''}})
                event('item/agentMessage/delta', {**progress_params, 'delta': commentary['text']})
                if scenario == 'commentary-legacy':
                    commentary.pop('phase')
                event('item/completed', {'threadId': 'dedicated-thread', 'turnId': turn, 'item': commentary})
                if scenario != 'mixed-phases':
                    event('turn/completed', {'threadId': 'dedicated-thread',
                          'turn': {'id': turn, 'status': 'completed', 'items': [commentary], 'error': None}})
                    continue
            if scenario in ('mixed-phases', 'incomplete-final', 'stream-before-completion'):
                event('item/started', {'threadId': 'dedicated-thread', 'turnId': turn,
                      'item': {'type': 'agentMessage', 'id': 'answer', 'text': '', 'phase': 'final_answer'}})
            if scenario in ('bare-deltas', 'incomplete-final', 'stream-before-completion'):
                event('item/agentMessage/delta', {**params, 'delta': 'Incomplete answer.'})
                if scenario != 'stream-before-completion':
                    event('turn/completed', {'threadId': 'dedicated-thread',
                          'turn': {'id': turn, 'status': 'completed', 'items': [], 'error': None}})
                continue
            if scenario in ('waiting', 'ignore-cancel'):
                continue
            if scenario == 'crash':
                print('PRIVATE_CREDENTIAL', file=sys.stderr, flush=True)
                return
            if scenario == 'malformed':
                print('{PRIVATE_CREDENTIAL', flush=True)
                continue
            if scenario == 'approval':
                send({'id': 'approval-1', 'method': 'item/commandExecution/requestApproval',
                      'params': params})
                continue
            if scenario == 'unknown-tool':
                send({'id': 'approval-1', 'method': 'item/tool/call', 'params': params})
                continue
            if scenario == 'failed-turn':
                event('turn/completed', {'threadId': 'dedicated-thread',
                      'turn': {'id': turn, 'status': 'failed', 'items': [],
                               'error': {'message': 'PRIVATE_CREDENTIAL'}}})
                continue
            event('item/agentMessage/delta', {**params, 'threadId': 'other-thread', 'delta': 'LEAK'})
            event('item/reasoning/textDelta', {**params, 'delta': 'PRIVATE_REASONING'})
            if scenario != 'completion-only':
                event('item/agentMessage/delta', {**params, 'delta': 'Hello '})
                event('item/agentMessage/delta', {**params, 'delta': 'world.'})
            item = {'type': 'agentMessage', 'id': 'answer', 'text': 'Hello world.',
                    'phase': 'final_answer'}
            if scenario == 'legacy-completed':
                item.pop('phase')
            event('item/completed', {'threadId': 'dedicated-thread', 'turnId': turn, 'item': item})
            event('turn/completed', {'threadId': 'dedicated-thread',
                  'turn': {'id': turn, 'status': 'completed', 'items': [item], 'error': None}})
        elif method == 'turn/interrupt':
            if scenario != 'ignore-cancel':
                reply(request, {})
                event('turn/completed', {'threadId': 'dedicated-thread',
                      'turn': {'id': pending, 'status': 'interrupted', 'items': [], 'error': None}})
        else:
            send({'id': request['id'], 'error': {'code': -32601, 'message': 'unknown method'}})


class CodexBackendTests(unittest.TestCase):
    def setUp(self):
        import codex_backend
        self.module = codex_backend
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cwd = Path(self.temp.name)
        self.source = self.cwd / 'source'
        self.source.mkdir()
        self.log = self.cwd / 'protocol.jsonl'
        self.commands = []
        original = subprocess.Popen

        def launch(args, **kwargs):
            self.commands.append((args, kwargs.copy()))
            return original([sys.executable, str(Path(__file__).resolve()), '--fake-codex', *args[1:]], **kwargs)

        self.addCleanup(patch.stopall)
        patch.object(codex_backend.subprocess, 'Popen', side_effect=launch).start()
        patch.dict(os.environ, {'FAKE_CODEX_LOG': str(self.log), 'FAKE_CODEX_SCENARIO': ''}).start()

    def backend(self, scenario='', **kwargs):
        os.environ['FAKE_CODEX_SCENARIO'] = scenario
        backend = self.module.CodexBackend(binary=sys.executable, cwd=self.cwd,
                                          roots=[self.source, self.source], **kwargs)
        self.addCleanup(backend.close)
        return backend

    def requests(self, method=None):
        rows = [json.loads(line) for line in self.log.read_text(encoding='utf-8').splitlines()] if self.log.exists() else []
        return [row for row in rows if row.get('method') == method] if method else rows

    def ask(self, backend, cancel=None, schema=None):
        deltas = []
        result = backend.ask('Explain the synthetic flow.', deltas.append, cancel or threading.Event(), schema)
        return result, deltas

    def test_stdio_handshake_streaming_persistent_thread_auth_and_restrictions(self):
        backend = self.backend(model='test-model')
        self.assertEqual(self.ask(backend), ('Hello world.', ['Hello ', 'world.']))
        self.assertEqual(self.ask(backend)[0], 'Hello world.')
        methods = [row.get('method') for row in self.requests()]
        self.assertEqual(methods[:2], ['initialize', 'initialized'])
        self.assertEqual(len(self.requests('thread/start')), 1)
        self.assertFalse(any('login' in str(method) or 'resume' in str(method) for method in methods))
        start = self.requests('thread/start')[0]['params']
        self.assertEqual(start['approvalPolicy'], 'never')
        self.assertEqual(start['sandbox'], 'read-only')
        self.assertEqual(start['dynamicTools'], [])
        for request in self.requests('turn/start'):
            params = request['params']
            self.assertEqual(params['threadId'], 'dedicated-thread')
            self.assertEqual(params['approvalPolicy'], 'never')
            self.assertEqual(params['sandboxPolicy'], {
                'type': 'readOnly', 'networkAccess': False,
                'access': {'type': 'restricted', 'includePlatformDefaults': True,
                           'readableRoots': [str(self.source.resolve())]}})
        status = backend.status()
        self.assertTrue(status['connected'])
        self.assertEqual(set(status), {'available', 'connected', 'model', 'message'})
        self.assertNotIn('PRIVATE_', json.dumps(status))
        self.assertNotIn(str(self.cwd), json.dumps(status))
        server_commands = [command for command, _ in self.commands if 'generate-json-schema' not in command]
        self.assertEqual(len(server_commands), 1)
        for _, options in self.commands:
            self.assertFalse(options.get('shell', False))
            self.assertNotIn('CODEX_HOME', options.get('env', {}))

    def test_schema_forwarded_only_when_supplied(self):
        backend = self.backend()
        self.ask(backend)
        schema = {'type': 'object', 'properties': {'summary': {'type': 'string'}}}
        self.ask(backend, schema=schema)
        requests = self.requests('turn/start')
        self.assertNotIn('outputSchema', requests[0]['params'])
        self.assertEqual(requests[1]['params']['outputSchema'], schema)

    def test_completion_only_emits_once(self):
        self.assertEqual(self.ask(self.backend('completion-only')), ('Hello world.', ['Hello world.']))

    def test_notifications_before_turn_response_are_not_lost(self):
        result, deltas = self.ask(self.backend('early-events'))
        self.assertEqual(deltas, ['early ', 'Hello ', 'world.'])
        self.assertEqual(result, 'Hello world.')

    def test_commentary_only_turn_never_becomes_an_answer(self):
        for scenario in ('commentary-only', 'late-commentary', 'commentary-legacy'):
            with self.subTest(scenario=scenario):
                backend = self.backend(scenario)
                deltas = []
                with self.assertRaisesRegex(RuntimeError, 'final answer'):
                    backend.ask('Explain.', deltas.append, threading.Event())
                self.assertEqual(deltas, [])
                self.assertFalse(backend.status()['connected'])

    def test_commentary_is_filtered_per_item_without_losing_final_answer(self):
        self.assertEqual(self.ask(self.backend('mixed-phases')),
                         ('Hello world.', ['Hello ', 'world.']))

    def test_deltas_alone_do_not_prove_a_completed_answer(self):
        for scenario in ('bare-deltas', 'incomplete-final'):
            with self.subTest(scenario=scenario):
                backend = self.backend(scenario)
                deltas = []
                with self.assertRaisesRegex(RuntimeError, 'final answer'):
                    backend.ask('Explain.', deltas.append, threading.Event())
                if scenario == 'bare-deltas':
                    self.assertEqual(deltas, [])

    def test_legacy_completed_message_without_phase_is_an_explicit_answer(self):
        self.assertEqual(self.ask(self.backend('legacy-completed')),
                         ('Hello world.', ['Hello ', 'world.']))

    def test_known_final_item_streams_before_completion(self):
        backend = self.backend('stream-before-completion')
        cancel = threading.Event()
        deltas = []

        def emit(delta):
            deltas.append(delta)
            cancel.set()

        with patch.object(self.module, 'TURN_TIMEOUT', 2):
            with self.assertRaisesRegex(RuntimeError, '[Cc]ancel'):
                backend.ask('Explain.', emit, cancel)
        self.assertEqual(deltas, ['Incomplete answer.'])
        self.assertTrue(self.requests('turn/interrupt'))

    def test_old_readonly_schema_is_rejected_before_starting_server(self):
        backend = self.backend('old-sandbox')
        with self.assertRaisesRegex(RuntimeError, 'restricted.*read|read.*restrict'):
            self.ask(backend)
        self.assertFalse(self.requests())
        self.assertFalse(backend.status()['connected'])
        self.assertIn('restrict', backend.status()['message'].lower())

    def test_toolless_fallback_does_not_pretend_to_enforce_read_roots(self):
        backend = self.backend('tool-less')
        self.assertEqual(self.ask(backend)[0], 'Hello world.')
        start = self.requests('thread/start')[0]['params']
        turn = self.requests('turn/start')[0]['params']
        self.assertEqual(start['environments'], [])
        self.assertEqual(turn['environments'], [])
        self.assertEqual(start['runtimeWorkspaceRoots'], [])
        self.assertEqual(turn['sandboxPolicy'], {'type': 'readOnly', 'networkAccess': False})
        self.assertIn('tool-less', backend.status()['message'])
        self.assertIn('host', backend.status()['message'])

    def test_inherited_tools_are_disabled_individually_before_any_thread(self):
        backend = self.backend('inherited-tools')
        self.assertEqual(self.ask(backend)[0], 'Hello world.')
        self.assertEqual(len(self.requests('thread/start')), 1)
        commands = [command for command, _ in self.commands if 'generate-json-schema' not in command]
        self.assertGreaterEqual(len(commands), 2)
        self.assertIn('mcp_servers={"external.with.dots"={enabled=false}}', commands[-1])
        self.assertIn('plugins={"synthetic@marketplace"={enabled=false}}', commands[-1])
        self.assertIn('features.inherited_action=false', commands[-1])

    def test_runtime_features_must_agree_with_disabled_config(self):
        backend = self.backend('effective-tool-enabled')
        with self.assertRaises(RuntimeError):
            self.ask(backend)
        self.assertFalse(self.requests('thread/start'))
        self.assertFalse(self.requests('turn/start'))

    def test_engine_selection_is_only_safe_with_shell_tools_disabled(self):
        backend = self.backend('engine-selected')
        self.assertEqual(self.ask(backend)[0], 'Hello world.')
        backend.close()
        count = len(self.requests('turn/start'))
        with self.assertRaises(RuntimeError):
            self.ask(self.backend('effective-shell-enabled'))
        self.assertEqual(len(self.requests('turn/start')), count)

    def test_unverified_external_tool_settings_fail_before_thread_or_turn(self):
        for scenario in ('mcp-enabled', 'tools-enabled', 'unverified-config'):
            with self.subTest(scenario=scenario):
                backend = self.backend(scenario)
                with self.assertRaises(RuntimeError):
                    self.ask(backend)
                self.assertFalse(self.requests('thread/start'))
                self.assertFalse(self.requests('turn/start'))
                self.assertFalse(backend.status()['connected'])

    def test_no_auth_is_safe_and_does_not_trigger_login(self):
        backend = self.backend('unauthenticated')
        with self.assertRaisesRegex(RuntimeError, 'sign in|Sign in'):
            self.ask(backend)
        self.assertFalse(self.requests('turn/start'))

    def test_raw_errors_and_crashes_are_not_exposed(self):
        for scenario in ('raw-error', 'crash', 'malformed', 'failed-turn'):
            with self.subTest(scenario=scenario):
                backend = self.backend(scenario)
                with self.assertRaises(RuntimeError) as caught:
                    self.ask(backend)
                self.assertNotIn('PRIVATE_', str(caught.exception))
                self.assertNotIn('PRIVATE_', json.dumps(backend.status()))
                self.assertFalse(backend.status()['connected'])

    def test_stream_consumer_errors_are_sanitized_and_process_stops(self):
        backend = self.backend()

        def broken_consumer(_):
            raise RuntimeError('PRIVATE_CREDENTIAL from downstream consumer')

        with self.assertRaises(RuntimeError) as caught:
            backend.ask('Explain.', broken_consumer, threading.Event())
        self.assertNotIn('PRIVATE_', str(caught.exception))
        self.assertNotIn('PRIVATE_', json.dumps(backend.status()))
        self.assertFalse(backend.status()['connected'])

    def test_status_notices_a_process_that_has_exited(self):
        backend = self.backend()
        self.ask(backend)
        backend._process.terminate()
        backend._process.wait(timeout=3)
        self.assertFalse(backend.status()['connected'])
        self.assertNotIn('Connected', backend.status()['message'])

    def test_unrecognized_enabled_features_fail_closed(self):
        config = {'features': {name: False for name in self.module._DISABLED_FEATURES},
                  'mcp_servers': {}, 'plugins': {}, 'notify': [], 'web_search': 'disabled',
                  'approval_policy': 'never', 'sandbox_mode': 'read-only', 'approvals_reviewer': 'user'}
        config['features']['unknown_external_action'] = True
        with self.assertRaises(RuntimeError):
            self.module.CodexBackend._check_tools(config)

    def test_null_feature_config_can_be_verified_by_effective_feature_check(self):
        config = {'features': {name: False for name in self.module._DISABLED_FEATURES},
                  'mcp_servers': {}, 'plugins': {}, 'notify': [], 'web_search': 'disabled',
                  'approval_policy': 'never', 'sandbox_mode': 'read-only', 'approvals_reviewer': 'user'}
        config['features']['network_proxy'] = None
        self.module.CodexBackend._check_tools(config)

    def test_approval_and_unknown_tool_requests_are_denied_and_abort(self):
        for scenario in ('approval', 'unknown-tool'):
            with self.subTest(scenario=scenario):
                backend = self.backend(scenario)
                with self.assertRaises(RuntimeError):
                    self.ask(backend)
                responses = [row for row in self.requests() if row.get('id') == 'approval-1']
                # The refusal may be followed by immediate process teardown.
                for response in responses:
                    self.assertNotIn('accept', json.dumps(response))
                self.assertFalse(backend.status()['connected'])

    def test_precancel_does_not_start_a_process(self):
        backend = self.backend()
        cancel = threading.Event()
        cancel.set()
        with self.assertRaisesRegex(RuntimeError, '[Cc]ancel'):
            self.ask(backend, cancel)
        self.assertFalse(self.commands)

    def test_timeout_and_unacknowledged_cancel_are_bounded(self):
        backend = self.backend('waiting')
        with patch.object(self.module, 'TURN_TIMEOUT', .15):
            started = time.monotonic()
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                self.ask(backend)
            self.assertLess(time.monotonic() - started, 4)
            self.assertFalse(backend.status()['connected'])
        backend = self.backend('ignore-cancel')
        cancel = threading.Event()
        timer = threading.Timer(.6, cancel.set)
        timer.start()
        try:
            with patch.object(self.module, 'CANCEL_TIMEOUT', .15):
                started = time.monotonic()
                with self.assertRaisesRegex(RuntimeError, '[Cc]ancel'):
                    self.ask(backend, cancel)
                self.assertLess(time.monotonic() - started, 4)
                self.assertFalse(backend.status()['connected'])
        finally:
            timer.cancel()
            timer.join()

    def test_concurrent_ask_and_close_during_pending_turn(self):
        backend = self.backend('waiting')
        errors = []

        def ask():
            try:
                self.ask(backend)
            except RuntimeError as error:
                errors.append(str(error))

        worker = threading.Thread(target=ask)
        worker.start()
        deadline = time.monotonic() + 8
        while not self.requests('turn/start') and time.monotonic() < deadline:
            time.sleep(.02)
        try:
            self.assertTrue(self.requests('turn/start'))
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                self.ask(backend)
        finally:
            backend.close()
            worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertTrue(errors)
        self.assertFalse(backend.status()['connected'])

    def test_cancellation_interrupts_then_allows_new_owned_session(self):
        backend = self.backend('waiting')
        cancel = threading.Event()
        errors = []

        def ask():
            try:
                self.ask(backend, cancel)
            except RuntimeError as error:
                errors.append(str(error))

        worker = threading.Thread(target=ask)
        worker.start()
        deadline = time.monotonic() + 8
        while not self.requests('turn/start') and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(self.requests('turn/start'))
        cancel.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(errors and 'cancel' in errors[0].lower())
        self.assertEqual(self.requests('turn/interrupt')[0]['params'],
                         {'threadId': 'dedicated-thread', 'turnId': 'turn-1'})
        os.environ['FAKE_CODEX_SCENARIO'] = ''
        self.assertEqual(self.ask(backend)[0], 'Hello world.')

    def test_close_is_idempotent_and_prevents_more_questions(self):
        backend = self.backend()
        self.ask(backend)
        backend.close()
        backend.close()
        self.assertFalse(backend.status()['connected'])
        with self.assertRaisesRegex(RuntimeError, '[Cc]losed'):
            self.ask(backend)

    def test_reset_context_isolates_compilation_memory_and_preserves_configuration(self):
        backend = self.backend('memory', model='test-model')
        cancel = threading.Event()
        self.assertEqual(backend.ask('UNSELECTED_PRIVATE', lambda _: None, cancel), 'FRESH')
        self.assertIn('UNSELECTED_PRIVATE', backend.ask('Remember?', lambda _: None, cancel))
        old_process = backend._process
        old_workspace = Path(backend._session_dir.name)
        backend.reset_context()
        self.assertIsNotNone(old_process.poll())
        self.assertFalse(old_workspace.exists())
        self.assertFalse(backend.status()['connected'])
        self.assertEqual(backend.status()['model'], 'test-model')
        self.assertEqual(backend.ask('SELECTED_ONLY_COMPILATION', lambda _: None, cancel), 'FRESH')
        self.assertIsNot(backend._process, old_process)
        backend.reset_context()
        self.assertEqual(backend.ask('Next question', lambda _: None, cancel), 'FRESH')
        starts = self.requests('thread/start')
        self.assertEqual(len(starts), 3)
        self.assertTrue(all(row['params']['model'] == 'test-model' for row in starts))
        turns = self.requests('turn/start')
        for row in turns:
            self.assertEqual(row['params']['sandboxPolicy'], turns[0]['params']['sandboxPolicy'])
        self.assertEqual(turns[-1]['params']['sandboxPolicy']['access']['readableRoots'], [str(self.source.resolve())])
        self.assertTrue(all(command[0] == str(Path(sys.executable).resolve()) for command, _ in self.commands))
        methods = [row.get('method', '') for row in self.requests()]
        self.assertFalse(any('resume' in method or 'fork' in method or 'login' in method for method in methods))

    def test_reset_unused_context_is_idempotent_and_never_reopens_closed_backend(self):
        backend = self.backend()
        backend.reset_context()
        backend.reset_context()
        self.assertFalse(self.commands)
        self.assertEqual(self.ask(backend)[0], 'Hello world.')
        backend.close()
        count = len(self.commands)
        with self.assertRaisesRegex(RuntimeError, '[Cc]losed'):
            backend.reset_context()
        with self.assertRaisesRegex(RuntimeError, '[Cc]losed'):
            self.ask(backend)
        self.assertEqual(len(self.commands), count)

    def test_reset_rejects_active_question_without_interrupting_it(self):
        backend = self.backend('waiting')
        cancel = threading.Event()
        errors = []

        def ask():
            try:
                self.ask(backend, cancel)
            except RuntimeError as error:
                errors.append(str(error))

        worker = threading.Thread(target=ask)
        worker.start()
        deadline = time.monotonic() + 8
        while not self.requests('turn/start') and time.monotonic() < deadline:
            time.sleep(.02)
        try:
            self.assertTrue(self.requests('turn/start'))
            process = backend._process
            with self.assertRaisesRegex(RuntimeError, 'running|active'):
                backend.reset_context()
            self.assertIs(backend._process, process)
            self.assertIsNone(process.poll())
            self.assertFalse(self.requests('turn/interrupt'))
        finally:
            cancel.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(errors and 'cancel' in errors[0].lower())
        backend.reset_context()

    def test_question_cannot_start_while_reset_is_running(self):
        backend = self.backend()
        entered = threading.Event()
        release = threading.Event()
        errors = []
        stop = backend._stop

        def paused_stop():
            entered.set()
            release.wait(5)
            stop()

        def reset():
            try:
                backend.reset_context()
            except Exception as error:
                errors.append(error)

        with patch.object(backend, '_stop', side_effect=paused_stop):
            worker = threading.Thread(target=reset)
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    self.ask(backend)
                self.assertFalse(self.commands)
            finally:
                release.set()
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertFalse(errors)
        self.assertEqual(self.ask(backend)[0], 'Hello world.')

    def test_invalid_roots_and_models_never_echo_input(self):
        for kwargs in ({'roots': [self.cwd / 'PRIVATE_missing']}, {'model': 'PRIVATE_/secret'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError) as caught:
                self.module.CodexBackend(binary=sys.executable, cwd=self.cwd, **kwargs)
            self.assertNotIn('PRIVATE_', str(caught.exception))

    def test_discovery_honors_explicit_env_and_does_not_fallback_on_bad_override(self):
        with patch.dict(os.environ, {'CODEX_BIN': sys.executable}):
            backend = self.module.CodexBackend(cwd=self.cwd)
            self.addCleanup(backend.close)
            self.assertTrue(backend.status()['available'])
        with patch.dict(os.environ, {'CODEX_BIN': str(self.cwd / 'PRIVATE_missing.exe')}):
            backend = self.module.CodexBackend(cwd=self.cwd)
            self.addCleanup(backend.close)
            self.assertFalse(backend.status()['available'])
            self.assertNotIn('PRIVATE_', json.dumps(backend.status()))


if __name__ == '__main__':
    if '--fake-codex' in sys.argv:
        fake_codex()
    else:
        unittest.main()
