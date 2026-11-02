"""User-requested Windows file picker for the two executable locations."""
import json
import os
from pathlib import Path
import subprocess
import threading

_active = threading.Lock()
_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Windows.Forms
$picker = New-Object System.Windows.Forms.OpenFileDialog
try {
    $picker.Filter = 'Executable (*.exe)|*.exe'
    $picker.CheckFileExists = $true
    $picker.Multiselect = $false
    if (Test-Path -LiteralPath $env:MI_PATH_PICKER_START -PathType Container) {
        $picker.InitialDirectory = $env:MI_PATH_PICKER_START
    }
    $picker.FileName = $env:MI_PATH_PICKER_NAME
    if ($picker.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        ConvertTo-Json -InputObject $picker.FileName -Compress
    } else { 'null' }
} finally { $picker.Dispose() }
'''

def choose(kind, current=''):
    if kind not in ('game', 'rained'):
        raise ValueError('Unknown installation path.')
    if os.name != 'nt':
        raise ValueError('File selection is available on Windows.')
    if not _active.acquire(blocking=False):
        raise ValueError('A file selection window is already open.')
    try:
        start = Path(current) if current else Path.home()
        if start.is_file():
            start = start.parent
        env = dict(os.environ, MI_PATH_PICKER_START=str(start),
                   MI_PATH_PICKER_NAME='RainWorld.exe' if kind == 'game' else 'Rained.exe')
        shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        result = subprocess.run([str(shell), '-NoProfile', '-STA', '-Command', _SCRIPT],
                                env=env, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise ValueError('The file selection window could not be opened.')
        return json.loads(result.stdout.decode('utf-8-sig').strip())
    finally:
        _active.release()
