# Ensures the Job Bot backend + Career Coach tabs exist in Orca.
# Tracks the terminals by handle (in data\) instead of by title, because
# Claude Code renames its own tab as the conversation goes on.

$ErrorActionPreference = 'SilentlyContinue'
$Root     = 'C:\ClaudeProjects\Job Bot'
$Selector = 'path:C:/ClaudeProjects/Job Bot'

function Get-LiveTerminals {
    try { (& orca terminal list --json 2>$null | ConvertFrom-Json).result.terminals } catch { @() }
}

function Ensure-Tab([string]$StampName, [string]$Title, [string]$Command, [bool]$Focus) {
    $stamp  = Join-Path $Root "data\$StampName"
    $handle = $null
    if (Test-Path $stamp) { $handle = (Get-Content $stamp -Raw).Trim() }

    if ($handle) {
        $match = Get-LiveTerminals | Where-Object { $_.handle -eq $handle -and $_.connected }
        if ($match) {
            Write-Host "  $Title is already open in Orca."
            if ($Focus) { & orca terminal switch --terminal $handle 2>$null | Out-Null }
            return
        }
    }

    Write-Host "  Opening $Title in Orca..."
    $argv = @('terminal','create','--worktree',$Selector,'--title',$Title,'--command',$Command,'--json')
    if ($Focus) { $argv += '--focus' }
    $created = & orca @argv 2>$null | ConvertFrom-Json
    $new = $created.result.terminal.handle
    if ($new) { Set-Content -Path $stamp -Value $new -Encoding ascii }
}

# --- Backend: only start one if nothing is answering on :8000 ---------------
$serverUp = $false
try {
    if ((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2).StatusCode -eq 200) {
        $serverUp = $true
    }
} catch {}

if ($serverUp) {
    Write-Host "  Backend is already running on http://localhost:8000."
} else {
    Ensure-Tab '.server-terminal' 'Job Bot Server' 'scripts\run-server.cmd' $false
}

# --- Career Coach -----------------------------------------------------------
Ensure-Tab '.coach-terminal' 'Career Coach' 'scripts\career-coach.cmd' $true
