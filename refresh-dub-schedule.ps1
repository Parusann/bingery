# Bingery dub-schedule refresh trigger
#
# Triggers the live Bingery admin sync (Crunchyroll RSS + AnimeSchedule.net +
# synthetic reproject) by POSTing to the in-process admin endpoint. This is a
# local backup to the daily GitHub Action (.github/workflows/refresh-schedule.yml)
# — handy if you'd rather drive the refresh from your own PC (like the Ollama
# tunnel) or run it on demand.
#
# It does NOT need Python or the repo — it's a single HTTPS POST.
#
# Setup (one time):
#   1. Restore real dub data first: set ANIMESCHEDULE_API_KEY on the server
#      (see docs/runbooks/dub-schedule.md). Without it, only Crunchyroll +
#      synthetic estimates are refreshed.
#   2. Provide the admin secret + URL via environment variables (preferred):
#        setx BINGERY_ADMIN_SECRET "your-admin-sync-secret"
#        setx BINGERY_URL          "https://bingery.fly.dev"   # optional, this is the default
#      (Open a NEW terminal after setx so the values are visible.)
#
# Run manually:
#   powershell -ExecutionPolicy Bypass -File ".\refresh-dub-schedule.ps1"
#
# Schedule monthly (or weekly) via Task Scheduler — see the runbook for the
# exact schtasks command.

[CmdletBinding()]
param(
    [string]$Url    = $env:BINGERY_URL,
    [string]$Secret = $env:BINGERY_ADMIN_SECRET
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Url)) { $Url = "https://bingery.fly.dev" }
$Url = $Url.TrimEnd("/")

if ([string]::IsNullOrWhiteSpace($Secret)) {
    Write-Error "BINGERY_ADMIN_SECRET is not set. Set it with: setx BINGERY_ADMIN_SECRET ""<secret>"" (then open a new terminal)."
    exit 1
}

# 1) Wake the Fly machine if it's been idle (first request after sleep is slow).
$awake = $false
for ($i = 1; $i -le 5; $i++) {
    try {
        Invoke-RestMethod -Method Get -Uri "$Url/api/health" -TimeoutSec 30 | Out-Null
        $awake = $true; break
    } catch {
        Write-Host "attempt $i: app not up yet, retrying in 5s..."
        Start-Sleep -Seconds 5
    }
}
if (-not $awake) { Write-Error "Bingery never responded at $Url/api/health"; exit 1 }

# 2) Run the syncs in-process on the live worker.
Write-Host "Triggering dub-source sync at $Url ..."
try {
    $resp = Invoke-RestMethod -Method Post -Uri "$Url/api/admin/sync-dub-sources" `
        -Headers @{ "X-Admin-Secret" = $Secret; "Content-Type" = "application/json" } `
        -TimeoutSec 600
} catch {
    Write-Error "Sync request failed: $($_.Exception.Message)"
    exit 1
}

$snap = $resp.snapshot
Write-Host ""
Write-Host "Done. Dub-date snapshot:"
if ($snap) {
    Write-Host ("  total dub episodes : {0}" -f $snap.total_dub_eps)
    Write-Host ("  airing next 7 days : {0}" -f $snap.next_7d)
    Write-Host ("  airing next 14 days: {0}" -f $snap.next_14d)
    if ($snap.by_source) {
        Write-Host "  by source:"
        $snap.by_source.PSObject.Properties | ForEach-Object {
            Write-Host ("    {0,-18}: {1}" -f $_.Name, $_.Value)
        }
    }
} else {
    $resp | ConvertTo-Json -Depth 6
}
exit 0
