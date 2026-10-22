"""Tests del motor de audio de entrega: cama determinista, duck por envolvente,
mezcla a -14 LUFS y QC verificar(). Todo local (numpy + ffmpeg), sin red."""
import os
import subprocess
import sys

import numpy as np
import pytest

import entrega_audio as ea

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _voz_ejemplo(duracion=10.0, pico=0.8, niveles=None):
    """Voz falsa determinista: ráfagas de habla de 1 s cada 2 s, con pausas claras.
    Con ``niveles`` (uno por ráfaga) simula la dinámica real del habla."""
    t = np.arange(int(duracion * ea.SR)) / ea.SR
    carriers = np.sin(2 * np.pi * 180 * t) + 0.5 * np.sin(2 * np.pi * 520 * t + 1.1)
    voz = np.zeros_like(t)
    brillos = [] if niveles is None else list(niveles)
    for i, inicio in enumerate(np.arange(0.0, duracion - 0.99, 2.0)):
        nivel = brillos[i % len(brillos)] if brillos else 1.0
        voz[(t >= inicio) & (t < inicio + 1.0)] = carriers[(t >= inicio) & (t < inicio + 1.0)] * nivel
    return _en_pico(voz, pico)


def _en_pico(sig, pico):
    actual = np.max(np.abs(sig))
    return sig / actual * pico if actual > 0 else sig


# ---------------------------------------------------------------------------
# cama(): determinista, discreta, sin trampas
# ---------------------------------------------------------------------------

def test_cama_determinista_y_longitud():
    a = ea.cama(10.0, cues=(1.5, 6.5), drop=3.0, cta=8.0)
    b = ea.cama(10.0, cues=(1.5, 6.5), drop=3.0, cta=8.0)
    assert len(a) == int(10.0 * ea.SR)
    assert np.array_equal(a, b)  # sin ruido aleatorio: la misma llamada da lo mismo
    assert 0.45 <= np.max(np.abs(a)) <= 0.55  # pico ~0.5 (-6 dBFS), cama baja


def test_cama_sin_entradas_extremas():
    # total corto: sin drop/cta/cues igual produce algo razonable
    a = ea.cama(1.5)
    assert len(a) == int(1.5 * ea.SR) and np.isfinite(a).all()
    # peca también si drop/cta caen fuera del total: no hay índices raros
    assert ea.cama(4.0, drop=10.0, cta=10.0, cues=(9.9, -1.0)).shape == (int(4.0 * ea.SR),)


# ---------------------------------------------------------------------------
# duck: profundidad -8 dB, ataque 60 ms, desprendimiento 400 ms
# ---------------------------------------------------------------------------

def test_duck_baja_hasta_menos_8db_bajo_habla():
    voz = _voz_ejemplo(8.0, pico=0.7)
    g = ea._ganancia_duck(voz)
    assert len(g) == len(voz)
    piso = 10 ** (ea.PROFUNDIDAD_DUCK_DB / 20)  # 10^(-8/20) ~ 0.398
    def g_en(seg):  # g en la posición t (segundos)
        return float(g[int(seg * ea.SR)])
    # bajo la voz (ya pasada la fase de ataque): cerca del piso
    assert g_en(0.50) < piso + 0.05
    assert g_en(2.50) < piso + 0.05
    assert g_en(4.50) < piso + 0.05
    assert g_en(6.50) < piso + 0.05
    # en pausa larga (0.9 s despues de que la voz calla): vuelve a ~0 dB
    assert g_en(1.90) > 0.90
    assert g_en(3.90) > 0.90
    assert g_en(5.90) > 0.90


def test_duck_ataque_rapido_y_desprendimiento_lento():
    voz = _voz_ejemplo(8.0, pico=0.7)
    g = ea._ganancia_duck(voz)
    def g_en(seg):
        return float(g[int(seg * ea.SR)])
    # ataque: 100 ms después de arrancar una ráfaga ya está bien bajado (60 ms)
    assert g_en(2.10) < 0.75
    # desprendimiento: 50 ms después de que la voz calla, la cama sigue baja (400 ms)
    assert g_en(3.05) < 0.75


def test_duck_sin_voz_no_hay_duck():
    g = ea._ganancia_duck(np.zeros(ea.SR))
    assert np.all(g == 1.0)


# ---------------------------------------------------------------------------
# mezclar() + verificar(): un solo loudnorm al final
# ---------------------------------------------------------------------------

def _cama_ejemplo(duracion=10.0):
    return ea.cama(duracion, cues=(1.5, 6.5), drop=3.0, cta=8.0)


def test_mezclar_llega_a_luces_de_entrega(tmp_path):
    # voz con dinamica real (niveles distintos por rafaga): permite medir LRA >= 4
    mez = ea.mezclar(_voz_ejemplo(10.0, pico=0.6, niveles=(1.0, 0.4, 0.9, 0.5, 0.8)),
                     _cama_ejemplo(10.0), 10.0,
                     salida=str(tmp_path / "mezcla.wav"))
    assert len(mez) == int(10.0 * ea.SR)
    assert np.max(np.abs(mez)) <= 0.98  # sin saturación
    m = ea.verificar(str(tmp_path / "mezcla.wav"))
    assert ea.LUFS_MIN <= m["lufs"] <= ea.LUFS_MAX
    assert m["tp"] <= ea.TP_MAX_DB
    assert m["lra"] >= ea.LRA_MIN


def test_mezclar_es_determinista(tmp_path):
    a = ea.mezclar(_voz_ejemplo(10.0, pico=0.6), _cama_ejemplo(10.0), 10.0)
    b = ea.mezclar(_voz_ejemplo(10.0, pico=0.6), _cama_ejemplo(10.0), 10.0)
    assert np.allclose(a, b)


def test_mezclar_acepta_rutas_y_total_corto(tmp_path):
    voz_r = str(tmp_path / "voz.wav")
    cama_r = str(tmp_path / "cama.wav")
    ea.guardar(_voz_ejemplo(2.0, pico=0.5), voz_r, estereo=False)
    ea.guardar(_cama_ejemplo(2.0), cama_r, estereo=False)
    mez = ea.mezclar(voz_r, cama_r, 2.0)
    assert len(mez) == int(2.0 * ea.SR) and np.isfinite(mez).all()


def test_mezclar_con_voz_de_pico_cercano_a_cero_db(tmp_path):
    # voz fuerte de pico > 0.97 en todo el reel: mezcla sin clipping
    t = np.arange(int(6.0 * ea.SR)) / ea.SR
    voz = 0.99 * np.sin(2 * np.pi * 220 * t)
    mez = ea.mezclar(voz, _cama_ejemplo(6.0), 6.0)
    assert np.isfinite(mez).all() and np.max(np.abs(mez)) <= 0.98


def test_mezclar_con_cama_vacia(tmp_path):
    mez = ea.mezclar(_voz_ejemplo(4.0, pico=0.5), np.zeros(int(4.0 * ea.SR)), 4.0)
    assert len(mez) == int(4.0 * ea.SR)


def test_mezclar_solo_silencio(tmp_path):
    mez = ea.mezclar(np.zeros(int(2.0 * ea.SR)), np.zeros(int(2.0 * ea.SR)), 2.0)
    assert np.all(mez == 0.0)


def test_mezclar_solo_silencio_con_salida(tmp_path):
    # incluso en silencio puro, salida= debe escribir el WAV (cero frames faltantes)
    ruta = str(tmp_path / "silencio.wav")
    mez = ea.mezclar(np.zeros(int(1.5 * ea.SR)), np.zeros(int(1.5 * ea.SR)), 1.5, salida=ruta)
    guardado = ea._leer_wav(ruta)
    assert guardado.shape == mez.shape == (int(1.5 * ea.SR),)
    assert np.all(guardado == 0.0)


def test_leer_wav_a_48k_remuestrea(tmp_path):
    # voz extraida a 48 kHz (como la de los mp4): debe remuestrearse, no leerse bit a bit
    import wave
    ruta = str(tmp_path / "voz48.wav")
    fr = 48000
    t48 = np.arange(int(2.0 * fr)) / fr
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fr)
        w.writeframes(np.round(0.5 * np.sin(2 * np.pi * 440 * t48) * 32767).astype(np.int16).tobytes())
    datos = ea._leer_wav(ruta)
    assert len(datos) == int(2.0 * ea.SR)  # duracion correcta (no corrida ~9 % al 44.1)
    mues = np.abs(np.fft.rfft(datos * np.hanning(len(datos))))
    freqs = np.fft.rfftfreq(len(datos), 1.0 / ea.SR)
    assert abs(freqs[np.argmax(mues)] - 440.0) < 5.0  # y el tono sigue en su frecuencia
    mez = ea.mezclar(ruta, np.zeros(int(2.0 * fr)), 2.0)  # y pasa limpia por mezclar
    assert len(mez) == int(2.0 * ea.SR)


def test_verificar_rechaza_master_bajo(tmp_path):
    voz = _voz_ejemplo(10.0, pico=0.06)  # muy por debajo de la ventana
    ruta = str(tmp_path / "bajo.wav")
    ea.guardar(voz, ruta, estereo=False)
    with pytest.raises(AssertionError):
        ea.verificar(ruta)


def test_verificar_lee_metricas_reales(tmp_path):
    # fixture de prueba: la mezcla entregada debe medir coherente (volumedetect + ebur128)
    mez = ea.mezclar(_voz_ejemplo(10.0, pico=0.6), _cama_ejemplo(10.0), 10.0,
                     salida=str(tmp_path / "ok.wav"))
    m = ea.medir(str(tmp_path / "ok.wav"))
    assert m["lufs"] < -10 and m["lufs"] > -30  # rango realista de una mezcla
    assert m["tp"] >= m["pico_muestra"] - 0.5  # true peak >= pico muestra (aprox)


def test_guardar_escribe_wav_estereofonico(tmp_path):
    import wave
    ruta = str(tmp_path / "salida.wav")
    ea.guardar(np.zeros(1000), ruta)
    with wave.open(ruta, "rb") as w:
        assert w.getnchannels() == 2
        assert w.getsampwidth() == 2
        assert w.getframerate() == ea.SR
        assert w.getnframes() == 1000


# ---------------------------------------------------------------------------
# gen_music delega en el nuevo motor (compatible con su CLI/API de siempre)
# ---------------------------------------------------------------------------

def test_gen_music_delega_en_entrega_audio(tmp_path):
    import gen_music
    ruta = str(tmp_path / "musica.wav")
    gen_music.music(6.0, [1.5], 2.0, 5.0, ruta)
    esperada = ea.cama(6.0, cues=(1.5,), drop=2.0, cta=5.0)
    datos = ea._leer_wav(ruta)
    assert len(datos) == int(6.0 * ea.SR)
    assert np.round(esperada * 32767) / 32767 == pytest.approx(datos, abs=3e-5)


def test_gen_music_cli(tmp_path):
    ruta = str(tmp_path / "cli.wav")
    r = subprocess.run(
        [sys.executable, os.path.join(RAIZ, "gen_music.py"),
         "6", "2", "5", ruta, "1.5"],
        capture_output=True, text=True, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    assert os.path.exists(ruta)
    assert len(ea._leer_wav(ruta)) == int(6.0 * ea.SR)