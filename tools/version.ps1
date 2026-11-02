param([Parameter(Mandatory=$true)][string]$ProjectRoot)
$ErrorActionPreference='Stop'
$v=Get-Content -LiteralPath (Join-Path $ProjectRoot 'version.json') -Raw | ConvertFrom-Json
if($v.version -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-(dev|alpha|beta|rc)\.(0|[1-9]\d*))?$'){throw 'Use X.Y.Z or X.Y.Z-dev.N / alpha.N / beta.N / rc.N'}
$base=$v.version.Split('-')[0]
if($v.pluginVersion -ne $base -or $v.assemblyVersion -ne ($base+'.0')){throw 'Plugin/assembly versions must match the semantic base version'}
$manifestPath=Join-Path $ProjectRoot 'mod\modinfo.json'
$manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$manifest.version=$v.version
$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$namespace=if($manifest.id -eq 'moreiterators.core'){'MoreIterators'}else{'EOE'}
$info=@"
using System.Reflection;
[assembly: AssemblyVersion("$($v.assemblyVersion)")]
[assembly: AssemblyFileVersion("$($v.assemblyVersion)")]
[assembly: AssemblyInformationalVersion("$($v.version)")]
namespace $namespace {
 public static class BuildVersion {
  public const string Plugin = "$($v.pluginVersion)";
  public const string Display = "$($v.version)";
 }
}
"@
Set-Content -LiteralPath (Join-Path $ProjectRoot 'src\BuildVersion.cs') -Value $info -Encoding UTF8
