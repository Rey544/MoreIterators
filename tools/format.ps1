param(
    [ValidateSet('check', 'write')][string]$Mode = 'check',
    [string]$Dotnet = 'dotnet',
    [string[]]$Files = @(),
    [Parameter(Mandatory = $true)][string]$EvidenceDirectory
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$evidence = [IO.Path]::GetFullPath($EvidenceDirectory)
if ($evidence.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Keep formatting evidence outside the product source directory.'
}
if (Test-Path -LiteralPath $evidence) {
    throw 'Use a new evidence directory; previous results are preserved.'
}
$dotnetCommand = (Get-Command $Dotnet -ErrorAction Stop).Source
$previousDotnetRoot = $env:DOTNET_ROOT
$previousTelemetry = $env:DOTNET_CLI_TELEMETRY_OPTOUT
$previousCertificate = $env:DOTNET_GENERATE_ASPNET_CERTIFICATE
$env:DOTNET_ROOT = [IO.Path]::GetDirectoryName($dotnetCommand)
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:DOTNET_GENERATE_ASPNET_CERTIFICATE = 'false'
$utf8 = [Text.UTF8Encoding]::new($false, $true)
$exitCode = 0
Push-Location $root
try {
    $sdk = (& $dotnetCommand --version).Trim()
    if ($LASTEXITCODE -ne 0 -or $sdk -ne '8.0.419') { throw 'Formatting requires the pinned .NET SDK 8.0.419.' }
    & $dotnetCommand tool restore
    if ($LASTEXITCODE -ne 0) { throw 'Could not restore the pinned formatter.' }
    & $dotnetCommand restore 'tools/format-guard/FormatGuard.csproj' --locked-mode
    if ($LASTEXITCODE -ne 0) { throw 'Could not restore the locked token guard.' }
    & $dotnetCommand build 'tools/format-guard/FormatGuard.csproj' --no-restore --configuration Release --verbosity quiet
    if ($LASTEXITCODE -ne 0) { throw 'Could not build the token guard.' }
    $guard = Join-Path $root 'tools/format-guard/bin/Release/net8.0/FormatGuard.dll'

    $allowed = @(Get-ChildItem -LiteralPath (Join-Path $root 'src') -Filter '*.cs')
    $allowed += @(Get-ChildItem -LiteralPath (Join-Path $root 'templates/standalone') -Filter '*.cs')
    $relativeFiles = @($allowed | ForEach-Object { [IO.Path]::GetRelativePath($root, $_.FullName).Replace('\', '/') } | Sort-Object)
    if ($Files.Count -gt 0) {
        foreach ($file in $Files) {
            if ($relativeFiles -cnotcontains $file) { throw "File is outside the formatting scope: $file" }
        }
        $relativeFiles = @($Files | Sort-Object -Unique)
    }
    $before = Join-Path $evidence 'before'
    $candidate = Join-Path $evidence 'candidate'
    $after = Join-Path $evidence 'after'
    $inputHashes = [ordered]@{}
    foreach ($relative in $relativeFiles) {
        foreach ($directory in @($before, $candidate, $after)) {
            New-Item -ItemType Directory -Path (Split-Path (Join-Path $directory $relative)) -Force | Out-Null
        }
        $original = Join-Path $root $relative
        $inputHashes[$relative] = (Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash.ToLowerInvariant()
        Copy-Item -LiteralPath $original -Destination (Join-Path $before $relative)
        $text = [IO.File]::ReadAllText($original, $utf8)
        if ($relative -eq 'templates/standalone/CreatorRuntime.cs') {
            if ([regex]::Matches($text, '(?m)^\s*__ENCOUNTER__\s*$').Count -ne 1) { throw 'Expected one encounter placeholder.' }
            $text = $text.Replace('__ENCOUNTER__', '/*ENCOUNTER*/')
        }
        [IO.File]::WriteAllText((Join-Path $candidate $relative), $text, $utf8)
    }
    [IO.File]::WriteAllText((Join-Path $evidence 'input-hashes.json'), ($inputHashes | ConvertTo-Json), $utf8)
    Copy-Item -LiteralPath (Join-Path $root '.editorconfig') -Destination (Join-Path $candidate '.editorconfig')
    & $dotnetCommand format whitespace $candidate --folder --verbosity minimal
    if ($LASTEXITCODE -ne 0) { throw 'Whitespace normalization failed; no production files were changed.' }
    & $dotnetCommand csharpier format $candidate --config-path (Join-Path $root '.csharpierrc.json') --include-generated
    if ($LASTEXITCODE -ne 0) { throw 'Formatter rejected an input; no production files were changed.' }
    & $dotnetCommand format whitespace $candidate --folder --verbosity minimal
    if ($LASTEXITCODE -ne 0) { throw 'Final whitespace normalization failed; no production files were changed.' }
    foreach ($relative in $relativeFiles) {
        $candidateFile = Join-Path $candidate $relative
        if ($relative -eq 'templates/standalone/CreatorRuntime.cs') {
            $text = [IO.File]::ReadAllText($candidateFile, $utf8)
            if ([regex]::Matches($text, '/\*ENCOUNTER\*/').Count -ne 1) { throw 'Encounter placeholder was altered.' }
            [IO.File]::WriteAllText($candidateFile, $text.Replace('/*ENCOUNTER*/', '__ENCOUNTER__'), $utf8)
        }
        & $dotnetCommand $guard preserve-format (Join-Path $before $relative) $candidateFile (Join-Path $after $relative) > (Join-Path $after ($relative + '.guard.json'))
        if ($LASTEXITCODE -ne 0) { throw "Token or comment preservation failed: $relative" }
    }
    & $dotnetCommand $guard check $before $after --output (Join-Path $evidence 'equivalence.json')
    if ($LASTEXITCODE -ne 0) { throw 'All-branch equivalence failed; no production files were changed.' }
    $changed = @()
    foreach ($relative in $relativeFiles) {
        $original = Join-Path $root $relative
        if ((Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputHashes[$relative]) {
            throw "Source changed during formatting; no write is allowed: $relative"
        }
        if ((Get-FileHash -LiteralPath (Join-Path $after $relative) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputHashes[$relative]) {
            $changed += $relative
        }
    }
    if ($Mode -eq 'write') {
        foreach ($relative in $changed) { Copy-Item -LiteralPath (Join-Path $after $relative) -Destination (Join-Path $root $relative) }
    } elseif ($changed.Count -gt 0) { $exitCode = 1 }
    $summary = [ordered]@{ mode = $Mode; sdk = $sdk; formatter = 'CSharpier 1.2.2'; selected = $relativeFiles.Count; changed = $changed; tokenEquivalent = $true; applied = ($Mode -eq 'write') }
    [IO.File]::WriteAllText((Join-Path $evidence 'result.json'), ($summary | ConvertTo-Json -Depth 5), $utf8)
    $summary | ConvertTo-Json -Depth 5
} finally {
    Pop-Location
    $env:DOTNET_ROOT = $previousDotnetRoot
    $env:DOTNET_CLI_TELEMETRY_OPTOUT = $previousTelemetry
    $env:DOTNET_GENERATE_ASPNET_CERTIFICATE = $previousCertificate
}
exit $exitCode
