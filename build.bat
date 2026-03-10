@echo off
chcp 65001 >nul 2>&1
title Daily Hydrate - Build Script

:: Switch to script directory
cd /d "%~dp0"

echo ==========================================
echo   Daily Hydrate - Build Script
echo ==========================================
echo.
echo Current directory: %cd%
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python first.
    goto :end
)

echo [1/4] Checking dependencies...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] PyInstaller installation failed!
        goto :end
    )
)

echo.
echo [2/4] Checking source files...
if not exist "main.py" (
    echo [ERROR] main.py not found!
    goto :end
)
if not exist "src" (
    echo [ERROR] src folder not found!
    goto :end
)
echo Source files OK.

echo.
echo [3/4] Building...
echo.
if exist "icon.ico" (
    echo Using custom icon: icon.ico
    pyinstaller --onefile --windowed --name "DailyHydrate" --icon="icon.ico" --add-data "src;src" main.py
) else (
    echo No custom icon found, using default icon.
    pyinstaller --onefile --windowed --name "DailyHydrate" --add-data "src;src" main.py
)
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check the error message above.
    goto :end
)

echo.
echo [4/4] Cleaning up...
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec" 2>nul

echo.
echo ==========================================
echo   Build completed!
echo   Output: dist\DailyHydrate.exe
echo ==========================================

:end
echo.
echo Press any key to exit...
pause >nul
