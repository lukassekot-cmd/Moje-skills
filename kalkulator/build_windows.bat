@echo off
REM Zostavenie samostatneho programu Kalkulator.exe (spustit na Windows s Python 3.10+)
cd /d "%~dp0"
python -m pip install -q -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name Kalkulator ^
  --add-data "priklady;priklady" main.py
echo.
echo Hotovo: dist\Kalkulator.exe
pause
