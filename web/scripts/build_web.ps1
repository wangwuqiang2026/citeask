# Build the citeask SPA and optionally copy it into the Python package.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_web.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_web.ps1 -CopyToPackage
#
# The FastAPI host prefers the checkout-local web/dist and falls back to the
# copy inside libs/ktem/ktem/web/dist, so copying is only needed for packaging.

param(
    [switch]$CopyToPackage
)

$ErrorActionPreference = "Stop"

$webRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $webRoot
Set-Location $webRoot

if (-not $env:npm_config_cache) {
    $env:npm_config_cache = Join-Path $repoRoot "ktem_app_data\tmp\npm-cache"
}
New-Item -ItemType Directory -Force $env:npm_config_cache | Out-Null

npm install --ignore-scripts
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$dist = Join-Path $webRoot "dist"
if (-not (Test-Path (Join-Path $dist "index.html"))) {
    Write-Error "build did not produce $dist\index.html"
    exit 1
}

if ($CopyToPackage) {
    $target = Join-Path $repoRoot "libs\ktem\ktem\web\dist"
    New-Item -ItemType Directory -Force $target | Out-Null
    Copy-Item (Join-Path $dist "*") $target -Recurse -Force
    Write-Host "copied $dist -> $target"
}

Write-Host "done: $dist"
