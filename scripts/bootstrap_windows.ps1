#requires -version 5.1
<#
.SYNOPSIS
    One-command bootstrap for this repository on Windows.

.DESCRIPTION
    Prepares a checkout with the toolchain this project actually needs and then
    starts the application:

      1. find (or install) Python 3.10 - the project does not run on 3.13;
      2. `uv sync` the workspace, skipping llama-cpp-python (no Windows wheel);
      3. copy `.env.example` to `.env` when `.env` is missing - never overwrite;
      4. point the temp directories at the checkout;
      5. wait for the port to answer, then open the browser, and start `app.py`.

    Written in plain ASCII on purpose: PowerShell 5.1 reads a BOM-less script as
    ANSI/GBK, so a non-ASCII character anywhere would break parsing on this host.

.PARAMETER NoStart
    Do everything except starting the app (used to verify the setup step alone).

.PARAMETER SkipSync
    Skip `uv sync` (environment already prepared). This is also the default whenever
    `.venv\Scripts\python.exe` already exists.

.PARAMETER ForceSync
    Run `uv sync` even when the environment already exists (first deploy, lock change).

.PARAMETER NoBrowser
    Do not open a browser window (headless checks, remote sessions).

.EXAMPLE
    .\scripts\bootstrap_windows.ps1

.EXAMPLE
    .\scripts\bootstrap_windows.ps1 -NoStart
#>
[CmdletBinding()]
param(
    [switch] $NoStart,
    [switch] $SkipSync,
    [switch] $ForceSync,
    [switch] $NoBrowser
)

$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string] $Message)
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Note {
    param([string] $Message)
    Write-Host "    $Message" -ForegroundColor DarkGray
}

function Write-Warn {
    param([string] $Message)
    Write-Host "    WARN: $Message" -ForegroundColor Yellow
}

function Invoke-Uv {
    # Run uv through cmd so its own error lines reach both the window and the
    # transcript: native stderr is not captured by Start-Transcript on PowerShell 5.1,
    # which would leave a failed run with only our own "uv sync failed" line.
    param([string[]] $Arguments)
    $commandLine = 'uv ' + ($Arguments -join ' ')
    $output = cmd /c "$commandLine 2>&1"
    $code = $LASTEXITCODE
    $output | ForEach-Object { Write-Host "    $_" }
    return $code
}

# The script lives in <repo>/scripts, so the checkout is its parent.
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
Write-Step "repository: $RepoRoot"

# Keep a transcript: a double-clicked window that closes on failure leaves nothing to
# read, and "it failed" without the message cannot be diagnosed (MODIFICATIONS 5.6).
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$LogDir = Join-Path $RepoRoot 'ktem_app_data\logs'
$Transcript = $null
try {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $Transcript = Join-Path $LogDir ("bootstrap-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    Start-Transcript -Path $Transcript -Force | Out-Null
} catch {
    $Transcript = $null
    Write-Warn 'could not start a transcript; the window output is all there is'
}

# --------------------------------------------------------------------------- #
# 1. toolchain
# --------------------------------------------------------------------------- #
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is not on PATH. Install it first: https://docs.astral.sh/uv/getting-started/installation/"
}

Write-Step 'checking Python 3.10'
$Python = (& uv python find 3.10 2>$null)
if (-not $Python) {
    Write-Note 'not found - installing it through uv'
    if ((Invoke-Uv @('python', 'install', '3.10')) -ne 0) {
        throw 'uv python install 3.10 failed (see the uv output above)'
    }
    $Python = (& uv python find 3.10 2>$null)
}
if (-not $Python) { throw 'Python 3.10 is still not available after installing it' }
Write-Note $Python

# --------------------------------------------------------------------------- #
# 2. dependencies
# --------------------------------------------------------------------------- #
$HasEnv = Test-Path $VenvPython

if ($SkipSync) {
    Write-Step 'skipping dependency sync (-SkipSync)'
} elseif ($HasEnv -and -not $ForceSync) {
    # The common double-click: the environment is already installed. Running `uv sync`
    # here needs the network and can fail for reasons that have nothing to do with
    # starting the app, so it is skipped unless asked for.
    Write-Step 'environment already exists - skipping uv sync'
    Write-Note ("python: {0}" -f $VenvPython)
    Write-Note 'use -ForceSync to re-sync dependencies (needs network)'
} else {
    Write-Step 'syncing dependencies (llama-cpp-python is skipped: no Windows wheel)'
    $syncArgs = @('sync', '--python', '3.10', '--no-install-package', 'llama-cpp-python')

    # --locked keeps a shipped lockfile authoritative; if it is out of date, say so
    # and fall back to a normal resolve instead of failing in the user's face.
    $lockedArgs = $syncArgs + '--locked'
    if ((Invoke-Uv $lockedArgs) -ne 0) {
        Write-Warn 'uv.lock is out of date with pyproject.toml - resolving it now'
        if ((Invoke-Uv $syncArgs) -ne 0) {
            throw 'uv sync failed (the uv error is in the lines above and in the log)'
        }
    }
}

if (-not $HasEnv) { throw "no virtual environment at $VenvPython" }

# --------------------------------------------------------------------------- #
# 3. configuration
# --------------------------------------------------------------------------- #
Write-Step 'checking .env'
$EnvFile = Join-Path $RepoRoot '.env'
$EnvExample = Join-Path $RepoRoot '.env.example'
if (Test-Path $EnvFile) {
    Write-Note '.env exists - leaving it untouched'
} elseif (Test-Path $EnvExample) {
    Copy-Item $EnvExample $EnvFile
    Write-Note 'created .env from .env.example'
    Write-Warn 'fill in DEEPSEEK_API_KEY (and DASHSCOPE_API_KEY for cloud embeddings) before asking questions'
} else {
    Write-Warn 'neither .env nor .env.example exists - the app will start with defaults'
}

# --------------------------------------------------------------------------- #
# 4. run
# --------------------------------------------------------------------------- #
# The app writes sqlite / LanceDB under ktem_app_data; pointing TMP/TEMP inside the
# checkout keeps the platform temp clean and avoids permission issues on this host.
$TempDir = Join-Path $RepoRoot 'ktem_app_data\tmp'
$FlowTempDir = Join-Path $RepoRoot 'flow_tmp'
New-Item -ItemType Directory -Force -Path $TempDir, $FlowTempDir | Out-Null
$env:TMP = $TempDir
$env:TEMP = $TempDir
$env:THEFLOW_TEMP_PATH = $FlowTempDir
$env:PYTHONIOENCODING = 'utf-8'

Write-Step 'environment'
Write-Note "TMP/TEMP         = $TempDir"
Write-Note "THEFLOW_TEMP_PATH= $FlowTempDir"

if ($NoStart) {
    Write-Step 'ready (-NoStart: not starting the app)'
    Write-Note "start it with: $VenvPython -X utf8 app.py"
    exit 0
}

# --------------------------------------------------------------------------- #
# 5. browser
# --------------------------------------------------------------------------- #
# Gradio opens the page itself when `inbrowser=True`, but the app can take a while to
# start and on some hosts `webbrowser.open` does nothing at all. Poll the port here and
# open the page only once it answers 200 - never a "connection refused" tab.
$AppPort = if ($env:GRADIO_SERVER_PORT) { $env:GRADIO_SERVER_PORT } else { '7860' }
$AppUrl = "http://127.0.0.1:$AppPort"
$BrowserLog = Join-Path $LogDir 'browser.log'

function Test-AppReady {
    param([string] $Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        return ($response.StatusCode -eq 200)
    } catch {
        return $false
    }
}

if (-not $NoBrowser) {
    if (Test-AppReady $AppUrl) {
        Write-Step "an instance is already serving $AppUrl"
        Write-Note 'opening the browser; close the old window first if you wanted a restart'
        Start-Process $AppUrl
        exit 0
    }

    $pollScript = {
        param($Url, $LogPath, $TimeoutSeconds)
        $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
        while ((Get-Date) -lt $deadline) {
            try {
                $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    try {
                        Start-Process $Url
                        Add-Content -Path $LogPath -Value ("{0} opened {1}" -f (Get-Date -Format 'HH:mm:ss'), $Url)
                    } catch {
                        Add-Content -Path $LogPath -Value ("{0} could not open {1}: {2}" -f (Get-Date -Format 'HH:mm:ss'), $Url, $_.Exception.Message)
                    }
                    return
                }
            } catch { }
            Start-Sleep -Milliseconds 700
        }
        Add-Content -Path $LogPath -Value ("{0} timeout after {1}s waiting for {2}" -f (Get-Date -Format 'HH:mm:ss'), $TimeoutSeconds, $Url)
    }
    $browserJob = Start-Job -ScriptBlock $pollScript -ArgumentList $AppUrl, $BrowserLog, 240
    Write-Note 'the browser opens as soon as the port answers (job in the background)'
}

# Let the app own the browser decision: the launcher has already taken care of it.
$env:KH_OPEN_BROWSER_ON_START = '0'

Write-Step "starting the application on $AppUrl"
Write-Note 'stop it with Ctrl+C; the index lives in ktem_app_data/user_data'
if ($Transcript) { Write-Note "launcher log: $Transcript" }

# Tee the app output: the launcher's own log stops at this point, so a crash inside
# the app (an import error, a busy port) would otherwise only scroll past in a window
# that closes. -u keeps the lines flowing instead of arriving at exit.
#
# The launch goes through cmd on purpose: with `$ErrorActionPreference = 'Stop'`, a
# native command that merely writes to stderr (the app prints nltk/absl warnings there)
# is turned into a terminating error and would kill the launcher before the app starts.
$AppLog = Join-Path $LogDir 'app.log'
Write-Note "app log     : $AppLog"
$appCommand = '"{0}" -X utf8 -u app.py 2>&1' -f $VenvPython
cmd /c $appCommand | Tee-Object -FilePath $AppLog -Append
$AppExit = $LASTEXITCODE

if ($browserJob) {
    Stop-Job $browserJob -ErrorAction SilentlyContinue
    Remove-Job $browserJob -Force -ErrorAction SilentlyContinue
}

if ($Transcript) {
    Write-Step "application exited with code $AppExit"
    Write-Note "launcher log: $Transcript"
    Write-Note "app log     : $AppLog"
}
exit $AppExit
