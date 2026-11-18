"""Dibuja un marco delgado (4 franjas de color) sobre la zona real de pantalla
que esta vigilando watch.py, para que se vea claramente cual es esa zona
mientras corre. Se lanza como proceso aparte y se mata cuando watch.py termina.

Uso: overlay.py <x> <y> <width> <height>
"""
import sys
import tkinter as tk

THICKNESS = 4
COLOR = "#00ffcc"


def strip(root, x, y, w, h):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.configure(bg=COLOR)
    win.geometry(f"{w}x{h}+{x}+{y}")
    return win


def main():
    x, y, w, h = (int(v) for v in sys.argv[1:5])

    root = tk.Tk()
    root.withdraw()

    strip(root, x, y, w, THICKNESS)                       # arriba
    strip(root, x, y + h - THICKNESS, w, THICKNESS)        # abajo
    strip(root, x, y, THICKNESS, h)                        # izquierda
    strip(root, x + w - THICKNESS, y, THICKNESS, h)        # derecha

    root.mainloop()


if __name__ == "__main__":
    main()
