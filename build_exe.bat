@echo off
:: ═══════════════════════════════════════════════════════
::  Build Invoice Adjustment Bot → single .exe
::  Usage: double-click build_exe.bat  (or run in terminal)
:: ═══════════════════════════════════════════════════════
setlocal

set APP_NAME=InvoiceAdjustmentBot
set ENTRY=gui_app.py

:: ── 1. Generate icon (requires Pillow) ──────────────────
echo [1/3] Tao icon...
python make_icon.py
if errorlevel 1 (
    echo  WARNING: Could not create icon, continuing without it.
    set ICON_FLAG=
) else (
    set ICON_FLAG=--icon=assets\app_icon.ico
)

:: ── 2. Locate pyinstaller executable ────────────────────
echo [2/3] Kiem tra PyInstaller...
where pyinstaller >nul 2>&1
if not errorlevel 1 (
    set PYINST=pyinstaller
    goto :build
)
:: Fallback: check user Scripts folder (pip install --user)
for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_path(\"scripts\",\"nt_user\"))" 2^>nul') do set USER_SCRIPTS=%%i
if exist "%USER_SCRIPTS%\pyinstaller.exe" (
    set PYINST="%USER_SCRIPTS%\pyinstaller.exe"
    goto :build
)
:: Last resort: install it
echo  Installing PyInstaller...
python -m pip install --user pyinstaller
for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_path(\"scripts\",\"nt_user\"))" 2^>nul') do set USER_SCRIPTS=%%i
set PYINST="%USER_SCRIPTS%\pyinstaller.exe"

:build
:: ── 3. Bundle Tesseract nếu tồn tại ────────────────────
set TESS_FLAG=
set TESS_DIR=C:\Program Files\Tesseract-OCR
if exist "%TESS_DIR%\tesseract.exe" (
    echo  Found Tesseract at %TESS_DIR% - se bundle vao exe
    set "TESS_FLAG=--add-data "%TESS_DIR%;Tesseract-OCR""
) else (
    echo  WARNING: Tesseract not found at %TESS_DIR% - may cich phai tu cai
)

:: ── 4. Build ─────────────────────────────────────────────
echo [3/3] Build EXE...
%PYINST% ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "%APP_NAME%" ^
    %ICON_FLAG% ^
    --add-data "assets;assets" ^
    --add-data "locales;locales" ^
    --add-data ".env.example;." ^
    --add-data "version.txt;." ^
    %TESS_FLAG% ^
    --hidden-import "PIL._tkinter_finder" ^
    --collect-all "easyocr" ^
    --collect-all "pywinauto" ^
    %ENTRY%

if errorlevel 1 (
    echo.
    echo BUILD THAT BAI! Xem loi o tren.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  BUILD THANH CONG!
 echo  Thu muc: dist\%APP_NAME%\
echo ========================================
echo.
echo Sao chep .env vao thu muc dist\%APP_NAME%\ truoc khi chay:
echo   copy .env dist\
echo   copy key\order-adjustment-bot.json dist\key\
echo.
pause
