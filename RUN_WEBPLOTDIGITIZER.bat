@echo off
setlocal

set "WPD_DIR=%~dp0..\WebPlotDigitizer"
set "WPD_PORT=8080"

if not exist "%WPD_DIR%\offline.html" (
  echo WebPlotDigitizer offline.html was not found.
  echo Expected: "%WPD_DIR%\offline.html"
  echo.
  echo Build WebPlotDigitizer first, then run this file again.
  pause
  exit /b 1
)

cd /d "%WPD_DIR%"
echo Starting WebPlotDigitizer local server...
echo.
echo Open http://127.0.0.1:%WPD_PORT%/offline.html in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.

start "" "http://127.0.0.1:%WPD_PORT%/offline.html"
py -m http.server %WPD_PORT% --bind 127.0.0.1

echo.
echo WebPlotDigitizer server stopped or failed to start.
pause
