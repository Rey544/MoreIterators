"""User-requested Windows file picker for the two executable locations."""
import json
import os
from pathlib import Path
import subprocess
import threading
import time

_active = threading.Lock()
_state_lock = threading.Lock()
_pending = None
_closing = False
_TIMEOUT_SECONDS = 300
_POLL_SECONDS = .25


class _PendingPicker:
    def __init__(self):
        self.process = None
        self.cancelled = False


def cancel_pending():
    
    global _closing
    with _state_lock:
        _closing = True
        pending = _pending
        if pending is None:
            return
        
        
        if pending.process is not None and pending.process.poll() is not None:
            return
        pending.cancelled = True


def _cancelled(pending):
    with _state_lock:
        return pending.cancelled


def _stop_and_collect(process):
    if process.poll() is None:
        try:
            process.terminate()
        except OSError:
            if process.poll() is None:
                raise
    return process.communicate()


def _wait(pending):
    process = pending.process
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while True:
        if _cancelled(pending):
            _stop_and_collect(process)
            return None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, _TIMEOUT_SECONDS)
        try:
            return process.communicate(timeout=min(_POLL_SECONDS, remaining))
        except subprocess.TimeoutExpired:
            pass


class PickerError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Windows.Forms
$picker = New-Object System.Windows.Forms.OpenFileDialog
$owner = New-Object System.Windows.Forms.Form
try {
    $owner.ShowInTaskbar = $false
    $owner.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $owner.Size = New-Object System.Drawing.Size(1, 1)
    $owner.Opacity = 0
    $owner.TopMost = $true
    $picker.AutoUpgradeEnabled = $false
    $picker.Filter = 'Executable (*.exe)|*.exe'
    $picker.CheckFileExists = $true
    $picker.Multiselect = $false
    if (Test-Path -LiteralPath $env:MI_PATH_PICKER_START -PathType Container) {
        $picker.InitialDirectory = $env:MI_PATH_PICKER_START
    }
    $picker.FileName = $env:MI_PATH_PICKER_NAME
    $owner.Show()
    $owner.Activate()
    if ($picker.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {
        ConvertTo-Json -InputObject $picker.FileName -Compress
    } else { 'null' }
} finally { $picker.Dispose(); $owner.Dispose() }
'''

def choose(kind, current=''):
    global _pending
    if kind not in ('game', 'rained'):
        raise ValueError('Unknown installation path.')
    if os.name != 'nt':
        raise ValueError('File selection is available on Windows.')
    if not _active.acquire(blocking=False):
        raise PickerError('paths.pickerBusy', 'A file selection window is already open.')
    pending = _PendingPicker()
    try:
        with _state_lock:
            if _closing:
                return None
            _pending = pending
        start = Path(current) if current else Path.home()
        if start.is_file():
            start = start.parent
        env = dict(os.environ, MI_PATH_PICKER_START=str(start),
                   MI_PATH_PICKER_NAME='RainWorld.exe' if kind == 'game' else 'Rained.exe')
        shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        try:
            if _cancelled(pending):
                return None
            process = subprocess.Popen([str(shell), '-NoProfile', '-STA', '-Command', _SCRIPT],
                                       env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            with _state_lock:
                pending.process = process
            result = _wait(pending)
        except subprocess.TimeoutExpired as error:
            _stop_and_collect(pending.process)
            if _cancelled(pending):
                return None
            raise PickerError('paths.pickerTimeout', 'File selection timed out. Please try again.') from error
        except OSError as error:
            if _cancelled(pending):
                return None
            raise PickerError('paths.pickerFailed', 'The file selection window could not be opened.') from error
        if result is None or _cancelled(pending):
            return None
        stdout, stderr = result
        if process.returncode:
            detail=(stderr or stdout).decode('utf-8-sig', errors='replace').strip()
            raise PickerError('paths.pickerFailed', 'The file selection window could not be opened.') from RuntimeError(detail)
        try:
            selected = json.loads(stdout.decode('utf-8-sig').strip())
            if selected is not None and not isinstance(selected, str):
                raise ValueError('Expected a selected path or cancellation.')
            return selected
        except (UnicodeError, ValueError) as error:
            raise PickerError('paths.pickerFailed', 'The file selection window could not be opened.') from error
    finally:
        try:
            if pending.process is not None and pending.process.poll() is None:
                _stop_and_collect(pending.process)
        finally:
            with _state_lock:
                if _pending is pending:
                    _pending = None
            _active.release()
