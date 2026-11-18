#!/bin/bash
# Lanzador sin consola: deja el log en watcher.log por si hay que revisar algo.
cd "$(dirname "$0")"
exec .venv/bin/python -u watch.py "$@" > watcher.log 2>&1
