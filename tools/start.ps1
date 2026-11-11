# Starts the career coach on Windows. Run by "Start Coach - Windows.cmd".
#
# Each time it: checks Claude Code and Python are installed (and offers to
# install what is missing), then opens your tracker sheet and the coach.
# The first time, it also opens the two pages where you connect Google Drive
# and Chrome. Nothing is installed without asking first.
#
# Where the coach opens: if the Orca app is installed and this folder is open
# in it, the coach opens as a "Career Coach" tab in Orca. Otherwise it opens
# right here in this window.
#
#   -DryRun          print what would be opened or started, and start nothing
#   -NoOrca          open the coach in this window even if Orca is installed
#   -CoachCommand    run this command instead of Claude (for testing the launcher)

param([switch]$DryRun, [switch]$NoOrca, [string]$CoachCommand)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Have($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Say($text) { Write-Host "  $text" }
function Step($text) { Write-Host ""; Write-Host "  $text" -ForegroundColor Cyan }
function Open-Page($url) { if ($DryRun) { Say "[dry run] would open $url" } else { Start-Process $url } }

Write-Host ""
Write-Host "  Career Coach" -ForegroundColor Green

# ---- 1. Claude Code ---------------------------------------------------------
if (-not (Have 'claude')) {
    Step "Claude Code is not installed yet."
    Say "It is the program the coach runs in. You need a paid Claude plan to sign in."
    $answer = if ($DryRun) { 'n' } else { Read-Host "  Install it now? (Y/n)" }
    if ($answer -notmatch '^[nN]') {
        Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
        $env:Path += ";$env:USERPROFILE\.local\bin"
    }
    if (-not (Have 'claude')) {
        Step "Claude Code is still not available in this window."
        Say "Close this window and double-click Start Coach again."
        Say "To install it by hand, see SETUP.md, step 1."
        if (-not $DryRun) { Read-Host "  Press Enter to close" | Out-Null }
        exit 1
    }
}

# ---- 2. Python and the PDF checker's one package ----------------------------
$python = $null
foreach ($candidate in 'python', 'py', 'python3') {
    if (Have $candidate) {
        & $candidate --version *> $null
        if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
    }
}
if (-not $python) {
    Step "Python is not installed."
    Say "The coach uses it to measure your resume PDF. Everything else works without it."
    if (Have 'winget') {
        $answer = if ($DryRun) { 'n' } else { Read-Host "  Install Python now? (Y/n)" }
        if ($answer -notmatch '^[nN]') {
            winget install -e --id Python.Python.3.13
            Say "Python was installed. It will be picked up the next time you start the coach."
        }
    } else {
        Say "Download it from https://www.python.org/downloads/ and start the coach again."
    }
} else {
    & $python -c "import pdfminer" *> $null
    if ($LASTEXITCODE -ne 0) {
        Step "Installing the resume checker's one Python package..."
        if ($DryRun) { Say "[dry run] would run: $python -m pip install -r tools\requirements.txt" }
        else { & $python -m pip install --quiet -r tools\requirements.txt }
    }
}

# ---- 3. First run, or a normal day ------------------------------------------
if (-not (Test-Path 'coach\COACH.md')) {
    Step "First time here. Two things to connect, once:"
    Say "1. Google Drive, so the coach can read your tracker sheet."
    Say "      On the page that opens, add Google Drive and sign in."
    Say "2. The Claude extension for Chrome, so the coach can add rows to your sheet."
    Say "      On the page that opens, click Add to Chrome and sign in."
    $answer = if ($DryRun) { '' } else { Read-Host "  Press Enter to open both pages (or type s to skip)" }
    if ($answer -notmatch '^[sS]') {
        Open-Page 'https://claude.ai/customize/connectors'
        Open-Page 'https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn'
        if (-not $DryRun) { Read-Host "  When both are connected, press Enter to meet your coach" | Out-Null }
    }
    $prompt = 'set me up'
} else {
    $sheet = $null
    if (Test-Path 'coach\tracker.md') {
        $match = Select-String -Path 'coach\tracker.md' -Pattern 'https://docs\.google\.com/spreadsheets/[^\s)>]+' |
            Select-Object -First 1
        if ($match) { $sheet = $match.Matches[0].Value }
    }
    if ($sheet) { Open-Page $sheet }
    $prompt = 'Where are we?'
}

# ---- 4. Open the coach: in Orca when this folder is open there, else here -----
function Invoke-OrcaJson([string[]]$OrcaArgs) {
    # Returns the parsed reply, or $null when the call fails or is not JSON.
    try { & $script:orca @OrcaArgs --json 2>$null | Out-String | ConvertFrom-Json } catch { $null }
}

function Start-InOrca([string]$command) {
    # True when the coach was opened (or found already open) in Orca.
    $script:orca = if ($env:ORCA_CLI_COMMAND) { $env:ORCA_CLI_COMMAND } elseif (Have 'orca') { 'orca' } else { $null }
    if (-not $script:orca) { return $false }
    $selector = 'path:' + ($root -replace '\\', '/')

    $status = Invoke-OrcaJson @('status')
    $running = [bool]($status -and $status.ok -and $status.result.app.running)
    if ($DryRun -and -not $running) {
        Say "[dry run] Orca is installed but not running; would start it and open the coach there"
        return $true
    }
    if (-not $DryRun) {
        & $script:orca open --json *> $null      # starts Orca, or brings its window forward
        for ($i = 0; $i -lt 30; $i++) {
            $status = Invoke-OrcaJson @('status')
            if ($status -and $status.ok -and $status.result.runtime.reachable) { break }
            Start-Sleep -Seconds 1
        }
    }

    $shown = Invoke-OrcaJson @('worktree', 'show', '--worktree', $selector)
    if (-not ($shown -and $shown.ok)) {
        Say "Orca is installed, but this folder is not open in it, so the coach will open here."
        Say "(Add this folder as a project in Orca to have the coach open there next time.)"
        return $false
    }

    # Still open from last time? Then just switch to it.
    $stamp = Join-Path $root 'coach\.orca-terminal'
    if (Test-Path $stamp) {
        $handle = (Get-Content $stamp -Raw).Trim()
        $listed = Invoke-OrcaJson @('terminal', 'list', '--worktree', $selector)
        $term = $listed.result.terminals | Where-Object { $_.handle -eq $handle -and $_.connected } | Select-Object -First 1
        if ($term) {
            $pane = "$($term.tabId):$($term.leafId)"
            $agents = (Invoke-OrcaJson @('worktree', 'ps')).result.worktrees.agents
            $live = $agents | Where-Object { $_.paneKey -eq $pane -and $_.hasLivePty -ne $false } | Select-Object -First 1
            if ($live) {
                if ($DryRun) { Say "[dry run] the coach is already open in Orca; would switch to that tab" }
                else {
                    & $script:orca terminal switch --terminal $handle --json *> $null
                    Say "Your coach is already open in Orca."
                }
                return $true
            }
        }
    }

    if ($DryRun) { Say "[dry run] would open a Career Coach tab in Orca running: $command"; return $true }
    $created = Invoke-OrcaJson @('terminal', 'create', '--worktree', $selector, '--title', 'Career Coach',
                                 '--command', $command, '--focus')
    $handle = $created.result.terminal.handle
    if (-not ($created -and $created.ok -and $handle)) {
        Say "Could not open a tab in Orca, so the coach will open here."
        return $false
    }
    if (Test-Path (Join-Path $root 'coach')) { Set-Content -Path $stamp -Value $handle -Encoding ascii }
    Say "Your coach is open in Orca."
    return $true
}

Step "Starting the coach..."
$command = if ($CoachCommand) { $CoachCommand } else { "claude --chrome `"$prompt`"" }
if (-not $NoOrca) {
    if (Start-InOrca $command) { exit 0 }
}
if ($DryRun) { Say "[dry run] would run here: $command"; exit 0 }
if ($CoachCommand) { Invoke-Expression $CoachCommand } else { claude --chrome $prompt }
