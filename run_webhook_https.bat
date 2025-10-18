@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Configure environment
set HOST=0.0.0.0
set PORT=5443
set SSL_CERTFILE=%~dp0certs\server.crt
set SSL_KEYFILE=%~dp0certs\server.key
set WEBHOOK_TOKEN=change-me-strong-secret
REM Optional: set WEBHOOK_BAT to a handler script
set WEBHOOK_BAT=%~dp0webhook-handler.bat

if not exist "%SSL_CERTFILE%" (
  echo [error] SSL_CERTFILE not found: %SSL_CERTFILE%
  echo        Create self-signed certs with make_self_signed_certs.bat
  exit /b 1
)
if not exist "%SSL_KEYFILE%" (
  echo [error] SSL_KEYFILE not found: %SSL_KEYFILE%
  echo        Create self-signed certs with make_self_signed_certs.bat
  exit /b 1
)

echo Starting HTTPS server on https://%HOST%:%PORT%
where waitress-serve >nul 2>nul
if %ERRORLEVEL%==0 (
  waitress-serve --host=%HOST% --port=%PORT% --url-scheme=https --ssl-certfile="%SSL_CERTFILE%" --ssl-keyfile="%SSL_KEYFILE%" app:app
) else (
  echo waitress-serve not found on PATH, falling back to Python launcher...
  python "%~dp0serve_https.py"
)

endlocal

