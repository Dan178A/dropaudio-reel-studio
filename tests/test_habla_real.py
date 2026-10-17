"""Voz real vs. voz en off de plantilla: lo que pasó con el reel educativo del Castor Pro (oct. 2026).
El modelo falló, el respaldo por reglas puso «Segundo: esto es lo que trae la caja» encima de Daniel hablando de
otra cosa y numeró los chips «Dato 2» y «Dato 4». Estas pruebas fijan el comportamiento corregido: el marcado
«audio + sin voz en off» donde hay habla real vale para TODAS las vías (modelo, reglas, crítico y flujo clásico)."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
import reel_studio as rs

D = {"archivo": "cam.mp4", "foto": False, "dur": 60.0, "tomas": [],
     "habla": [{"ini": 0.0, "fin": 3.5, "texto": "Un gusto, el chico de DropAudio."},
               {"ini": 4.0, "fin": 9.0, "texto": "Si se te daña el cable no tienes que botar los audífonos"},
               {"ini": 9.5, "fin": 30.0, "texto": "monólogo largo"}]}


def test_habla_del_clip_relativa_y_recortada():
    h = rs.habla_del_clip(D, 3.0, 7.0)  # clip 3–10 s
    assert [(x["ini"], x["fin"]) for x in h] == [(0.0, 0.5), (1.0, 6.0), (6.5, 7.0)]
    assert [x["completa"] for x in h] == [False, True, False]


def test_tiene_habla():
    assert rs.tiene_habla({"segundos": 7.0, "habla": rs.habla_del_clip(D, 3.0, 7.0)})
    assert not rs.tiene_habla({"segundos": 10.0, "habla": []})


def test_subtitulos_trozos_cortos_y_frases_recortadas():
    subs = rs.subtitulos(rs.habla_del_clip(D, 3.0, 7.0), por=4)
    textos = [t for _, _, t in subs]
    # las frases que quedaron cortadas por el borde del clip TAMBIÉN se subtitulan, con «…»
    assert textos == ["… Un gusto, el chico", "de DropAudio.", "Si se te daña", "el cable no tienes",
                      "que botar los audífonos", "… monólogo largo"]
    assert all(d >= 0.4 for _, d, _ in subs)
    # la frase completa (1.0-6.0 en el clip) conserva su reparto de tiempo
    assert abs(sum(d for i, d, t in subs if i >= 1.0 and not t.startswith("…")) - 5.0) < 0.05


def test_subtitulos_no_se_solapan_y_avanzan_lo_que_muestran():
    habla = [{"ini": 0.0, "fin": 0.5, "texto": "uno dos", "completa": False},
             {"ini": 0.5, "fin": 3.0, "texto": "tres cuatro cinco", "completa": True}]
    subs = sorted(rs.subtitulos(habla))
    for (a, d, _), (b, _, _) in zip(subs, subs[1:]):
        assert a + d <= b + 1e-9  # una caja nunca pisa a la siguiente: se muestra lo que se avanza
    assert all(d >= 0.4 for _, d, _ in subs)


def test_validar_adjunta_habla():
    datos = {"cam.mp4": D}
    sel = rs.validar({"clips": [{"archivo": "cam.mp4", "desde": 4.0, "hasta": 9.0, "paso": "1"}]}, datos)
    assert sel["clips"][0]["habla"][0]["texto"].startswith("Si se te daña")


def test_gancho_educativo_sin_numero_fijo():
    assert "3 cosas" not in rs.FORMATOS["educativo"]["gancho_prod"]
    assert "3 cosas" not in rs.FORMATOS["educativo"]["gancho_ej"]


# ---------------------------------------------------------------- marcado central (una vía para todas)
def test_tiene_habla_por_frases_y_no_solo_por_cociente():
    # una frase entera en un clip largo también es voz de verdad (antes: cociente 0.4 la ignoraba)
    frases = [{"ini": 10.0, "fin": 13.0, "texto": "la frase clave"}]
    assert rs.tiene_habla({"segundos": 40.0, "habla": frases})
    # un tropiezo de menos de 1.5 s en un clip largo: alucinación de Whisper probable, no manda
    assert not rs.tiene_habla({"segundos": 40.0, "habla": [{"ini": 10.0, "fin": 10.8, "texto": "sí"}]})
    assert rs.tiene_habla({"segundos": 7.0, "habla": rs.habla_del_clip(D, 3.0, 7.0)})  # la regla del cociente sigue


def test_validar_quita_la_narracion_sobre_habla_real_via_modelo():
    """Vía del modelo y del crítico: validar() es el único punto — lo que traiga narración sobre voz real
    se limpia ahí, modelado o editado a mano, y el clip queda con su audio original encendido."""
    sel = {"formato": "asi_compras", "clips": [{"archivo": "cam.mp4", "desde": 4.0, "hasta": 9.0, "paso": "1"},
                                               {"archivo": "cam.mp4", "desde": 50.0, "hasta": 54.0, "paso": "2"}],
           "narracion": [{"clip": 0, "en": 0.3, "texto": "Segundo: esto es lo que trae la caja."},
                         {"clip": 1, "en": 0.3, "texto": "otra"}]}
    out = rs.validar(sel, {"cam.mp4": D})
    assert [n["texto"] for n in out["narracion"]] == ["otra"]  # solo las de clips sin habla real
    assert out["clips"][0]["audio"] is True and out["clips"][1]["audio"] is False


def test_marcar_habla_sel_frase_corta_en_clip_largo():
    """El marcado va por frases: quien habla poco en un clip largo suena y no se le pone voz encima."""
    d = {"archivo": "cam.mp4", "foto": False, "dur": 40.0, "tomas": [],
         "habla": [{"ini": 10.0, "fin": 13.0, "texto": "la frase clave"}]}
    sel = {"clips": [{"archivo": "cam.mp4", "desde": 5.0, "segundos": 25.0, "audio": False}],
           "narracion": [{"clip": 0, "en": 0.2, "texto": "voz de plantilla"}]}
    out = rs.marcar_habla_sel(sel, {"cam.mp4": d})
    assert out["clips"][0]["audio"] is True
    assert out["narracion"] == []
    assert out["clips"][0]["habla"][0]["texto"] == "la frase clave"  # recalculada con los cortes actuales


def test_marcar_habla_sel_deja_la_narracion_donde_no_habla():
    d = {"archivo": "cam.mp4", "foto": False, "dur": 40.0, "tomas": [], "habla": []}
    sel = {"clips": [{"archivo": "cam.mp4", "desde": 0.0, "segundos": 8.0, "audio": False},
                     {"escena": "cta", "datos": {"linea": "x"}, "segundos": 2.0, "paso": "cta"}],
           "narracion": [{"clip": "0", "en": 0.3, "texto": "paso uno"}, {"clip": 1, "texto": "cta escena"}]}
    out = rs.marcar_habla_sel(sel, {"cam.mp4": d})
    assert out["narracion"] == [{"clip": 0, "en": 0.3, "texto": "paso uno"}, {"clip": 1, "texto": "cta escena"}]
    assert out["clips"][0]["audio"] is False


def test_marcar_habla_sel_descarta_narracion_fuera_de_rango():
    """Una narración que apunta a un clip inexistente (guion editado a mano) antes sacaba un IndexError
    en armar_sel: ahora se descarta al marcar, igual que en validar."""
    out = rs.marcar_habla_sel({"clips": [{"archivo": "a.mp4", "desde": 0, "segundos": 4, "audio": False}],
                               "narracion": [{"clip": 9, "texto": "x"}, {"clip": "nada", "texto": "y"}]})
    assert out["narracion"] == []


def test_narracion_de_plantilla_ordinales_como_los_chips():
    """El «Dato N» del chip se numera por la posición del paso entre los vistos: la voz dice lo mismo."""
    sel = {"clips": [{"archivo": "a.mp4", "foto": False, "desde": 0, "segundos": 4, "paso": "gancho"},
                     {"archivo": "a.mp4", "foto": False, "desde": 4, "segundos": 4, "paso": "1"},
                     {"archivo": "b.mp4", "foto": False, "desde": 0, "segundos": 4, "paso": "3"}]}  # no hay «2»
    plantilla = rs.NARR_REGLAS["educativo"]
    assert plantilla["1"].startswith("{ord}:") and plantilla["2"].startswith("{ord}:")
    narr = rs.narracion_de_plantilla(sel, "educativo", "KZ Castor Pro (Harman)", [])
    textos = {n["clip"]: n["texto"] for n in narr}
    # hay voz de plantilla en gancho (no lleva ordinal) y en los dos datos vistos:
    assert textos[0] == "Antes de comprarlo, mira esto."
    assert textos[1].startswith("Primero:") and textos[2].startswith("Segundo:")
    assert "el KZ Castor Pro" in textos[1] and "Cuesta " not in textos[2]
    assert rs.ordinal_es(1) == "Primero" and rs.ordinal_es(3) == "Tercero"


def test_narracion_de_plantilla_no_va_sobre_habla_ni_sobre_escenas():
    sel = {"clips": [{"archivo": "a.mp4", "foto": False, "desde": 0, "segundos": 4, "paso": "1", "habla": [
                          {"ini": 0.0, "fin": 2.0, "texto": "lo que sea", "completa": True}]},
                     {"escena": "precio", "datos": {}, "segundos": 2.0, "paso": "5"}]}
    narr = rs.narracion_de_plantilla(sel, "educativo", "KZ Castor Pro (Harman)", [])
    assert narr == []


def test_narracion_reglas_plantilla_cubre_los_pasos():
    sel = {"clips": [{"archivo": "a.mp4", "foto": False, "desde": 0, "segundos": 4, "paso": "gancho"},
                     {"archivo": "a.mp4", "foto": False, "desde": 4, "segundos": 4, "paso": "4"}]}
    narr = rs.narracion_de_plantilla(sel, "unboxing", "KZ Castor Pro (Harman)", [])
    assert [n["texto"] for n in narr] == ["¿Original o réplica? Te lo abro aquí mismo.",
                                          "Fíjate en el acabado de cerca."]
    # sin precio en el catálogo cae a «buen precio»
    narr5 = rs.narracion_de_plantilla({"clips": [dict(sel["clips"][0], paso="5")]}, "unboxing",
                                      "KZ Castor Pro (Harman)", [])
    assert "buen precio" in narr5[0]["texto"]


def test_fusionar_fragmentos_diminutos():
    """Un fragmento de 0.05–0.1 s tumba pycapcut (ValueError): se fusiona con el clip anterior si es el
    mismo tramo contiguo; si no, se salta (y la narración sigue a su clip)."""
    base = {"archivo": "a.mp4", "desde": 0.0, "segundos": 2.0, "paso": "1"}
    frag = dict(base, desde=2.0, segundos=0.08)  # contiguo: se fusiona
    otro = {"archivo": "b.mp4", "desde": 0.0, "segundos": 0.06, "paso": "2"}
    sel = {"clips": [dict(base), frag, otro],
           "narracion": [{"clip": 0, "texto": "y"}, {"clip": 2, "texto": "x"}]}
    out, fusionados, saltados = rs.fusionar_fragmentos(sel)
    assert (fusionados, saltados) == (1, 1)
    assert len(out["clips"]) == 1
    assert abs(out["clips"][0]["segundos"] - 2.08) < 1e-9
    assert out["narracion"] == [{"clip": 0, "texto": "y"}]
    # uno que no se puede fusionar (tras una escena) se salta
    sel2 = {"clips": [{"archivo": "a.mp4", "desde": 0.0, "segundos": 2.0, "paso": "1"},
                      {"escena": "cta", "datos": {}, "segundos": 0.05, "paso": "cta"}],
            "narracion": [{"clip": 1, "texto": "x"}]}
    out2, fus2, salt2 = rs.fusionar_fragmentos(sel2)
    assert (fus2, salt2) == (0, 1)
    assert len(out2["clips"]) == 1 and out2["narracion"] == []
    assert len(sel["clips"]) == 3  # no muerde el original


def test_completar_voz_llena_solo_los_huecos():
    """Botón «Completar la voz en off» (interfaz web): rellena los clips sin habla real y sin voz escrita;
    lo que ya hay no se toca y donde habla alguien tampoco se mete voz de plantilla."""
    sel = {"formato": "educativo", "clips": [
        {"archivo": "a.mp4", "foto": False, "desde": 0, "segundos": 10, "paso": "1", "habla": [
            {"ini": 0.0, "fin": 4.0, "texto": "yo hablo aquí", "completa": True}]},
        {"archivo": "b.mp4", "foto": False, "desde": 0, "segundos": 6, "paso": "2", "habla": []},
        {"archivo": "b.mp4", "foto": False, "desde": 6, "segundos": 6, "paso": "3", "habla": []}],
        "narracion": [{"clip": 1, "en": 0.5, "texto": "esta ya la escribió alguien"}]}
    n = rs.completar_voz(sel, "educativo", "KZ Castor Pro (Harman)", precio=13, info={})
    assert n == 1
    textos = {int(x["clip"]): x["texto"] for x in sel["narracion"]}
    assert set(textos) == {1, 2}
    assert textos[2].startswith("Tercero:")
    # con precio real de la tienda se dice en dólares (paso 5)
    hueco5 = {"clips": [{"archivo": "b.mp4", "foto": False, "desde": 0, "segundos": 6, "paso": "5", "habla": []}],
              "narracion": []}
    assert rs.completar_voz(hueco5, "educativo", "KZ Castor Pro (Harman)", precio=13, info={}) == 1
    assert "13 dólares" in hueco5["narracion"][0]["texto"]
    n2 = rs.completar_voz(sel, "educativo", "KZ Castor Pro (Harman)", precio=13, info={})
    assert n2 == 0  # ya no quedan huecos, y vuelve a añadir la misma, otra vez no
