$ErrorActionPreference = 'Stop'
$editorRoot = Join-Path (Split-Path $PSScriptRoot -Parent) 'editor'
$parts = @('broadcast-exchange.js', 'broadcast-icons.js', 'broadcast-editor.js')
$content = @()
foreach ($part in $parts) {
    $content += [IO.File]::ReadAllText((Join-Path $editorRoot $part))
}
[IO.File]::WriteAllText((Join-Path $editorRoot 'broadcasts.js'), ($content -join "`n") + "`n", (New-Object System.Text.UTF8Encoding($false)))
