import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ollama_catalogo as oc  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "ollama_search.html")


@pytest.fixture(autouse=True)
def _limpiar_cache():
    oc._CACHE.clear()
    yield
    oc._CACHE.clear()


def _html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def test_parsear_fixture_real():
    ms = oc.parsear(_html())
    assert len(ms) > 3
    p = ms[0]
    assert p["nombre"] == "gemma4"
    assert p["capacidades"] == ["vision", "tools", "thinking", "audio"]
    assert p["cloud"] is True
    assert "e2b" in p["tamanos"] and "31b" in p["tamanos"]
    assert p["descripcion"].startswith("Gemma 4 models")
    assert p["pulls"] == "26.3M"
    assert "&" not in p["descripcion"].replace("&&", "") or "&amp;" not in p["descripcion"]


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_buscar_web_y_cache(monkeypatch):
    llamadas = []

    def falso(req, timeout=None):
        llamadas.append(req.full_url)
        return _Resp(_html().encode("utf-8"))
    monkeypatch.setattr(oc.urllib.request, "urlopen", falso)
    r = oc.buscar("gemma", "vision")
    assert r["fuente"] == "web" and r["modelos"][0]["nombre"] == "gemma4"
    assert "q=gemma" in llamadas[0] and "c=vision" in llamadas[0]
    oc.buscar("gemma", "vision")
    assert len(llamadas) == 1  # cache


def test_filtro_invalido_se_ignora(monkeypatch):
    urls = []

    def falso(req, timeout=None):
        urls.append(req.full_url)
        return _Resp(_html().encode("utf-8"))
    monkeypatch.setattr(oc.urllib.request, "urlopen", falso)
    oc.buscar("x", "http://evil")
    assert "c=" not in urls[0] and "evil" not in urls[0]


def test_fallback_a_lista_curada(monkeypatch):
    def falla(req, timeout=None):
        raise OSError("sin red")
    monkeypatch.setattr(oc.urllib.request, "urlopen", falla)
    r = oc.buscar("", "")
    assert r["fuente"] == "lista" and len(r["modelos"]) >= 10
    assert {"nombre", "descripcion", "capacidades", "cloud", "tamanos", "pulls"} <= set(r["modelos"][0])


def test_filtro_sobre_lista_curada(monkeypatch):
    def falla(req, timeout=None):
        raise OSError("sin red")
    monkeypatch.setattr(oc.urllib.request, "urlopen", falla)
    v = oc.buscar("", "vision")["modelos"]
    assert v and all("vision" in m["capacidades"] for m in v)
    c = oc.buscar("", "cloud")["modelos"]
    assert c and all(m["cloud"] for m in c)
    assert [m["nombre"] for m in oc.buscar("qwen", "")["modelos"]] and \
        all("qwen" in m["nombre"] or "qwen" in m["descripcion"].lower() for m in oc.buscar("qwen", "")["modelos"])


def test_lista_vacia_sin_q_cae_a_lista(monkeypatch):
    monkeypatch.setattr(oc.urllib.request, "urlopen", lambda req, timeout=None: _Resp(b"<html></html>"))
    assert oc.buscar("", "")["fuente"] == "lista"


@pytest.mark.parametrize("n", ["gemma3:4b", "glm-5.3:cloud", "library/x"])
def test_nombres_validos(n):
    assert oc.nombre_valido(n)


@pytest.mark.parametrize("n", ["../x", "a b", "http://x", "", None])
def test_nombres_invalidos(n):
    assert not oc.nombre_valido(n)


def test_descargar_nombre_invalido():
    with pytest.raises(ValueError):
        oc.descargar("../x")


def _ndjson(*lineas):
    return _Resp(("\n".join(json.dumps(x) for x in lineas) + "\n").encode())


def test_descargar_progreso(monkeypatch):
    vistos = []
    cuerpo = {}

    def falso(req, timeout=None):
        cuerpo["url"] = req.full_url
        cuerpo["data"] = json.loads(req.data)
        return _ndjson({"status": "pulling manifest"},
                       {"status": "downloading", "digest": "x", "total": 100, "completed": 40},
                       {"status": "success"})
    monkeypatch.setattr(oc.urllib.request, "urlopen", falso)
    oc.descargar("gemma3:4b", lambda c, t, s: vistos.append((c, t, s)))
    assert cuerpo["url"].endswith("/api/pull")
    assert cuerpo["data"] == {"model": "gemma3:4b", "stream": True}
    assert (40, 100, "downloading") in vistos and vistos[-1][2] == "success"


def test_descargar_error(monkeypatch):
    monkeypatch.setattr(oc.urllib.request, "urlopen", lambda req, timeout=None: _ndjson({"error": "pull model manifest: file does not exist"}))
    with pytest.raises(RuntimeError, match="file does not exist"):
        oc.descargar("zzz")


def test_descargar_error_autorizacion(monkeypatch):
    monkeypatch.setattr(oc.urllib.request, "urlopen", lambda req, timeout=None: _ndjson({"error": "unauthorized"}))
    with pytest.raises(RuntimeError, match="ollama signin"):
        oc.descargar("glm-5.3:cloud")


def test_descargar_sin_ollama(monkeypatch):
    def falla(req, timeout=None):
        raise oc.urllib.error.URLError("refused")
    monkeypatch.setattr(oc.urllib.request, "urlopen", falla)
    with pytest.raises(RuntimeError, match="No se pudo conectar con Ollama en"):
        oc.descargar("gemma3")


def test_descargar_timeout_de_lectura_no_es_error_de_conexion(monkeypatch):
    class Lenta:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __iter__(self):
            raise TimeoutError("timed out")
    monkeypatch.setattr(oc.urllib.request, "urlopen", lambda req, timeout=None: Lenta())
    with pytest.raises(RuntimeError) as e:
        oc.descargar("gemma3")
    assert "No se pudo conectar" not in str(e.value) and "tiempo agotado" in str(e.value)


def test_descargar_usa_timeout_largo(monkeypatch):
    vistos = []

    def falso(req, timeout=None):
        vistos.append(timeout)
        return _ndjson({"status": "success"})
    monkeypatch.setattr(oc.urllib.request, "urlopen", falso)
    oc.descargar("gemma3")
    assert vistos[0] >= 600


def test_nombre_valido_rechaza_salto_de_linea_final():
    assert oc.nombre_valido("llama3:8b")
    assert not oc.nombre_valido("llama3:8b\n")
