import os
import sys

import rutas


def _congelar(monkeypatch, tmp_path):
    exe = tmp_path / "ReelStudio" / "current" / "ReelStudio.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "perfil"))
    monkeypatch.setenv("HOME", str(tmp_path / "perfil"))
    return exe


def test_desarrollo_devuelve_carpeta_del_modulo():
    assert rutas.datos() == os.path.dirname(os.path.abspath(rutas.__file__))


def test_congelado_crea_carpeta_estable(monkeypatch, tmp_path):
    _congelar(monkeypatch, tmp_path)
    esperado = tmp_path / "roaming" / "ReelStudio"
    assert rutas.datos() == str(esperado)
    assert esperado.is_dir()
    # fuera de la carpeta que administra Velopack (la que se borra al desinstalar)
    assert not str(esperado).startswith(str(tmp_path / "local"))


def test_congelado_sin_appdata_usa_home(monkeypatch, tmp_path):
    _congelar(monkeypatch, tmp_path)
    monkeypatch.delenv("APPDATA")
    assert rutas.datos() == os.path.join(os.path.expanduser("~"), "ReelStudio")


def test_videos_defecto_congelado_en_videos_del_usuario(monkeypatch, tmp_path):
    _congelar(monkeypatch, tmp_path)
    assert rutas.videos_defecto() == os.path.join(os.path.expanduser("~"), "Videos", "Reel Studio")


def test_videos_defecto_desarrollo_junto_al_script():
    assert rutas.videos_defecto() == os.path.join(rutas.datos(), "Videos Dropaudioccs")


def test_migracion_copia_una_vez_sin_borrar(monkeypatch, tmp_path):
    exe = _congelar(monkeypatch, tmp_path)
    viejo = exe.parent / "studio_config.json"
    viejo.write_text('{"a": 1}', encoding="utf-8")
    rutas.migrar_datos()
    nuevo = tmp_path / "roaming" / "ReelStudio" / "studio_config.json"
    assert nuevo.read_text(encoding="utf-8") == '{"a": 1}'
    assert viejo.exists()
    # un segundo cambio junto al exe no pisa el config ya migrado
    viejo.write_text('{"a": 2}', encoding="utf-8")
    rutas.migrar_datos()
    assert nuevo.read_text(encoding="utf-8") == '{"a": 1}'


def test_migracion_no_sobrescribe_config_existente(monkeypatch, tmp_path):
    exe = _congelar(monkeypatch, tmp_path)
    (exe.parent / "studio_config.json").write_text("viejo", encoding="utf-8")
    nuevo = tmp_path / "roaming" / "ReelStudio"
    nuevo.mkdir(parents=True)
    (nuevo / "studio_config.json").write_text("propio", encoding="utf-8")
    rutas.migrar_datos()
    assert (nuevo / "studio_config.json").read_text(encoding="utf-8") == "propio"


def test_migracion_en_desarrollo_no_hace_nada(tmp_path):
    antes = sorted(os.listdir(rutas.datos()))
    rutas.migrar_datos()
    assert sorted(os.listdir(rutas.datos())) == antes
