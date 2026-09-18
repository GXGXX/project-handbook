import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'project-handbook/scripts'))
from build_flow import build


class LaunchTests(unittest.TestCase):
    def test_background_server_outlives_launcher_and_job(self):
        with tempfile.TemporaryDirectory() as temp:
            book = Path(temp) / 'book with spaces'
            build(json.loads((ROOT / 'project-handbook/assets/damage.example.json').read_text(encoding='utf-8')), book)
            pid = None
            try:
                result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'project-handbook/scripts/flow_server.py'),
                                         str(book), '--background'], capture_output=True, text=True, timeout=25)
                self.assertEqual(result.returncode, 0, result.stderr)
                ready = json.loads((book / '.flow-server.json').read_text(encoding='utf-8'))
                pid = ready['pid']
                self.assertIn(ready['url'], result.stdout)
                with urlopen(ready['url'] + '/api/session', timeout=5) as response:
                    session = json.load(response)
                self.assertEqual(session['pid'], pid)
                self.assertNotIn(session['token'], (book / '.flow-server.json').read_text(encoding='utf-8'))
                self.assertNotIn(session['token'], result.stdout)
                if os.name == 'nt':
                    from ctypes import wintypes
                    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                    kernel.OpenProcess.restype = wintypes.HANDLE
                    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
                    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                    handle = kernel.OpenProcess(0x1000, False, pid)
                    self.assertTrue(handle)
                    try:
                        inside = wintypes.BOOL()
                        self.assertTrue(kernel.IsProcessInJob(handle, None, ctypes.byref(inside)))
                        self.assertFalse(inside.value, 'Helper must not be killed when the task job closes')
                    finally:
                        kernel.CloseHandle(handle)
                duplicate = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'project-handbook/scripts/flow_server.py'),
                                            str(book), '--background'], capture_output=True, text=True, timeout=25)
                self.assertNotEqual(duplicate.returncode, 0)
                self.assertEqual(json.loads((book / '.flow-server.json').read_text(encoding='utf-8'))['pid'], pid)
            finally:
                if pid is not None:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, check=True)
                    else:
                        import signal
                        os.kill(pid, signal.SIGTERM)
                    time.sleep(.2)
