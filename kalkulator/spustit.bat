@echo off
REM Spustenie kalkulatora zo zdrojovych suborov (vyzaduje Python 3.10+ z python.org)
cd /d "%~dp0"
python -m pip install --user -q -r requirements.txt
start "" pythonw main.py %*
