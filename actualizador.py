"""Actualizador de Reel Studio (Velopack + releases públicos de GitHub).

Nunca falla hacia afuera: si la app no corre desde una instalación Velopack
(desarrollo, carpeta dist suelta) solo informa `instalada=False`.
"""
import json
import threading
import urllib.request

import version

try:
    import velopack
except Exception:  # paquete ausente: se comporta como "no instalada"
    velopack = None

REPO = "https://github.com/Dan178A/dropaudio-reel-studio"
API_ULTIMA = "https://api.github.com/repos/Dan178A/dropaudio-reel-studio/releases/latest"

_LOCK = threading.Lock()
_ESTADO = {"instalada": False, "actual": version.__version__, "nueva": None, "notas": "", "error": None}
_PENDIENTE = {"mgr": None, "info": None}


def estado():
    with _LOCK:
        return dict(_ESTADO)


def _guardar(**kw):
    with _LOCK:
        _ESTADO.update(kw)


def _manager():
    """UpdateManager con la fuente GitHub; lanza si la app no está instalada con Velopack."""
    if velopack is None:
        raise RuntimeError("velopack no disponible")
    return velopack.UpdateManager(velopack.GithubSource(REPO))


def _notas_github():
    """Notas de la última release vía API pública (mejor esfuerzo; '' si falla)."""
    try:
        req = urllib.request.Request(API_ULTIMA, headers={"User-Agent": "ReelStudio", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return str(json.load(r).get("body") or "")
    except Exception:
        return ""


def buscar():
    """Consulta si hay versión nueva. Nunca lanza: los errores quedan en estado()['error']."""
    _guardar(actual=version.__version__, nueva=None, notas="", error=None)
    try:
        mgr = _manager()
    except Exception:
        _guardar(instalada=False)
        return estado()
    _guardar(instalada=True)
    try:
        info = mgr.check_for_updates()
        if info is None:
            with _LOCK:
                _PENDIENTE.update(mgr=None, info=None)
            return estado()
        rel = info.TargetFullRelease
        notas = str(getattr(rel, "NotesMarkdown", "") or "") or _notas_github()
        with _LOCK:
            _PENDIENTE.update(mgr=mgr, info=info)
        _guardar(nueva=str(rel.Version), notas=notas)
    except Exception as e:
        _guardar(error=str(e) or e.__class__.__name__)
    return estado()


def aplicar(progreso=None):
    """Descarga la versión encontrada por buscar() (progreso 0-100) y reinicia la app."""
    with _LOCK:
        mgr, info = _PENDIENTE["mgr"], _PENDIENTE["info"]
    if mgr is None or info is None:
        raise RuntimeError("No hay una actualización pendiente. Busca de nuevo.")

    def cb(p):
        if progreso:
            try:
                progreso(int(p))
            except Exception:
                pass
    mgr.download_updates(info, cb)
    cb(100)
    mgr.apply_updates_and_restart(info)
    return "Actualización lista; reiniciando…"
