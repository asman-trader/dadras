@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul
cls
echo ===================================================
echo   🚀 در حال ارسال تغییرات پروژه به GitHub
echo ===================================================
echo.

:: پیکربندی
set REPO=https://github.com/asman-trader/dadras.git
set BRANCH=main
set MSG=%*
if "%MSG%"=="" set MSG=Auto commit - %DATE% %TIME%

:: بررسی git
where git >nul 2>nul
if errorlevel 1 (
  echo ❌ Git نصب نشده است. ابتدا Git را نصب کنید.
  pause
  exit /b 1
)

:: ایجاد مخزن در صورت نبود
if not exist .git (
  echo 📦 ایجاد مخزن جدید...
  git init
)

:: تعیین ریموت origin
for /f "delims=" %%U in ('git remote get-url origin 2^>nul') do set CUR_ORIGIN=%%U
if not defined CUR_ORIGIN (
  echo 🔗 افزودن ریموت origin ...
  git remote add origin %REPO%
) else (
  if /I not "!CUR_ORIGIN!"=="%REPO%" (
    echo 🔗 به‌روزرسانی آدرس ریموت origin ...
    git remote set-url origin %REPO%
  )
)

:: اطمینان از نام شاخه
git branch -M %BRANCH% >nul 2>nul

:: افزودن فایل‌ها
echo ➕ افزودن فایل‌ها...
git add -A

:: اگر چیزی برای کامیت نیست، مرحله را رد کن
git diff --cached --quiet
if errorlevel 1 (
  echo 📝 ثبت تغییرات...
  git commit -m "%MSG%"
) else (
  echo ℹ️ تغییری برای ثبت وجود ندارد.
)

:: همگام‌سازی با ریموت (در صورت وجود)
echo 🔄 همگام‌سازی با ریموت...
git fetch origin %BRANCH% >nul 2>nul
if not errorlevel 1 (
  git pull --rebase origin %BRANCH% >nul 2>nul || git pull origin %BRANCH% --allow-unrelated-histories
)

:: ارسال به ریموت
echo 🚀 ارسال به GitHub...
git push -u origin %BRANCH%
if errorlevel 1 (
  echo ❌ ارسال ناموفق بود. تعارض یا محدودیت دسترسی را بررسی کنید.
  pause
  exit /b 1
)

echo.
echo ✅ انجام شد.
echo 🌐 %REPO%
echo ---------------------------------------------------
pause