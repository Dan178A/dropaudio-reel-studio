"""Voz clonada LOCAL (XTTS-v2 por Coqui) para la voz en off de los reels.

API publica: ``clonar(texto, ref_wav, salida)`` -> ruta del WAV generado o
``None`` si no se puede (fail-soft: sin torch/modelo/referencia el pipeline
sigue caminando, la opcion de voz clonada queda abierta, nunca obligatoria).
El resto del pipeline NO exige torch: la importacion del paquete pesado (TTS)
es LAZY, dentro de ``disponible()``/``_generar_xtts``; importar este modulo
solo carga os/subprocess/tempfile/wave.

**LICENCIA — LIMITE REAL Y VERIFICADO:** XTTS-v2 se distribuye bajo la licencia
**CPML (Coqui Public Model License), que PROHIBE el uso comercial del modelo y
de los audios derivados de el**. Las muestras de esta tarea son para decidir si
sirven; **publicar reels que usen la voz clonada es una decision de Daniel**, y
si esa salida llega a un uso comercial hay que cambiar de backend (ver abajo).

Notas de instalacion (venv del repo, Windows):
    venv\\Scripts\\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
    venv\\Scripts\\python.exe -m pip install coqui-tts
La primera vez que se genera audio con clonacion, XTTS-v2 se descarga
(~1.9 GB) a la cache de Coqui (``%LOCALAPPDATA%\\tts`` o ``$TTS_HOME``) y despues
todo corre offline. GPU objetivo: RTX 3060 Ti (8 GB, CUDA 12.4); sin GPU cae a
CPU (lento pero funciona). Backend abstraido en ``_generar``: XTTS-v2 es el
primario; cambiar a otro modelo futuro solo toca esa funcion.

numpy + ffmpeg (en PATH). Sin red en runtime, salvo la descarga inicial del
modelo (una sola vez, la misma que hace cualquier uso del backend).
"""
import os
import shutil
import subprocess
import tempfile
import wave

# Formato de entrega de las muestras (la mezcla final las trae al master -14 LUFS)
SR = 48000
LUFS_OBJETIVO = -16.0
TP_OBJETIVO_DB = -2.0
LRA_OBJETIVO = 7.0

# Idioma de la voz clonada y backend primario (abstraccion para cambiar despues)
IDIOMA = "es"
BACKEND = "xtts"

# Cache del modelo cargado (instancia pesada; se reusa entre llamadas)
_modelo = None


def _registros(mensaje):
    """Log corto a stderr: visible en consola, silencioso para el pipeline."""
    from sys import stderr

    print("[voces_clon] " + mensaje, file=stderr)


def disponible():
    """(disponible, razon) sin romper nada: revisa torch/TTS por lazy cada vez."""
    try:
        import torch  # noqa: PLC0415  (lazy a proposito)
    except Exception as e:  # ImportError de torch u otro paquete pesado
        return False, "sin paquete TTS/torch instalado (: {})".format(e)
    try:
        torch.cuda.is_available()
    except Exception:
        pass
    return True, "ok"


def _modelo_cargado():
    """Instancia de TTS con XTTS-v2 (GPU si hay, CPU si no). Se cachea."""
    global _modelo
    if _modelo is not None:
        return _modelo
    os.environ.setdefault("COQUI_TOS_AGREED", "1")  # acepta CPML sin prompt interactivo
    try:
        import torch  # noqa: PLC0415

        from TTS.api import TTS  # noqa: PLC0415  (lazy: el resto del pipeline no la necesita)
    except Exception as e:
        _registros("no se pudo importar TTS (: {})".format(e))
        return None
    try:
        gpu = bool(torch.cuda.is_available())
        _modelo = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=gpu)
        _registros("XTTS-v2 cargado en {}".format(_dispositivo()))
    except Exception as e:
        _registros("no se pudo cargar XTTS-v2 (: {})".format(e))
        return None
    return _modelo


def _dispositivo():
    """Nombre del dispositivo usado (informativo)."""
    try:
        import torch  # noqa: PLC0415

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _loudnorm_medidas(entrada):
    """(I_med, TP_med, LRA_med, umbral_med) de un primer paso de loudnorm (JSON)."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", entrada, "-map", "a",
         "-af", "loudnorm=I={:g}:TP={:g}:LRA={:g}:print_format=json".format(
             LUFS_OBJETIVO, TP_OBJETIVO_DB, LRA_OBJETIVO),
         "-f", "null", "-"],
        capture_output=True, text=True)
    linea = r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1]
    try:
        import json as json_mod

        d = json_mod.loads(linea)
        return (float(d["input_i"]), float(d["input_tp"]),
                float(d["input_lra"]), float(d["input_thresh"]))
    except Exception:
        return None


def _a_formato_entrega(entrada, salida):
    """Remuestrea a 48 kHz estereo 16-bit y normaliza a I=-16 LUFS / pico TP=-2 dB.

    Loudnorm en DOS pasos (medicion + linear=true), mismo ruling que
    ``entrega_audio``: una sola normalizacion, sin apilar dinamica.
    Si la medicion del primer paso falla, cae al single-pass (peor pero usable).
    Devuelve ``salida`` o None si ffmpeg falla.
    """
    af = "loudnorm=I={:g}:TP={:g}:LRA={:g},aresample={}:resampler=soxr".format(
        LUFS_OBJETIVO, TP_OBJETIVO_DB, LRA_OBJETIVO, SR)
    m = _loudnorm_medidas(entrada)
    if m is not None:
        af = ("loudnorm=I={:g}:TP={:g}:LRA={:g}:measured_I={:g}:measured_TP={:g}"
              ":measured_LRA={:g}:measured_thresh={:g}:linear=true:offset=0.0,"
              "aresample={}:resampler=soxr").format(
            LUFS_OBJETIVO, TP_OBJETIVO_DB, LRA_OBJETIVO, m[0], m[1], m[2], m[3], SR)
    ok = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", entrada,
         "-map", "a", "-af", af, "-ar", str(SR), "-ac", "2",
         "-c:a", "pcm_s16le", salida],
        capture_output=True).returncode == 0
    if not ok or not os.path.isfile(salida) or os.path.getsize(salida) < 200:
        return None
    return salida


def _generar_xtts(texto, ref_wav, destino_backend):
    """Backend XTTS-v2: texto en espanol clonado de ``ref_wav`` a un WAV temporal.

    Devuelve ``destino_backend`` o None si falla (modelo, red, inferencia).
    """
    m = _modelo_cargado()
    if m is None:
        return None
    try:
        m.tts_to_file(text=texto, speaker_wav=ref_wav, language=IDIOMA,
                      file_path=destino_backend, split_sentences=True)
    except Exception as e:
        _registros("inferencia XTTS fallo (: {})".format(e))
        return None
    return destino_backend if os.path.isfile(destino_backend) else None


def _generar(texto, ref_wav, destino_backend):
    """Despachador de backend (una funcion por backend; extender aqui)."""
    if BACKEND == "xtts":
        return _generar_xtts(texto, ref_wav, destino_backend)
    return None


def clonar(texto, ref_wav, salida):
    """Voz clonada de un tramo de referencia → WAV 48 kHz estereo 16-bit.

    ``texto``   str con la frase en espanol (no vacia).
    ``ref_wav`` ruta a un WAV (o cualquier audio que ffmpeg decode) con la voz
                real de referencia (recomendado 6-30 s limpios, como
                ``voces/ref_daniel/*.wav``).
    ``salida``  ruta destino del WAV final.

    Devuelve la ruta ``salida`` si todo salio bien, o ``None`` (fail-soft,
    con un log a stderr del motivo) si: texto/ref vacios o inexistentes, no
    hay torch/coqui-tts instalado, el modelo no carga, o la inferencia falla.
    Nunca levanta excepcion: el pipeline puede llamarlo y seguir.
    """
    if not isinstance(texto, str) or not texto.strip():
        _registros("texto vacio: nada que generar")
        return None
    ref = os.path.abspath(ref_wav) if ref_wav else None
    if not ref or not os.path.isfile(ref) or os.path.getsize(ref) == 0:
        _registros("sin muestra de referencia: la voz clonada queda en skip")
        return None
    if not shutil.which("ffmpeg"):
        _registros("ffmpeg no encontrado en PATH")
        return None
    ok, razon = disponible()
    if not ok:
        _registros(razon)
        return None
    salida = os.path.abspath(salida)
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voces_clon_") as tmp:
        crudo = os.path.join(tmp, "crudo.wav")
        if _generar(texto, ref, crudo) is None:
            _registros("generacion sin resultado (razon arriba)")
            return None
        final = _a_formato_entrega(crudo, salida)
    if final is None:
        _registros("post-proceso ffmpeg fallo")
        return None
    return final


def _leer_wav(ruta):
    """(sr, canales) de un WAV PCM (solo para tests/diagnostico)."""
    with wave.open(ruta, "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth()