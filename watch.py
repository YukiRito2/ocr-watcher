"""Vigila una zona de pantalla durante N segundos, usando OCR para detectar un
codigo (texto con formato tipo XXX-XXXX-123) y copiarlo al portapapeles apenas
aparece.

Si ya existe una zona guardada de una vez anterior, pregunta (con un dialogo,
sin consola) si usar la misma o marcar una nueva.

Uso:
    .venv/bin/python watch.py                  # pregunta la zona y vigila 12 min
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

from PIL import Image, ImageChops, ImageOps
import pytesseract

from screencast import ScreenCastSession, FrameGrabber

REGION_FILE = "region.json"
DEFAULT_PATTERN = r"\b([A-Z0-9]{3,5}-[A-Z0-9]{3,5}-[A-Z0-9]{3,5})\b"
TESSERACT_CONFIG = (
    "--psm 6 -c tessedit_char_whitelist="
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:- "
)
TESSERACT_CONFIG_LINE = (
    "--psm 7 -c tessedit_char_whitelist="
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-"
)

# Color del texto del codigo en el video de prueba (rosado/magenta tipo
# #F7A4C5): H~335 grados, S~30%, V~90%. En la escala 0-255 que usa PIL
# para HSV eso es H~237. Se usa para aislar el texto del codigo del resto
# del fondo/otros textos, que no tienen ese color.
CODE_HUE_RANGE = (210, 255)
CODE_SAT_MIN = 15
CODE_VAL_MIN = 80


def preprocess(crop):
    """Sube nitidez y contraste SIN binarizar a blanco/negro duro: un umbral
    duro borraba los guiones (trazos finos). Tesseract (motor LSTM) funciona
    mejor con gris suave que con blanco/negro forzado."""
    crop = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
    gray = ImageOps.grayscale(crop)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    return gray


def isolate_code_color(crop):
    """Aisla solo los pixeles con el color rosado/magenta del codigo, y deja
    todo lo demas (fondo, otros textos) en blanco. Le quita al OCR todo el
    ruido alrededor cuando el codigo tiene ese color especifico."""
    hsv = crop.convert("HSV")
    h, s, v = hsv.split()
    lo, hi = CODE_HUE_RANGE
    h_mask = h.point(lambda x: 255 if lo <= x <= hi else 0)
    s_mask = s.point(lambda x: 255 if x >= CODE_SAT_MIN else 0)
    v_mask = v.point(lambda x: 255 if x >= CODE_VAL_MIN else 0)
    mask = ImageChops.multiply(ImageChops.multiply(h_mask, s_mask), v_mask)
    # texto negro sobre fondo blanco, que es lo que mejor lee Tesseract
    text_on_white = mask.point(lambda x: 0 if x == 255 else 255)
    return text_on_white.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)


MAX_THUMB_WIDTH = 2800


def ask_use_last_region():
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    with open(REGION_FILE) as f:
        region = json.load(f)
    answer = messagebox.askyesno(
        "Zona a vigilar",
        f"¿Usar la misma zona que la vez anterior?\n\n{region}",
        parent=root,
    )
    root.destroy()
    return answer


def ensure_region(grabber):
    if os.path.exists(REGION_FILE) and ask_use_last_region():
        pass
    else:
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


def notify(title, body):
    subprocess.run(["notify-send", title, body])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=720, help="tiempo maximo de vigilancia")
    parser.add_argument("--interval", type=float, default=0.7, help="segundos entre capturas")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN, help="regex del codigo a detectar")
    parser.add_argument("--lang", default="spa+eng", help="idiomas para tesseract")
    args = parser.parse_args()

    pattern = re.compile(args.pattern)

    print("Pidiendo permiso para compartir pantalla (dialogo del sistema)...")
    session = ScreenCastSession()
    node_id, pw_fd, _size = session.start()
    print("Permiso concedido.")
    grabber = FrameGrabber(node_id, pw_fd)

    region = ensure_region(grabber)
    print(f"Zona: {region}")
    print("Vigilando...")

    def grab_crop():
        frame = grabber.grab()
        return frame.crop((
            region["x"], region["y"],
            region["x"] + region["width"], region["y"] + region["height"],
        ))

    FALLBACK_EVERY = 2  # cada cuantos ciclos se corre tambien el OCR generico
    cycle = 0

    def read_and_match():
        """Primero revisa (sin Tesseract, muy rapido) si hay pixeles del color
        rosado del codigo en la zona. Si no hay, no vale la pena correr OCR y
        se salta el ciclo casi gratis. Si hay, lee solo esa mascara (limpia,
        sin ruido de fondo). Cada FALLBACK_EVERY ciclos ademas corre el OCR
        generico por si el codigo aparece con otro color en algun momento."""
        nonlocal cycle
        cycle += 1
        crop = grab_crop()
        mask = isolate_code_color(crop)
        min_val, _ = mask.getextrema()
        if min_val < 255:
            text = pytesseract.image_to_string(mask, lang=args.lang, config=TESSERACT_CONFIG_LINE)
            match = pattern.search(text.upper())
            if match:
                return match, text
        else:
            text = ""

        if cycle % FALLBACK_EVERY == 0:
            text_full = pytesseract.image_to_string(preprocess(crop), lang=args.lang, config=TESSERACT_CONFIG)
            match_full = pattern.search(text_full.upper())
            if match_full:
                return match_full, text_full
            text = text_full or text

        return None, text

    deadline = time.monotonic() + args.seconds
    last_seen_raw = None

    try:
        while time.monotonic() < deadline:
            try:
                match, text = read_and_match()
            except RuntimeError as e:
                print(f"[{time.strftime('%H:%M:%S')}] aviso: {e}, reintentando...")
                time.sleep(args.interval)
                continue
            if text.strip() and text != last_seen_raw:
                last_seen_raw = text
                print(f"[{time.strftime('%H:%M:%S')}] leido: {text.strip()!r}")

            if match:
                # El codigo puede aparecer con un desvanecido (fade-in): si lo
                # agarramos recien apareciendo sale muy tenue y el OCR falla mas.
                # Esperamos un poco y volvemos a leer para confirmar con una
                # imagen mas nitida antes de copiar.
                time.sleep(0.5)
                try:
                    match2, _ = read_and_match()
                    if match2:
                        match = match2
                except RuntimeError:
                    pass

                codigo = match.group(1).replace("-", "")
                copy_to_clipboard(codigo)
                print(f"\n>>> CODIGO DETECTADO: {codigo}  (copiado al portapapeles)")
                notify("Codigo detectado", f"{codigo} copiado al portapapeles")
                return

            time.sleep(args.interval)

        print("Tiempo agotado, no se detecto ningun codigo.")
        notify("OCR Watcher", "Tiempo agotado, no se detecto ningun codigo.")
    finally:
        grabber.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        notify("OCR Watcher - error", str(e))
        raise
