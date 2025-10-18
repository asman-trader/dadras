@echo off
setlocal ENABLEDELAYEDEXPANSION

REM First argument: path to payload JSON file
set PAYLOAD_FILE=%~1
if "%PAYLOAD_FILE%"=="" (
  echo [handler] No payload file path received.
  exit /b 1
)

if not exist "%PAYLOAD_FILE%" (
  echo [handler] Payload file not found: %PAYLOAD_FILE%
  exit /b 1
)

echo [handler] Processing payload file: %PAYLOAD_FILE%
REM Example: append a timestamped line to tmp\webhook.log
set LOGDIR=%~dp0tmp
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
for /f "tokens=*" %%i in ("%PAYLOAD_FILE%") do (
  echo [%%DATE%% %%TIME%%] %%~nxi >> "%LOGDIR%\webhook.log"
  goto :done
)

:done
echo [handler] Done.
exit /b 0


