@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul

set "REPO=https://github.com/asman-trader/dadras.git"
set "BRANCH=main"
set "MSG=%*"

if "%MSG%"=="" set "MSG=Auto commit - %DATE% %TIME%"

where git >nul 2>nul || (
  echo ❌ Git نصب نشده است.
  pause
  exit /b 1
)

if not exist .git (
  echo 🔧 git init
  git init || goto :fail
)

git remote get-url origin >nul 2>nul || (
  echo 🔗 افزودن origin
  git remote add origin %REPO% || goto :fail
)

git branch -M %BRANCH% >nul 2>nul

echo ➕ git add -A
git add -A || goto :fail

git diff --cached --quiet
if errorlevel 1 (
  echo 📝 git commit
  git commit -m "%MSG%" || goto :fail
) else (
  echo ℹ️ تغییری برای ثبت وجود ندارد.
)

git ls-remote --exit-code origin %BRANCH% >nul 2>nul && (
  echo 🔄 git pull --rebase
  git pull --rebase origin %BRANCH% || goto :fail
)

echo 🚀 git push
git push -u origin %BRANCH% || goto :fail

echo.
echo ✅ عملیات با موفقیت انجام شد.
pause
exit /b 0

:fail
echo.
echo ❌ عملیات متوقف شد.
pause
exit /b 1