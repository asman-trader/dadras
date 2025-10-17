@echo off
cls
echo ===================================================
echo   🚀 در حال آپلود پروژه دادرس هوشمند به GitHub ...
echo ===================================================
echo.

:: تنظیمات اولیه
set REPO=https://github.com/asman-trader/dadras.git
set BRANCH=main

:: بررسی وجود git
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Git نصب نشده است. لطفاً ابتدا Git را نصب کنید.
    pause
    exit /b
)

:: شروع مراحل
echo 🌀 مرحله 1: بررسی مخزن محلی...
if not exist ".git" (
    echo 📦 در حال ایجاد مخزن جدید...
    git init
)

echo 🌀 مرحله 2: افزودن فایل‌ها...
git add .

echo 🌀 مرحله 3: ثبت تغییرات...
git commit -m "Auto commit from push_to_github.bat"

echo 🌀 مرحله 4: تنظیم شاخه اصلي...
git branch -M %BRANCH%

echo 🌀 مرحله 5: افزودن ریموت (در صورت نیاز)...
git remote remove origin >nul 2>nul
git remote add origin %REPO%

echo 🌀 مرحله 6: ادغام در صورت وجود تاریخچه متفاوت...
git pull origin %BRANCH% --allow-unrelated-histories

echo 🌀 مرحله 7: ارسال تغییرات به GitHub...
git push -u origin %BRANCH%

echo.
echo ✅ آپلود با موفقیت انجام شد!
echo 🌐 لینک ریپازیتوری: %REPO%
echo ---------------------------------------------------
pause
