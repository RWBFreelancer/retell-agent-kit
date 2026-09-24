@echo off
title Sync - uploading your work
cd /d "%~dp0"

echo.
echo  Syncing %CD%
echo.

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo  [X] This folder is not a git repository.
    echo.
    echo      Open GitHub Desktop, use File - Add local repository,
    echo      point it at this folder, then publish it.
    echo.
    pause
    exit /b 1
)

echo  [1/4] Staging changes...
git add -A

echo  [2/4] Saving a checkpoint...
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "sync from %COMPUTERNAME% - %DATE% %TIME%"
) else (
    echo        nothing new to save
)

echo  [3/4] Pulling anything from your other devices...
git pull --rebase
if errorlevel 1 (
    echo.
    echo  [!] A conflict needs your input.
    echo      Open GitHub Desktop - it will show you exactly which
    echo      files disagree and let you pick. Nothing is lost.
    echo.
    pause
    exit /b 1
)

echo  [4/4] Uploading...
git push
if errorlevel 1 (
    echo.
    echo  [X] Upload failed.
    echo.
    pause
    exit /b 1
)

echo.
echo  done - retell-agent-kit is up to date on GitHub
echo.
pause
