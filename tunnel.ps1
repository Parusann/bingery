<#
.SYNOPSIS
  One-command Bingery tunnel manager.

  Starts (or stops) the cloudflared quick-tunnel that exposes local Ollama
  (localhost:11434) to the Fly.io backend, and keeps the OLLAMA_BASE_URL
  Fly secret in sync with the rotating *.trycloudflare.com URL.

.PARAMETER Stop
  Stops the running cloudflared process(es). Leaves Ollama and Fly alone.

.PARAMETER Status
  Reports what's running locally and what Fly secret name is set.

.EXAMPLE
  .\tunnel.ps1            # bring tunnel up + sync Fly secret (~45s)
  .\tunnel.ps1 -Stop      # tear it down
  .\tunnel.ps1 -Status    # report state
#>
[CmdletBinding(DefaultParameterSetName='Up')]
param(
  [Parameter(ParameterSetName='Stop')]   [switch] $Stop,
  [Parameter(ParameterSetName='Status')] [switch] $Status
)

$ErrorActionPreference = 'Stop'

$CloudflaredExe = Join-Path $HOME '.cloudflared\cloudflared.exe'
$FlyctlExe      = Join-Path $HOME '.fly\bin\flyctl.exe'
$App            = 'bingery'
$Log            = Join-Path $env:TEMP 'cloudflared-bingery.log'

function Get-CloudflaredProcs {
  Get-Process cloudflared -ErrorAction SilentlyContinue
}

function Stop-Cloudflared {
  $procs = Get-CloudflaredProcs
  if (-not $procs) { Write-Host "cloudflared: not running"; return }
  foreach ($p in $procs) {
    Write-Host "Stopping cloudflared PID $($p.Id)"
    Stop-Process -Id $p.Id -Force
  }
  Start-Sleep -Seconds 1
  if (Get-CloudflaredProcs) { throw "cloudflared is still running after Stop-Process" }
  Write-Host "cloudflared: stopped"
}

function Test-OllamaUp {
  try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -UseBasicParsing -TimeoutSec 5
    return ($r.StatusCode -eq 200)
  } catch { return $false }
}

if ($Status) {
  Write-Host "--- Local ---"
  $procs = Get-CloudflaredProcs
  if ($procs) {
    foreach ($p in $procs) { Write-Host "cloudflared PID $($p.Id), started $($p.StartTime)" }
  } else { Write-Host "cloudflared: not running" }
  if (Test-OllamaUp) { Write-Host "ollama:      up on 11434" }
  else                { Write-Host "ollama:      NOT RESPONDING on 11434" }
  Write-Host ""
  Write-Host "--- Fly secret ---"
  # flyctl writes a benign "Metrics token unavailable" warning to stderr on
  # every call; under this script's EAP=Stop that surfaces as a terminating
  # NativeCommandError and aborts -Status before the secret prints. Relax EAP
  # locally and fold stderr into the captured text so the warning is inert.
  $prevEAP = $ErrorActionPreference
  $ErrorActionPreference = 'SilentlyContinue'
  $list = (& $FlyctlExe secrets list -a $App 2>&1 | Out-String) -split '\r?\n'
  $ErrorActionPreference = $prevEAP
  $line = $list | Select-String 'OLLAMA_BASE_URL'
  if ($line) { Write-Host $line.ToString().Trim() }
  else        { Write-Host "OLLAMA_BASE_URL: unset on Fly app '$App'" }
  return
}

if ($Stop) { Stop-Cloudflared; return }

# --- Up flow ---

if (-not (Test-Path $CloudflaredExe)) {
  throw "cloudflared not found at $CloudflaredExe. Reinstall, then retry."
}
if (-not (Test-Path $FlyctlExe)) {
  throw "flyctl not found at $FlyctlExe. Reinstall, then retry."
}
if (-not (Test-OllamaUp)) {
  throw "Ollama isn't responding on http://127.0.0.1:11434. Start Ollama first, then retry."
}

if (Get-CloudflaredProcs) {
  Write-Host "An existing cloudflared is running -- stopping it first so URLs don't collide."
  Stop-Cloudflared
}

Write-Host "Starting cloudflared quick-tunnel..."
Remove-Item $Log -ErrorAction SilentlyContinue
$null = Start-Process -FilePath $CloudflaredExe `
  -ArgumentList @('tunnel','--url','http://localhost:11434') `
  -RedirectStandardError $Log `
  -WindowStyle Hidden -PassThru

$pattern = 'https://[\w-]+\.trycloudflare\.com'
$url = $null
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  if (Test-Path $Log) {
    $m = Select-String -Path $Log -Pattern $pattern -ErrorAction SilentlyContinue |
         Select-Object -First 1
    if ($m) { $url = $m.Matches.Value; break }
  }
}
if (-not $url) {
  throw "Timed out waiting for cloudflared to publish a URL. Check log: $Log"
}
Write-Host "Tunnel URL: $url"

Write-Host "Updating Fly secret OLLAMA_BASE_URL (Fly machine will restart, ~30s)..."
& $FlyctlExe secrets set "OLLAMA_BASE_URL=$url" -a $App | Out-Host
if ($LASTEXITCODE -ne 0) { throw "flyctl secrets set failed (exit $LASTEXITCODE)" }

Write-Host ""
Write-Host "Done. Verify: open https://bingery.fly.dev/, log in, send a chat message."
Write-Host "cloudflared is detached -- you can close this PowerShell window."
