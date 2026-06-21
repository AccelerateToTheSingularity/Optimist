# Creates a Start Menu shortcut for Optimist Prime local settings GUI.
# Run once: right-click -> Run with PowerShell, or: powershell -ExecutionPolicy Bypass -File install_start_menu_shortcut.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $RepoRoot "launch_settings_gui.vbs"
$StartMenu = [Environment]::GetFolderPath("Programs")
$ShortcutPath = Join-Path $StartMenu "Optimist Prime Settings.lnk"

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
