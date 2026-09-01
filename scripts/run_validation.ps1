param(
    [Parameter(Mandatory = $true)]
    [string]$CSpyServerExe,

    [string]$LaunchJson = "",

    [switch]$SkipLive
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $CSpyServerExe)) {
    throw "CSpyServer2 executable not found: $CSpyServerExe"
}

$liveArgs = @("-q", "tests", "-m", "live", "--cspyserver2", $CSpyServerExe)

if ($LaunchJson -and -not (Test-Path -LiteralPath $LaunchJson)) {
    throw "Launch JSON not found: $LaunchJson"
}
if ($LaunchJson) {
    $liveArgs += @("--launch-json", $LaunchJson)
}

Write-Host "Running unit tests..." -ForegroundColor Cyan
pytest -q tests/test_server_tools_unit.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($SkipLive) {
    Write-Host "Skipping live tests (--SkipLive)." -ForegroundColor Yellow
    exit 0
}

Write-Host "Running live tests..." -ForegroundColor Cyan
pytest @liveArgs
exit $LASTEXITCODE
