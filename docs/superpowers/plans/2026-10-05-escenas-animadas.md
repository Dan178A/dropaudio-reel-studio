# Plan — Escenas animadas con HyperFrames

Spec: `docs/superpowers/specs/2026-10-05-escenas-animadas-design.md` (autoridad; leer el componente indicado).

Worktree: `C:\Users\DAN_PC\Documents\GitHub\reel-capcut-escenas` (rama `feat/escenas-animadas`).
Python: `C:\Users\DAN_PC\Documents\GitHub\reel-capcut\venv\Scripts\python.exe`. Node 22.12 y FFmpeg 7 están instalados.
Tests: `<python> -m pytest -q` desde el worktree (hoy 38 en verde; deben seguir en verde).

## Global Constraints
- Python 3.10, librería estándar. HyperFrames: `npx --yes hyperframes@0.8.77 …`.
- Textos de UI/escenas y comentarios en español, estilo de `reel_studio.py` / `studio_web.py`.
- Marca: negro #090807/#0C0B09, dorado #CDA860/#E2BE72/#967337, hueso #F0EDE8; Space Grotesk 700 (tracking -0.04em) +
  Plus Jakarta Sans; logo onda `M2 12h3l2-6 4 14 4-18 3 10h4` + "DropAudio·CCS"; ritmo de los reels v1; textos 1–2
  líneas ≥ 1,5 s en pantalla.
- Precios en $, solo del catálogo de la app. CTA «Comenta ASESORÍA» / «o escríbenos al 0422-1609357».
- Tipos: precio, comparativa, tres_datos, para_quien, cta. Duración NO fija: calidad y legibilidad primero, calculada
  por `escenas.duracion(tipo, datos)` dentro de `dur_min`/`dur_max` de cada plantilla (spec A «Duración»). Mínimo real con
  escenas 20 s; escenas ≤ 40 % del reel; duracion_objetivo ∈ {35, 45, 60}.
- Tests sin red ni Node (subprocess simulado). No git push, tags ni releases. Respetar finales de línea de cada archivo.

### Task 1: Plantillas HyperFrames y catálogo
Spec: componente A.
- Usa las skills `hyperframes-core`, `hyperframes-animation` y `hyperframes-cli` (invócalas con la herramienta Skill)
  antes de escribir HTML.
- Crear `escenas/precio/`, `escenas/comparativa/`, `escenas/tres_datos/`, `escenas/para_quien/`, `escenas/cta/`
  (cada uno un proyecto HyperFrames válido: `index.html` + `hyperframes.json` si `init` lo crea), `escenas/fonts/`
  (Space Grotesk y Plus Jakarta Sans locales; descargarlas de Google Fonts si no existen en el repo) y
  `escenas/productos/` con los `*-t.webp` de `C:\Users\DAN_PC\Documents\GitHub\DropAudio CCS landing\public\img\hero`
  renombrados por slug del nombre del catálogo (`productos.json`), más un `escenas/productos/mapa.json`
  `{nombre_producto: archivo}` solo para los que tengan imagen.
- Variables exactamente como la tabla del spec A (ids, tipos, máximos), con `default` útiles en español.
- Diseña cada plantilla para que se entienda: jerarquía clara, texto grande, entrada/salida que respiren; fija
  `dur_min`/`dur_max` por lo que se ve bien en los snapshots. Implementa el mecanismo de duración variable (spec A).
- `escenas/catalogo.json` según spec A (`dur_min`, `dur_max`, `pasos`, `descripcion`, `variables` {id: {"tipo", "max"}}), coherente
  con cada `index.html`.
- Verificación: en cada plantilla `npx --yes hyperframes@0.8.77 lint` y `check`, `snapshot` en 2–3 tiempos y un
  render de prueba `--quality draft` de `precio` y `cta` con `--variables` de ejemplo; reportar duración con `ffprobe`.
  No commitear `.mp4`, `node_modules`, renders ni snapshots (añadir a `.gitignore` lo necesario).

### Task 2: Motor `escenas.py`
Spec: componente B.
- `disponible()`, `catalogo()`, `duracion(tipo, datos)`, `validar_escena(tipo, datos, catalogo_precios)`,
  `render(tipo, datos, cache_dir)` (renderiza con la duración calculada)
  exactamente como el spec B. `imagen` se resuelve con `escenas/productos/mapa.json` a partir de `producto` /
  `a_nombre`; nunca se acepta del LLM.
- Tests `tests/test_escenas.py` (ver spec «Pruebas»).

### Task 3: Planificador, esquema, prompt, validación y chequeos
Spec: componente C. Depende de `escenas.py` (Task 2).
- `reel_studio.py`: `MIN_REAL_CON_ESCENAS = 20`; `planear_serie` usa ese mínimo cuando `cfg` tiene escenas activas y
  disponibles (pasar la bandera explícita desde `hacer_serie`; mantener la firma compatible con un parámetro opcional);
  plan con `"objetivo"` y `"escenas"`.
- `ESQUEMA_GUION` con `anyOf` (video | escena); prompt adicional con el catálogo cuando el plan tiene escenas;
  `validar`, `chequeos`, `guion_en_texto`, `guion_por_reglas` según spec C. El crítico recibe el mismo esquema.
- `studio_web.py`: defaults `"escenas": True`, `"duracion_objetivo": 35` en `CFG`.
- Tests `tests/test_guion_escenas.py` (ver spec «Pruebas»). Los 38 tests existentes siguen en verde.

### Task 4: Armado en CapCut y empaquetado
Spec: componente D. Depende de Tasks 2–3.
- `armar_sel`: render previo de escenas a `<carpeta>/_reel_studio/escenas/`, inserción como `VideoSegment` (volumen 0),
  sin chip de paso sobre escenas, sin `png_cta` si el último clip es escena `cta`, escenas fallidas omitidas con aviso.
- `ReelStudio.spec`: `('escenas', 'escenas')` en `datas`.
- Test: `armar_sel` con pycapcut real si importable (pyCapCut está en `..\pyCapCut`; añadir al `sys.path` en el test) o
  con un doble mínimo, verificando que un clip escena genera un segmento de video con el `.mp4` renderizado (render
  simulado) y que no se pide `png_paso` para ese clip.
- Verificación manual: armar un borrador real con una escena (`precio`) renderizada de verdad en una carpeta temporal de
  borradores (no en la de CapCut del usuario) y reportar que `draft_content.json` referencia el `.mp4`.

### Task 5: Interfaz
Spec: componente E. Depende de Tasks 3–4.
- `studio_web.py`: `/api/estado` incluye `escenas: {disponible, motivo}` y `catalogo_escenas` (solo con `fmt=1`, junto a
  `formatos`).
- `studio.html`: casilla y selector en «Ajustes avanzados» (`data-k="escenas"`, `data-k="duracion_objetivo"`),
  desactivados con motivo si no disponible; editor del guion con tarjetas «ESCENA · <tipo>» (inputs por variable,
  escapados con `esc()`), color propio en la línea de tiempo, mover/quitar como los clips de video. Comprobar que el
  guardado del guion (`/api/guion`) conserva `escena`/`datos`.
- Verificación: `node --check` del script; servidor en puerto libre, `curl /` y `/api/estado?fmt=1`; tests en verde.
