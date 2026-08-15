@echo off
setlocal
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0cortex.py" %*
) else (
    python "%~dp0cortex.py" %*
)
