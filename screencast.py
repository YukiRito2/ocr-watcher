"""Maneja el protocolo del portal ScreenCast de escritorio (Wayland/GNOME) para
obtener un stream de PipeWire de la pantalla, sin necesitar sudo ni APIs privadas.
Pide permiso UNA vez (dialogo nativo de 'compartir pantalla')."""
import os

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gio, GLib, Gst

BUS_NAME = "org.freedesktop.portal.Desktop"
OBJ_PATH = "/org/freedesktop/portal/desktop"
SCREENCAST_IFACE = "org.freedesktop.portal.ScreenCast"
RESTORE_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".restore_token")


class ScreenCastSession:
    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.sender_token = self.bus.get_unique_name()[1:].replace(".", "_")
        self._counter = 0
        self.session_handle = None
        self.node_id = None
        self.pw_fd = None

    def _next_token(self, prefix):
        self._counter += 1
        return f"{prefix}{self._counter}"

    def _call_and_wait(self, method, args, extra_options=None):
        token = self._next_token("tok")
        options = dict(extra_options or {})
        options["handle_token"] = GLib.Variant("s", token)

        request_path = f"/org/freedesktop/portal/desktop/request/{self.sender_token}/{token}"

        loop = GLib.MainLoop()
        result_box = {}

        def on_signal(_conn, _sender, _path, _iface, _signal, params):
            code, results = params.unpack()
            result_box["code"] = code
            result_box["results"] = results
            loop.quit()

        sub_id = self.bus.signal_subscribe(
            BUS_NAME, "org.freedesktop.portal.Request", "Response",
            request_path, None, Gio.DBusSignalFlags.NONE, on_signal,
        )

        full_args = args + (options,)
        self.bus.call_sync(
            BUS_NAME, OBJ_PATH, SCREENCAST_IFACE, method,
            GLib.Variant(self._sig_for(method), full_args),
            None, Gio.DBusCallFlags.NONE, -1, None,
        )

        loop.run()
        self.bus.signal_unsubscribe(sub_id)

        if result_box.get("code") != 0:
            raise RuntimeError(f"{method} fue rechazado o cancelado por el usuario")
        return result_box["results"]

    @staticmethod
    def _load_restore_token():
        if os.path.exists(RESTORE_TOKEN_FILE):
            with open(RESTORE_TOKEN_FILE) as f:
                return f.read().strip() or None
        return None

    @staticmethod
    def _save_restore_token(token):
        with open(RESTORE_TOKEN_FILE, "w") as f:
            f.write(token)

    @staticmethod
    def _sig_for(method):
        return {
            "CreateSession": "(a{sv})",
            "SelectSources": "(oa{sv})",
            "Start": "(osa{sv})",
        }[method]

    def start(self):
        session_token = self._next_token("session")
        results = self._call_and_wait(
            "CreateSession", (), {"session_handle_token": GLib.Variant("s", session_token)}
        )
        self.session_handle = results["session_handle"]

        select_options = {
            "types": GLib.Variant("u", 1),
            "multiple": GLib.Variant("b", False),
            "cursor_mode": GLib.Variant("u", 1),
            "persist_mode": GLib.Variant("u", 2),  # 2 = recordar hasta que lo revoques tu mismo
        }
        saved_token = self._load_restore_token()
        if saved_token:
            select_options["restore_token"] = GLib.Variant("s", saved_token)

        self._call_and_wait("SelectSources", (self.session_handle,), select_options)

        results = self._call_and_wait("Start", (self.session_handle, ""))
        streams = results["streams"]
        self.node_id, stream_props = streams[0]
        self.stream_size = stream_props.get("size")

        new_token = results.get("restore_token")
        if new_token:
            self._save_restore_token(new_token)

        fd_result = self.bus.call_with_unix_fd_list_sync(
            BUS_NAME, OBJ_PATH, SCREENCAST_IFACE, "OpenPipeWireRemote",
            GLib.Variant("(oa{sv})", (self.session_handle, {})),
            GLib.VariantType("(h)"), Gio.DBusCallFlags.NONE, -1, None, None,
        )
        variant, fd_list = fd_result
        handle_index = variant.unpack()[0]
        self.pw_fd = fd_list.get(handle_index)
        return self.node_id, self.pw_fd, self.stream_size


class FrameGrabber:
    """Arma el pipeline de PipeWire UNA sola vez y despues solo pide samples.
    Recrear el pipeline en cada frame (como se hacia antes) es lento y a veces
    la negociacion falla y pull-sample devuelve None."""

    def __init__(self, node_id, pw_fd):
        Gst.init(None)
        self.pipeline = Gst.parse_launch(
            f"pipewiresrc fd={pw_fd} path={node_id} ! videoconvert ! "
            f"video/x-raw,format=RGB ! appsink name=sink emit-signals=false "
            f"max-buffers=1 drop=true sync=false"
        )
        self.sink = self.pipeline.get_by_name("sink")
        self.pipeline.set_state(Gst.State.PLAYING)
        self.pipeline.get_state(Gst.CLOCK_TIME_NONE)  # espera a que realmente arranque

    def grab(self):
        """Devuelve el frame mas reciente del stream como PIL.Image (RGB)."""
        from PIL import Image

        for _ in range(3):  # reintenta si una negociacion puntual devuelve None
            sample = self.sink.emit("try-pull-sample", 2 * Gst.SECOND)
            if sample is not None:
                break
        else:
            raise RuntimeError("No se pudo obtener un frame de la pantalla (sample vacio)")

        buf = sample.get_buffer()
        caps = sample.get_caps()
        width = caps.get_structure(0).get_value("width")
        height = caps.get_structure(0).get_value("height")

        success, mapinfo = buf.map(Gst.MapFlags.READ)
        try:
            return Image.frombytes("RGB", (width, height), mapinfo.data, "raw", "RGB", 0, 1).copy()
        finally:
            buf.unmap(mapinfo)

    def close(self):
        self.pipeline.set_state(Gst.State.NULL)
