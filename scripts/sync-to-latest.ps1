# Bring the app checkout up to the newest Job Bot code before the server starts.
#
# Rules, in order:
#   1. Never touch a dirty working tree - somebody is mid-edit, run what's there.
#   2. Fetch origin, but keep working offline if that fails.
#   3. Target the newer of local 'main' and 'origin/main' (whichever is a
#      descendant). If they've diverged, don't guess - leave it alone and say so.
#   4. Never move BACKWARD: only fast-forward to a descendant of the current HEAD.
#
# Rule 4 is the important one. The first version of this synced to local 'main'
# unconditionally, which would have rolled the app back two commits as soon as
# another session pushed to GitHub without updating the local branch.
param(
    [string]$Root = 'C:\ClaudeProjects\Job Bot'
)

# Resolve the real git.exe. Do NOT name this helper 'Git' - PowerShell resolves
# a bare 'git' call inside it back to the function itself and recurses forever.
$GitExe = (Get-Command git -CommandType Application -ErrorAction SilentlyContinue |
           Select-Object -First 1 -ExpandProperty Source)
if (-not $GitExe) { Write-Host "  [!] git not found on PATH - not updating."; exit 0 }

function Invoke-Git { & $GitExe -C $Root @args }

# --- 1. Dirty tree: run as-is -----------------------------------------------
$dirty = @(Invoke-Git status --porcelain --untracked-files=no)
if ($dirty.Count -gt 0) {
    Write-Host "  [!] Uncommitted changes here - running them as-is, not updating:"
    $dirty | Select-Object -First 5 | ForEach-Object { Write-Host "      $_" }
    $extra = $dirty.Count - 5
    if ($extra -gt 0) { Write-Host "      ...and $extra more" }
    exit 0
}

# --- 2. Fetch (offline is fine) ---------------------------------------------
Invoke-Git fetch --quiet origin main | Out-Null

# --- 3. Pick the newer of local main / origin-main ---------------------------
$local  = (Invoke-Git rev-parse --verify -q main)
$remote = (Invoke-Git rev-parse --verify -q origin/main)

if (-not $local -and -not $remote) { Write-Host "  [!] No 'main' branch found - not updating."; exit 0 }

if     (-not $remote) { $target = $local }
elseif (-not $local)  { $target = $remote }
else {
    Invoke-Git merge-base --is-ancestor $local $remote | Out-Null
    $localBehind = ($LASTEXITCODE -eq 0)
    Invoke-Git merge-base --is-ancestor $remote $local | Out-Null
    $remoteBehind = ($LASTEXITCODE -eq 0)

    if     ($localBehind)  { $target = $remote }
    elseif ($remoteBehind) { $target = $local }
    else {
        Write-Host "  [!] local 'main' and 'origin/main' have diverged - not updating."
        Write-Host "      Reconcile them by hand, then relaunch."
        exit 0
    }
}

# --- 4. Fast-forward only ----------------------------------------------------
$head = (Invoke-Git rev-parse HEAD)
if ($head -eq $target) { Write-Host "  Already on the latest code."; exit 0 }

Invoke-Git merge-base --is-ancestor $head $target | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [!] Newest branch is not ahead of what's checked out - not moving backward."
    exit 0
}

$short   = (Invoke-Git rev-parse --short $target)
$subject = (Invoke-Git log -1 --format=%s $target)
Write-Host "  Updating to $short - $subject"
Invoke-Git checkout --detach $target --quiet | Out-Null
exit 0
