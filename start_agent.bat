@echo off
title Personal Local Job Agent (Naukri ^& Wellfound)
color 0A
cd /d "%~dp0"

echo ==================================================================
echo   Starting Personal Local Job Agent...
echo ==================================================================

if exist "backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=backend\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" -m local_agent.cli %*

if "%~1"=="" pause
