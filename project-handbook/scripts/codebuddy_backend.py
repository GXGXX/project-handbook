"""Answer page questions through the CodeBuddy CLI (WorkBuddy's command line).

Each question runs one `codebuddy -p --output-format stream-json` with the
prompt on stdin, in an empty temporary folder, without `-y`. In headless mode
the CLI blocks file access, commands and network tools unless `-y` is given,
so the model only sees the prompt; source lookup stays with the bounded host
retriever, as with Codex. Sign-in stays with the CLI (browser login with the
user's own account); no key or credential passes through here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time

TURN_TIMEOUT = 300
MAX_LINE = 2 * 1024 * 1024
MAX_ANSWER = 1024 * 1024


def _model_name(value):
    if (isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,99}', value)
            and not value.lower().startswith(('sk-', 'bearer', 'eyj'))):
        return value
    return None


def discover_binary(binary=None):
    """The CodeBuddy CLI on this computer, or None."""
    explicit = binary or os.environ.get('CODEBUDDY_BIN')
    names = [explicit] if explicit else ['codebuddy', 'cbc']
    for name in names:
        found = shutil.which(str(name)) or (str(name) if explicit and Path(str(name)).is_file() else None)
        if found:
            return found
    return None


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(block.get('text', '') for block in content
                       if isinstance(block, dict) and block.get('type') == 'text' and isinstance(block.get('text'), str))
    return ''


class CodeBuddyBackend:
    name = 'CodeBuddy'

    def __init__(self, binary=None, model=None, cwd=None, roots=()):
        self._binary = discover_binary(binary)
        self._model = _model_name(model)
        self._operation = threading.Lock()
        self._process = None
        self._closed = False
        self._signed_in = None
        self._message = '' if self._binary else 'CodeBuddy executable not found. Install the CodeBuddy CLI or set CODEBUDDY_BIN.'

    def status(self):
        # Polling never starts the CLI: sign-in is only learned from a real question.
        return {'available': self._binary is not None and not self._closed,
                'connected': bool(self._binary) and self._signed_in is True and not self._closed,
                'model': self._model, 'message': self._message, 'name': self.name}

    def _command(self):
        command = [self._binary, '-p', '--output-format', 'stream-json']
        if self._model:
            command += ['--model', self._model]
        return command

    def ask(self, prompt, emit, cancel_event, schema=None):
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 256 * 1024:
            raise ValueError('Question must be nonempty text within the size limit.')
        if self._closed:
            raise RuntimeError('CodeBuddy backend closed.')
        if not self._binary:
            raise RuntimeError(self._message)
        if cancel_event.is_set():
            raise RuntimeError('Request cancelled.')
        if schema is not None:
            prompt += '\n\nReturn only the JSON object, matching this JSON schema:\n' + json.dumps(schema, ensure_ascii=False)
        if not self._operation.acquire(blocking=False):
            raise RuntimeError('A CodeBuddy request is already running.')
        try:
            with tempfile.TemporaryDirectory(prefix='flow-codebuddy-') as empty:
                return self._run(prompt, emit, cancel_event, empty)
        finally:
            self._operation.release()

    def _run(self, prompt, emit, cancel_event, cwd):
        env = {key: value for key, value in os.environ.items() if key != 'CODEBUDDY_IS_SANDBOX'}
        try:
            process = subprocess.Popen(
                self._command(), cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except OSError:
            self._message = 'CodeBuddy could not start.'
            raise RuntimeError(self._message) from None
        self._process = process
        lines, errors = queue.Queue(), []

        def read_out():
            for raw in iter(process.stdout.readline, b''):
                lines.put(raw[:MAX_LINE])
            lines.put(None)

        def read_err():
            errors.append(process.stderr.read(64 * 1024).decode('utf-8', 'replace'))

        threading.Thread(target=read_out, daemon=True).start()
        threading.Thread(target=read_err, daemon=True).start()
        try:
            process.stdin.write(prompt.encode('utf-8'))
            process.stdin.close()
        except OSError:
            pass
        shown, final, failed = '', None, None
        deadline = time.monotonic() + TURN_TIMEOUT
        try:
            while True:
                if cancel_event.is_set():
                    raise RuntimeError('Request cancelled.')
                if time.monotonic() > deadline:
                    raise RuntimeError('CodeBuddy request timed out.')
                try:
                    raw = lines.get(timeout=.2)
                except queue.Empty:
                    continue
                if raw is None:
                    break
                try:
                    event = json.loads(raw.decode('utf-8', 'replace'))
                except ValueError:
                    continue
                if not isinstance(event, dict):
                    continue
                kind = event.get('type')
                text = None
                if kind == 'assistant' and isinstance(event.get('message'), dict):
                    whole = _text_of(event['message'].get('content'))
                    # Whole messages repeat what streamed before; show only what is new.
                    text = whole[len(shown):] if whole.startswith(shown) else ('\n\n' + whole if shown else whole)
                elif kind == 'stream_event' and isinstance(event.get('event'), dict):
                    delta = event['event'].get('delta')
                    if isinstance(delta, dict) and delta.get('type') == 'text_delta':
                        text = delta.get('text')
                elif kind == 'result':
                    if event.get('is_error') or str(event.get('subtype', 'success')) != 'success':
                        failed = str(event.get('result') or event.get('error') or event.get('subtype') or 'failed')
                    elif isinstance(event.get('result'), str):
                        final = event['result']
                    break
                if isinstance(text, str) and text:
                    shown += text
                    if len(shown) > MAX_ANSWER:
                        raise RuntimeError('CodeBuddy answer too large.')
                    emit(text)
        finally:
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            for stream in (process.stdout, process.stderr):
                try:
                    stream.close()
                except OSError:
                    pass
            self._process = None
        detail = (failed or '') + ' ' + ' '.join(errors)
        if failed or (final is None and not shown):
            if re.search(r'log.?in|sign.?in|auth|unauthori[sz]ed|登录|未登录', detail, re.I):
                self._signed_in = False
                self._message = 'CodeBuddy sign-in required.'
            else:
                self._message = 'CodeBuddy request failed.'
            raise RuntimeError(self._message)
        self._signed_in, self._message = True, ''
        answer = final if final is not None else shown
        if final is not None and shown and final.startswith(shown) and len(final) > len(shown):
            emit(final[len(shown):])
        return answer

    def fresh_thread(self):
        """Every question already runs in its own CLI process."""

    def reset_context(self):
        """Nothing is kept between questions."""

    def close(self):
        self._closed = True
        process = self._process
        if process and process.poll() is None:
            process.kill()
