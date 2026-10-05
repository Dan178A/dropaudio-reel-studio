# Escenas animadas con HyperFrames — Diseño

Fecha: 2026-10-05 · Rama: `feat/escenas-animadas`

## Objetivo

Que Reel Studio pueda **rescatar reels cortos** (material real entre 20 y 35 s, hoy descartados por `MIN_MATERIAL`)
y **alargar reels buenos** hasta una duración objetivo (35, 45 o 60 s), rellenando con escenas animadas de la marca
renderizadas con HyperFrames. El modelo de guion (glm, deepseek, etc. vía Ollama) elige qué escenas usar y escribe sus
textos; nunca escribe HTML ni animaciones.

## Decisiones (tomadas con el usuario)

| Tema | Decisión |
|---|---|
| Uso | A) rescatar reels cortos y B) alargar reels buenos |
| Ubicación | Solo en los pasos que encajan (cada plantilla declara sus pasos); el video real sigue siendo el núcleo |
| Mínimo de video real | 20 s |
| Motor | Plantillas HyperFrames fijas con variables; el LLM solo rellena JSON |

## Restricciones globales

- Python 3.10, librería estándar; HyperFrames se ejecuta como `npx --yes hyperframes@0.8.77 render …`
  (requiere Node ≥ 22 y FFmpeg en el PATH). Si faltan, la función se desactiva con un aviso; nada falla.
- Textos de UI, comentarios y textos de las escenas en español, estilo existente.
- Marca (de `dropaudio-contenido`): negro #090807/#0C0B09, dorado #CDA860/#E2BE72/#967337, hueso #F0EDE8; Space
  Grotesk 700 (titulares, tracking -0.04em) + Plus Jakarta Sans; logo onda `M2 12h3l2-6 4 14 4-18 3 10h4` +
  "DropAudio·CCS"; premium, motion design, ritmo de los reels v1; textos de 1–2 líneas y ≥ 1,5 s en pantalla.
- Precios siempre en $, solo los del catálogo de la app (`CFG["catalogo"]`); nunca inventados ni en Bs.
- CTA fijo: «Comenta ASESORÍA» / «o escríbenos al 0422-1609357».
- Tests sin red ni Node: el render se prueba con `subprocess` simulado.

## Componentes

### A. Plantillas — `escenas/<tipo>/` (proyectos HyperFrames)
Cinco plantillas 1080×1920, 30 fps, sin audio (la música/voz la pone el reel). **Duración no fija: prioridad calidad
y legibilidad.** Cada escena dura lo necesario para que su texto se lea con calma y la animación respire (ver «Duración»).

| tipo | pasos donde encaja | variables (string salvo indicación) |
|---|---|---|
| `precio` | "5", "cta" | `producto`, `precio` (number), `detalle` (≤ 40) , `imagen` (src opcional) |
| `comparativa` | "3", "4", "5" | `a_nombre`, `a_precio` (number), `a_punto`, `b_nombre`, `b_precio` (number), `b_punto`, `veredicto` |
| `tres_datos` | "1", "2", "3", "4" | `titulo` (≤ 40), `dato1`, `dato2`, `dato3` (≤ 50 c/u) |
| `para_quien` | "4", "5" | `producto`, `para` (≤ 60), `imagen` (src opcional) |
| `cta` | "cta" | `linea` (≤ 50, p. ej. «Lo pruebas antes de pagar») |

- Cada plantilla declara `data-composition-variables` con `default` útiles, usa `data-var-text`/`data-var-src`, y
  pasa `npx hyperframes lint` y `check`. Fuentes locales en `escenas/fonts/`. Imágenes de producto recortadas en
  `escenas/productos/<slug>.webp` (copiadas de `../DropAudio CCS landing/public/img/hero/*-t.webp`; si no hay imagen,
  la escena es solo tipográfica).
- **Duración:** la decide la legibilidad, no un número fijo. `escenas.duracion(tipo, datos)` = entrada + tiempo de
  lectura (≈ 2,5 palabras/s del texto visible, ≥ 1,5 s por bloque de texto) + pausa final legible + salida, acotada por
  `dur_min`/`dur_max` que el diseñador de cada plantilla fija según lo que se ve bien. La duración calculada se pasa al
  render y la plantilla reparte su animación en ese tiempo (el estado final legible se mantiene hasta el corte). Si
  HyperFrames no permite variar la duración de la composición por variable, el implementador elige el mecanismo
  equivalente (p. ej. componer la duración en el `index.html` generado antes del render) y lo documenta.
- `escenas/catalogo.json`: por tipo → `{"dur_min", "dur_max", "pasos", "descripcion", "variables": {id: {"tipo", "max"}}}`. Es la
  única fuente para el prompt del LLM, la validación y el render.

### B. Motor — `escenas.py`
- `disponible()` → `(bool, motivo)`: Node ≥ 22 y `ffmpeg` en el PATH (cacheado).
- `catalogo()` → dict de `catalogo.json` (de `RES`/`_MEIPASS` o carpeta del módulo).
- `validar_escena(tipo, datos, catalogo_precios)` → datos limpios o `None`: tipo conocido, recorta textos a `max`,
  precios numéricos y **solo si coinciden con un producto del catálogo** (por nombre); `imagen` se resuelve del slug
  del producto, nunca de una ruta/URL del LLM.
- `render(tipo, datos, cache_dir)` → ruta `.mp4`: hash de (tipo, datos, versión plantilla) → si existe en caché lo
  reutiliza; si no, copia la plantilla a una carpeta temporal y ejecuta
  `npx --yes hyperframes@0.8.77 render --variables-file vars.json --quality looks --output <hash>.mp4`
  (timeout 300 s; con `Popen` y, al vencer, se mata todo el árbol de procesos — `taskkill /T /F` en Windows, donde
  `npx` es `npx.cmd`). Error → `RuntimeError` en español con las últimas líneas de salida. Todo `subprocess` de
  `escenas.py` va sin ventana de consola en Windows (`CREATE_NO_WINDOW`). La clave de caché incluye además la versión
  de HyperFrames y el hash del archivo de imagen; el `.mp4` se publica vía un `.part` único (`mkstemp`) y, si otro
  render ya dejó el destino, se reutiliza.
- Precios por nombre: primero el nombre completo del catálogo; el nombre corto solo vale si es de un único producto
  (ambiguo → escena inválida, con un mensaje que pide el nombre completo). El prompt lista los nombres completos.
- Caché en `<carpeta>/_reel_studio/escenas/`.

### C. Planificador y guion — `reel_studio.py`
- Config nueva: `"escenas": true` (solo efectivo si `disponible()`), `"duracion_objetivo": 35` (35 | 45 | 60).
- `planear_serie`: con escenas activas el mínimo de material real es **20 s** (`MIN_REAL_CON_ESCENAS = 20`); sin
  escenas sigue `MIN_MATERIAL = 35`. El plan guarda `"objetivo"` y `"escenas": true/false`.
- `ESQUEMA_GUION`: cada clip es **o** un tramo de video (`archivo, desde, hasta, paso, audio?, motivo?`) **o** una
  escena (`escena` ∈ tipos, `paso`, `datos` objeto) — `anyOf`.
- Prompt del escritor (solo si el plan tiene escenas): lista de plantillas desde `catalogo.json` (tipo, duración, pasos,
  variables), segundos de video real disponibles, objetivo, y reglas: escenas solo en sus pasos, video real primero,
  máximo 40 % del reel en escenas, precios solo del catálogo, el gancho siempre es video real.
- `validar`: conserva las escenas válidas (`validar_escena`) con `segundos = escenas.duracion(tipo, datos)` y `paso` permitido;
  descarta las inválidas.
- **Objetivo = meta, no obligación (R3):** el prompt da un presupuesto explícito de escenas
  X = min(objetivo − real, real·2/3) s (redondeado hacia abajo a 0,5 s) y dice que el reel puede quedar por debajo
  del objetivo; nunca se pasa del 40 % para completarlo. El crítico recibe la misma regla.
- `chequeos`: la duración incluye escenas; la banda ideal sale del objetivo (35 → 30–45, 45 → 40–48, 60 → 55–63; la
  interfaz usa la misma) y un reel rescatado con las escenas al tope del 40 % no se castiga por quedar corto; nuevos problemas: video real < 20 s (grave 3), escenas > 40 % (grave 1),
  escena en paso no permitido (grave 1). `guion_en_texto` describe las escenas para el crítico.
- `guion_por_reglas` (sin IA): si falta duración, agrega `precio` (si hay producto con precio) y `cta` al final.

### D. Armado en CapCut — `armar_sel`
- Antes de crear el borrador, renderiza las escenas (con progreso en el log). Si una falla, se omite con aviso y el
  reel se arma igual.
- Una escena entra en la pista `video` como `VideoSegment` del `.mp4` (volumen 0, sin encuadre/blur).
- Si el `.mp4` dura menos que lo pedido, el clip se acorta a `duración real − 0,01 s`; si pycapcut aun así lo rechaza
  (`ValueError`), la escena se omite como una fallida.
- Sin chip de paso sobre una escena (la escena ya es el texto). **`png_cta` nunca va sobre una escena (R1):** si el
  último clip es la escena `cta`, no hay `png_cta`; si es otra escena, la tarjeta va al final del último clip de video
  real (si no hay ninguno, no va).
- **Narración (R2):** los textos de la pista «voz» se conservan (CapCut los convierte en voz); sobre video real van
  donde siempre (`transform_y = -0.42`) y, si tocan una escena, bajan a la franja libre de abajo (`transform_y = -0.74`,
  centro en y ≈ 1670) para no tapar los textos de la escena. La música sigue igual sobre todo el reel.
- `ReelStudio.spec`: agrega `('escenas', 'escenas')` a `datas`.

### E. Interfaz — `studio.html` / `studio_web.py`
- En «Ajustes avanzados»: casilla «Escenas animadas (HyperFrames)» y selector «Duración objetivo» (35/45/60 s). Si
  `disponible()` es falso, la casilla queda desactivada con el motivo («Instala Node 22+»…). `/api/estado` expone
  `escenas: {disponible, motivo}`.
- Editor del guion: los clips de escena se muestran como tarjeta «ESCENA · <tipo>» con sus textos editables (inputs
  por variable del catálogo), duración calculada (se actualiza al editar el texto), y se pueden mover/quitar como los demás. En la línea de tiempo llevan un
  color propio.

## Manejo de errores
- Sin Node/FFmpeg → función desactivada, reels como hoy.
- Primer `npx` sin internet → error claro «HyperFrames no está descargado; conéctate una vez».
- Escena inválida del LLM → se descarta; si el reel queda < 20 s reales se avisa como hoy.

## Pruebas
- `tests/test_escenas.py`: catálogo cargado, validación (recorte, precio fuera de catálogo → None, imagen no aceptada
  del LLM), caché por hash, comando de render armado (subprocess simulado), `disponible()` con PATH simulado.
- `tests/test_guion_escenas.py`: `planear_serie` con 22 s y escenas → plan; sin escenas → aviso; `validar` mezcla clips;
  `chequeos` con escenas; `guion_por_reglas` agrega precio+cta.
- Plantillas: `npx hyperframes lint` + `check` + `snapshot` de cada una (evidencia en el informe).

## Fuera de alcance
Reels 100 % motion, voz sintetizada dentro de las escenas, plantillas editables desde la UI, más de 5 plantillas.
