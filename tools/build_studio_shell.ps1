param([string]$OutputPath = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (!(Test-Path -LiteralPath $compiler -PathType Leaf)) { throw '.NET Framework C# compiler was not found.' }
if (!$OutputPath) { $OutputPath = Join-Path $projectRoot 'editor\StudioShell.exe' }
$output = [IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Force -Path (Split-Path $output -Parent) | Out-Null
& $compiler /nologo /target:exe /platform:anycpu /optimize+ /debug- /reference:Microsoft.CSharp.dll "/out:$output" (Join-Path $PSScriptRoot 'StudioShell.cs')
if ($LASTEXITCODE -ne 0) { throw 'StudioShell compilation failed.' }
Write-Output "Built $output"
