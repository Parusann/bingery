<#
.SYNOPSIS
  Bingery Tunnel control panel — a tiny WinForms app with Start/Stop buttons
  that drive the same logic as tunnel.ps1. Auto-refreshes status every
  second and streams output from the start-up flow into a log pane.

.NOTES
  Launch via tunnel-app.cmd (silent) or directly:
    powershell -ExecutionPolicy Bypass -File tunnel-gui.ps1
#>

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# --- Paths / config -------------------------------------------------------

$ScriptDir      = $PSScriptRoot
$TunnelScript   = Join-Path $ScriptDir 'tunnel.ps1'
$CloudflaredExe = Join-Path $HOME '.cloudflared\cloudflared.exe'
$FlyctlExe      = Join-Path $HOME '.fly\bin\flyctl.exe'
$Log            = Join-Path $env:TEMP 'cloudflared-bingery.log'

if (-not (Test-Path $TunnelScript)) {
  [System.Windows.Forms.MessageBox]::Show(
    "Can't find tunnel.ps1 next to this app.`n`nExpected at: $TunnelScript",
    "Bingery Tunnel", 'OK', 'Error') | Out-Null
  return
}

$script:CurrentJob = $null

# --- Bingery palette ------------------------------------------------------

$BgDeep    = [System.Drawing.Color]::FromArgb(15, 12, 22)
$BgPanel   = [System.Drawing.Color]::FromArgb(22, 18, 32)
$BgInput   = [System.Drawing.Color]::FromArgb(28, 24, 38)
$TextMain  = [System.Drawing.Color]::FromArgb(230, 224, 218)
$TextMute  = [System.Drawing.Color]::FromArgb(140, 130, 145)
$Amber     = [System.Drawing.Color]::FromArgb(244, 182, 144)
$AmberDeep = [System.Drawing.Color]::FromArgb(217, 147, 104)
$Good      = [System.Drawing.Color]::FromArgb(143, 201, 164)
$Bad       = [System.Drawing.Color]::FromArgb(217, 117, 117)
$ButtonBg  = [System.Drawing.Color]::FromArgb(40, 34, 52)

# --- Helpers --------------------------------------------------------------

function Test-OllamaUp {
  try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' `
         -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    return ($r.StatusCode -eq 200)
  } catch { return $false }
}

function Get-TunnelStatus {
  $procs = @(Get-Process cloudflared -ErrorAction SilentlyContinue)
  $url = ''
  if ($procs -and (Test-Path $Log)) {
    $m = Select-String -Path $Log -Pattern 'https://[\w-]+\.trycloudflare\.com' `
         -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches.Value }
  }
  [PSCustomObject]@{
    Running  = $procs.Count -gt 0
    Pid      = if ($procs) { $procs[0].Id } else { $null }
    Url      = $url
    OllamaUp = (Test-OllamaUp)
  }
}

# --- Form ------------------------------------------------------------------

$form = New-Object System.Windows.Forms.Form
$form.Text          = 'Bingery Tunnel'
$form.Size          = New-Object System.Drawing.Size(560, 480)
$form.MinimumSize   = New-Object System.Drawing.Size(420, 360)
$form.StartPosition = 'CenterScreen'
$form.BackColor     = $BgDeep
$form.ForeColor     = $TextMain
$form.Font          = New-Object System.Drawing.Font('Segoe UI', 9.5)

# Title
$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text     = 'Bingery Tunnel'
$titleLabel.Location = New-Object System.Drawing.Point(20, 18)
$titleLabel.Size     = New-Object System.Drawing.Size(500, 28)
$titleLabel.Font     = New-Object System.Drawing.Font('Segoe UI Semibold', 14)
$titleLabel.ForeColor = $Amber
$form.Controls.Add($titleLabel)

# Status row
$statusDot = New-Object System.Windows.Forms.Label
$statusDot.Text     = [char]0x25CF  # ●
$statusDot.Location = New-Object System.Drawing.Point(20, 58)
$statusDot.Size     = New-Object System.Drawing.Size(18, 22)
$statusDot.Font     = New-Object System.Drawing.Font('Segoe UI', 14)
$statusDot.ForeColor = $TextMute
$form.Controls.Add($statusDot)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text     = 'Checking...'
$statusLabel.Location = New-Object System.Drawing.Point(40, 60)
$statusLabel.Size     = New-Object System.Drawing.Size(480, 22)
$statusLabel.Font     = New-Object System.Drawing.Font('Segoe UI', 10.5)
$statusLabel.Anchor   = 'Top,Left,Right'
$form.Controls.Add($statusLabel)

# URL box
$urlLabel = New-Object System.Windows.Forms.Label
$urlLabel.Text     = 'URL'
$urlLabel.Location = New-Object System.Drawing.Point(20, 95)
$urlLabel.Size     = New-Object System.Drawing.Size(40, 22)
$urlLabel.ForeColor = $TextMute
$form.Controls.Add($urlLabel)

$urlBox = New-Object System.Windows.Forms.TextBox
$urlBox.Location = New-Object System.Drawing.Point(60, 93)
$urlBox.Size     = New-Object System.Drawing.Size(460, 24)
$urlBox.ReadOnly = $true
$urlBox.BackColor = $BgInput
$urlBox.ForeColor = $Amber
$urlBox.BorderStyle = 'FixedSingle'
$urlBox.Font     = New-Object System.Drawing.Font('Consolas', 9.5)
$urlBox.Anchor   = 'Top,Left,Right'
$form.Controls.Add($urlBox)

# Buttons
$startButton = New-Object System.Windows.Forms.Button
$startButton.Text       = 'Start tunnel'
$startButton.Location   = New-Object System.Drawing.Point(20, 135)
$startButton.Size       = New-Object System.Drawing.Size(160, 44)
$startButton.BackColor  = $Amber
$startButton.ForeColor  = $BgDeep
$startButton.FlatStyle  = 'Flat'
$startButton.FlatAppearance.BorderSize = 0
$startButton.Font       = New-Object System.Drawing.Font('Segoe UI Semibold', 10)
$startButton.Cursor     = 'Hand'
$form.Controls.Add($startButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text       = 'Stop tunnel'
$stopButton.Location   = New-Object System.Drawing.Point(188, 135)
$stopButton.Size       = New-Object System.Drawing.Size(160, 44)
$stopButton.BackColor  = $ButtonBg
$stopButton.ForeColor  = $TextMain
$stopButton.FlatStyle  = 'Flat'
$stopButton.FlatAppearance.BorderSize = 1
$stopButton.FlatAppearance.BorderColor = $AmberDeep
$stopButton.Font       = New-Object System.Drawing.Font('Segoe UI Semibold', 10)
$stopButton.Cursor     = 'Hand'
$form.Controls.Add($stopButton)

$copyButton = New-Object System.Windows.Forms.Button
$copyButton.Text       = 'Copy URL'
$copyButton.Location   = New-Object System.Drawing.Point(356, 135)
$copyButton.Size       = New-Object System.Drawing.Size(160, 44)
$copyButton.BackColor  = $BgPanel
$copyButton.ForeColor  = $TextMute
$copyButton.FlatStyle  = 'Flat'
$copyButton.FlatAppearance.BorderSize = 1
$copyButton.FlatAppearance.BorderColor = $BgPanel
$copyButton.Font       = New-Object System.Drawing.Font('Segoe UI', 10)
$copyButton.Cursor     = 'Hand'
$copyButton.Anchor     = 'Top,Right'
$form.Controls.Add($copyButton)

# Log pane
$logHeader = New-Object System.Windows.Forms.Label
$logHeader.Text     = 'Output'
$logHeader.Location = New-Object System.Drawing.Point(20, 200)
$logHeader.Size     = New-Object System.Drawing.Size(120, 20)
$logHeader.ForeColor = $TextMute
$form.Controls.Add($logHeader)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline   = $true
$logBox.ReadOnly    = $true
$logBox.ScrollBars  = 'Vertical'
$logBox.Location    = New-Object System.Drawing.Point(20, 222)
$logBox.Size        = New-Object System.Drawing.Size(500, 195)
$logBox.BackColor   = $BgInput
$logBox.ForeColor   = $TextMain
$logBox.BorderStyle = 'FixedSingle'
$logBox.Font        = New-Object System.Drawing.Font('Consolas', 9)
$logBox.Anchor      = 'Top,Left,Right,Bottom'
$form.Controls.Add($logBox)

# --- Logic ----------------------------------------------------------------

function Add-Log {
  param([string] $Text)
  $stamp = (Get-Date).ToString('HH:mm:ss')
  $logBox.AppendText("[$stamp] $Text`r`n")
}

function Update-Ui {
  $s = Get-TunnelStatus
  $jobBusy = $null -ne $script:CurrentJob

  if ($jobBusy) {
    $statusDot.ForeColor = $Amber
    $statusLabel.Text    = 'Working...'
  } elseif ($s.Running) {
    $statusDot.ForeColor = $Good
    $statusLabel.Text    = "Tunnel: UP (PID $($s.Pid))"
  } else {
    $statusDot.ForeColor = $TextMute
    if ($s.OllamaUp) {
      $statusLabel.Text  = 'Tunnel: stopped'
    } else {
      $statusDot.ForeColor = $Bad
      $statusLabel.Text  = 'Tunnel: stopped  |  Ollama not running on :11434'
    }
  }

  if ($s.Url) {
    if ($urlBox.Text -ne $s.Url) { $urlBox.Text = $s.Url }
  } else {
    if ($s.Running -and -not $jobBusy) { $urlBox.Text = '(detecting URL...)' }
    elseif (-not $jobBusy)             { $urlBox.Text = '' }
  }

  $startButton.Enabled = (-not $jobBusy) -and (-not $s.Running) -and $s.OllamaUp
  $stopButton.Enabled  = (-not $jobBusy) -and $s.Running
  $copyButton.Enabled  = -not [string]::IsNullOrWhiteSpace($urlBox.Text) `
                        -and $urlBox.Text -notlike '(*)'
}

# Start handler — runs tunnel.ps1 as a background job
$startButton.Add_Click({
  if ($script:CurrentJob) { return }
  $startButton.Enabled = $false
  $stopButton.Enabled  = $false
  Add-Log 'Launching tunnel.ps1 ...'
  $scriptPath = $TunnelScript
  $script:CurrentJob = Start-Job -ScriptBlock {
    param($p)
    & $p 2>&1
  } -ArgumentList $scriptPath
})

# Stop handler — direct kill, no script needed
$stopButton.Add_Click({
  $stopButton.Enabled = $false
  Add-Log 'Stopping cloudflared ...'
  $killed = 0
  Get-Process cloudflared -ErrorAction SilentlyContinue | ForEach-Object {
    try { Stop-Process -Id $_.Id -Force -ErrorAction Stop; $killed++ } catch {}
  }
  if ($killed -gt 0) { Add-Log "Stopped $killed cloudflared process(es)." }
  else               { Add-Log 'cloudflared was not running.' }
})

# Copy handler
$copyButton.Add_Click({
  if (-not [string]::IsNullOrWhiteSpace($urlBox.Text) -and $urlBox.Text -notlike '(*)') {
    [System.Windows.Forms.Clipboard]::SetText($urlBox.Text)
    Add-Log "Copied: $($urlBox.Text)"
  }
})

# Polling timer
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 700
$timer.Add_Tick({
  if ($script:CurrentJob) {
    $job = $script:CurrentJob
    $output = Receive-Job -Job $job -ErrorAction SilentlyContinue
    foreach ($line in $output) {
      if ($null -ne $line -and "$line".Trim().Length -gt 0) {
        Add-Log ("$line".Trim())
      }
    }
    if ($job.State -in @('Completed', 'Failed', 'Stopped')) {
      Add-Log "(tunnel.ps1 $($job.State.ToString().ToLower()))"
      Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
      $script:CurrentJob = $null
    }
  }
  Update-Ui
})
$timer.Start()

# Initial state
Add-Log 'Ready. "Start tunnel" brings the home Ollama path online and syncs the Fly secret.'
Update-Ui

# Clean up on close
$form.Add_FormClosing({
  $timer.Stop()
  if ($script:CurrentJob) {
    Remove-Job -Job $script:CurrentJob -Force -ErrorAction SilentlyContinue
  }
})

# Run
[void]$form.ShowDialog()
