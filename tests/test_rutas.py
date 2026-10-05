import os
import sys

import rutas


def _congelar(monkeypatch, tmp_path):
    exe = tmp_path / "ReelStudio" / "current" / "ReelStudio.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return exe


def test_desarrollo_devuelve_carpeta_del_modulo():
    assert rutas.datos() == os.path.dirname(os.path.abspath(rutas.__file__))


def test_congelado_crea_carpeta_estable(monkeypatch, tmp_path):
    _congelar(monkeypatch, tmp_path)
    esperado = tmp_path / "local" / "ReelStudio" / "datos"
    assert rutas.datos() == str(esperado)
    assert esperado.is_dir()


def test_migracion_copia_una_vez_sin_borrar(monkeypatch, tmp_path):
    exe = _congelar(monkeypatch, tmp_path)
    viejo = exe.parent / "studio_config.json"
    viejo.write_text('{"a": 1}', encoding="utf-8")
    rutas.migrar_datos()
    nuevo = tmp_path / "local" / "ReelStudio" / "datos" / "studio_config.json"
    assert nuevo.read_text(encoding="utf-8") == '{"a": 1}'
    assert viejo.exists()
    # un segundo cambio junto al exe no pisa el config ya migrado
    viejo.write_text('{"a": 2}', encoding="utf-8")
    rutas.migrar_datos()
    assert nuevo.read_text(encoding="utf-8") == '{"a": 1}'


def test_migracion_no_sobrescribe_config_existente(monkeypatch, tmp_path):
    exe = _congelar(monkeypatch, tmp_path)
    (exe.parent / "studio_config.json").write_text("viejo", encoding="utf-8")
    nuevo = tmp_path / "local" / "ReelStudio" / "datos"
    nuevo.mkdir(parents=True)
    (nuevo / "studio_config.json").write_text("propio", encoding="utf-8")
    rutas.migrar_datos()
    assert (nuevo / "studio_config.json").read_text(encoding="utf-8") == "propio"


def test_migracion_en_desarrollo_no_hace_nada(tmp_path):
    rutas.migrar_datos()  # no debe fallar ni crear nada
