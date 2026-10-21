param(
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$GameRoot,
    [string]$OutputPath = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$GameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$managed = Join-Path $GameRoot 'RainWorld_Data\Managed'
$names = @('Assembly-CSharp.dll','Assembly-CSharp-firstpass.dll','UnityEngine.dll','Unity.Mathematics.dll','UnityEngine.CoreModule.dll','UnityEngine.InputLegacyModule.dll','UnityEngine.JSONSerializeModule.dll','UnityEngine.ImageConversionModule.dll','UnityEngine.AudioModule.dll','UnityEngine.UnityWebRequestModule.dll','UnityEngine.UnityWebRequestAudioModule.dll','UnityEngine.IMGUIModule.dll','UnityEngine.TextRenderingModule.dll')
$referencePaths = @($names | ForEach-Object { Join-Path $managed $_ })
foreach ($name in @('BepInEx\core\BepInEx.dll','BepInEx\plugins\HOOKS-Assembly-CSharp.dll','BepInEx\core\MonoMod.Utils.dll','BepInEx\core\MonoMod.RuntimeDetour.dll','BepInEx\core\Mono.Cecil.dll')) {
    $referencePaths += Join-Path $GameRoot $name
}
foreach ($reference in $referencePaths) {
    if (!(Test-Path -LiteralPath $reference -PathType Leaf)) { throw "Missing game reference: $reference" }
}
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (!(Test-Path -LiteralPath $compiler -PathType Leaf)) { throw '.NET Framework C# compiler was not found.' }
& (Join-Path $PSScriptRoot 'version.ps1') -ProjectRoot $projectRoot
if (!$OutputPath) { $OutputPath = Join-Path $projectRoot 'mod\plugins\MoreIterators.dll' }
$output = [IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Force -Path (Split-Path $output -Parent) | Out-Null
$references = @($referencePaths | ForEach-Object { '/r:' + $_ })
$sources = (Get-ChildItem -LiteralPath (Join-Path $projectRoot 'src') -Filter '*.cs' -File).FullName
$resources = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'localization\game') -Filter '*.json' -File | ForEach-Object { '/resource:' + $_.FullName + ',mi.ui.' + $_.BaseName + '.json' })
& $compiler /nologo /target:library "/out:$output" $references $resources $sources
if ($LASTEXITCODE -ne 0) { throw 'MoreIterators compilation failed.' }
Write-Output "Built $output"
