"""
Reel Studio · DropAudio CCS — app de escritorio (Python + pywebview).
Ventana nativa de Windows (motor Edge WebView2) con la misma interfaz y motor de Reel Studio.

Abrir:   doble clic en ReelStudio.pyw   (o:  pythonw ReelStudio.pyw)
Requisito extra:  pip install pywebview
"""
import os, sys

# Sin consola (pythonw) no hay stdout: los mensajes van a reel_studio.log junto a la app
BASE = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import rutas
from version import __version__
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(os.path.join(rutas.datos(), "reel_studio.log"), "a", encoding="utf-8", buffering=1)

import webview
import studio_web

FOLDER = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
ventana = None


class Api:
    """Funciones que la interfaz puede llamar con window.pywebview.api.*"""

    def elegir_carpeta(self):
        r = ventana.create_file_dialog(FOLDER, directory=studio_web.CFG.get("carpeta", ""))
        return (r[0] if isinstance(r, (list, tuple)) else r) if r else ""


def al_cerrar():
    if studio_web.JOB.get("corriendo") and studio_web.JOB.get("tarea") != "modelos":
        return ventana.create_confirmation_dialog(
            "Reel Studio", "Hay una tarea en curso. Si cierras ahora se detiene. ¿Cerrar de todas formas?")
    return True


def main():
    global ventana
    _, url = studio_web.iniciar_servidor(0)  # puerto libre, solo en esta PC
    ventana = webview.create_window(f"Reel Studio {__version__} · DropAudio CCS", url, js_api=Api(), width=1440, height=920,
                                    min_size=(1080, 700), background_color="#090807", text_select=True)
    ventana.events.closing += al_cerrar
    webview.start(private_mode=False)


if __name__ == "__main__":
    main()
