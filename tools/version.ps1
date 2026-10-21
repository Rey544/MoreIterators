param([Parameter(Mandatory=$true)][string]$ProjectRoot)
$ErrorActionPreference = 'Stop'
$v = Get-Content -LiteralPath (Join-Path $ProjectRoot 'version.json') -Raw | ConvertFrom-Json
if ($v.version -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-(dev|alpha|beta|rc)\.(0|[1-9]\d*))?$') { throw 'Use a semantic version such as X.Y.Z.' }
$base = $v.version.Split('-')[0]
if ($v.pluginVersion -ne $base -or $v.assemblyVersion -ne ($base + '.0')) { throw 'Plugin and assembly versions must match the semantic base version.' }
$manifestPath = Join-Path $ProjectRoot 'mod\modinfo.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.id -ne 'moreiterators.core') { throw 'This version tool only supports MoreIterators core.' }
$manifest.version = $v.version
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 20) + [Environment]::NewLine, $utf8)
$info = @"
using System.Reflection;
[assembly: AssemblyVersion("$($v.assemblyVersion)")]
[assembly: AssemblyFileVersion("$($v.assemblyVersion)")]
[assembly: AssemblyInformationalVersion("$($v.version)")]
namespace MoreIterators {
 public static class BuildVersion {
  public const string Plugin = "$($v.pluginVersion)";
  public const string Display = "$($v.version)";
 }
}
"@
[IO.File]::WriteAllText((Join-Path $ProjectRoot 'src\BuildVersion.cs'), $info + [Environment]::NewLine, $utf8)
