@echo off
REM Hidden launcher — Start Menu shortcut uses launch_settings_gui.vbs instead.
cd /d "%~dp0"
start "" wscript.exe "%~dp0launch_settings_gui.vbs"
