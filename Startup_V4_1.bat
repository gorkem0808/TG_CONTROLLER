@echo off
setlocal
set "APP=%~dp0TG_CONTROLLER_PRO_MANAGER_V4_1.exe"
if not exist "%APP%" (
  echo TG_CONTROLLER_PRO_MANAGER_V4_1.exe bulunamadi.
  pause
  exit /b 1
)
start "TG_CONTROLLER_PRO" "%APP%" --minimized
exit /b 0
