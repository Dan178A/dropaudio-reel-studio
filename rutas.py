"""Carpetas de Reel Studio. No importa módulos de la app (evita ciclos)."""
import os, shutil, sys


def _congelado():
    return bool(getattr(sys, "frozen", False))


def datos():
    """Carpeta de datos del usuario (config, log, fuentes). Estable entre actualizaciones y reinstalaciones:
    en el .exe vive en %APPDATA%/ReelStudio, FUERA de la carpeta que Velopack administra (%LOCALAPPDATA%/ReelStudio)."""
    if _congelado():
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        carpeta = os.path.join(base, "ReelStudio")
        os.makedirs(carpeta, exist_ok=True)
        return carpeta
    return os.path.dirname(os.path.abspath(__file__))


def videos_defecto():
    """Carpeta de videos por defecto: en el .exe, Videos/Reel Studio del usuario; en desarrollo, junto al script."""
    if _congelado():
        return os.path.join(os.path.expanduser("~"), "Videos", "Reel Studio")
    return os.path.join(datos(), "Videos Dropaudioccs")


def migrar_datos():
    """Solo en el .exe: copia studio_config.json de junto al exe a la carpeta de datos, una vez. No borra nada."""
    if not _congelado():
        return
    nuevo = os.path.join(datos(), "studio_config.json")
    viejo = os.path.join(os.path.dirname(sys.executable), "studio_config.json")
    if not os.path.exists(nuevo) and os.path.exists(viejo):
        shutil.copy2(viejo, nuevo)
