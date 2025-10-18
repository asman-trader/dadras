@echo off
setlocal

set CERTDIR=%~dp0certs
if not exist "%CERTDIR%" mkdir "%CERTDIR%"

REM Requires OpenSSL installed and on PATH
where openssl >nul 2>nul
if not %ERRORLEVEL%==0 (
  echo OpenSSL not found on PATH. Install it or create certs manually.
  exit /b 1
)

set CRT=%CERTDIR%\server.crt
set KEY=%CERTDIR%\server.key
set CN=localhost

echo Generating self-signed certificate for CN=%CN%
openssl req -x509 -nodes -newkey rsa:2048 -keyout "%KEY%" -out "%CRT%" -days 365 -subj "/CN=%CN%"
if %ERRORLEVEL%==0 (
  echo Done. Created:
  echo   %CRT%
  echo   %KEY%
) else (
  echo Failed to generate certificate.
)

endlocal

