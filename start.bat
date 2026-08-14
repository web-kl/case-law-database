@echo off
cd /d "%~dp0"
start "Rechtsprechungs-Agent" python server.py
timeout /t 3 /nobreak >nul
start "" "msedge.exe" "http://localhost:8765"
