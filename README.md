<div align="center">

<img src="docs/media/reel-studio.gif" alt="Reel Studio · DropAudio CCS" width="100%" />

# Reel Studio · DropAudio CCS

**De los videos del teléfono a un reel en CapCut, con IA local.**

Tú grabas. La IA transcribe, mira cada toma, decide cuál sirve, escribe el guion «Así compras» y arma el borrador 1080×1920 en CapCut. Todo corre en tu PC con Ollama.

[Ver el video en MP4](docs/media/reel-studio-motion.mp4) · [Historia completa del proyecto](reel-studio-capcut-2026-10.md)

</div>

---

## Cómo funciona

| Paso | Qué hace | Con qué |
|---|---|---|
| **1 · Analizar** | Transcribe la voz, describe un fotograma cada N segundos y puntúa cada toma (usable / engancha). Guarda en `analisis.json` y retoma si se corta. | faster-whisper `small` · `gemma3:4b` · Jev (`nimble`, `/v1/systemone`) |
| **2 · Escribir guion** | Gancho → 01 Elige tu modelo → 02 Escríbenos → 03 Vamos a ti → 04 Lo pruebas ahí mismo → 05 Y solo entonces, pagas → CTA. Mueve los cortes que caen en mitad de una frase. | `glm-5.3:cloud`, `deepseek-v4.1-flash:cloud`, `qwen3.6`… o reglas sin IA |
| **3 · Crear en CapCut** | Borrador 1080×1920 con clips, gancho de marca, chips "PASO 0X", CTA, música propia y la narración como textos en la pista **voz**. | pyCapCut · Pillow · `gen_music.py` |

## Instalar y abrir

Requisitos: Windows, Python 3.10+, [Ollama](https://ollama.com) abierto, `ffmpeg` en el PATH y CapCut de escritorio (cerrado al crear el borrador).

```powershell
git clone https://github.com/GuanYixuan/pyCapCut ..\pyCapCut
pip install -e ..\pyCapCut
pip install -r requirements.txt
```

Luego, doble clic en **`Reel_Studio.bat`** (o `pythonw ReelStudio.pyw`). Para generar un `.exe`: `Crear_exe.bat` → `dist\ReelStudio\ReelStudio.exe`.

### Voz narrada (Nandez) en CapCut

1. Abre el borrador (si CapCut estaba abierto, reinícialo).
2. Selecciona los textos de la pista "voz" (clic en el primero, Shift + clic en el último).
3. Texto a voz → **Nandez** → Generar.

## Estructura

| Archivo | Para qué |
|---|---|
| `ReelStudio.pyw` | App de escritorio (pywebview, ventana nativa con WebView2) |
| `Reel_Studio.bat` | Abre la app sin consola |
| `studio_web.py` | Servidor local (solo 127.0.0.1) entre interfaz y motor |
| `studio.html` | Interfaz (negro/dorado, Space Grotesk + Plus Jakarta Sans) |
| `reel_studio.py` | Motor: analizar, guion, armar en CapCut, PNG de marca, HEIC→JPG |
| `reel_capcut.py` | Versión de línea de comandos (`analizar` / `elegir` / `armar`) |
| `gen_music.py` | Música sintetizada sin derechos (128 BPM) |
| `make_overlays.py`, `overlays/` | Textos y fondos de marca en PNG/JPG |
| `readme-motion/` | Proyecto [HyperFrames](https://hyperframes.heygen.com) del video de este README |
| `reel-studio-capcut-2026-10.md` | Decisiones, evolución del flujo, lecciones y pendientes |

La carpeta de material crudo (`Videos Dropaudioccs/`) no se sube al repo.

## Regenerar el video del README

```bash
cd readme-motion
npx hyperframes check
npx hyperframes render --quality delivery --output renders/reel-studio-motion.mp4
ffmpeg -i renders/reel-studio-motion.mp4 -vf "fps=15,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" ../docs/media/reel-studio.gif
```

## Lecciones

- En video hablado, **la transcripción manda**: sin ella la IA elige buenas tomas pero corta frases.
- Nada de fotos sin audio de relleno; si van fotos, con zoom lento y voz encima.
- Lo que mejor funciona: cara en cámara al inicio, POV de la entrega en moto y "el cliente prueba y luego paga".
- Exportar siempre en 1080p, 30 fps.
- Privacidad: de las capturas de ventas solo se usan los productos, nunca nombres ni teléfonos de clientes.
