import types

import pytest

import actualizador


class _Rel:
    def __init__(self, v, notas):
        self.Version, self.NotesMarkdown = v, notas


class _Info:
    def __init__(self, v, notas):
        self.TargetFullRelease = _Rel(v, notas)


def _falso(monkeypatch, *, info=None, error_ctor=None, error_check=None, descargas=None):
    class UM:
        def __init__(self, fuente):
            if error_ctor:
                raise error_ctor

        def check_for_updates(self):
            if error_check:
                raise error_check
            return info

        def download_updates(self, i, cb):
            for p in (10, 60):
                cb(p)
            if descargas is not None:
                descargas.append(i)

        def apply_updates_and_restart(self, i):
            if descargas is not None:
                descargas.append("reinicio")

    fake = types.SimpleNamespace(UpdateManager=UM, GithubSource=lambda url: url)
    monkeypatch.setattr(actualizador, "velopack", fake)
    monkeypatch.setattr(actualizador, "_notas_github", lambda: "")


def test_no_instalada(monkeypatch):
    _falso(monkeypatch, error_ctor=RuntimeError("not installed"))
    e = actualizador.buscar()
    assert e["instalada"] is False and e["nueva"] is None and e["error"] is None


def test_version_nueva_con_notas(monkeypatch):
    _falso(monkeypatch, info=_Info("9.9.9", "- mejoras"))
    e = actualizador.buscar()
    assert e["instalada"] and e["nueva"] == "9.9.9" and e["notas"] == "- mejoras" and e["error"] is None


def test_sin_novedad(monkeypatch):
    _falso(monkeypatch, info=None)
    e = actualizador.buscar()
    assert e["instalada"] and e["nueva"] is None and e["error"] is None


def test_error_de_red(monkeypatch):
    _falso(monkeypatch, error_check=OSError("sin red"))
    e = actualizador.buscar()
    assert e["instalada"] and e["nueva"] is None and "sin red" in e["error"]


def test_notas_de_respaldo(monkeypatch):
    _falso(monkeypatch, info=_Info("9.9.9", ""))
    monkeypatch.setattr(actualizador, "_notas_github", lambda: "desde api")
    assert actualizador.buscar()["notas"] == "desde api"


def test_aplicar_reporta_progreso(monkeypatch):
    hechos = []
    _falso(monkeypatch, info=_Info("9.9.9", "x"), descargas=hechos)
    actualizador.buscar()
    prog = []
    actualizador.aplicar(prog.append)
    assert prog == [10, 60, 100] and hechos[-1] == "reinicio"


def test_aplicar_sin_pendiente(monkeypatch):
    _falso(monkeypatch, info=None)
    actualizador.buscar()
    with pytest.raises(RuntimeError):
        actualizador.aplicar()
