"""Catálogo de modelos de ollama.com y descarga con progreso.

Nunca rompe hacia afuera al buscar: sin internet o si cambia el HTML, cae a la lista curada
(`ollama_curados.json`). El cliente nunca aporta una URL: solo `q` y un filtro de la lista blanca.
"""
import html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

import reel_studio as core

URL_BUSQUEDA = "https://ollama.com/search"
FILTROS = ("", "vision", "cloud", "tools", "embedding", "thinking")
TTL = 600  # segundos de cache por (q, filtro)
RE_NOMBRE = re.compile(r"^[a-z0-9][a-z0-9._/-]*(:[a-z0-9._-]+)?$")

_CACHE = {}
_LOCK = threading.Lock()


# ------------------------------------------------------------------ parseo
class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.modelos = []
        self._m = None
        self._pila = []       # (etiqueta, clase) de lo abierto dentro del <li>
        self._ultimo = ""     # último texto de un <span> sin estilo (candidato a «pulls»)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "li" and self._m is None:
            self._m = {"nombre": "", "descripcion": "", "capacidades": [], "cloud": False, "tamanos": [], "pulls": ""}
            self._pila = []
            self._ultimo = ""
            return
        if self._m is None:
            return
        if tag == "a" and not self._m["nombre"] and (a.get("href") or "").startswith("/library/"):
            self._m["nombre"] = a["href"][len("/library/"):].strip("/")
        if tag not in ("br", "img", "input", "path", "meta", "link"):
            self._pila.append((tag, a.get("class") or ""))

    def handle_endtag(self, tag):
        if self._m is None:
            return
        if tag == "li":
            if self._m["nombre"]:
                self.modelos.append(self._m)
            self._m = None
            return
        for i in range(len(self._pila) - 1, -1, -1):
            if self._pila[i][0] == tag:
                del self._pila[i:]
                break

    def handle_data(self, data):
        if self._m is None or not self._pila:
            return
        t = " ".join(data.replace("\xa0", " ").split())
        if not t:
            return
        tag, cls = self._pila[-1]
        if tag == "p" and "max-w-lg" in cls:
            self._m["descripcion"] = (self._m["descripcion"] + " " + t).strip()
        elif tag == "span" and "bg-indigo-50" in cls:
            self._m["capacidades"].append(t)
        elif tag == "span" and "bg-cyan-50" in cls:
            if t.lower() == "cloud":
                self._m["cloud"] = True
        elif tag == "span" and "bg-[#ddf4ff]" in cls:
            self._m["tamanos"].append(t)
        elif tag == "span" and t.lower() == "pulls":
            if self._ultimo:
                self._m["pulls"] = self._ultimo
        elif tag == "span" and not cls:
            self._ultimo = t


def parsear(texto_html):
    """HTML de ollama.com/search -> lista de modelos (mismo esquema que la lista curada)."""
    p = _Parser()
    p.feed(texto_html)
    p.close()
    for m in p.modelos:
        m["descripcion"] = html.unescape(m["descripcion"])
    return p.modelos


# ------------------------------------------------------------------ lista curada
def _ruta_curados():
    res = getattr(sys, "_MEIPASS", None)
    for base in (res, os.path.dirname(os.path.abspath(__file__))):
        if base:
            r = os.path.join(base, "ollama_curados.json")
            if os.path.isfile(r):
                return r
    return None


def curados():
    r = _ruta_curados()
    if not r:
        return []
    try:
        with open(r, encoding="utf-8") as f:
            return list(json.load(f).get("modelos", []))
    except Exception:
        return []


def _filtrar(modelos, q, filtro):
    q = (q or "").strip().lower()
    out = []
    for m in modelos:
        if filtro == "cloud" and not m.get("cloud"):
            continue
        if filtro and filtro != "cloud" and filtro not in m.get("capacidades", []):
            continue
        if q and q not in m["nombre"].lower() and q not in m.get("descripcion", "").lower():
            continue
        out.append(m)
    return out


# ------------------------------------------------------------------ búsqueda
def buscar(q="", filtro=""):
    """-> {"fuente": "web"|"lista", "modelos": [...]}. Cache de 10 min por (q, filtro)."""
    q = (q or "").strip()
    filtro = filtro if filtro in FILTROS else ""
    clave = (q, filtro)
    with _LOCK:
        c = _CACHE.get(clave)
        if c and time.time() - c[0] < TTL:
            return c[1]
    res = None
    try:
        params = {"q": q}
        if filtro:
            params["c"] = filtro
        req = urllib.request.Request(URL_BUSQUEDA + "?" + urllib.parse.urlencode(params),
                                     headers={"User-Agent": "ReelStudio/1.0 (catalogo ollama)"})
        with urllib.request.urlopen(req, timeout=8) as r:
            modelos = parsear(r.read().decode("utf-8", "replace"))
        if modelos or q:
            res = {"fuente": "web", "modelos": modelos}
    except Exception:
        res = None
    if res is None:
        return {"fuente": "lista", "modelos": _filtrar(curados(), q, filtro)}
    with _LOCK:
        _CACHE[clave] = (time.time(), res)
    return res


# ------------------------------------------------------------------ descarga
def nombre_valido(modelo):
    return bool(isinstance(modelo, str) and RE_NOMBRE.match(modelo))


def descargar(modelo, progreso=None):
    """Descarga con /api/pull (NDJSON). progreso(completed, total, status). Lanza RuntimeError si falla."""
    if not nombre_valido(modelo):
        raise ValueError("Nombre de modelo no válido")
    req = urllib.request.Request(
        core.OLLAMA.rstrip("/") + "/api/pull",
        data=json.dumps({"model": modelo, "stream": True}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            for linea in r:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    d = json.loads(linea)
                except ValueError:
                    continue
                if d.get("error"):
                    err = str(d["error"])
                    if re.search(r"unauthori|authoriz|sign ?in|\b40[13]\b", err, re.I):
                        raise RuntimeError("Inicia sesión en Ollama: ejecuta `ollama signin`")
                    raise RuntimeError(err)
                if progreso:
                    progreso(d.get("completed") or 0, d.get("total") or 0, d.get("status", ""))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama respondió {e.code} al descargar «{modelo}»")
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"No se pudo conectar con Ollama en {core.OLLAMA}") from e
    return f"Modelo «{modelo}» listo"
