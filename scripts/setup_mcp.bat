@echo off
REM ============================================================
REM WC Optimizer — One-Click MCP Auto-Configuration (Windows)
REM Double-click this file to auto-configure Claude Desktop
REM and Cursor IDE to connect to WC Optimizer.
REM ============================================================

echo.
echo ========================================
echo  WC Optimizer - MCP Auto-Setup
echo ========================================
echo.

REM Try python3 first, then python
where python3 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python3 "%~dp0setup_mcp.py" %*
    goto :done
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python "%~dp0setup_mcp.py" %*
    goto :done
)

echo ERROR: Python is not installed or not in PATH.
echo Please install Python 3.8+ from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
echo.

:done
echo.
echo Press any key to close...
pause >nul
