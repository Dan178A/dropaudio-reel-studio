<div align="center">

<img src="docs/media/reel-studio.gif" alt="Reel Studio · DropAudio CCS" width="100%" />

# Reel Studio · DropAudio CCS

**De los videos del teléfono a un borrador terminado en CapCut, con IA corriendo en mi propia máquina.**

Yo grabo. La app transcribe, mira cada toma, decide cuál sirve, escribe el guion
y arma el borrador 1080×1920 en CapCut, listo para exportar.

**Un reel que me tomaba ~2 horas montar a mano ahora toma ~15 minutos, y la mayor parte sin supervisión.**

[Ver el video en MP4](docs/media/reel-studio-motion.mp4) · [Read me in English](README.md) · [Historia completa del proyecto](reel-studio-capcut-2026-10.md) · [Documentos de contexto](docs/contexto/README.md)

</div>

---

## El problema

Llevo [DropAudio CCS](https://dropaudioccs.com), una tienda de audio. Cada reel eran las mismas dos
horas: revisar todo lo grabado en el teléfono, buscar las tomas donde no me trabo, escribir el guion,
meterlo todo en CapCut y cuadrar los textos. Editar nunca fue lo difícil — **encontrar las tomas
usables sí**, y ninguna herramienta hace eso por ti.

Así que la app mira el material en mi lugar.

## Cómo funciona

| Paso | Qué hace | Con qué |
|---|---|---|
| **1 · Analizar** | Transcribe la voz, describe un fotograma cada N segundos y puntúa cada toma (usable / engancha). Guarda en `analisis.json` y retoma si se corta. | faster-whisper `small` · modelo de visión vía Ollama |
| **2 · Escribir guion** | Arma la narrativa «Así compras»: gancho → 5 pasos → CTA. Mueve los cortes que caen en mitad de una frase. | modelo de texto vía Ollama, o un respaldo por reglas sin modelo |
| **3 · Crear en CapCut** | Borrador 1080×1920 con clips, gancho de marca, chips "PASO 0X", CTA, música propia y la narración como textos en la pista `voz`. | pyCapCut · Pillow · `gen_music.py` |

**Sobre lo «local»:** la transcripción y el análisis de fotogramas corren enteros en esta máquina a
través de [Ollama](https://ollama.com) — el material nunca sale de aquí. El paso del guion usa por
defecto un modelo alojado en la nube, también vía Ollama; apúntalo a un modelo local y el flujo
completo queda offline.

## Notas de ingeniería

Lo interesante no son las llamadas a la IA, sino qué pasa cuando algo falla: un análisis de 10 minutos
que muere en el minuto 9 y empieza de cero es peor que no tener herramienta.

- **Análisis reanudable.** El progreso se escribe en `analisis.json` sobre la marcha; un cierre
  inesperado cuesta el archivo en curso, no la corrida entera.
- **Los fotogramas se deduplican antes de que un modelo los vea.** Cada fotograma se reduce a una
  miniatura gris de 24×24 y se compara con el anterior: las tomas estáticas se saltan el modelo de
  visión por completo. De ahí salió casi toda la velocidad, no de una GPU más grande.
- **Nada se queda colgado.** Cada llamada tiene timeout explícito con progreso visible (caracteres
  generados, segundos transcurridos), y si el modelo falla el guion se arma por reglas: la corrida
  siempre termina en un borrador.
- **Los modelos no se ponen de acuerdo sobre sus propias opciones.** Se desactiva el razonamiento largo
  con `think: false` y, si el modelo rechaza esa opción, se reintenta sin ella en vez de fallar.
- **La interfaz es una web local en ventana nativa.** pywebview + servidor atado solo a `127.0.0.1`,
  empaquetado en un `.exe` con PyInstaller: sin navegador, sin puerto expuesto, sin ritual de
  instalación.
- **Pegamento aburrido del mundo real:** conversión HEIC → JPG (CapCut y los modelos de visión no leen
  HEIC de forma confiable), descarga de fuentes y overlays de marca generados como PNG.

## Instalar y abrir

Requisitos: Windows, Python 3.10+, [Ollama](https://ollama.com) abierto, `ffmpeg` en el PATH y CapCut
de escritorio (cerrado al crear el borrador).

```powershell
git clone https://github.com/GuanYixuan/pyCapCut ..\pyCapCut
pip install -e ..\pyCapCut
pip install -r requirements.txt
```

Luego, doble clic en **`Reel_Studio.bat`** (o `pythonw ReelStudio.pyw`).
Para generar un `.exe`: `Crear_exe.bat` → `dist\ReelStudio\ReelStudio.exe`.

### Voz narrada en CapCut

1. Abre el borrador (si CapCut estaba abierto, reinícialo).
2. Selecciona los textos de la pista `voz` (clic en el primero, Shift + clic en el último).
3. Texto a voz → elige la voz → Generar.

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

## Lo que me enseñó el material

- En video hablado, **la transcripción manda**: sin ella la IA elige buenas tomas pero corta frases.
- Nada de fotos sin audio de relleno; si van fotos, con zoom lento y voz encima.
- Lo que mejor funciona: cara en cámara al inicio, POV de la entrega en moto y «el cliente prueba y
  luego paga».
- Exportar siempre en 1080p, 30 fps.
- Privacidad: de las capturas de ventas solo se usan los productos, nunca nombres ni teléfonos de
  clientes.

## Alcance y créditos

Es una herramienta interna que construí para mi propia tienda, publicada tal cual — no es un producto
ni un servicio que ofrezca. Se apoya en [pyCapCut](https://github.com/GuanYixuan/pyCapCut) para escribir
el formato de borrador de CapCut, que no es una API pública: puede romperse cuando CapCut cambie.
Sin afiliación ni respaldo de CapCut.

## Licencia

MIT © Daniel Alejandro Silva Rojas — ver [LICENSE](LICENSE).
Portafolio: [my-resume-landing.vercel.app](https://my-resume-landing.vercel.app/) · [LinkedIn](https://www.linkedin.com/in/daniel-alejandro-silva-rojas/)
