@echo off
setlocal

:: Get the directory where the batch file is located
set "PROJECT_ROOT=%~dp0"

:: Set PYTHONPATH to include the Ramses-Fusion lib and app directories
set "PYTHONPATH=%PROJECT_ROOT%Ramses-Fusion;%PROJECT_ROOT%Ramses-Fusion\lib;%PYTHONPATH%"

echo [Ramses-Fusion] Running complete test suite...
echo.

:: Run discovery from the project root
python -m unittest discover -v tests

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Some tests failed!
    exit /b %ERRORLEVEL%
)

echo.
echo [SUCCESS] All tests passed.
pause
