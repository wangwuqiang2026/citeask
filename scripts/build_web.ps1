#requires -version 5.1
<#
.SYNOPSIS
    Build the React web UI (thin wrapper around web/scripts/build_web.ps1).

.DESCRIPTION
    The actual build lives next to the frontend sources so that it also works when
    only web/ is present. This wrapper exists because the repository README and
    the release notes refer to scripts/build_web.ps1 from the repository root.

    The output is web/dist, which app.py serves from a checkout. Use
    -CopyToPackage to also copy it into libs/ktem/ktem/web/dist for a wheel
    (that copy step is best effort: some sandboxed environments cannot write
    under libs/).

.PARAMETER CopyToPackage
    Also copy web/dist into libs/ktem/ktem/web/dist (for packaging).

.PARAMETER NoCopy
    Build only; skip the package copy even if -CopyToPackage was given.

.EXAMPLE
    .\scripts\build_web.ps1

.EXAMPLE
    .\scripts\build_web.ps1 -CopyToPackage
#>
[CmdletBinding()]
param(
    [switch] $CopyToPackage,
    [switch] $NoCopy
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$WebBuild = Join-Path $RepoRoot 'web\scripts\build_web.ps1'

if (-not (Test-Path $WebBuild)) {
    throw "web/scripts/build_web.ps1 not found - is this the repository root?"
}

$arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $WebBuild)
if ($CopyToPackage -and -not $NoCopy) {
    $arguments += '-CopyToPackage'
}

& powershell @arguments
exit $LASTEXITCODE
