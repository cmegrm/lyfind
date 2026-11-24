@echo off
setlocal
cd /d "%~dp0"
py -3 setup_ai.py
if errorlevel 1 echo AI setup did not finish. Read the error above; typed matching remains available.
pause
