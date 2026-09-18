"""Start a local reader independently of the coding task's process lifetime."""
import base64
import ctypes
import json
import os
import subprocess
from ctypes import wintypes


class WindowsProcess:
    def __init__(self, pid):
        self.pid = pid
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.OpenProcess(0x100001 | 0x1000, False, pid)

    def poll(self):
        if not self.handle:
            return 1
        code = wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return None if code.value == 259 else code.value

    def terminate(self):
        if self.poll() is None and not self.kernel.TerminateProcess(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def wait(self, timeout):
        if self.handle and self.kernel.WaitForSingleObject(self.handle, int(timeout * 1000)) == 258:
            raise TimeoutError('Local server did not stop')

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def spawn(command, cwd):
    if os.name != 'nt':
        return subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    # CREATE_BREAKAWAY_FROM_JOB only escapes the innermost Windows job. A
    # local WMI launch avoids an outer kill-on-close job without changing it.
    payload = base64.b64encode(json.dumps({'command': subprocess.list2cmdline(command), 'cwd': str(cwd)}).encode()).decode()
    script = """$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$p = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('%s')) | ConvertFrom-Json
$startup = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]0}
$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$p.command;CurrentDirectory=$p.cwd;ProcessStartupInformation=$startup}
if ($result.ReturnValue -ne 0) {throw ('Background launch failed: ' + $result.ReturnValue)}
[string]$result.ProcessId
""" % payload
    encoded = base64.b64encode(script.encode('utf-16le')).decode()
    powershell = os.path.join(os.environ['SystemRoot'], 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('Windows could not start the local reader independently: ' + result.stderr.strip())
    return WindowsProcess(int(result.stdout.strip()))
