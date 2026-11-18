#!/bin/bash
# Lanzador sin consola: deja el log en watcher.log por si hay que revisar algo.
cd "$(dirname "$0")"

if pgrep -f "watch\.py" > /dev/null; then
    notify-send "OCR Watcher" "Ya hay una instancia corriendo, no se abrio otra."
    exit 0
fi

exec .venv/bin/python -u watch.py "$@" > watcher.log 2>&1
