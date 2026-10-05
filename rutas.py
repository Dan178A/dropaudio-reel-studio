"""Carpetas de Reel Studio. No importa módulos de la app (evita ciclos)."""
import os, shutil, sys


def _congelado():
    return bool(getattr(sys, "frozen", False))


def datos():
    """Carpeta de datos del usuario (config, log, videos). Estable entre actualizaciones."""
    if _congelado():
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        carpeta = os.path.join(base, "ReelStudio", "datos")
        os.makedirs(carpeta, exist_ok=True)
        return carpeta
    return os.path.dirname(os.path.abspath(__file__))


def migrar_datos():
    """Solo en el .exe: copia studio_config.json de junto al exe a la carpeta de datos, una vez. No borra nada."""
    if not _congelado():
        return
    nuevo = os.path.join(datos(), "studio_config.json")
    viejo = os.path.join(os.path.dirname(sys.executable), "studio_config.json")
    if not os.path.exists(nuevo) and os.path.exists(viejo):
        shutil.copy2(viejo, nuevo)
