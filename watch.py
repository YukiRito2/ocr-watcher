"""Vigila una zona de pantalla durante N segundos, usando OCR para detectar un
codigo (texto con formato tipo XXX-XXXX-123) y copiarlo al portapapeles apenas
aparece.

Uso:
    .venv/bin/python watch.py                  # selecciona zona y vigila 120s
    .venv/bin/python watch.py --reselect        # vuelve a pedir la zona
    .venv/bin/python watch.py --seconds 60
    .venv/bin/python watch.py --pattern '[A-Z0-9]{4,6}'
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

from PIL import Image, ImageOps
import pytesseract

from screencast import ScreenCastSession, FrameGrabber

REGION_FILE = "region.json"
DEFAULT_PATTERN = r"C[OÓ0]DIGO[^A-Z0-9]{0,5}([A-Z0-9]{3,6}-[A-Z0-9]{3,6}-[A-Z0-9]{3,6})"
TESSERACT_CONFIG = (
    "--psm 6 -c tessedit_char_whitelist="
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:- "
)


def preprocess(crop):
    """Sube nitidez y contraste SIN binarizar a blanco/negro duro: un umbral
    duro borraba los guiones (trazos finos). Tesseract (motor LSTM) funciona
    mejor con gris suave que con blanco/negro forzado."""
    crop = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
    gray = ImageOps.grayscale(crop)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    return gray


MAX_THUMB_WIDTH = 2800


def ensure_region(force_reselect, grabber):
    if force_reselect or not os.path.exists(REGION_FILE):
        print("Tomando una foto de tu pantalla para usar de miniatura en el selector...")
        full = grabber.grab()
        real_w, real_h = full.size

        scale = min(1.0, MAX_THUMB_WIDTH / real_w)
        thumb = full.resize((int(real_w * scale), int(real_h * scale)))
        bg_path = "bg_select.png"
        thumb.save(bg_path)

        while True:
            print("Selecciona con el mouse la zona a vigilar (arrastra y suelta, Esc cancela)...")
            result = subprocess.run(
                [sys.executable, "select_region.py", REGION_FILE, bg_path, str(real_w), str(real_h)],
            )
            if result.returncode == 0:
                break
            print("Seleccion cancelada o invalida, intenta de nuevo (arrastra un rectangulo real y suelta)...")
    with open(REGION_FILE) as f:
        return json.load(f)


def copy_to_clipboard(text):
    subprocess.run(["wl-copy"], input=text.encode(), check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=120, help="tiempo maximo de vigilancia")
    parser.add_argument("--interval", type=float, default=0.7, help="segundos entre capturas")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN, help="regex del codigo a detectar")
    parser.add_argument("--lang", default="spa+eng", help="idiomas para tesseract")
    parser.add_argument("--reselect", action="store_true", help="volver a elegir la zona")
    args = parser.parse_args()

    pattern = re.compile(args.pattern)

    print("Pidiendo permiso para compartir pantalla (dialogo del sistema)...")
    session = ScreenCastSession()
    node_id, pw_fd, _size = session.start()
    print("Permiso concedido.")
    grabber = FrameGrabber(node_id, pw_fd)

    region = ensure_region(args.reselect, grabber)
    print(f"Zona: {region}")
    print("Vigilando...")

    deadline = time.monotonic() + args.seconds
    last_seen_raw = None

    try:
        while time.monotonic() < deadline:
            try:
                frame = grabber.grab()
            except RuntimeError as e:
                print(f"[{time.strftime('%H:%M:%S')}] aviso: {e}, reintentando...")
                time.sleep(args.interval)
                continue
            crop = frame.crop((
                region["x"], region["y"],
                region["x"] + region["width"], region["y"] + region["height"],
            ))
            crop = preprocess(crop)

            text = pytesseract.image_to_string(crop, lang=args.lang, config=TESSERACT_CONFIG)
            if text.strip() and text != last_seen_raw:
                last_seen_raw = text
                print(f"[{time.strftime('%H:%M:%S')}] leido: {text.strip()!r}")

            match = pattern.search(text.upper())
            if match:
                codigo = match.group(1).replace("-", "")
                copy_to_clipboard(codigo)
                print(f"\n>>> CODIGO DETECTADO: {codigo}  (copiado al portapapeles)")
                return

            time.sleep(args.interval)

        print("Tiempo agotado, no se detecto ningun codigo.")
    finally:
        grabber.close()


if __name__ == "__main__":
    main()
