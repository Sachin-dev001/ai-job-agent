@echo off
title AutoApply Local Web Dashboard (http://localhost:8000)
color 0B
cd /d "%~dp0"

echo ==================================================================
echo   🚀 Starting AutoApply Local Web Dashboard...
echo ==================================================================
echo   Dashboard URL: http://localhost:8000
echo   Engine:        Playwright + Chrome (Home Residential IP)
echo ==================================================================

if exist "backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=backend\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Opening browser at http://localhost:8000 ...
"%PYTHON_EXE%" -m local_agent.server

pause
