@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" desktop_launcher.py %*
  goto done
)
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 desktop_launcher.py %*
  goto done
)
where python >nul 2>nul
if %errorlevel% equ 0 (
  python desktop_launcher.py %*
  goto done
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" desktop_launcher.py %*
  goto done
)
echo Install Python 3.10 or newer and run START_CSA.bat again.
pause
exit /b 1
:done
if errorlevel 1 pause
