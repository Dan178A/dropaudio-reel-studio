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

HYPERFRAMES = "0.8.77"
TIMEOUT_RENDER = 300  # segundos
CREAR = 0x08000000  # CREATE_NO_WINDOW (el mismo valor que reel_studio.CREAR): sin ventanas de consola en Windows
_RE_DURACION = r'(<div id="root"[^>]*?data-duration=")[0-9.]+(")'


def _nombre_corto(p):
    """«KZ AE01 (Adaptador BT)» -> «KZ AE01» (misma regla que reel_studio.nombre_corto)."""
    return re.sub(r"\s*\([^)]*\)", "", p or "").strip() or p


def _sin_ventana():
    """creationflags para subprocess: en Windows, sin ventana de consola (la app empaquetada no tiene consola)."""
    return {"creationflags": CREAR} if sys.platform == "win32" else {}


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
        r = _comprobar()
        if not r[0]:
            # El PATH del proceso se fija al arrancar: un instalador de Node o FFmpeg que agrega su carpeta al PATH
            # solo se nota tras reiniciar Reel Studio (por eso el motivo lo pide). El fallo no se cachea solo por
            # si el programa aparece en una carpeta que ya estaba en el PATH; studio_web repite esto cada 30 s.
            return r
        _DISPONIBLE = r
    return _DISPONIBLE


def _comprobar():
    node = shutil.which("node")
    if not node:
        return False, "Instala Node 22 o superior (nodejs.org) para las escenas animadas y reinicia Reel Studio"
    try:
        r = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=15, **_sin_ventana())
        m = re.match(r"v?(\d+)", (r.stdout or "").strip())
        mayor = int(m.group(1)) if m else 0
    except (OSError, subprocess.SubprocessError):
        mayor = 0
    if mayor < 22:
        return False, "Instala Node 22 o superior (nodejs.org) para las escenas animadas y reinicia Reel Studio"
    if not shutil.which("ffmpeg"):
        return False, "Instala FFmpeg y ponlo en el PATH para las escenas animadas, y reinicia Reel Studio"
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


def _coincidencias(nombre, nombres):
    """Nombres de `nombres` que corresponden a `nombre` (sin mayúsculas): el nombre completo exacto si existe; si
    no, los que tienen ese nombre corto. Más de uno = ambiguo (p. ej. «KZ Castor Pro» con Harman y Bass)."""
    n = (nombre or "").strip().lower()
    if not n:
        return []
    exactos = [k for k in nombres if (k or "").strip().lower() == n]
    if exactos:
        return exactos[:1]
    return [k for k in nombres if (_nombre_corto(k) or "").strip().lower() == n]


def _imagen_de(nombre):
    """Archivo de `productos/` para un producto (nombre completo, o corto si no es ambiguo) o ''."""
    mapa = _mapa()
    k = _coincidencias(nombre, list(mapa))
    return mapa[k[0]] if len(k) == 1 else ""


# ------------------------------------------------------------------ duración
def _palabras(valor):
    return len(str(valor).split()) if valor is not None else 0


def duracion(tipo, datos):
    """Entrada + lectura (2,5 palabras/s, >= 1,5 s por bloque) + pausa final + salida, acotado y a 0,1 s."""
    cat = catalogo()[tipo]
    mec = _mecanismo()
    pps = mec.get("palabras_por_segundo", 2.5)
    minimo = mec.get("minimo_por_bloque", 1.5)
    pausa = cat.get("pausa_final", mec.get("pausa_final", 1.0))
    datos = datos or {}
    palabras = 0  # el texto fijo (kicker/CTA) se lee durante la entrada: no suma
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


def _con_precio(catalogo_precios):
    return {(p.get("nombre") or ""): p["precio"] for p in catalogo_precios or []
            if isinstance(p, dict) and p.get("nombre") and _numero(p.get("precio")) is not None}


def ambiguos(nombre, catalogo_precios):
    """Nombres completos del catálogo (con precio) que comparten el nombre corto `nombre`, si son varios; si no, []."""
    k = _coincidencias(nombre, list(_con_precio(catalogo_precios)))
    return k if len(k) > 1 else []


def _precio_catalogo(nombre, catalogo_precios):
    """Precio del producto del catálogo de la app que coincide con `nombre` o None. Primero el nombre completo;
    el nombre corto solo vale si es de un único producto (si es ambiguo, None: hay que usar el completo)."""
    precios = _con_precio(catalogo_precios)
    k = _coincidencias(nombre, list(precios))
    return _numero(precios[k[0]]) if len(k) == 1 else None


def nombre_para_escena(nombre, catalogo_precios, maximo=32):
    """Cómo nombrar el producto en una escena: el nombre completo; si no cabe en `maximo`, el corto (si no es
    ambiguo). Así el precio siempre se resuelve sin dudas contra el catálogo."""
    nombre = (nombre or "").strip()
    if len(nombre) <= maximo:
        return nombre
    corto, nombres = _nombre_corto(nombre), list(_con_precio(catalogo_precios))
    propio = _coincidencias(nombre, nombres)
    return corto if propio and _coincidencias(corto, nombres) == propio else nombre


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


def _huella_imagen(datos):
    """Hash del archivo de imagen del producto (si cambia la foto con el mismo nombre, cambia la clave) o ''."""
    img = (datos or {}).get("imagen") or ""
    ruta = os.path.join(_carpeta_escenas(), "productos", img) if img else ""
    if not ruta or not os.path.isfile(ruta):
        return ""
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _clave(tipo, datos, dur):
    base = json.dumps([tipo, datos, dur, _version_plantilla(tipo), HYPERFRAMES, _huella_imagen(datos)],
                      sort_keys=True, ensure_ascii=False)
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


def _matar_arbol(proc):
    """Mata el proceso y todos sus hijos. En Windows npx es npx.cmd (cmd.exe -> node -> Chromium/ffmpeg): matar
    solo cmd.exe deja vivos a los nietos con las tuberías abiertas, así que se usa taskkill /T."""
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30,
                           **_sin_ventana())
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        proc.kill()
    except OSError:
        pass


def _ejecutar(cmd, cwd, timeout):
    """(código de salida, stdout+stderr) del comando; RuntimeError si no arranca. TimeoutExpired si se pasa del
    tiempo (tras matar todo el árbol de procesos)."""
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace", **_sin_ventana())
    except OSError as e:
        raise RuntimeError("No se pudo ejecutar HyperFrames: %s" % e)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _matar_arbol(proc)
        try:
            proc.communicate(timeout=30)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass
        raise
    return proc.returncode, (out or "") + "\n" + (err or "")


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
    # ignore_cleanup_errors: si Chromium aún retiene algún archivo al salir, no se pierde un render que salió bien
    with tempfile.TemporaryDirectory(prefix="escena_", ignore_cleanup_errors=True) as tmp:
        _ensamblar(tipo, datos, dur, tmp)
        salida = os.path.join(tmp, "salida.mp4")
        cmd = [npx, "--yes", "hyperframes@" + HYPERFRAMES, "render", "--variables-file", "vars.json",
               "--quality", "looks", "--output", salida]
        try:
            rc, texto = _ejecutar(cmd, tmp, TIMEOUT_RENDER)
        except subprocess.TimeoutExpired:
            raise RuntimeError("La escena «%s» tardó más de %d s en renderizarse." % (tipo, TIMEOUT_RENDER))
        if rc != 0 or not os.path.isfile(salida):
            texto = texto.strip()
            ultimas = "\n".join(texto.splitlines()[-15:])
            if re.search(r"ENOTFOUND|EAI_AGAIN|ETIMEDOUT|ECONNREFUSED|ECONNRESET|network", texto, re.I) \
                    and "hyperframes" in texto.lower():
                raise RuntimeError("HyperFrames no está descargado; conéctate a internet una vez.\n" + ultimas)
            raise RuntimeError("Falló el render de la escena «%s»:\n%s" % (tipo, ultimas))
        _publicar(salida, destino, cache_dir)
    return destino


def _publicar(salida, destino, cache_dir):
    """Copia el render a la caché sin pisar a otro render simultáneo de la misma escena: un .part único y luego
    os.replace. Si el destino ya apareció (otro render lo dejó), se reutiliza."""
    fd, part = tempfile.mkstemp(dir=cache_dir, suffix=".part")
    os.close(fd)
    try:
        shutil.copyfile(salida, part)
        if os.path.isfile(destino) and os.path.getsize(destino) > 0:
            return
        try:
            os.replace(part, destino)
        except PermissionError:  # Windows: el destino está abierto por otro proceso (lo acaba de dejar otro render)
            if not (os.path.isfile(destino) and os.path.getsize(destino) > 0):
                raise
    finally:
        if os.path.exists(part):
            try:
                os.remove(part)
            except OSError:
                pass
