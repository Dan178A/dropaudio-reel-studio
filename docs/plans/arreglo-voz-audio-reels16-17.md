# Plan · Arreglo de voz/audio y reedición de reel16 + reel17 (carpeta `ig-v2`)

## Problema (dignóstico medido, 16-10-2026)

El usuario dice: se usan bien las tomas, pero **los voz en off son pésimos** y
`ig/reel16_elige-el-color.mp4` + `ig/reel17_pedido-real_ig.mp4` quedan con **mal audio** y
**mal edición**.

Evidencia medida sobre los mp4 finales de IG:

| Archivo | I (LUFS) | LRA | Referencia buena (reel15) |
|---|---|---|---|
| ig/reel16_elige-el-color.mp4 | **-17.6** | 6.0 | -14.5 |
| ig/reel17_pedido-real_ig.mp4 | **-16.0** | **2.2** | -14.5 / LRA 5.5 |

- **A1 · Master demasiado bajo**: reel16 sale a -17.6 LUFS; IG normaliza ≈ a -14, así que abre
  apagado. Causa: normalización encadenada (master a -15.5 y encima `volume=-1.5dB` en la
  versión IG del mismo patrón usado en reel17). Regla nueva: **una sola normalización final a
  I=-14 LUFS · TP=-1.2, sin trims apilados** (la corrección de picos se hace ANTES del
  loudnorm, no después).
- **A2 · reel17: dinámica aplastada (LRA 2.2)**: `sidechaincompress=threshold=0.03:ratio=8`
  (umbral ≈ -30 dB, ratio 8) machaca la música el 90 % del reel y `loudnorm` encima. La cama
  bombea y el conjunto suena "asfixiado". Duck correcto: ganancia máx. -8 dB, ataque ~60 ms,
  subida ~400 ms.
- **A3 · Cama musical sintética audiblemente barata**: `gen_music.py` / `gen_music_v2` son
  pads de senos con vibrato (`sin(2π·0.3t)`), hats/risers de ruido blanco, kick sintetizado.
  Esa "musiquita" se oye sola en los huecos de reel16 (0.24 → tramos con música a -35 dB casi
  nula y luego "respira" de vuelta).
- **A4 · Voz en off TTS pésima (sistema)**: los narradores de plantilla son edge-tts
  (es-MX-JorgeNeural en reel16 v1/v2) y los textos "para aplicar Nandez en CapCut". El usuario
  lo rechaza una y otra vez. El reel17 entregado no lleva NI el TTS ni voz en los huecos
  (0-3.4 s = solo tarjeta + música).
- **A5 · Voz real de Daniel sin limpiar**: `cut.py` aplica solo `loudnorm` por tramo; no hay
  des-viento/hi-pass/compresión; con casco + moto queda seca/ruidosa.

Hallazgos visuales (fotogramas revisados):

- **E1 · reel16 t≈10 s**: tarjeta MRW sobre un primerísimo plano de cara con mirada rara; el
  encuadre del tramo F es incómodo en el corte.
- **E2 · reel16 t≈60 s**: tarjeta "Un Castor + cable tipo C" que duplica literalmente la
  información del subtítulo abajo ("mercado libre,").
- **E3 · reel17 t≈10 s**: tablero de moto detenido (0 km/h), muerto, sin caption ni tarjeta en
  el tramo "vamos en camino" — contradicción audio/visual y toma rellena.
- **E4 · reel16**: la tarjeta gancho se queda estática ~8 s sobre tomas distintas (h1 0→4.53,
  h2 4.63→7.97) — bien en contenido, flojo en contraste sobre cielo.

## Objetivo

1. **Reels 16 y 17 RE-EDITADOS** en carpeta nueva `.../reels/ig-v2/` (los originales NO se
   tocan): voz real de Daniel protagonista, cama musical limpia y discreta, master a
   -14 LUFS, cortes limpios (sin tomas muertas ni frases cortadas), entregables
   `IG <10 MB` y `máster <30 MB`.
2. **Sistema (repo)**: un solo módulo de mezcla/master con QC de audio (LUFS/TP/LRA) que el
   pipeline use para TODOS los futuros reels + política de voz correcta (sin narrador TTS
   donde está la voz real) + motor de música como CAMA (también re-utilizable por los reels
   ad-hoc).

## Decisions (D1–D4)

- **D1 · Voz (respondida)**: opción abierta — clonar la voz de Daniel EN LOCAL con la
  RTX 3060 Ti. Nuevo task **T1b** con `voz_clon.py` (XTTS-v2, import opcional/lazy, clona
  desde muestra limpia de la voz real). En gancho/cierre sin audio se usa la voz clonada
  SOLO si pasa el QC auditivo; si no, tarjeta sola. Fuera: narradores edge-tts y Nandez de
  plantilla; ninguna voz inventada sobre habla real.
- **D2 · Música (respondida)**: cama discreta nueva (T1): sin wobble ni risers de ruido,
  entra SOLO en huecos/entradas con fade ~300 ms, nunca bajo la voz.
- **D3 · Carpeta (respondida)**: `.../instagram/reels/ig-v2/` con los mismos nombres.
- **D4 · Alcance (respondida)**: reels + sistema. T5 = los hallazgos confirmados del
  `/code-review` (8 en `reel_studio.py`, 1 en `make_overlays.py`) que explican "no edita
  bien todos los videos"; to-dos menores quedan en el ledger.

## Global Constraints (obligan a todos los tasks)

- Voz real protagonista; NADA de voz en off de plantilla sobre/entre habla de Daniel.
- Master del entregable: I=-14 LUFS ±0.5 · TP=-1.2 · LRA ≥ 4, medido con ebur128 en el
  archivo final (no en el intermedio). Sin normalizaciones apiladas.
- Cama musical ≤ -20 dB respecto de la voz media; desaparece (fade) cuando no aporta.
- Los cortes NO cortan frases (la transcripción manda); sin tomas muertas >2 s sin voz y sin
  tarjeta; NADA de jump-cuts dentro de tomas de entrega completas de reel17.
- Fuente de verdad de estética: paleta negro/dorado/hueso, Space Grotesk + Plus Jakarta,
  precios verificados hoy (Castor Bass $25, Cable DAC $15, Castor Pro $28, EDX Pro X $13,
  AE01 $35), garantía 7 días, CTA ASESORÍA + 0422-1609357.
- Los originales de `ig/` no se tocan; todo lo nuevo va a `ig-v2/`.
- Sin push ni publicación; todo local. Los commits los hace el implementador del repo con
  los tests al día.
- La herramienta es ffmpeg/numpy ya en uso (venv del repo); no se agrega dependencia nueva
  sin justificarla en el propio task.

## Tasks

### Task 1 (T1) · Motor de audio de entrega (repo)
Crear `entrega_audio.py` (o ampliar `gen_music.py` con una API clara):
`cama()`: genera la cama musical discreta (kick suave + sub + pad corto, BPM 100,
sin vibrato/wobble, sin risers de ruido; cues de entrada en momentos clave);
`mezclar(voz, cama, total)`: duck suave por envolvente (ataque 60 ms, release 400 ms,
mín -8 dB) + single-pass `loudnorm=I=-14:TP=-1.2:LRA=9` al final; `verificar(path)`: ebur128
+ volumedetect → assert I∈[-14.5,-13.5], TP≤-1.2, LRA≥4.
Ajustar `gen_music.py` para delegar en el nuevo motor (compatible con su uso actual).
Tests: mezcla determinista en fixture corto con asserts de LUFS/duck (numpy, sin red).
Criterio: tests verdes en `pytest tests/`.

### Task 2 (T1b) · Voz clonada local (repo, opcional y lazy)
Nuevo `voces_clon.py`: XTTS-v2 (paquete `coqui-tts`/`TTS`, import LAZY — el resto del
pipeline no exige torch), es de español, GPU RTX 3060 Ti (8 GB) con fallback CPU.
Referencia: trozos limpios de la voz real (`assets/talk.mp4` del reel16, ya analizado) o
`voces/` del repo. API: `clonar(texto, ref_wav, salida)`. Sin voz clonada si no hay muestra
o GPU: fallar suave (skip) — la opción queda abierta, nada obligatorio.
Tests: no-resultado sin referencia (skip limpio); con torch disponible, generación corta
marcada como test lento (skipeable con `pytest -k`).
Nota de instalación: pip dentro del venv del repo; documento los pasos en el docstring.

### Task 3 (T2) · Reedición reel16 → `ig-v2`
A partir de `reel16-src` (copia mínima a `reel16-fix/`): re-corte del tramo F (encuadre por
fotogramas, no el close-up raro), tarjetas sin duplicar caption (quitar la de t60 o quitar
el caption en esa ventana), camas de música solo en huecos, mix con `entrega_audio.mezclar`,
verificación `verificar`, entregables a `ig-v2/` (IG 780k 2-pasadas + máster 2500k) con los
NOMBRES ORIGINALES. QC de fotogramas clave en ig-v2/QC-reel16/.

### Task 4 (T3) · Reedición reel17 → `ig-v2`
A partir de `reel17-src` + `reel17-t10`: re-mix con duck suave (kill del sidechain 0.03/8),
cama re-generada con el nuevo motor, master -14 LUFS una sola vez (sin el trim -1.5 dB IG),
cortes: sustituir/retirar el tramo muerto del tablero (t≈10 s), revisión de captions sobre
todas las pieza talk, entregables a `ig-v2/`. QC de fotogramas en ig-v2/QC-reel17/.

### Task 6 (T4) · QC con subagentes (gancho · edición · comunicación · calidad)
Sub-revisión por reel con 4 veredictos + evidencia (fotogramas + métricas ebur128 +
transcripción contra subtítulos). Fix rounds: cada hallazgo Critical/Important regresa al
implementador del task correspondiente (máx. 5 rondas, igual que el loop SDD).
Entregable delQC: `ig-v2/QC-resumen.md` con veredictos y las métricas de ambos reels.

### Task 5 (T5) · Hallazgos confirmados del /code-review (repo)
En `reel_studio.py`, en orden de importancia (reporte del 16-10-2026):
1. La exclusión de narración sobre habla real solo corre en la vía de
   reglas (`not sel.get("narracion")`); en la vía del modelo NUNCA → dos voces superpuestas
   (el bug original sigue vivo por la vía principal). Fix: filtrar narración contra
   `tiene_habla` en `armar_sel`/`validar` (una única vez, en el punto por donde pasan
   TODAS las vías: modelo, reglas y crítico).
2. `revisar`/crítico: la copia de `cand` vuelve a montar narración sin re-aplicar el
   marcado `audio=True` ni la exclusión → misma corrección centralizada debe cubrirlo.
3. Subtítulos y narración comparten `transform_y=Y_VOZ` y la narración no se recorta al
   final de su clip → cajas superpuestas. Fix: recortar narración a su clip + pista/y
   distinto si coincide en tiempo.
4. `tiene_habla` umbral 0.4: frases cortas en clips largos quedan sin subtítulos y
   silenciadas; y `subtitulos()` omite frases parciales (`completa=False`) → el espectador
   ve labios sin sonido. Fix: subtítulos para frases recortadas (marcadas `[…]` o
   similares) y marcado de audio por frases, no por cociente fijo.
5. `subtitulos()`: `max(0.4, d)` avanza el tiempo con `d` sin limitar → fragmentos
   superpuestos. Fix unificado con (4).
6. Fragmento de 0.05–0.1 s puede tumbar `armar_sel` completo (pycapcut ValueError). Fix:
   fusionar/saltar fragmentos < 0.25 s.
7. Chip renumerado "Dato N" vs ordinales fijos "Segundo..." de `NARR_REGLAS` →
   inconsistencia chip↔voz. Fix: ordinales derivados de `paso_visto`.
8. Flujo clásico `hacer_guion`→`armar` (Tkinter) nunca aplica el marcado/exclusión →
   re-validar `seleccion.json` en `armar` (centralizado igual que (1)).
9. `make_overlays.py:156`: código muerto `... if False else ...` — simplificar.
Tests nuevos por regresión en `tests/test_habla_real.py` / `test_guion_escenas.py`
(vía del modelo: narración sobre parla; crítico con clips re-insertados; fragmentos
cortos; flujo clásico). Criterio: `pytest` verde, cero voz de plantilla sobre habla real
en TODAS las vías.

## Especificación de los entregables en `ig-v2/`

- `reel16_elige-el-color.mp4` (≤10 MB, I=-14 LUFS) · `reel16_elige-el-color_full.mp4`
- `reel17_pedido-real_ig.mp4` (≤10 MB) · `reel17_pedido-real_full.mp4`
- `QC-reel16/`, `QC-reel17/` (fotogramas clave) · `QC-resumen.md`
- Nombres exactos para copiar/pegar a IG sin renombrar nada.

## Verificación final

1. `ffmpeg ebur128` sobre CADA mp4 de `ig-v2/`: I ∈ [-14.5, -13.5], LRA ≥ 4.
2. `ffprobe`: tamaño <10 MB en el de IG; streams aac 48 kHz estéreo.
3. Fotogramas de gancho (t 0.3, 2, 4) + medio + cierre: tarjeta legible, sin tomas muertas.
4. `pytest` del repo verde en lo tocado.
5. Reporte del QC de subagentes con 4 veredictos ✅/❌ por reel y sin halagos; los ❌ no
   supervivientes van al ledger.