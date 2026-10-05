import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import escenas as es  # noqa: E402

PRECIOS = [
    {"nombre": "KZ Castor Pro (Harman)", "precio": 13.0},
    {"nombre": "Cable Silver Upgrade", "precio": 8.0},
    {"nombre": "KZ AE01 (Adaptador BT)", "precio": 5.5},
    {"nombre": "Sin Precio", "precio": None},
]


@pytest.fixture(autouse=True)
def _limpiar():
    es._DISPONIBLE = None
    yield
    es._DISPONIBLE = None


# ---------------------------------------------------------------- catálogo y duración
def test_catalogo_excluye_duracion():
    c = es.catalogo()
    assert "duracion" not in c
    assert set(c) == {"precio", "comparativa", "tres_datos", "para_quien", "cta"}


def test_duracion_corta_menor_que_larga_y_acotada():
    corto = {"titulo": "Tres datos", "dato1": "Uno", "dato2": "Dos", "dato3": "Tres"}
    largo = {"titulo": "x " * 18, "dato1": "palabra " * 8, "dato2": "palabra " * 8, "dato3": "palabra " * 8}
    dc, dl = es.duracion("tres_datos", corto), es.duracion("tres_datos", largo)
    cat = es.catalogo()["tres_datos"]
    assert dc < dl
    assert cat["dur_min"] <= dc and dl <= cat["dur_max"]
    assert round(dc, 1) == dc and round(dl, 1) == dl
    assert dl - dc >= 2


def test_duracion_todos_los_tipos_en_rango():
    for tipo, cat in es.catalogo().items():
        d = es.duracion(tipo, {})
        assert cat["dur_min"] <= d <= cat["dur_max"]


# ---------------------------------------------------------------- validar
def test_validar_recorta_y_resuelve_precio_y_imagen():
    datos = {"producto": "  KZ Castor Pro (Harman)  ", "precio": 13, "detalle": "d" * 100, "imagen": "../../etc/x"}
    r = es.validar_escena("precio", datos, PRECIOS)
    assert r["producto"] == "KZ Castor Pro (Harman)"
    assert len(r["detalle"]) == 40
    assert r["precio"] == 13
    assert r["imagen"] == "kz-castor-pro-harman.webp"


def test_validar_precio_incorrecto_none():
    d = {"producto": "Cable Silver Upgrade", "precio": 9, "detalle": "x"}
    assert es.validar_escena("precio", d, PRECIOS) is None
    d["producto"] = "Sin Precio"
    assert es.validar_escena("precio", d, PRECIOS) is None
    d["producto"] = "Producto Inventado"
    assert es.validar_escena("precio", d, PRECIOS) is None


def test_validar_nombre_corto_y_mayusculas():
    d = {"producto": "kz ae01", "precio": 5.5, "detalle": "BT"}
    r = es.validar_escena("precio", d, PRECIOS)
    assert r and r["precio"] == 5.5 and r["imagen"] == ""


def test_validar_imagen_nunca_del_input():
    d = {"producto": "Producto Libre", "para": "gamers", "imagen": "productos/kz-castor-pro-bass.webp"}
    r = es.validar_escena("para_quien", d, PRECIOS)
    assert r["imagen"] == ""


def test_validar_comparativa_y_textos_vacios():
    d = {"a_nombre": "KZ Castor Pro (Harman)", "a_precio": 13, "a_punto": "Graves",
         "b_nombre": "Cable Silver Upgrade", "b_precio": 8, "b_punto": "Detalle", "veredicto": "Elige A"}
    r = es.validar_escena("comparativa", d, PRECIOS)
    assert r and "imagen" not in r and r["b_precio"] == 8
    d["veredicto"] = "   "
    assert es.validar_escena("comparativa", d, PRECIOS) is None
    d["veredicto"] = "ok"
    d["b_precio"] = 7
    assert es.validar_escena("comparativa", d, PRECIOS) is None


def test_validar_tipo_desconocido():
    assert es.validar_escena("nada", {"linea": "x"}, PRECIOS) is None
    assert es.validar_escena("cta", "no es dict", PRECIOS) is None
    assert es.validar_escena("cta", {"linea": "Hola" * 30}, PRECIOS)["linea"] == ("Hola" * 30)[:50]


# ---------------------------------------------------------------- render
class _Ejec:
    def __init__(self, rc=0, out="", crear=True):
        self.llamadas = []
        self.rc, self.out, self.crear = rc, out, crear

    def __call__(self, cmd, **kw):
        self.llamadas.append((cmd, kw))
        tmp = kw["cwd"]
        self.html = open(os.path.join(tmp, "index.html"), encoding="utf-8").read()
        self.vars = json.load(open(os.path.join(tmp, "vars.json"), encoding="utf-8"))
        self.tiene = {d: os.path.isdir(os.path.join(tmp, d)) for d in ("fonts", "vendor", "productos")}
        if self.crear:
            with open(cmd[cmd.index("--output") + 1], "wb") as f:
                f.write(b"mp4")
        return subprocess.CompletedProcess(cmd, self.rc, self.out, "")


def test_render_comando_cwd_vars_y_duracion(monkeypatch, tmp_path):
    ej = _Ejec()
    monkeypatch.setattr(es.subprocess, "run", ej)
    monkeypatch.setattr(es.shutil, "which", lambda n: "C:/n/npx.cmd")
    datos = es.validar_escena("para_quien", {"producto": "KZ Castor Pro (Bass)", "para": "bajos"}, PRECIOS)
    ruta = es.render("para_quien", datos, str(tmp_path), dur=6.4)
    cmd, kw = ej.llamadas[0]
    assert cmd[1:5] == ["--yes", "hyperframes@0.8.77", "render", "--variables-file"]
    assert cmd[5] == "vars.json" and cmd[6:8] == ["--quality", "looks"]
    assert os.path.isabs(cmd[cmd.index("--output") + 1])
    assert kw["timeout"] == 300 and os.path.isabs(kw["cwd"])
    assert 'data-duration="6.4"' in ej.html
    assert ej.vars["imagen"] == "productos/kz-castor-pro-bass.webp"
    assert all(ej.tiene.values())
    assert os.path.isfile(ruta) and ruta.startswith(str(tmp_path))


def test_render_sin_imagen_pasa_cadena_vacia(monkeypatch, tmp_path):
    ej = _Ejec()
    monkeypatch.setattr(es.subprocess, "run", ej)
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    es.render("para_quien", {"producto": "Otro", "para": "x", "imagen": ""}, str(tmp_path))
    assert ej.vars["imagen"] == "" and not ej.tiene["productos"]


def test_render_cache_evita_subprocess(monkeypatch, tmp_path):
    ej = _Ejec()
    monkeypatch.setattr(es.subprocess, "run", ej)
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    a = es.render("cta", {"linea": "Hola"}, str(tmp_path))
    b = es.render("cta", {"linea": "Hola"}, str(tmp_path))
    assert a == b and len(ej.llamadas) == 1
    es.render("cta", {"linea": "Hola"}, str(tmp_path), dur=7.0)  # otra duración, otra clave
    assert len(ej.llamadas) == 2


def test_render_error_con_ultimas_lineas(monkeypatch, tmp_path):
    salida = "\n".join("linea %d" % i for i in range(40))
    monkeypatch.setattr(es.subprocess, "run", _Ejec(rc=1, out=salida, crear=False))
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    with pytest.raises(RuntimeError) as e:
        es.render("cta", {"linea": "x"}, str(tmp_path))
    assert "linea 39" in str(e.value) and "linea 25" in str(e.value) and "linea 24" not in str(e.value)


def test_render_sin_internet_mensaje_propio(monkeypatch, tmp_path):
    out = "npm error code ENOTFOUND\nnpm error request to https://registry.npmjs.org/hyperframes failed"
    monkeypatch.setattr(es.subprocess, "run", _Ejec(rc=1, out=out, crear=False))
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    with pytest.raises(RuntimeError, match="HyperFrames no está descargado; conéctate a internet una vez"):
        es.render("cta", {"linea": "x"}, str(tmp_path))


def test_render_timeout(monkeypatch, tmp_path):
    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 300)
    monkeypatch.setattr(es.subprocess, "run", boom)
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    with pytest.raises(RuntimeError, match="300"):
        es.render("cta", {"linea": "x"}, str(tmp_path))


# ---------------------------------------------------------------- disponible
def _simular(monkeypatch, version, ffmpeg=True, node=True):
    def which(n):
        if n == "node":
            return "node" if node else None
        return "ffmpeg" if ffmpeg else None
    monkeypatch.setattr(es.shutil, "which", which)
    monkeypatch.setattr(es.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, version + "\n", ""))


def test_disponible_ok(monkeypatch):
    _simular(monkeypatch, "v22.12.0")
    assert es.disponible() == (True, "")


def test_disponible_node_viejo_sin_node_o_sin_ffmpeg(monkeypatch):
    _simular(monkeypatch, "v20.11.1")
    ok, motivo = es.disponible()
    assert not ok and "Node 22" in motivo
    es._DISPONIBLE = None
    _simular(monkeypatch, "v22.0.0", node=False)
    assert not es.disponible()[0]
    es._DISPONIBLE = None
    _simular(monkeypatch, "v22.0.0", ffmpeg=False)
    ok, motivo = es.disponible()
    assert not ok and "FFmpeg" in motivo


def test_disponible_cacheado(monkeypatch):
    _simular(monkeypatch, "v22.1.0")
    es.disponible()
    monkeypatch.setattr(es.shutil, "which", lambda n: None)
    assert es.disponible()[0] is True
