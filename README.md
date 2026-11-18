# OCR Screen Code Watcher

Vigila una zona de tu pantalla (que tu mismo marcas con el mouse, como un recorte
de captura de pantalla) y usa OCR para detectar un codigo con el formato
`CODIGO:XXX-XXXX-123` apenas aparece en pantalla, copiandolo directamente al
portapapeles. Pensado para codigos que aparecen brevemente en un video, una
transmision en vivo, etc., sin tener que pausar nada ni copiarlo a mano.

Funciona sobre GNOME/Wayland usando el portal de escritorio
(`org.freedesktop.portal.ScreenCast`) + PipeWire, asi que no necesita privilegios
de administrador para capturar pantalla.

## Como funciona

1. Pide permiso de captura de pantalla una sola vez (dialogo nativo del sistema).
   El permiso queda guardado (`restore_token`) para no volver a preguntar en las
   siguientes ejecuciones.
2. Te muestra una miniatura de tu pantalla actual en una ventana normal y
   arrastras un rectangulo sobre la zona que quieres vigilar.
3. Captura esa zona repetidamente, le aplica OCR (Tesseract) y busca el patron
   `CODIGO` seguido de algo con forma `XXX-XXXX-XXX` (letras y numeros).
4. En cuanto lo encuentra, copia el codigo (sin guiones) al portapapeles y
   termina.

## Instalacion

```bash
./setup.sh
```

Esto instala Tesseract, GStreamer/PipeWire, `wl-clipboard` y crea el entorno
virtual de Python con las dependencias (`pytesseract`, `Pillow`; PyGObject se
usa del sistema).

## Uso

```bash
./run.sh                      # marca la zona y vigila 120s
./run.sh --reselect           # vuelve a pedir que marques la zona
./run.sh --seconds 60         # cambia el tiempo maximo de espera
./run.sh --interval 0.4       # cambia la frecuencia de lectura
./run.sh --pattern '...'      # usa tu propio patron de regex
```

La primera vez (o con `--reselect`) te va a pedir que marques con el mouse la
zona de pantalla a vigilar. Si cancelas o sueltas sin arrastrar, te lo vuelve a
pedir en vez de cerrarse.

**Importante:** antes de que salga el selector, deja visible en pantalla lo que
vas a vigilar (el video, la ventana, etc.) — la miniatura del selector es una
foto de lo que este en pantalla en ese momento.

## Anclarlo a la barra de tareas (Ubuntu/GNOME)

Ver `ocr-watcher.desktop`: se instala en `~/.local/share/applications/` y se
puede anclar al dock como cualquier otra aplicacion.

## Archivos

- `watch.py` — logica principal (bucle de vigilancia, OCR, deteccion, portapapeles).
- `screencast.py` — manejo del portal ScreenCast + captura de frames via PipeWire.
- `select_region.py` — ventana de seleccion de zona (miniatura + arrastrar rectangulo).
- `run.sh` — lanzador rapido.
- `setup.sh` — instalacion de dependencias.
