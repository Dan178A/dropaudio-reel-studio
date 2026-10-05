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
