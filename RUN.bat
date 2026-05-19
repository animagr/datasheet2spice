@echo off
setlocal

cd /d "%~dp0"
echo Starting datasheet2spice local workbench...
echo.
echo Open http://127.0.0.1:8765 in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.

datasheet2spice serve --host 127.0.0.1 --port 8765

echo.
echo datasheet2spice workbench stopped or failed to start.
pause
