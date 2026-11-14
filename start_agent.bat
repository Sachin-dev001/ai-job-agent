@echo off
title Personal Local Job Agent (Naukri, Wellfound, LinkedIn, YC)
color 0A
cd /d "%~dp0"

echo ==================================================================
echo   🚀 Starting Autonomous Job Agent (4 Platforms Supported)
echo   Platforms: Naukri | Wellfound | LinkedIn | Y Combinator
echo ==================================================================

if exist "backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=backend\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" -m local_agent.cli %*

if "%~1"=="" pause
