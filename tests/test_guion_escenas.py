"""Escenas animadas en el guion: planificador, validación, chequeos, texto para el crítico y reglas sin IA.
Sin red, sin Ollama y sin Node: escenas.disponible() se simula."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import escenas  # noqa: E402
import reel_studio as rs  # noqa: E402

CATALOGO = [
    {"nombre": "KZ Castor Pro (Harman)", "precio": 13.0},
    {"nombre": "KZ EDX Pro", "precio": 12.0},
    {"nombre": "KZ ZSN Pro X", "precio": None},
]


def archivo(nombre, dur, tipo, producto=None, usable=0.9, interes=0.8, habla=None, foto=False):
    """Un archivo analizado con una toma cada 3 s (la última, lo que sobre)."""
    tomas, t = [], 0.0
    while t < dur - 0.01:
        d = min(3.0, dur - t)
        tomas.append({"inicio": round(t, 2), "dur": round(d, 2), "tipo": tipo, "usable": usable, "interes": interes,
                      "descripcion": f"{tipo} en {nombre}"})
        t += d
    d = {"archivo": nombre, "foto": foto, "dur": dur, "tomas": tomas, "habla": habla or []}
    if producto:
        d["producto"] = producto
        d["precio"] = rs.precio_de(producto, CATALOGO)
    return d


def datos_de(*arch):
    return {a["archivo"]: a for a in arch}


@pytest.fixture
def con_escenas(monkeypatch):
    monkeypatch.setattr(escenas, "disponible", lambda: (True, ""))


@pytest.fixture
def sin_escenas(monkeypatch):
    monkeypatch.setattr(escenas, "disponible", lambda: (False, "Instala Node 22 o superior"))


def precio_ok():
    return {"escena": "precio", "paso": "cta",
            "datos": {"producto": "KZ Castor Pro", "precio": 13, "detalle": "7 días de garantía"}}


# ---------------------------------------------------------------- planear_serie
def material_corto():
    # 22 s de unboxing del mismo producto: menos que MIN_MATERIAL (35) pero más que 20
    return datos_de(archivo("a.mp4", 12, "unboxing", "KZ Castor Pro (Harman)"),
                    archivo("b.mp4", 10, "unboxing", "KZ Castor Pro (Harman)"))


def test_planear_serie_22s_con_escenas_da_plan():
    planes, avisos = rs.planear_serie(material_corto(), 0.5, ["unboxing"], 1, escenas=True, objetivo=45)
    assert len(planes) == 1
    p = planes[0]
    assert p["escenas"] is True and p["objetivo"] == 45
    assert p["segundos_material"] == 22.0
    assert sorted(p["archivos"]) == ["a.mp4", "b.mp4"]


def test_planear_serie_22s_sin_escenas_avisa():
    planes, avisos = rs.planear_serie(material_corto(), 0.5, ["unboxing"], 1)
    assert planes == []
    assert any("35" in a for a in avisos)


def test_planear_serie_menos_de_20s_con_escenas_avisa():
    datos = datos_de(archivo("a.mp4", 15, "unboxing", "KZ Castor Pro (Harman)"))
    planes, avisos = rs.planear_serie(datos, 0.5, ["unboxing"], 1, escenas=True)
    assert planes == []
    assert any("20" in a for a in avisos)


def test_planear_serie_plan_largo_guarda_objetivo_y_bandera():
    datos = datos_de(archivo("a.mp4", 20, "unboxing", "KZ Castor Pro (Harman)"),
                     archivo("b.mp4", 20, "unboxing", "KZ Castor Pro (Harman)"))
    planes, _ = rs.planear_serie(datos, 0.5, ["unboxing"], 1)
    assert planes and planes[0]["escenas"] is False and planes[0]["objetivo"] == 35
    planes, _ = rs.planear_serie(datos, 0.5, ["unboxing"], 1, escenas=True, objetivo=60)
    assert planes[0]["escenas"] is True and planes[0]["objetivo"] == 60  # puede alargarse con escenas


def test_escenas_activas_segun_cfg_y_disponible(con_escenas):
    assert rs.escenas_activas({}) is True
    assert rs.escenas_activas({"escenas": False}) is False


def test_escenas_activas_sin_node(sin_escenas):
    assert rs.escenas_activas({"escenas": True}) is False


# ---------------------------------------------------------------- validar
def test_validar_mezcla_video_y_escenas():
    datos = material_corto()
    sel = {"formato": "unboxing", "gancho": "x", "promesa": "y", "clips": [
        {"archivo": "a.mp4", "desde": 0, "hasta": 6, "paso": "gancho"},
        {"escena": "tres_datos", "paso": "3", "datos": {"titulo": "Qué trae", "dato1": "Cable", "dato2": "Puntas",
                                                         "dato3": "Estuche"}},
        {"escena": "precio", "paso": "cta", "datos": {"producto": "KZ Castor Pro", "precio": 99, "detalle": "x"}},
        {"escena": "precio", "paso": "1", "datos": precio_ok()["datos"]},     # paso no permitido
        {"escena": "inventada", "paso": "cta", "datos": {}},                 # tipo desconocido
        {"archivo": "b.mp4", "desde": 0, "hasta": 5, "paso": "4"},
        precio_ok(),
    ], "narracion": [{"clip": 0, "en": 0.3, "texto": "uno"}, {"clip": 2, "en": 0.3, "texto": "descartada"},
                     {"clip": 5, "en": 0.3, "texto": "cinco"}, {"clip": 6, "en": 0.3, "texto": "precio"}]}
    out = rs.validar(sel, datos, {"a.mp4", "b.mp4"}, catalogo=CATALOGO)
    c = out["clips"]
    assert [x.get("escena") or x["archivo"] for x in c] == ["a.mp4", "tres_datos", "b.mp4", "precio"]
    esc = c[3]
    assert set(esc) == {"escena", "datos", "segundos", "paso"}
    assert esc["paso"] == "cta" and esc["datos"]["precio"] == 13
    assert esc["segundos"] == escenas.duracion("precio", esc["datos"])
    assert "imagen" in esc["datos"]  # la pone validar_escena, nunca el modelo
    # la narración sigue a su clip aunque se hayan descartado clips en medio
    assert [(n["clip"], n["texto"]) for n in out["narracion"]] == [(0, "uno"), (2, "cinco"), (3, "precio")]


def test_validar_sin_escenas_las_descarta():
    datos = material_corto()
    sel = {"clips": [{"archivo": "a.mp4", "desde": 0, "hasta": 6, "paso": "gancho"}, precio_ok()], "narracion": []}
    out = rs.validar(sel, datos, catalogo=CATALOGO, escenas_ok=False)
    assert [x.get("archivo") for x in out["clips"]] == ["a.mp4"]


def test_validar_clip_de_video_igual_que_antes():
    datos = material_corto()
    sel = {"clips": [{"archivo": "a.mp4", "desde": 1, "hasta": 7, "paso": "1", "audio": True, "motivo": "m"}]}
    c = rs.validar(sel, datos)["clips"][0]
    assert c == {"archivo": "a.mp4", "foto": False, "desde": 1.0, "segundos": 6.0, "paso": "1", "motivo": "m",
                 "audio": True}


# ---------------------------------------------------------------- chequeos y texto para el crítico
def video(archivo_, desde, seg, paso):
    return {"archivo": archivo_, "foto": False, "desde": desde, "segundos": seg, "paso": paso, "motivo": "",
            "audio": False}


def escena(tipo, datos, paso):
    return {"escena": tipo, "datos": datos, "segundos": escenas.duracion(tipo, datos), "paso": paso}


def test_chequeos_cuenta_escenas_en_la_duracion():
    datos = material_corto()
    d_precio = escenas.validar_escena("precio", precio_ok()["datos"], CATALOGO)
    d_cta = {"linea": "Lo pruebas antes de pagar"}
    sel = {"formato": "unboxing", "clips": [video("a.mp4", 0, 12, "gancho"), video("b.mp4", 0, 10, "2"),
                                            escena("precio", d_precio, "cta"), escena("cta", d_cta, "cta")],
           "narracion": []}
    probs, graves = rs.chequeos(sel, datos, voz=False)
    total = 22 + escenas.duracion("precio", d_precio) + escenas.duracion("cta", d_cta)
    assert total > 25  # sin las escenas sería «muy corto»
    assert not any("corto" in p for p in probs)
    assert not any("40 %" in p and "escena" in p.lower() for p in probs)


def test_chequeos_video_real_menor_a_20s_es_grave():
    datos = material_corto()
    d = {"titulo": "Tres datos", "dato1": "palabra " * 8, "dato2": "palabra " * 8, "dato3": "palabra " * 8}
    sel = {"formato": "unboxing", "clips": [video("a.mp4", 0, 10, "gancho"), escena("tres_datos", d, "3")],
           "narracion": []}
    probs, graves = rs.chequeos(sel, datos, voz=False)
    assert any("video real" in p for p in probs)
    assert graves >= 3


def test_chequeos_escenas_mas_del_40_por_ciento():
    datos = material_corto()
    d = {"titulo": "Tres datos clave", "dato1": "palabra " * 8, "dato2": "palabra " * 8, "dato3": "palabra " * 8}
    sel = {"formato": "unboxing", "clips": [video("a.mp4", 0, 12, "gancho"), video("b.mp4", 0, 10, "2"),
                                            escena("tres_datos", d, "3"), escena("tres_datos", dict(d, titulo="Otro"), "4")],
           "narracion": []}
    probs, _ = rs.chequeos(sel, datos, voz=False)
    assert any("40 %" in p and "escena" in p.lower() for p in probs)


def test_chequeos_escena_en_paso_no_permitido():
    datos = material_corto()
    d_cta = {"linea": "Lo pruebas antes de pagar"}
    sel = {"formato": "unboxing", "clips": [video("a.mp4", 0, 12, "gancho"), video("b.mp4", 0, 10, "2"),
                                            escena("cta", d_cta, "3")], "narracion": []}
    probs, _ = rs.chequeos(sel, datos, voz=False)
    assert any("paso" in p and "cta" in p for p in probs)


def test_chequeos_voz_no_cuenta_escenas_como_hueco():
    datos = material_corto()
    d_precio = escenas.validar_escena("precio", precio_ok()["datos"], CATALOGO)
    sel = {"formato": "unboxing", "clips": [video("a.mp4", 0, 12, "gancho"), video("b.mp4", 0, 10, "2"),
                                            escena("precio", d_precio, "cta")],
           "narracion": [{"clip": 0, "en": 0.3, "texto": "a"}, {"clip": 1, "en": 0.3, "texto": "b"}]}
    probs, _ = rs.chequeos(sel, datos, voz=True)
    assert not any("sin voz" in p for p in probs)


def test_guion_en_texto_describe_escenas():
    datos = material_corto()
    d_precio = escenas.validar_escena("precio", precio_ok()["datos"], CATALOGO)
    sel = {"formato": "unboxing", "gancho": "g", "promesa": "p",
           "clips": [video("a.mp4", 0, 12, "gancho"), escena("precio", d_precio, "cta")],
           "narracion": [{"clip": 1, "en": 0.3, "texto": "Cuesta trece dólares"}]}
    txt = rs.guion_en_texto(sel, datos)
    assert "ESCENA precio" in txt
    assert "producto=KZ Castor Pro" in txt and "precio=$13" in txt
    assert "Cuesta trece dólares" in txt
    assert "imagen=" not in txt


# ---------------------------------------------------------------- guion por reglas
def test_guion_por_reglas_agrega_precio_y_cta():
    datos = material_corto()
    plan = {"formato": "unboxing", "producto": "KZ Castor Pro (Harman)", "escenas": True, "objetivo": 35}
    sel = rs.guion_por_reglas(datos, 0.5, "unboxing", plan=plan, catalogo=CATALOGO)
    tipos = [c.get("escena") for c in sel["clips"]]
    assert tipos[-2:] == ["precio", "cta"]
    assert all(c.get("archivo") for c in sel["clips"][:-2])  # el video real va primero
    out = rs.validar(dict(sel, formato="unboxing"), datos, catalogo=CATALOGO)
    assert [c.get("escena") for c in out["clips"]][-2:] == ["precio", "cta"]
    assert out["clips"][-1]["datos"]["linea"] == "Lo pruebas antes de pagar"
    assert out["clips"][-2]["datos"]["precio"] == 13


def test_guion_por_reglas_sin_precio_solo_cta():
    datos = datos_de(archivo("a.mp4", 12, "unboxing", "KZ ZSN Pro X"), archivo("b.mp4", 10, "unboxing", "KZ ZSN Pro X"))
    plan = {"formato": "unboxing", "producto": "KZ ZSN Pro X", "escenas": True, "objetivo": 35}
    sel = rs.guion_por_reglas(datos, 0.5, "unboxing", plan=plan, catalogo=CATALOGO)
    assert [c.get("escena") for c in sel["clips"] if c.get("escena")] == ["cta"]


def test_guion_por_reglas_sin_escenas_igual_que_antes():
    datos = material_corto()
    plan = {"formato": "unboxing", "producto": "KZ Castor Pro (Harman)", "escenas": False, "objetivo": 35}
    a = rs.guion_por_reglas(datos, 0.5, "unboxing", plan=plan, catalogo=CATALOGO)
    b = rs.guion_por_reglas(datos, 0.5, "unboxing")
    assert a == b and not any(c.get("escena") for c in a["clips"])


def test_guion_por_reglas_no_agrega_si_ya_alcanza():
    datos = datos_de(*(archivo(f"{k}.mp4", 20, "unboxing", "KZ Castor Pro (Harman)") for k in "abc"))
    plan = {"formato": "unboxing", "producto": "KZ Castor Pro (Harman)", "escenas": True, "objetivo": 20}
    sel = rs.guion_por_reglas(datos, 0.5, "unboxing", plan=plan, catalogo=CATALOGO)
    assert not any(c.get("escena") for c in sel["clips"])


# ---------------------------------------------------------------- esquema y prompt
def test_esquema_guion_admite_video_o_escena():
    items = rs.ESQUEMA_GUION["properties"]["clips"]["items"]
    assert "anyOf" in items and len(items["anyOf"]) == 2
    esc = next(x for x in items["anyOf"] if "escena" in x["properties"])
    assert set(esc["properties"]["escena"]["enum"]) == set(escenas.catalogo())
    assert esc["properties"]["datos"]["type"] == "object"
    # el crítico devuelve el guion con el mismo esquema
    assert rs.ESQUEMA_GUION in rs.ESQUEMA_CRITICA["properties"]["guion"]["anyOf"]


def test_prompt_escenas_con_catalogo_y_reglas():
    plan = {"formato": "unboxing", "producto": "KZ Castor Pro (Harman)", "escenas": True, "objetivo": 45,
            "segundos_material": 22.0}
    txt = rs.prompt_escenas(plan, CATALOGO)
    for tipo, cat in escenas.catalogo().items():
        assert tipo in txt
        assert cat["descripcion"] in txt
    assert "22 s" in txt and "45 s" in txt
    assert "40 %" in txt and "gancho" in txt
    assert "KZ Castor Pro" in txt and "$13" in txt
    assert "KZ EDX Pro" not in txt  # solo los precios del producto del reel
    assert "máx. 40" in txt  # variables con su máximo


def test_hacer_serie_pasa_bandera_y_prompt(tmp_path, monkeypatch, con_escenas):
    import json
    datos = material_corto()
    (tmp_path / "analisis.json").write_text(json.dumps(datos), encoding="utf-8")
    vistos = {}

    def falso(material, modelo, log=None, sistema=None, esquema=None, **kw):
        if esquema is rs.ESQUEMA_CRITICA or esquema is rs.ESQUEMA_CRITICA_VIDEO:
            raise RuntimeError("sin crítico en la prueba")
        vistos["sistema"], vistos["esquema"] = sistema, esquema
        return {"gancho": "g", "promesa": "p", "clips": [
            {"archivo": "a.mp4", "desde": 0, "hasta": 9, "paso": "gancho"},
            {"archivo": "b.mp4", "desde": 0, "hasta": 9, "paso": "2"}, precio_ok()], "narracion": []}

    monkeypatch.setattr(rs, "escribir_guion", falso)
    cfg = {"minimo": 0.5, "formatos": ["unboxing"], "max_por_formato": 1, "escritor": "modelo:falso",
           "catalogo": CATALOGO, "voz_en_off": False, "critico": False, "duracion_objetivo": 45}
    serie = rs.hacer_serie(str(tmp_path), cfg, lambda *a: None)
    v = serie["videos"][0]
    assert vistos["esquema"] is rs.ESQUEMA_GUION
    assert "ESCENAS" in vistos["sistema"] and "45 s" in vistos["sistema"]
    assert v["clips"][-1].get("escena") == "precio"
    assert v["escenas"] is True and v["objetivo"] == 45


def test_sin_clips_reubica_narracion():
    sel = {"clips": [video("a.mp4", 0, 5, "gancho"), escena("cta", {"linea": "Hola"}, "cta"), video("b.mp4", 0, 5, "4")],
           "narracion": [{"clip": 1, "en": 0.3, "texto": "x"}, {"clip": 2, "en": 0.3, "texto": "y"}]}
    out = rs.sin_clips(sel, {1})
    assert [c["archivo"] for c in out["clips"]] == ["a.mp4", "b.mp4"]
    assert out["narracion"] == [{"clip": 1, "en": 0.3, "texto": "y"}]
    assert len(sel["clips"]) == 3  # no toca el original
