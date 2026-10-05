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


def test_nombre_corto_ambiguo_no_vale_y_el_completo_si():
    precios = PRECIOS + [{"nombre": "KZ Castor Pro (Bass)", "precio": 14.0}]
    d = {"producto": "KZ Castor Pro", "precio": 13, "detalle": "x"}
    assert es.validar_escena("precio", d, precios) is None  # «KZ Castor Pro» es Harman o Bass: ambiguo
    assert es.ambiguos("kz castor pro", precios) == ["KZ Castor Pro (Harman)", "KZ Castor Pro (Bass)"]
    assert es.ambiguos("KZ Castor Pro (Bass)", precios) == []
    r = es.validar_escena("precio", dict(d, producto="KZ Castor Pro (Bass)", precio=14), precios)
    assert r["precio"] == 14 and r["imagen"] == "kz-castor-pro-bass.webp"
    assert es._imagen_de("KZ Castor Pro") == ""  # en mapa.json también es ambiguo
    # un producto cuyo nombre completo ES el corto de otro gana por coincidencia exacta
    precios.append({"nombre": "KZ Castor Pro", "precio": 11.0})
    assert es.validar_escena("precio", dict(d, precio=11), precios)["precio"] == 11


def test_nombre_para_escena():
    largo = [{"nombre": "Audífonos Inalámbricos Premium X (Edición Negra)", "precio": 30.0}]
    assert es.nombre_para_escena("KZ Castor Pro (Harman)", PRECIOS) == "KZ Castor Pro (Harman)"
    assert es.nombre_para_escena(largo[0]["nombre"], largo) == "Audífonos Inalámbricos Premium X"
    otro = largo + [{"nombre": "Audífonos Inalámbricos Premium X (Edición Blanca)", "precio": 31.0}]
    assert es.nombre_para_escena(largo[0]["nombre"], otro) == largo[0]["nombre"]  # el corto sería ambiguo


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
class _Proc:
    """Popen simulado: communicate() devuelve la salida o se pasa del tiempo (hasta que lo matan)."""
    pid = 4321

    def __init__(self, ej, cmd):
        self.ej, self.cmd, self.returncode, self.matado = ej, cmd, None, False

    def communicate(self, timeout=None):
        self.ej.timeouts.append(timeout)
        if self.ej.colgado and not self.matado:
            raise subprocess.TimeoutExpired(self.cmd, timeout)
        self.returncode = self.ej.rc
        return self.ej.out, ""

    def kill(self):
        self.matado = True


class _Ejec:
    def __init__(self, rc=0, out="", crear=True, colgado=False):
        self.llamadas, self.timeouts, self.procs = [], [], []
        self.rc, self.out, self.crear, self.colgado = rc, out, crear, colgado

    def __call__(self, cmd, **kw):
        self.llamadas.append((cmd, kw))
        tmp = kw["cwd"]
        self.html = open(os.path.join(tmp, "index.html"), encoding="utf-8").read()
        self.vars = json.load(open(os.path.join(tmp, "vars.json"), encoding="utf-8"))
        self.tiene = {d: os.path.isdir(os.path.join(tmp, d)) for d in ("fonts", "vendor", "productos")}
        if self.crear and not self.colgado:
            with open(cmd[cmd.index("--output") + 1], "wb") as f:
                f.write(b"mp4")
        self.procs.append(_Proc(self, cmd))
        return self.procs[-1]


def test_render_comando_cwd_vars_y_duracion(monkeypatch, tmp_path):
    ej = _Ejec()
    monkeypatch.setattr(es.subprocess, "Popen", ej)
    monkeypatch.setattr(es.shutil, "which", lambda n: "C:/n/npx.cmd")
    datos = es.validar_escena("para_quien", {"producto": "KZ Castor Pro (Bass)", "para": "bajos"}, PRECIOS)
    ruta = es.render("para_quien", datos, str(tmp_path), dur=6.4)
    cmd, kw = ej.llamadas[0]
    assert cmd[1:5] == ["--yes", "hyperframes@0.8.77", "render", "--variables-file"]
    assert cmd[5] == "vars.json" and cmd[6:8] == ["--quality", "looks"]
    assert os.path.isabs(cmd[cmd.index("--output") + 1])
    assert ej.timeouts == [300] and os.path.isabs(kw["cwd"])
    assert 'data-duration="6.4"' in ej.html
    assert ej.vars["imagen"] == "productos/kz-castor-pro-bass.webp"
    assert all(ej.tiene.values())
    assert os.path.isfile(ruta) and ruta.startswith(str(tmp_path))


def test_render_sin_imagen_pasa_cadena_vacia(monkeypatch, tmp_path):
    ej = _Ejec()
    monkeypatch.setattr(es.subprocess, "Popen", ej)
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    es.render("para_quien", {"producto": "Otro", "para": "x", "imagen": ""}, str(tmp_path))
    assert ej.vars["imagen"] == "" and not ej.tiene["productos"]


def test_render_cache_evita_subprocess(monkeypatch, tmp_path):
    ej = _Ejec()
    monkeypatch.setattr(es.subprocess, "Popen", ej)
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    a = es.render("cta", {"linea": "Hola"}, str(tmp_path))
    b = es.render("cta", {"linea": "Hola"}, str(tmp_path))
    assert a == b and len(ej.llamadas) == 1
    es.render("cta", {"linea": "Hola"}, str(tmp_path), dur=7.0)  # otra duración, otra clave
    assert len(ej.llamadas) == 2


def test_render_error_con_ultimas_lineas(monkeypatch, tmp_path):
    salida = "\n".join("linea %d" % i for i in range(40))
    monkeypatch.setattr(es.subprocess, "Popen", _Ejec(rc=1, out=salida, crear=False))
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    with pytest.raises(RuntimeError) as e:
        es.render("cta", {"linea": "x"}, str(tmp_path))
    assert "linea 39" in str(e.value) and "linea 25" in str(e.value) and "linea 24" not in str(e.value)


def test_render_sin_internet_mensaje_propio(monkeypatch, tmp_path):
    out = "npm error code ENOTFOUND\nnpm error request to https://registry.npmjs.org/hyperframes failed"
    monkeypatch.setattr(es.subprocess, "Popen", _Ejec(rc=1, out=out, crear=False))
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    with pytest.raises(RuntimeError, match="HyperFrames no está descargado; conéctate a internet una vez"):
        es.render("cta", {"linea": "x"}, str(tmp_path))


def test_render_timeout_mata_el_arbol(monkeypatch, tmp_path):
    ej = _Ejec(colgado=True)
    matados = []
    monkeypatch.setattr(es.subprocess, "Popen", ej)
    monkeypatch.setattr(es.subprocess, "run", lambda cmd, **kw: matados.append((cmd, kw)))
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    monkeypatch.setattr(es.sys, "platform", "win32")
    with pytest.raises(RuntimeError, match="tardó más de 300 s"):
        es.render("cta", {"linea": "x"}, str(tmp_path))
    assert ej.timeouts[0] == 300 and len(ej.timeouts) == 2  # tras matar, se recogen las tuberías
    assert matados and matados[0][0] == ["taskkill", "/T", "/F", "/PID", "4321"]
    assert matados[0][1]["creationflags"] == 0x08000000
    assert ej.procs[0].matado
    assert not [f for f in os.listdir(tmp_path) if f.endswith((".mp4", ".part"))]


def test_render_timeout_fuera_de_windows_solo_kill(monkeypatch, tmp_path):
    ej = _Ejec(colgado=True)
    matados = []
    monkeypatch.setattr(es.subprocess, "Popen", ej)
    monkeypatch.setattr(es.subprocess, "run", lambda cmd, **kw: matados.append(cmd))
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    monkeypatch.setattr(es.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="300"):
        es.render("cta", {"linea": "x"}, str(tmp_path))
    assert matados == [] and ej.procs[0].matado
    assert "creationflags" not in ej.llamadas[0][1]


def test_render_y_node_sin_ventana_en_windows(monkeypatch, tmp_path):
    ej = _Ejec()
    monkeypatch.setattr(es.subprocess, "Popen", ej)
    monkeypatch.setattr(es.shutil, "which", lambda n: n)
    monkeypatch.setattr(es.sys, "platform", "win32")
    es.render("cta", {"linea": "x"}, str(tmp_path))
    assert ej.llamadas[0][1]["creationflags"] == 0x08000000
    vistos = []
    monkeypatch.setattr(es.subprocess, "run",
                        lambda cmd, **kw: (vistos.append(kw), subprocess.CompletedProcess(cmd, 0, "v22.3.0\n", ""))[1])
    assert es.disponible() == (True, "")
    assert vistos[0]["creationflags"] == 0x08000000


def _destino(tmp_path, tipo, datos):
    return os.path.join(str(tmp_path), es._clave(tipo, datos, es.duracion(tipo, datos))[:24] + ".mp4")


def test_render_reusa_destino_si_aparece_durante_el_render(monkeypatch, tmp_path):
    datos = {"linea": "x"}
    destino = _destino(tmp_path, "cta", datos)

    class _Otro(_Ejec):
        def __call__(self, cmd, **kw):
            p = super().__call__(cmd, **kw)
            with open(destino, "wb") as f:  # otro render simultáneo de la misma escena terminó antes
                f.write(b"otro")
            return p
    monkeypatch.setattr(es.subprocess, "Popen", _Otro())
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    assert es.render("cta", datos, str(tmp_path)) == destino
    assert open(destino, "rb").read() == b"otro"
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".part")]


def test_render_tolera_permission_error_con_destino_existente(monkeypatch, tmp_path):
    datos = {"linea": "y"}
    destino = _destino(tmp_path, "cta", datos)

    def replace(a, b):
        with open(destino, "wb") as f:
            f.write(b"otro")
        raise PermissionError("en uso")
    monkeypatch.setattr(es.subprocess, "Popen", _Ejec())
    monkeypatch.setattr(es.shutil, "which", lambda n: "npx")
    monkeypatch.setattr(es.os, "replace", replace)
    assert es.render("cta", datos, str(tmp_path)) == destino
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".part")]


def test_clave_incluye_version_de_hyperframes_e_imagen(monkeypatch):
    datos = es.validar_escena("para_quien", {"producto": "KZ Castor Pro (Bass)", "para": "bajos"}, PRECIOS)
    assert es._huella_imagen(datos)  # la imagen del producto existe y entra en la clave
    a = es._clave("para_quien", datos, 6.0)
    monkeypatch.setattr(es, "HYPERFRAMES", "9.9.9")
    assert es._clave("para_quien", datos, 6.0) != a
    monkeypatch.setattr(es, "HYPERFRAMES", "0.8.77")
    assert es._clave("para_quien", datos, 6.0) == a
    monkeypatch.setattr(es, "_huella_imagen", lambda d: "otra-foto")
    assert es._clave("para_quien", datos, 6.0) != a


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


def test_disponible_motivo_pide_reiniciar(monkeypatch):
    _simular(monkeypatch, "v20.0.0")
    assert "reinicia Reel Studio" in es.disponible()[1]
    _simular(monkeypatch, "v22.0.0", ffmpeg=False)
    assert "reinicia Reel Studio" in es.disponible()[1]


def test_disponible_cacheado(monkeypatch):
    _simular(monkeypatch, "v22.1.0")
    es.disponible()
    monkeypatch.setattr(es.shutil, "which", lambda n: None)
    assert es.disponible()[0] is True


def test_duracion_precio_y_cta_corto_menor_que_largo():
    pc = {"producto": "KZ AE01", "precio": 5, "detalle": "Bluetooth 5.3"}
    pl = {"producto": "KZ Castor Pro (Harman) edición", "precio": 13, "detalle": "palabra " * 8}
    cc = {"linea": "Lo pruebas"}
    cl = {"linea": "palabra " * 10}
    assert es.duracion("precio", pc) < es.duracion("precio", pl)
    assert es.duracion("cta", cc) < es.duracion("cta", cl)
    assert 5 <= es.duracion("precio", pc) <= 7
    assert 5 <= es.duracion("cta", cc) <= 6
