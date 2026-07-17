@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Virtual environment not found. Run: python -m venv .venv
    exit /b 1
)

"%PYTHON_EXE%" "%PROJECT_DIR%app.py"
