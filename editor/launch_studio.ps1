param(
    [string]$PythonExe = '',
    [ValidateSet('appearance','dialogue','pearls','broadcasts')][string]$Page = 'appearance',
    [switch]$CheckOnly,
    [switch]$CreateShortcut
)
$ErrorActionPreference = 'Stop'
$editorDirectory = $PSScriptRoot
$candidates = @()
if ($PythonExe) { $candidates += @{ Path=$PythonExe; Prefix=@() } }
elseif ($env:MORE_ITERATORS_PYTHON) { $candidates += @{ Path=$env:MORE_ITERATORS_PYTHON; Prefix=@() } }
else {
    foreach ($name in @('py.exe','python.exe','python3.exe')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command -and $command.Source -notlike '*\WindowsApps\*') {
            $candidates += @{ Path=$command.Source; Prefix=$(if($name -eq 'py.exe'){@('-3')}else{@()}) }
        }
    }
    foreach ($registryRoot in @('HKCU:\Software\Python\PythonCore','HKLM:\Software\Python\PythonCore','HKLM:\Software\WOW6432Node\Python\PythonCore')) {
        foreach ($version in @(Get-ChildItem -LiteralPath $registryRoot -ErrorAction SilentlyContinue)) {
            $key = Get-Item -LiteralPath ($version.PSPath+'\InstallPath') -ErrorAction SilentlyContinue
            if ($key) {
                $path = $key.GetValue('ExecutablePath')
                if (-not $path) { $base=$key.GetValue(''); if($base){$path = Join-Path $base 'python.exe'} }
                if ($path) { $candidates += @{ Path=$path; Prefix=@() } }
            }
        }
    }
}
$selected = ''
$probe = "import sys,PIL; assert sys.version_info >= (3,10); print('__MI_PYTHON__'+sys.executable)"
foreach ($candidate in $candidates) {
    try {
        $command = $candidate.Path
        $prefix = $candidate.Prefix
        $lines = @(& $command @prefix -c $probe 2>$null)
        if ($LASTEXITCODE -ne 0) { continue }
        $found = $lines | Where-Object { $_ -like '__MI_PYTHON__*' } | Select-Object -Last 1
        if ($found) {
            $path = $found.Substring('__MI_PYTHON__'.Length)
            if (Test-Path -LiteralPath $path -PathType Leaf) { $selected=$path; break }
        }
    } catch { }
}
if (-not $selected) {
    throw 'Python 3.10+ and Pillow are required. Install Python, then run: py -3 -m pip install -r editor/requirements.txt. You can also pass -PythonExe with your existing Python path.'
}
$windowless = Join-Path (Split-Path $selected -Parent) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $windowless -PathType Leaf)) { $windowless=$selected }
$script = Join-Path $editorDirectory 'studio_launcher.py'
if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw 'The editor launcher is missing. Extract the complete MI package first.' }
$arguments = '-B "'+$script+'" --page '+$Page
$icon = Join-Path $editorDirectory 'assets\studio.ico'
if (-not (Test-Path -LiteralPath $icon -PathType Leaf)) {
    throw 'The editor icon is missing. Extract the complete MI package again; keep editor/assets/studio.ico with the launcher.'
}
if ($CheckOnly) {
    [ordered]@{python=$selected;executable=$windowless;arguments=$arguments;editorDirectory=$editorDirectory;icon=$icon} | ConvertTo-Json
    return
}
if ($CreateShortcut) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path $desktop 'MI 外观编辑器.lnk'))
    $shortcut.TargetPath=$windowless
    $shortcut.Arguments=$arguments
    $shortcut.WorkingDirectory=$editorDirectory
    $shortcut.WindowStyle=7
    $shortcut.IconLocation=$icon+',0'
    $shortcut.Description='启动 More Iterators 外观编辑器'
    $shortcut.Save()
    return
}
Start-Process -FilePath $windowless -ArgumentList $arguments -WorkingDirectory $editorDirectory -WindowStyle Hidden | Out-Null
