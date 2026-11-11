# Starts the career coach on Windows. Run by "Start Coach (Windows).cmd".
#
# Each time it: checks Claude Code and Python are installed (and offers to
# install what is missing), then opens your tracker sheet and the coach.
# The first time, it also opens the two pages where you connect Google Drive
# and Chrome. Nothing is installed without asking first.
#
#   -DryRun   print what would be opened or started, and start nothing

param([switch]$DryRun)

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

Step "Starting the coach..."
if ($DryRun) { Say "[dry run] would run: claude --chrome `"$prompt`""; exit 0 }
claude --chrome $prompt
