#!/bin/bash
# Instala dependencias de sistema y crea el entorno virtual.
set -e
cd "$(dirname "$0")"

echo "Instalando dependencias de sistema (te va a pedir tu contrasena)..."
sudo apt install -y tesseract-ocr tesseract-ocr-spa wl-clipboard \
    python3-gi gir1.2-gst-plugins-base-1.0 gstreamer1.0-plugins-good \
    gstreamer1.0-pipewire

echo "Creando entorno virtual..."
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt

echo "Listo. Ejecuta ./run.sh para probarlo."
