"""Cama musical DropAudio para reel hablado: suave bajo la voz, golpes en los cambios.

Delega en ``entrega_audio`` (motor nuevo: 100 BPM, sin vibrato ni risers de ruido).
Mantiene API y CLI de siempre:
- ``music(total, cues, drop, cta, out)`` (desde reel_capcut.py / reel_studio.py)
- ``python gen_music.py total drop cta salida.wav [pops...]``
"""
from entrega_audio import BPM, cama, guardar


def music(total, cues, drop, cta, out):
    """Compatibilidad: genera la cama discreta y la escribe stereo 16-bit en ``out``."""
    guardar(cama(total, cues=cues, drop=drop, cta=cta), out, estereo=True)


if __name__ == '__main__':
    import sys  # uso: python gen_music.py total drop cta salida.wav [pops...]
    a = sys.argv[1:]
    music(float(a[0]), [float(x)
          for x in a[4:]], float(a[1]), float(a[2]), a[3])