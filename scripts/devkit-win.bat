@echo off
setlocal enabledelayedexpansion
echo ============================================
echo  FSKit Development Kit for Windows
echo ============================================
echo.

cd /d "%~dp0\.."

:: ── 1. uv の確認 / インストール ─────────────────────────────
where uv >nul 2>&1
if errorlevel 1 (
    echo [INFO] uv not found. Installing...
    powershell -ExecutionPolicy Bypass -Command ^
        "iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex"
    if errorlevel 1 (
        echo [CRITICAL] Failed to install uv.
        echo            Please install manually: https://docs.astral.sh/uv/
        pause
        exit /b 1
    )
    :: インストール直後はPATHが通っていないことがあるためリフレッシュ
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
) else (
    for /f "tokens=*" %%v in ('uv --version 2^>^&1') do echo [INFO] %%v found.
)

:: ── 2. pyproject.toml の確認 ────────────────────────────────
if not exist pyproject.toml (
    echo [CRITICAL] pyproject.toml not found.
    echo            Please run this script from the project root.
    pause
    exit /b 1
)

:: ── 3. uv sync で依存関係をインストール ─────────────────────
echo.
echo [INFO] Syncing dependencies with uv sync...
uv sync --no-install-project
if errorlevel 1 (
    echo [ERROR] uv sync failed.
    pause
    exit /b 1
)

:: ── 4. 完了メッセージ ────────────────────────────────────────
echo.
echo ============================================
echo  [SUCCESS] Environment is ready.
echo ============================================
echo.
echo  Run:
echo    uv run python FSKit.py
echo.
echo  Build:
echo    call scripts\build.bat
echo.
cmd /k
