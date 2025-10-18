# دادرس هوشمند — راه‌اندازی سریع (Windows)

## اجرا

- HTTP (PowerShell):
  powershell -ExecutionPolicy Bypass -File .\scripts\run_http.ps1

- HTTPS (نیازمند گواهی):
  powershell -ExecutionPolicy Bypass -File .\scripts\run_https.ps1

سلامت: http://127.0.0.1:5052/healthz

پنل ادمین: http://127.0.0.1:5052/admin

## DeepSeek
- از پنل ادمین تنظیمات را در بخش تنظیمات مدل ذخیره کنید یا با دستور زیر:
  Invoke-RestMethod -Uri http://127.0.0.1:5052/admin/set-deepseek -Method POST -ContentType application/json -Body '{"api_key":"YOUR_API_KEY","model":"deepseek-chat"}'

## وبهوک
- توکن: WEBHOOK_TOKEN
- امضا (اختیاری): هدر X-Signature با HMAC-SHA256 روی بادی خام و کلید WEBHOOK_HMAC_SECRET

## توسعه
- نصب وابستگی‌ها: pip install -r requirements.txt
- لاگ‌ها: logs/app.log (فرمت JSON با چرخش)

