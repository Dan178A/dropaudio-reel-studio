"""Escenas animadas (HyperFrames): catálogo, validación, duración y render a .mp4.

El LLM solo elige tipo y textos; aquí se valida todo (precios contra el catálogo de la app, imagen desde
`escenas/productos/mapa.json`) y se renderiza con HyperFrames en una carpeta temporal.
"""
import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import reel_studio as core

HYPERFRAMES = "0.8.77"
TIMEOUT_RENDER = 300  # segundos
_RE_DURACION = r'(<div id="root"[^>]*?data-duration=")[0-9.]+(")'


def _carpeta_escenas():
    """`escenas/` dentro del instalador (sys._MEIPASS) o junto al módulo."""
    res = getattr(sys, "_MEIPASS", None)
    for base in (res, os.path.dirname(os.path.abspath(__file__))):
        if base:
            r = os.path.join(base, "escenas")
            if os.path.isdir(r):
                return r
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "escenas")


# ------------------------------------------------------------------ disponibilidad
_DISPONIBLE = None


def disponible():
    """(bool, motivo): hace falta Node >= 22 y ffmpeg en el PATH. Cacheado."""
    global _DISPONIBLE
    if _DISPONIBLE is None:
        _DISPONIBLE = _comprobar()
    return _DISPONIBLE


def _comprobar():
    node = shutil.which("node")
    if not node:
        return False, "Instala Node 22 o superior (nodejs.org) para las escenas animadas"
    try:
        r = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=15)
        m = re.match(r"v?(\d+)", (r.stdout or "").strip())
        mayor = int(m.group(1)) if m else 0
    except (OSError, subprocess.SubprocessError):
        mayor = 0
    if mayor < 22:
        return False, "Instala Node 22 o superior (nodejs.org) para las escenas animadas"
    if not shutil.which("ffmpeg"):
        return False, "Instala FFmpeg y ponlo en el PATH para las escenas animadas"
    return True, ""


# ------------------------------------------------------------------ catálogo
@functools.lru_cache(maxsize=1)
def _cargar():
    with open(os.path.join(_carpeta_escenas(), "catalogo.json"), encoding="utf-8") as f:
        return json.load(f)


def catalogo():
    """Solo los tipos de escena (sin la clave técnica «duracion»)."""
    return {k: v for k, v in _cargar().items() if k != "duracion"}


def _mecanismo():
    return _cargar().get("duracion", {})


@functools.lru_cache(maxsize=1)
def _mapa():
    try:
        with open(os.path.join(_carpeta_escenas(), "productos", "mapa.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _imagen_de(nombre):
    """Archivo de `productos/` para un producto (nombre exacto o corto, sin mayúsculas) o ''."""
    n = (nombre or "").strip().lower()
    if not n:
        return ""
    mapa = _mapa()
    for k, v in mapa.items():
        if k.lower() == n:
            return v
    for k, v in mapa.items():
        if (core.nombre_corto(k) or "").lower() == n:
            return v
    return ""


# ------------------------------------------------------------------ duración
def _palabras(valor):
    return len(str(valor).split()) if valor is not None else 0


def duracion(tipo, datos):
    """Entrada + lectura (2,5 palabras/s, >= 1,5 s por bloque) + pausa final + salida, acotado y a 0,1 s."""
    cat = catalogo()[tipo]
    mec = _mecanismo()
    pps = mec.get("palabras_por_segundo", 2.5)
    minimo = mec.get("minimo_por_bloque", 1.5)
    pausa = mec.get("pausa_final", 1.0)
    datos = datos or {}
    palabras = _palabras(cat.get("texto_fijo", ""))
    for b in cat["bloques"]:
        palabras += _palabras(datos.get(b, ""))
    lectura = max(palabras / pps, minimo * len(cat["bloques"]))
    total = cat["entrada"] + lectura + pausa + cat["salida"]
    total = min(max(total, cat["dur_min"]), cat["dur_max"])
    return round(total, 1)


# ------------------------------------------------------------------ validación
def _numero(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip().lstrip("$").replace(",", "."))
        except ValueError:
            return None
    return None


def _precio_catalogo(nombre, catalogo_precios):
    """Precio del producto del catálogo de la app que coincide con `nombre` (completo o corto) o None."""
    n = (nombre or "").strip().lower()
    if not n:
        return None
    for exacto in (True, False):
        for p in catalogo_precios or []:
            nom = p.get("nombre") or ""
            cand = nom.lower() if exacto else (core.nombre_corto(nom) or "").lower()
            if cand == n and p.get("precio") is not None:
                return float(p["precio"])
    return None


def _limpio(x):
    return int(x) if float(x).is_integer() else x


def validar_escena(tipo, datos, catalogo_precios):
    """Datos limpios listos para `render`, o None si la escena no es válida."""
    cat = catalogo().get(tipo) if isinstance(tipo, str) else None
    if not cat or not isinstance(datos, dict):
        return None
    out = {}
    for var, cfg in cat["variables"].items():
        if var == "imagen":
            continue
        v = datos.get(var)
        if cfg["tipo"] == "string":
            if not isinstance(v, str):
                return None
            v = v.strip()
            if cfg.get("max"):
                v = v[:cfg["max"]].rstrip()
            if not v:
                return None
            out[var] = v
        else:
            if _numero(v) is None:
                return None
            out[var] = _numero(v)
    # Cada precio solo vale si es el del producto nombrado, en el catálogo de la app.
    for var in [k for k, c in cat["variables"].items() if c["tipo"] == "number"]:
        nombre = out.get("producto") if var == "precio" else out.get(var.replace("_precio", "_nombre"))
        real = _precio_catalogo(nombre, catalogo_precios)
        if real is None or abs(real - out[var]) > 0.005:
            return None
        out[var] = _limpio(real)
    if "imagen" in cat["variables"]:
        out["imagen"] = _imagen_de(out.get("producto"))
    return out


# ------------------------------------------------------------------ render
def _version_plantilla(tipo):
    with open(os.path.join(_carpeta_escenas(), tipo, "index.html"), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _clave(tipo, datos, dur):
    base = json.dumps([tipo, datos, dur, _version_plantilla(tipo)], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _ensamblar(tipo, datos, dur, tmp):
    res = _carpeta_escenas()
    shutil.copytree(os.path.join(res, tipo), tmp, dirs_exist_ok=True)
    for sub in ("fonts", "vendor"):
        shutil.copytree(os.path.join(res, sub), os.path.join(tmp, sub), dirs_exist_ok=True)
    variables = dict(datos)
    if "imagen" in catalogo()[tipo]["variables"]:
        img = datos.get("imagen") or ""
        if img and os.path.isfile(os.path.join(res, "productos", img)):
            os.makedirs(os.path.join(tmp, "productos"), exist_ok=True)
            shutil.copy2(os.path.join(res, "productos", img), os.path.join(tmp, "productos", img))
            variables["imagen"] = "productos/" + img
        else:
            variables["imagen"] = ""  # siempre se pasa: si no, se vería la imagen de ejemplo
    ruta = os.path.join(tmp, "index.html")
    with open(ruta, encoding="utf-8", newline="") as f:
        html = f.read()
    seg = ("%.2f" % dur).rstrip("0").rstrip(".")
    html, n = re.subn(_RE_DURACION, lambda m: m.group(1) + seg + m.group(2), html, count=1)
    if n != 1:
        raise RuntimeError("La plantilla de la escena «%s» no tiene data-duration en su raíz." % tipo)
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(html)
    with open(os.path.join(tmp, "vars.json"), "w", encoding="utf-8") as f:
        json.dump(variables, f, ensure_ascii=False)


def render(tipo, datos, cache_dir, dur=None):
    """Ruta del .mp4 de la escena (de la caché si ya existe). `datos` ya validados."""
    if tipo not in catalogo():
        raise RuntimeError("Tipo de escena desconocido: %s" % tipo)
    if dur is None:
        dur = duracion(tipo, datos)
    os.makedirs(cache_dir, exist_ok=True)
    destino = os.path.abspath(os.path.join(cache_dir, _clave(tipo, datos, dur)[:24] + ".mp4"))
    if os.path.isfile(destino) and os.path.getsize(destino) > 0:
        return destino
    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError("No se encontró npx: instala Node 22 o superior.")
    with tempfile.TemporaryDirectory(prefix="escena_") as tmp:
        _ensamblar(tipo, datos, dur, tmp)
        salida = os.path.join(tmp, "salida.mp4")
        cmd = [npx, "--yes", "hyperframes@" + HYPERFRAMES, "render", "--variables-file", "vars.json",
               "--quality", "looks", "--output", salida]
        extra = {"creationflags": 0x08000000} if os.name == "nt" else {}
        try:
            r = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=TIMEOUT_RENDER, **extra)
        except subprocess.TimeoutExpired:
            raise RuntimeError("La escena «%s» tardó más de %d s en renderizarse." % (tipo, TIMEOUT_RENDER))
        except OSError as e:
            raise RuntimeError("No se pudo ejecutar HyperFrames: %s" % e)
        if r.returncode != 0 or not os.path.isfile(salida):
            texto = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
            ultimas = "\n".join(texto.splitlines()[-15:])
            if re.search(r"ENOTFOUND|EAI_AGAIN|ETIMEDOUT|ECONNREFUSED|ECONNRESET|network", texto, re.I) \
                    and "hyperframes" in texto.lower():
                raise RuntimeError("HyperFrames no está descargado; conéctate a internet una vez.\n" + ultimas)
            raise RuntimeError("Falló el render de la escena «%s»:\n%s" % (tipo, ultimas))
        shutil.move(salida, destino)
    return destino
