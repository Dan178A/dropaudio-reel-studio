"""Guardado del guion por HTTP (/api/guion) y /api/estado con escenas. Servidor local en un puerto libre,
carpeta temporal; sin red, sin Ollama y sin Node (escenas.disponible() se simula)."""
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import escenas  # noqa: E402
import studio_web  # noqa: E402

CATALOGO = [{"nombre": "KZ Castor Pro (Harman)", "precio": 13.0}]


@pytest.fixture
def servidor(tmp_path, monkeypatch):
    monkeypatch.setitem(studio_web.CFG, "carpeta", str(tmp_path))
    monkeypatch.setitem(studio_web.CFG, "catalogo", CATALOGO)
    monkeypatch.setattr(escenas, "disponible", lambda: (False, "Instala Node 22 o superior"))
    monkeypatch.setattr(studio_web, "_ESC_CACHE", [0.0, None])
    (tmp_path / "analisis.json").write_text(json.dumps({"a.mp4": {
        "archivo": "a.mp4", "foto": False, "dur": 20.0, "tomas": [], "habla": []}}), encoding="utf-8")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), studio_web.H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path
    srv.shutdown()
    srv.server_close()


def pedir(base, ruta, cuerpo=None):
    req = urllib.request.Request(base + ruta, data=None if cuerpo is None else json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def serie(datos_escena, paso="cta"):
    return {"videos": [{
        "formato": "asi_compras", "titulo": "Así compras 1", "nombre": "reel_01", "gancho": "g", "promesa": "p",
        "clips": [
            {"archivo": "a.mp4", "foto": False, "desde": 0.0, "segundos": 6.0, "paso": "1", "motivo": "", "audio": False},
            {"escena": "precio", "datos": datos_escena, "segundos": 1.0, "paso": paso},
        ],
        "narracion": [{"clip": 1, "en": 0.3, "texto": "Corre por el tuyo"}]}]}


BUENA = {"producto": "KZ Castor Pro", "precio": 13, "detalle": "7 días de garantía"}


def test_estado_expone_escenas_y_catalogo_solo_con_fmt(servidor):
    base, _ = servidor
    _, d = pedir(base, "/api/estado")
    assert d["escenas"] == {"disponible": False, "motivo": "Instala Node 22 o superior"}
    assert "catalogo_escenas" not in d
    _, d = pedir(base, "/api/estado?fmt=1")
    assert {"precio", "cta"} <= set(d["catalogo_escenas"])
    assert "variables" in d["catalogo_escenas"]["precio"] and "pasos" in d["catalogo_escenas"]["precio"]


def test_guardar_guion_conserva_escena_y_recalcula_segundos(servidor):
    base, carpeta = servidor
    editada = dict(BUENA, detalle="Garantía de 7 días y envío gratis ya")
    code, r = pedir(base, "/api/guion", serie(editada))
    assert code == 200 and r["ok"]
    clips = r["guion"]["videos"][0]["clips"]
    esc = clips[1]
    assert esc["escena"] == "precio" and esc["paso"] == "cta"
    assert esc["datos"]["detalle"] == editada["detalle"] and esc["datos"]["precio"] == 13
    assert esc["segundos"] == escenas.duracion("precio", esc["datos"]) != 1.0
    assert "archivo" not in esc and clips[0]["archivo"] == "a.mp4"
    assert r["guion"]["videos"][0]["narracion"] == [{"clip": 1, "en": 0.3, "texto": "Corre por el tuyo"}]
    _, d = pedir(base, "/api/estado?gv=-1")  # lo que lee la interfaz al volver a abrir
    assert d["guion"]["videos"][0]["clips"][1]["datos"] == esc["datos"]
    assert json.loads((carpeta / "serie.json").read_text(encoding="utf-8")) == r["guion"]


@pytest.mark.parametrize("datos,paso,campo", [
    (dict(BUENA, precio=1), "cta", "precio"),            # precio que no es el del catálogo
    (dict(BUENA, producto="Otro"), "cta", "Otro"),       # producto fuera del catálogo
    (dict(BUENA, detalle="  "), "cta", "detalle"),       # texto vacío
    (BUENA, "1", "paso"),                                # paso donde esa plantilla no encaja
])
def test_guardar_escena_invalida_se_rechaza_sin_tocar_el_guion(servidor, datos, paso, campo):
    base, carpeta = servidor
    code, r = pedir(base, "/api/guion", serie(BUENA))
    assert code == 200
    antes = (carpeta / "serie.json").read_text(encoding="utf-8")
    code, r = pedir(base, "/api/guion", serie(datos, paso))
    assert code == 400 and r["ok"] is False
    assert "Así compras 1" in r["error"] and "clip 2" in r["error"] and "«precio»" in r["error"] and campo in r["error"]
    assert (carpeta / "serie.json").read_text(encoding="utf-8") == antes


def test_motivo_escena_nombre_corto_ambiguo():
    cat = [{"nombre": "KZ Castor Pro (Harman)", "precio": 13.0}, {"nombre": "KZ Castor Pro (Bass)", "precio": 14.0}]
    c = {"escena": "precio", "paso": "cta", "datos": {"producto": "KZ Castor Pro", "precio": 13, "detalle": "x"}}
    m = studio_web.motivo_escena(c, cat)
    assert "«KZ Castor Pro (Harman)» o «KZ Castor Pro (Bass)»" in m and "nombre completo" in m and "precio" in m
