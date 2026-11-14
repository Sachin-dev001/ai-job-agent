@echo off
title AutoApply Local Host (http://localhost:8000)
color 0A
cd /d "%~dp0"

echo ==================================================================
echo   🚀 Starting AutoApply Local Application Server...
echo ==================================================================
echo   Local URL:     http://localhost:8000
echo   Engine:        Playwright + Stealth (Residential Home IP)
echo   UI:            Original Full Interface (Console, Scout, Proofs)
echo ==================================================================

if exist "backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=backend\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

start "" "http://localhost:8000"

"%PYTHON_EXE%" -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend

pause
