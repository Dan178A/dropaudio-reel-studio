"""Voz real vs. voz en off de plantilla: lo que pasó con el reel educativo del Castor Pro (oct. 2026).
El modelo falló, el respaldo por reglas puso «Segundo: esto es lo que trae la caja» encima de Daniel hablando de
otra cosa y numeró los chips «Dato 2» y «Dato 4». Estas pruebas fijan el comportamiento corregido."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


def test_subtitulos_trozos_cortos_y_solo_frases_completas():
    subs = rs.subtitulos(rs.habla_del_clip(D, 3.0, 7.0), por=4)
    assert [t for _, _, t in subs] == ["Si se te daña", "el cable no tienes", "que botar los audífonos"]
    assert subs[0][0] == 1.0 and all(d >= 0.4 for _, d, _ in subs)
    assert abs(sum(d for _, d, _ in subs) - 5.0) < 0.05


def test_validar_adjunta_habla():
    datos = {"cam.mp4": D}
    sel = rs.validar({"clips": [{"archivo": "cam.mp4", "desde": 4.0, "hasta": 9.0, "paso": "1"}]}, datos)
    assert sel["clips"][0]["habla"][0]["texto"].startswith("Si se te daña")


def test_gancho_educativo_sin_numero_fijo():
    assert "3 cosas" not in rs.FORMATOS["educativo"]["gancho_prod"]
    assert "3 cosas" not in rs.FORMATOS["educativo"]["gancho_ej"]
