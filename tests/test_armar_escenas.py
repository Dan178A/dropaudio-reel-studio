"""armar_sel con escenas animadas: el render se simula con un mp4 diminuto y los borradores van a una carpeta temporal.
Se omiten si no están pycapcut o ffmpeg."""
import json
import os
import shutil
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
PYCAPCUT = os.path.join(os.path.dirname(RAIZ), "pyCapCut")
if os.path.isdir(PYCAPCUT):
    sys.path.insert(0, PYCAPCUT)

pytest.importorskip("pycapcut")
if not shutil.which("ffmpeg"):
    pytest.skip("ffmpeg no disponible", allow_module_level=True)

import escenas  # noqa: E402
import reel_studio as rs  # noqa: E402


def _mp4(dest, seg):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size=320x568:rate=30:duration={seg}",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(seg), "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-c:a", "aac", "-shortest", dest], check=True)
    return dest


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    carpeta = tmp_path / "videos"
    carpeta.mkdir()
    _mp4(str(carpeta / "real.mp4"), 4)
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    escena_mp4 = _mp4(str(tmp_path / "escena.mp4"), 3)
    llamadas = []
    pasos = []

    def falso_render(tipo, datos, cache_dir, dur=None):
        llamadas.append((tipo, dur))
        if tipo == "falla":
            raise RuntimeError("fallo simulado")
        return escena_mp4

    monkeypatch.setattr(escenas, "render", falso_render)
    original = rs.png_paso
    monkeypatch.setattr(rs, "png_paso", lambda num, *a, **k: (pasos.append(num), original(num, *a, **k))[1])
    cfg = {"drafts": str(drafts), "musica": False, "voz_en_off": True, "vol_clips": 1.0, "vol_musica": 0.25}
    return carpeta, drafts, cfg, llamadas, pasos, escena_mp4


def _sel(*escenas_):
    clips = [{"archivo": "real.mp4", "foto": False, "desde": 0.0, "segundos": 4.0, "paso": "1", "motivo": "", "audio": False}]
    clips += [{"escena": t, "datos": {}, "segundos": 3.0, "paso": "5"} for t in escenas_]
    return {"formato": "asi_compras", "gancho": "Gancho", "promesa": "Promesa", "clips": clips,
            "narracion": [{"clip": 0, "texto": "Hola uno"}, {"clip": len(clips) - 1, "texto": "Aquí el precio"}]}


def _contenido(drafts, nombre):
    return json.load(open(os.path.join(str(drafts), nombre, "draft_content.json"), encoding="utf-8"))


def test_escena_va_al_borrador_sin_chip_de_paso(entorno):
    carpeta, drafts, cfg, llamadas, pasos, escena_mp4 = entorno
    logs = []
    t = rs.armar_sel(str(carpeta), _sel("precio"), "t_escena", cfg, lambda k, x: logs.append((k, x)))
    assert llamadas == [("precio", 3.0)]
    assert abs(t - 7.0) < 1e-6
    d = _contenido(drafts, "t_escena")
    rutas = [m.get("path", "") for m in d["materials"]["videos"]]
    assert any(os.path.basename(escena_mp4) in r.replace("\\", "/") for r in rutas)
    assert "5" not in pasos  # la escena (paso 5) no genera chip
    assert d["duration"] == 7_000_000
    assert not [x for k, x in logs if k == "error"]
    voz = [tr for tr in d["tracks"] if tr["type"] == "text"]
    assert voz and len(voz[0]["segments"]) == 2  # la narración sobre la escena se conserva


def test_escena_fallida_se_omite_y_el_borrador_sale(entorno):
    carpeta, drafts, cfg, llamadas, pasos, escena_mp4 = entorno
    logs = []
    t = rs.armar_sel(str(carpeta), _sel("falla", "precio"), "t_falla", cfg, lambda k, x: logs.append((k, x)))
    assert abs(t - 7.0) < 1e-6  # real (4 s) + precio (3 s); la fallida no cuenta
    assert any(k == "error" and "falla" in x for k, x in logs)
    d = _contenido(drafts, "t_falla")
    assert d["duration"] == 7_000_000
    voz = [tr for tr in d["tracks"] if tr["type"] == "text"]
    assert len(voz[0]["segments"]) == 2  # la narración del clip "precio" se reubicó


def test_sin_cta_png_si_la_ultima_es_escena_cta(entorno, monkeypatch):
    carpeta, drafts, cfg, *_ = entorno
    pedidos = []
    original = rs.png_cta
    monkeypatch.setattr(rs, "png_cta", lambda dest: (pedidos.append(dest), original(dest))[1])
    rs.armar_sel(str(carpeta), _sel("cta"), "t_cta", cfg, lambda k, x: None)
    assert pedidos == []
    rs.armar_sel(str(carpeta), _sel("precio"), "t_cta2", cfg, lambda k, x: None)
    assert len(pedidos) == 1


def _pistas(d):
    ids = {m["id"]: m for m in d["materials"]["videos"]}
    return [(tr.get("name") or tr["type"], [(ids.get(sg["material_id"], {}).get("path", ""), sg["volume"],
                                              sg["target_timerange"]["start"]) for sg in tr["segments"]])
            for tr in d["tracks"] if tr["type"] == "video"]


def test_escena_consume_el_paso_y_no_hay_chip_tardio(entorno):
    carpeta, drafts, cfg, llamadas, pasos, _ = entorno
    sel = _sel("precio")
    sel["clips"].append(dict(sel["clips"][0], paso="5"))
    sel["narracion"] = []
    rs.armar_sel(str(carpeta), sel, "t_consumo", cfg, lambda k, x: None)
    assert "5" not in pasos


def test_escena_en_orden_con_volumen_cero(entorno):
    carpeta, drafts, cfg, llamadas, pasos, escena_mp4 = entorno
    rs.armar_sel(str(carpeta), _sel("precio"), "t_orden", cfg, lambda k, x: None)
    video = next(segs for nom, segs in _pistas(_contenido(drafts, "t_orden")) if nom == "video" or nom == "")
    assert [os.path.basename(r) for r, _, _ in video] == ["real.mp4", os.path.basename(escena_mp4)]
    assert video[1][1] == 0 and video[1][2] == 4_000_000


def test_fallida_reubica_narracion_y_no_referencia_su_mp4(entorno, tmp_path, monkeypatch):
    carpeta, drafts, cfg, llamadas, pasos, escena_mp4 = entorno
    otro = _mp4(str(tmp_path / "fallida.mp4"), 3)
    base = escenas.render
    monkeypatch.setattr(escenas, "render", lambda t, d, c, dur=None: otro if t == "tres_datos" else base(t, d, c, dur))
    sel = _sel("falla", "precio")
    sel["narracion"] = [{"clip": 0, "texto": "uno", "en": 0.5}, {"clip": 1, "texto": "dos", "en": 0.5},
                        {"clip": 2, "texto": "tres", "en": 0.5}]
    rs.armar_sel(str(carpeta), sel, "t_remap", cfg, lambda k, x: None)
    d = _contenido(drafts, "t_remap")
    textos = {m["id"]: json.loads(m["content"])["text"] for m in d["materials"]["texts"]}
    voz = next(tr for tr in d["tracks"] if tr["type"] == "text")
    assert [(textos[sg["material_id"]], sg["target_timerange"]["start"]) for sg in voz["segments"]] == [
        ("uno", 500_000), ("tres", 4_500_000)]
    assert not any("fallida.mp4" in m.get("path", "") for m in d["materials"]["videos"])


def test_primer_clip_escena_sin_gancho(entorno, monkeypatch):
    carpeta, drafts, cfg, *_ = entorno
    pedidos = []
    original = rs.png_gancho
    monkeypatch.setattr(rs, "png_gancho", lambda *a: (pedidos.append(a), original(*a))[1])
    sel = _sel("precio")
    sel["clips"].reverse()
    sel["narracion"] = []
    rs.armar_sel(str(carpeta), sel, "t_g", cfg, lambda k, x: None)
    assert pedidos == []
