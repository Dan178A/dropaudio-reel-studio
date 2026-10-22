"""Tests de voces_clon: fail-soft sin torch/modelo/referencia, import lazy del
paquete pesado, y formato de entrega (48 kHz estereo 16-bit, I=-16 LUFS TP=-2).
La generacion real (descarga de XTTS-v2 + red la primera vez) va en el test
lento ``test_generacion_corta_con_backend``, marcado ``lento`` para que la suite
normal lo deseleccione (pytest -m lento la corre explicitamente)."""
import os
import subprocess
import sys

import numpy as np
import pytest

import voces_clon as vc

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _wav_pcm(ruta, sr, canales, muestras, ancho=2):
    import wave

    with wave.open(ruta, "wb") as w:
        w.setnchannels(canales)
        w.setsampwidth(ancho)
        w.setframerate(sr)
        w.writeframes((np.clip(muestras, -1, 1) * 32767).astype("<i2").tobytes())


def test_importar_modulo_no_importa_torch_ni_tts():
    """El resto del pipeline no exige torch: importar voces_clon es liviano."""
    codigo = ("import sys, os;sys.path.insert(0, os.path.abspath(r'{}'));"
              "import voces_clon;"
              "assert 'torch' not in sys.modules, 'torch importado por voces_clon';"
              "assert 'TTS' not in sys.modules and 'coqui_tts' not in sys.modules, 'TTS importado'").format(RAIZ)
    r = subprocess.run([sys.executable, "-I", "-c", codigo], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout


def test_disponible_nunca_levanta():
    ok, razon = vc.disponible()
    assert isinstance(ok, bool) and isinstance(razon, str)
    # coherente: si no hay paquete pesado, el motivo dice que no esta
    if not ok:
        assert "instalado" in razon or "TTS" in razon or "XTTS" in razon


@pytest.mark.parametrize("caso", ["inexistente", "vacio"])
def test_clonar_sin_referencia_no_resultado(tmp_path, caso):
    """Fail-soft: sin muestra la voz clonada queda en skip, sin excepcion ni archivo."""
    salida = str(tmp_path / "out.wav")
    ref = str(tmp_path / "no_existe.wav")
    if caso == "vacio":
        ref = ""
    resultado = vc.clonar("Prueba.", ref, salida)
    assert resultado is None
    assert not os.path.exists(salida)


def test_clonar_texto_vacio_no_resultado(tmp_path):
    ref = str(tmp_path / "ref.wav")
    _wav_pcm(ref, 48000, 2, np.zeros(48000))
    assert vc.clonar("", ref, str(tmp_path / "out.wav")) is None
    assert not os.path.exists(str(tmp_path / "out.wav"))


def test_formato_entrega_48k_estereo_16bit_loudnorm(tmp_path):
    """El post-proceso local (sin backend) entregara 48 kHz estereo 16-bit y TP<=-2 dB."""
    sr_in = 24000
    t = np.arange(sr_in * 3) / sr_in
    senal = 0.2 * (np.sin(2 * np.pi * 300 * t) + 0.4 * np.sin(2 * np.pi * 1200 * t))
    crudo = str(tmp_path / "crudo.wav")
    _wav_pcm(crudo, sr_in, 1, senal)
    salida = str(tmp_path / "out.wav")
    assert vc._a_formato_entrega(crudo, salida) == salida
    with open(salida, "rb") as w:  # fmt/audio-format PCM (1, no float) en el offset 20
        w.seek(20)
        bytes_fmt = w.read(2)
    import wave

    with wave.open(salida) as w2:
        assert w2.getframerate() == 48000
        assert w2.getnchannels() == 2
        assert w2.getsampwidth() == 2
    assert int.from_bytes(bytes_fmt, "little") == 1  # PCM no float
    # pico bajo el techo TP=-2 dBFS (0.794) con margen por el overshoot del normalizador
    with wave.open(salida) as w2:
        muestras = np.frombuffer(w2.readframes(w2.getnframes()), "<i2").reshape(-1, 2)
        pico = np.abs(muestras / 32768).max()
    assert pico <= 10 ** (-1.8 / 20)
    # y audible: energia razonable (no silencio puro ni recortado)
    assert pico > 0.05


@pytest.mark.lento
def test_generacion_corta_con_backend(tmp_path):
    """Test LENTO (pytest -m lento): necesita coqui-tts + la descarga del modelo XTTS-v2."""
    try:
        import TTS  # noqa: F401  (TTS re-lanza ImportError con mensaje claro si falta torch)
        import torch  # noqa: F401
    except Exception:
        pytest.skip("backend XTTS no instalado o torch ausente")
    ref = os.path.join(RAIZ, "voces", "ref_daniel", "ref_a_daniel.wav")
    if not os.path.isfile(ref):
        pytest.skip("sin referencia de voz")
    salida = str(tmp_path / "prueba_corta.wav")
    texto = "Prueba corta de la voz clonada."
    resultado = vc.clonar(texto, ref, salida)
    if resultado is None:  # falla del modelo/red: fail-soft, el test reporta el motivo
        pytest.fail("clonar devolvio None con backend disponible y referencia valida")
    import wave

    with wave.open(salida) as w:
        dur = w.getnframes() / w.getframerate()
        assert w.getframerate() == 48000 and w.getnchannels() == 2 and w.getsampwidth() == 2
    assert 0.8 <= dur <= 12.0  # frase corta audible, no recortada ni infinita