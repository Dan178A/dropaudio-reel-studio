"""Motor de audio de entrega: cama musical discreta, duck suave y master a -14 LUFS.

Reemplaza el patrón viejo de gen_music (pads de senos con vibrato, hats/risers de
ruido, sidechaincompress agresivo) por:

- ``cama(total, ...)``: cama discreta 100 BPM (kick suave + sub + pad corto),
  sin vibrato/wobble y sin risers de ruido; golpes de entrada en los momentos
  clave (inicio, drop, CTA) y tics en los cues.
- ``mezclar(voz, cama, total)``: duck de la cama por envolvente de la voz
  (ataque 60 ms, desprendimiento 400 ms, profundidad máx. -8 dB) y UNA sola
  normalización final ``loudnorm=I=-14:TP=-1.2:LRA=9`` (modo lineal; ver nota
  en ``mezclar``).
- ``verificar(ruta)``: control de calidad del archivo final con ebur128 +
  volumedetect (I ∈ [-14.5, -13.5], TP ≤ -1.2, LRA ≥ 4).

numpy + ffmpeg (en PATH), sin red.
"""
import os
import re
import shutil
import subprocess
import tempfile
import wave

import numpy as np

SR = 44100
BPM = 100
BEAT = 60 / BPM
COMPAS = 4 * BEAT

# Objetivo de master del entregable (un solo loudnorm al final, sin apilar)
LUFS_OBJETIVO = -14.0
LUFS_MIN = -14.5
LUFS_MAX = -13.5
TP_MAX_DB = -1.2
LRA_MIN = 4.0

# Parametros del duck por envolvente (del plan: ataque 60 ms, release 400 ms, min -8 dB)
ATAQUE_DUCK_S = 0.060
DESPRENDIMIENTO_DUCK_S = 0.400
PROFUNDIDAD_DUCK_DB = -8.0

# La cama entra como max -20 dB respecto de la voz media (restriccion global del plan)
NIVEL_CAMA_DB = -20.0

# Progresion Am-F-C-G: sub (raiz grave) + triada del pad, igual timbre de escala que gen_music
PROGRESION = [
    (55.00, (220.00, 261.63, 329.63)),
    (43.65, (174.61, 220.00, 261.63)),
    (65.41, (261.63, 329.63, 392.00)),
    (49.00, (196.00, 246.94, 293.66)),
]

HOP_ENVOLVENTE = 128  # muestras por muestra de control del duck (~345 Hz)


def _env(n, ataque_s, caida_s):
    """Ataque lineal + caida exponencial (envolvente de nota)."""
    return np.minimum(1, np.arange(n) / (ataque_s * SR + 1)) * np.exp(-np.arange(n) / (caida_s * SR))


# ---------------------------------------------------------------------------
# Cama musical discreta
# ---------------------------------------------------------------------------

def _golpe_kick():
    """Kick suave: seno con caida de tono rapida y decaimiento corto."""
    n = int(0.30 * SR)
    tt = np.arange(n) / SR
    cuerpo = np.sin(2 * np.pi * (48 + 80 * np.exp(-tt / 0.025)) * tt)
    return cuerpo * _env(n, 0.002, 0.10)


def _nota_sub(f):
    """Sub grave continuo de un compas, con bordes atenuados (60 ms) para que el
    cambio de nota no haga clic."""
    n = int(COMPAS * SR)
    onda = np.sin(2 * np.pi * f * np.arange(n) / SR)
    borde = int(0.06 * SR)
    onda[:borde] *= np.linspace(0, 1, borde)
    onda[-borde:] *= np.linspace(1, 0, borde)
    return onda


def _pad_corto(freqs):
    """Pad corto: triada de senos con afinacion estatica (sin vibrato/wobble),
    solo sostiene el arranque del compas, no lo llena."""
    n = int(1.0 * SR)
    tt = np.arange(n) / SR
    pad = np.zeros(n)
    for f in freqs:
        pad += np.sin(2 * np.pi * f * tt)
        pad += 0.4 * np.sin(2 * np.pi * f * 1.003 * tt + 0.7)  # detune fijo, no vibrato
    return pad * _env(n, 0.02, 0.45) / len(freqs)


def _golpe_entrada():
    """Golpe suave que anuncia inicio / drop / CTA."""
    n = int(0.80 * SR)
    tt = np.arange(n) / SR
    cuerpo = np.sin(2 * np.pi * 55 * tt) + 0.3 * np.sin(2 * np.pi * 110 * tt)
    return cuerpo * _env(n, 0.002, 0.30)


def _tic():
    """Tic corto de seno puro para los cues (pop de subtitulos/gancho)."""
    n = int(0.10 * SR)
    tt = np.arange(n) / SR
    return np.sin(2 * np.pi * 880 * tt) * _env(n, 0.002, 0.025)


def cama(total, cues=(), drop=None, cta=None):
    """Genera la cama musical discreta (kick suave + sub + pad corto, 100 BPM,
    sin vibrato/wobble ni risers de ruido) y la devuelve como arreglo numpy mono
    (SR) de ``total`` segundos. Los golpes de entrada caen en los momentos clave
    (inicio, drop, CTA) y los tics en ``cues``. Pico ~0.5 (-6 dBFS) con fade
    final, lista para que ``mezclar`` la baje al nivel correcto.
    """
    total = max(float(total), 0.2)
    if drop is None:
        drop = 0.4 * total
    if cta is None:
        cta = max(total - 3.0, 0.0)
    drop = min(max(drop, 0.0), total)
    cta = min(max(cta, 0.0), total)
    n = int(total * SR)
    mezcla = np.zeros(n)

    def anadir(sig, en, g=1.0):
        i = int(en * SR)
        if i < 0:
            sig = sig[-i:]
            i = 0
        j = min(n, i + len(sig))
        if i < n and j > i:
            mezcla[i:j] += g * sig[: j - i]

    # sub continuo por compas (muy debajo de todo)
    n_compases = int(np.ceil(total / COMPAS))
    for k in range(n_compases):
        anadir(_nota_sub(PROGRESION[k % 4][0]), k * COMPAS, 0.05)
    # pad corto: solo el arranque de cada compas
    for k in range(n_compases):
        anadir(_pad_corto(PROGRESION[k % 4][1]), k * COMPAS + BEAT, 0.055)
    # kick suave en cada pulso
    kick = _golpe_kick()
    for b in np.arange(0, total, BEAT):
        anadir(kick, b, 0.20)
    # entradas en momentos clave y tics en cues
    entrada = _golpe_entrada()
    tic = _tic()
    for c in (0.0, drop, cta):
        anadir(entrada, c, 0.40)
    for c in cues:
        anadir(tic, c, 0.16)

    fade_entrada = np.minimum(1, np.arange(n) / (0.30 * SR + 1))   # entrada con fade ~300 ms
    mezcla *= fade_entrada
    mezcla *= np.minimum(1, (total - np.arange(n) / SR) / 0.5)     # fade final
    pico = np.max(np.abs(mezcla))
    if pico > 0:
        mezcla = mezcla / pico * 0.5
    return mezcla


# ---------------------------------------------------------------------------
# Duck por envolvente y mezcla final
# ---------------------------------------------------------------------------

def _a_arreglo(senal, total):
    """Acepta un arreglo numpy o una ruta de WAV; devuelve mono float a SR recortado
    o rellenado con ceros hasta ``total``."""
    if isinstance(senal, (str, os.PathLike)):
        datos = _leer_wav(str(senal))
        return _encajar(datos, total)
    return _encajar(np.asarray(senal, float), total)


def _encajar(sig, total):
    n = int(total * SR)
    if len(sig) < n:
        sig = np.pad(sig, (0, n - len(sig)))
    return sig[:n]


def _leer_wav(ruta):
    """Lee un WAV y lo devuelve mono float en [-1, 1]; convierte el formato con
    ffmpeg si no es PCM de 8/16 bits."""
    try:
        with wave.open(ruta, "rb") as w:
            ch, sw = w.getnchannels(), w.getsampwidth()
            datos = w.readframes(w.getnframes())
        if sw == 2:
            arr = np.frombuffer(datos, dtype="<i2").astype(float) / 32768.0
        elif sw == 1:
            arr = (np.frombuffer(datos, dtype=np.ubyte).astype(float) - 128) / 128.0
        else:
            return _leer_wav_convertido(ruta)
        if ch > 1:
            arr = arr.reshape(-1, ch).mean(axis=1)
        return arr
    except wave.Error:  # formato no PCM (mp4, flac, ...) o firma rara
        return _leer_wav_convertido(ruta)


def _leer_wav_convertido(ruta):
    """Decodifica cualquier media file a WAV mono 16-bit con ffmpeg y lo lee."""
    with tempfile.TemporaryDirectory() as tmp:
        convertido = os.path.join(tmp, "convertido.wav")
        _correr_ffmpeg(["-i", ruta, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", convertido])
        return _leer_wav(convertido)


def _envolvente(voz):
    """Envolvente de la voz en escala [0, 1]: media movil de 10 ms normalizada por
    el percentil 95 (el nivel de habla tipico)."""
    x = np.abs(np.asarray(voz, float))
    w = max(1, int(0.010 * SR))
    media = np.convolve(x, np.ones(w) / w, "same")
    ref = np.percentile(media, 95)
    if ref < 1e-6:
        return np.zeros_like(media)
    return np.clip(media / (ref + 1e-9), 0, 1)


def _ganancia_duck(voz):
    """Ganancia para la cama: baja hasta PROFUNDIDAD_DUCK_DB siguiendo la envolvente
    de la voz, con ataque 60 ms cuando baja y desprendimiento 400 ms cuando sube."""
    n = len(voz)
    if n == 0 or np.max(np.abs(voz)) < 1e-6:
        return np.ones(n)
    env_c = _envolvente(voz)[::HOP_ENVOLVENTE]
    objetivo = 10 ** ((PROFUNDIDAD_DUCK_DB * env_c) / 20)
    k_atk = 1 - np.exp(-HOP_ENVOLVENTE / (ATAQUE_DUCK_S * SR))
    k_rel = 1 - np.exp(-HOP_ENVOLVENTE / (DESPRENDIMIENTO_DUCK_S * SR))
    g = np.empty_like(objetivo)
    g[0] = objetivo[0]
    for i in range(1, len(objetivo)):
        paso = k_atk if objetivo[i] < g[i - 1] else k_rel
        g[i] = g[i - 1] + paso * (objetivo[i] - g[i - 1])
    return np.interp(np.arange(n), np.arange(len(g)) * HOP_ENVOLVENTE, g)


def _rms(sig):
    rms = np.sqrt(np.mean(np.square(sig))) if len(sig) else 0.0
    return float(rms)


def mezclar(voz, cama_senal, total, salida=None, nivel_cama_db=NIVEL_CAMA_DB):
    """Mezcla final: voz + cama con duck suave (por envolvente, ataque 60 ms,
    release 400 ms, min -8 dB) y UNA normalizacion final
    ``loudnorm=I=-14:TP=-1.2:LRA=9``. ``voz`` y ``cama_senal`` aceptan arreglo
    numpy o ruta de WAV. Devuelve el arreglo mono resultante; si se pasa
    ``salida``, ademas escribe el WAV (stereo 16-bit) ahi. Picos corregidos
    ANTES del loudnorm, nunca despues (sin normalizaciones apiladas).

    Nota: el loudnorm corre en modo lineal (etapa de analisis + aplicacion en
    una sola cadena): el single-pass dinamico en ffmpeg 7.0.2 sobre contenido
    con rango alto se pasa del objetivo (midio I=-10.8 y aplasto LRA a 2.6 al
    probarlo); el modo lineal deja I=-14 exacto y conserva la dinamica.
    """
    total = float(total)
    voz_a = _a_arreglo(voz, total)
    cama_a = _a_arreglo(cama_senal, total)
    if nivel_cama_db is not None:
        rms_voz = _rms(voz_a)
        rms_cama = _rms(cama_a)
        if rms_voz > 1e-6 and rms_cama > 1e-6:  # cama a ~-20 dB respecto de la voz media
            cama_a = cama_a * (10 ** (nivel_cama_db / 20.0)) * (rms_voz / rms_cama)
    mezcla = voz_a + cama_a * _ganancia_duck(voz_a)
    pico = float(np.max(np.abs(mezcla))) if len(mezcla) else 0.0
    if pico == 0.0:  # silencio puro: no hay nada que corregir
        return mezcla
    if pico > 0.97:  # resguardo de picos antes del loudnorm
        mezcla = mezcla * (0.97 / pico)

    with tempfile.TemporaryDirectory() as tmp:
        entrada = os.path.join(tmp, "mezcla.wav")
        normalizado = os.path.join(tmp, "normalizado.wav")
        # stereo: el objetivo I=-14 se mide sobre el archivo que se entrega
        guardar(mezcla, entrada, estereo=True)
        medidas = _analizar_loudnorm(entrada)
        filtro = ("loudnorm=I=-14:TP=-1.2:LRA=9"
                  f":measured_I={medidas['integrado']:.2f}"
                  f":measured_TP={medidas['tp_entrada']:.2f}"
                  f":measured_LRA={medidas['lra_entrada']:.2f}"
                  f":measured_thresh={medidas['umbral_entrada']:.2f}"
                  f":offset={medidas['desplazamiento']:.2f}"
                  ":linear=true:print_format=none")
        _correr_ffmpeg(["-i", entrada, "-af", filtro,
                        "-ar", str(SR), "-c:a", "pcm_s16le", normalizado])
        final = _leer_wav(normalizado)
    if salida is not None:
        guardar(final, str(salida))
    return final


def _analizar_loudnorm(ruta):
    """Etapa de analisis del loudnorm (print_format=summary): devuelve I, True
    peak, LRA y threshold del archivo, que alimentan la aplicacion lineal."""
    r = _correr_ffmpeg(["-i", str(ruta), "-af",
                        "loudnorm=I=-14:TP=-1.2:LRA=9:print_format=summary",
                        "-f", "null", "-"], loglevel="info")
    texto = r.stderr
    medidas = {}
    for clave, campo in (("integrado", "Input Integrated"), ("tp_entrada", "Input True Peak"),
                         ("lra_entrada", "Input LRA"), ("umbral_entrada", "Input Threshold"),
                         ("desplazamiento", "Target Offset")):
        encontrado = re.search(re.escape(campo) + r":\s*([-+]?\d+(?:\.\d+)?)", texto)
        if not encontrado:
            raise RuntimeError("No pude leer el resumen de loudnorm:\n" + texto[-2000:])
        medidas[clave] = float(encontrado.group(1))
    return medidas


# ---------------------------------------------------------------------------
# Escritura y verificacion (QC)
# ---------------------------------------------------------------------------

def guardar(sig, salida, estereo=True):
    """Escribe el arreglo como WAV 16-bit 44.1 kHz; stereo duplicado por defecto
    (el formato que consumen los guiones de CapCut y ffmpeg)."""
    sig = np.clip(np.asarray(sig, float), -1.0, 1.0)
    if estereo:
        sig = np.stack([sig, sig], axis=1)
    elif sig.ndim == 1:
        sig = sig[:, None]
    with wave.open(salida, "wb") as w:
        w.setnchannels(sig.shape[1])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.round(sig * 32767).astype(np.int16).tobytes())


def _correr_ffmpeg(args, loglevel="error"):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg no esta en PATH: necesario para mezclar/verificar")
    r = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-loglevel", loglevel, "-y", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg fallo: " + r.stderr.strip()[-2000:])
    return r


def medir(ruta):
    """Metricas del archivo final: I/LRA con ebur128, True peak con el analizador
    de loudnorm (mismo motor R128; el resumen de ebur128 no imprime picos en
    ffmpeg 7.0.2) y volumedetect para max/mean de muestra."""
    r = _correr_ffmpeg(["-i", str(ruta), "-filter_complex", "ebur128=framelog=quiet",
                        "-f", "null", "-"], loglevel="info")
    texto = r.stderr
    lufs = re.search(r"I:\s*([-+]?\d+(?:\.\d+)?)\s*LUFS", texto)
    lra = re.search(r"LRA:\s*([-+]?\d+(?:\.\d+)?)\s*LU\b", texto)
    if not (lufs and lra):
        raise RuntimeError("No pude leer el resumen ebur128 de ffmpeg:\n" + texto[-2000:])
    medidas = _analizar_loudnorm(str(ruta))
    salidas = _correr_ffmpeg(["-i", str(ruta), "-af", "volumedetect", "-f", "null", "-"],
                             loglevel="info")
    vmax = re.search(r"max_volume:\s*([-+]?\d+(?:\.\d+)?)\s*dB", salidas.stderr)
    vmedia = re.search(r"mean_volume:\s*([-+]?\d+(?:\.\d+)?)\s*dB", salidas.stderr)
    return {
        "lufs": float(lufs.group(1)),
        "lra": float(lra.group(1)),
        "tp": medidas["tp_entrada"],
        "pico_muestra": float(vmax.group(1)) if vmax else None,
        "media_volumen": float(vmedia.group(1)) if vmedia else None,
    }


def verificar(ruta):
    """QC del archivo final: I ∈ [-14.5, -13.5] LUFS, TP ≤ -1.2 dBFS, LRA ≥ 4.
    Devuelve las metricas de ``medir``; lanza AssertionError si la entrega no cumple."""
    m = medir(ruta)
    assert LUFS_MIN <= m["lufs"] <= LUFS_MAX, (
        f"Master fuera de ventana: I={m['lufs']:.1f} LUFS (esperado {LUFS_MIN}..{LUFS_MAX} LUFS)")
    assert m["tp"] <= TP_MAX_DB + 1e-9, f"True peak {m['tp']:.1f} dBFS sobre el tope {TP_MAX_DB} dBFS"
    assert m["lra"] >= LRA_MIN, f"LRA {m['lra']:.1f} LU < {LRA_MIN}: mezcla aplastada"
    return m