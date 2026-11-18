"""Ventana normal (NO pantalla completa) para seleccionar con el mouse la zona
de pantalla a vigilar. Muestra una miniatura de tu pantalla real; arrastras un
rectangulo sobre la miniatura y el resultado se escala de vuelta a coordenadas
reales de pantalla completa. Evita por completo los problemas de Tk con
pantalla completa/escalado de UI en este sistema.

Esc cancela. Guarda el resultado en un json: {x, y, width, height} en pixeles
reales de pantalla.
"""
import json
import sys
import tkinter as tk

OUT_PATH = sys.argv[1] if len(sys.argv) > 1 else "region.json"
BG_IMAGE_PATH = sys.argv[2] if len(sys.argv) > 2 else None
REAL_WIDTH = int(sys.argv[3]) if len(sys.argv) > 3 else None
REAL_HEIGHT = int(sys.argv[4]) if len(sys.argv) > 4 else None


class RegionSelector:
    def __init__(self, root, bg_image_path, real_width, real_height):
        self.root = root
        self.start = None
        self.rect = None
        self.result = None

        self.bg_photo = tk.PhotoImage(file=bg_image_path)
        shown_w, shown_h = self.bg_photo.width(), self.bg_photo.height()
        self.scale_x = real_width / shown_w
        self.scale_y = real_height / shown_h

        root.title("Elegi la zona a vigilar")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        root.config(cursor="crosshair")

        tk.Label(
            root, text="Arrastra sobre la miniatura para marcar la zona  -  Esc cancela",
            bg="#222", fg="white", font=("sans-serif", 11, "bold"), pady=6,
        ).pack(fill="x")

        self.canvas = tk.Canvas(root, width=shown_w, height=shown_h, highlightthickness=0)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_photo)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        root.bind("<Escape>", self.on_cancel)
        root.focus_force()

    def on_press(self, event):
        self.start = (event.x, event.y)
        self.rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#00ffcc", width=2
        )

    def on_drag(self, event):
        if self.rect is None:
            return
        x0, y0 = self.start
        self.canvas.coords(self.rect, x0, y0, event.x, event.y)

    def on_release(self, event):
        if self.start is None:
            return
        x0, y0 = self.start
        x1, y1 = event.x, event.y
        left, top = min(x0, x1), min(y0, y1)
        width, height = abs(x1 - x0), abs(y1 - y0)
        if width > 3 and height > 3:
            # Escalar de coordenadas de la miniatura a coordenadas reales de pantalla.
            self.result = {
                "x": int(left * self.scale_x),
                "y": int(top * self.scale_y),
                "width": int(width * self.scale_x),
                "height": int(height * self.scale_y),
            }
        self.root.destroy()

    def on_cancel(self, _event):
        self.result = None
        self.root.destroy()


def main():
    if not BG_IMAGE_PATH or not REAL_WIDTH or not REAL_HEIGHT:
        print("Uso: select_region.py <salida.json> <imagen_fondo.png> <ancho_real> <alto_real>", file=sys.stderr)
        sys.exit(2)

    root = tk.Tk()
    selector = RegionSelector(root, BG_IMAGE_PATH, REAL_WIDTH, REAL_HEIGHT)
    root.mainloop()

    if selector.result is None:
        print("Seleccion cancelada", file=sys.stderr)
        sys.exit(1)

    with open(OUT_PATH, "w") as f:
        json.dump(selector.result, f)
    print(f"Region guardada en {OUT_PATH}: {selector.result}")


if __name__ == "__main__":
    main()
