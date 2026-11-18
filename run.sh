#!/bin/bash
# Lanzador sin consola: deja el log en watcher.log por si hay que revisar algo.
cd "$(dirname "$0")"

if pgrep -f "watch\.py" > /dev/null; then
    pkill -f "watch\.py"
    pkill -f "select_region\.py"
    sleep 1
    notify-send "OCR Watcher" "Reiniciando..."
fi

exec .venv/bin/python -u watch.py "$@" > watcher.log 2>&1
