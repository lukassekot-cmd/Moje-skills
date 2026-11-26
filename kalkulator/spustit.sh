#!/bin/sh
# Spustenie kalkulátora na macOS / Linux (vyžaduje Python 3.10+ s Tkinter)
cd "$(dirname "$0")"
python3 -m pip install --user -q -r requirements.txt
exec python3 main.py "$@"
