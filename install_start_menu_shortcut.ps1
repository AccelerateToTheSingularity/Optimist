# Creates a Start Menu shortcut for Optimist Prime local settings GUI.
# Run once: right-click -> Run with PowerShell, or: powershell -ExecutionPolicy Bypass -File install_start_menu_shortcut.ps1
# Optionally offers a user-confirmed Start pin request (does not nag after decline).

param(
    [switch]$SkipPinPrompt
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $RepoRoot "launch_settings_gui.vbs"
$StartMenu = [Environment]::GetFolderPath("Programs")
$ShortcutPath = Join-Path $StartMenu "Optimist Prime Settings.lnk"
$PinStatePath = Join-Path $RepoRoot "data\settings_gui_prefs.json"

if (-not (Test-Path $Launcher)) {
    Write-Error "Launcher not found: $Launcher"
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $RepoRoot
$Shortcut.Description = "Open Optimist Prime bot settings in your browser"
# Gear icon from shell32.dll
$Shortcut.IconLocation = "$env:SystemRoot\System32\imageres.dll,109"
$Shortcut.Save()

Write-Host "Start Menu shortcut created:"
Write-Host "  $ShortcutPath"
Write-Host ""
Write-Host "Open Start and search for: Optimist Prime Settings"

function Get-PinState {
    if (-not (Test-Path $PinStatePath)) { return "not_offered" }
    try {
        $json = Get-Content -Raw -Path $PinStatePath | ConvertFrom-Json
        if ($null -ne $json.pinRequestState) { return [string]$json.pinRequestState }
    } catch {}
    return "not_offered"
}

function Set-PinState([string]$State) {
    $dir = Split-Path -Parent $PinStatePath
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    $obj = @{
        schemaVersion = 1
        screenId = "settings.main"
        hiddenSettingIds = @()
        customizeMode = $false
        showAdvanced = $false
        fontScale = 1.0
        actionUseCounts = @{}
        pinRequestState = $State
        expandedSections = @("Reddit", "Safety", "TLDR", "Engagement")
    }
    if (Test-Path $PinStatePath) {
        try {
            $existing = Get-Content -Raw -Path $PinStatePath | ConvertFrom-Json
            $existing.pinRequestState = $State
            $existing | ConvertTo-Json -Depth 6 | Set-Content -Path $PinStatePath -Encoding UTF8
            return
        } catch {}
    }
    $obj | ConvertTo-Json -Depth 6 | Set-Content -Path $PinStatePath -Encoding UTF8
}

$pinState = Get-PinState
if (-not $SkipPinPrompt -and $pinState -ne "declined" -and $pinState -ne "accepted") {
    Write-Host ""
    $answer = Read-Host "Pin Optimist Prime Settings to Start? [Y]es / [N]o / [S]kip"
    if ($answer -match '^[Yy]') {
        Start-Process explorer.exe $StartMenu
        Write-Host "Start Menu folder opened. Right-click 'Optimist Prime Settings' -> Pin to Start."
        Set-PinState "offered"
    } elseif ($answer -match '^[Nn]') {
        Set-PinState "declined"
        Write-Host "Pin request declined (will not ask again). Re-offer from the settings GUI if needed."
    } else {
        Write-Host "Skipped pin prompt."
    }
}
