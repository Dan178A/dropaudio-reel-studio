# -*- coding: utf-8 -*-
"""Task 2: genera las 3 muestras de prueba de la voz clonada de Daniel.

Ejecutar con el venv del repo DESPUES de instalar coqui-tts (ver docstring de
voces_clon). La primera vez descarga el modelo XTTS-v2 (~1.9 GB)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import voces_clon as vc

DESTINO = r"C:\Users\DAN_PC\Documents\GitHub\DropAudio CCS landing\instagram\reels\ig-v2\samples"
REFS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "voces", "ref_daniel", "ref_a_daniel.wav"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "voces", "ref_daniel", "ref_c_daniel.wav"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "voces", "ref_daniel", "ref_a_daniel.wav"),
]
TEXTOS = [
    "¿Miedo a comprar online? Ve un pedido real.",
    "El cliente los prueba ahí mismo, ya puesto.",
    "Revisas, escuchas y luego pagas. Comenta ASESORÍA.",
]


def main():
    os.makedirs(DESTINO, exist_ok=True)
    ok, razon = vc.disponible()
    if not ok:
        print("FAIL-SOFT: " + razon)
        return 0  # la tarea lo permite; quedan tests y pasos de instalacion
    for i, (texto, ref) in enumerate(zip(TEXTOS, REFS), 1):
        salida = os.path.join(DESTINO, "muestra_voz_daniel_{}.wav".format(i))
        print("[{}] {}".format(i, texto))
        res = vc.clonar(texto, ref, salida)
        print("  -> {}".format(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())