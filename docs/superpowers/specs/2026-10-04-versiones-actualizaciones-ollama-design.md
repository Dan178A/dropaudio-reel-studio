# Versiones, auto-actualización y buscador de modelos de ollama.com — Diseño

Fecha: 2026-10-04 · Rama: `feat/versiones-actualizaciones-ollama`

## Objetivo

1. Reel Studio tiene un número de versión y se distribuye con un **instalador** (Velopack, reemplaza a Inno Setup).
2. Publicar una versión = `git tag vX.Y.Z && git push --tags`. Una GitHub Action compila y publica el Release en
   `https://github.com/Dan178A/dropaudio-reel-studio` (repo público).
3. La app instalada revisa GitHub Releases al abrir; si hay versión nueva **avisa y pregunta** (banner con notas y
   botón «Actualizar y reiniciar»).
4. En «Modelos de Ollama» hay un buscador que consulta `https://ollama.com/search` (con filtros) y descarga el modelo
   elegido en el Ollama local (`/api/pull`) mostrando progreso. Si la web falla, usa una lista curada incluida.

## Decisiones (tomadas con el usuario)

| Tema | Decisión |
|---|---|
| Instalador/actualizador | Velopack (`vpk` CLI + paquete pip `velopack`) |
| Fuente de modelos | HTML en vivo de ollama.com/search + respaldo con lista curada `ollama_curados.json` |
| Comportamiento del update | Avisar y preguntar; nunca instalar en silencio |
| Git | Rama aparte; al final push + PR |

## Restricciones globales

- Python 3.10, solo librería estándar para HTTP/HTML (`urllib`, `html.parser`/`re`). Única dependencia nueva de
  runtime: `velopack`. Dependencia de desarrollo: `pytest` (en `requirements-dev.txt`).
- Todo texto visible al usuario y comentarios en **español**, siguiendo el estilo existente (comentarios breves, nombres
  en español: `buscar`, `descargar`, `CFG`, `ESTADO`, `JOB`).
- El servidor sigue escuchando solo en 127.0.0.1. Ningún endpoint nuevo acepta URLs arbitrarias.
- Las tareas largas usan el mecanismo existente `lanzar(tarea, fn)` + `JOB` (hecho/total/mensaje) en `studio_web.py`.
- Los tests no tocan la red: se usan fixtures (`tests/fixtures/ollama_search.html`) y monkeypatch.
- `ReelStudio.spec` es la **única** fuente de verdad del empaquetado; `Crear_exe.bat` deja de pasar flags y llama
  `pyinstaller --noconfirm ReelStudio.spec`.
- pyCapCut es un repo hermano (`../pyCapCut`, upstream `GuanYixuan/pyCapCut`). En CI se clona en la carpeta hermana,
  fijado al commit `27480a1e954740af50363076e6fea94f2893ae93`.

## Componentes

### A. Versión única — `version.py`
`__version__ = "1.0.0"`. La usan: título de la ventana (`Reel Studio 1.0.0 · DropAudio CCS`), `/api/estado`
(`"version"`), la barra lateral de `studio.html` y la Action (que falla si el tag ≠ `v` + `__version__`).

### B. Carpeta de datos estable — `rutas.py`
Velopack instala en `%LOCALAPPDATA%\ReelStudio\current\` y **reemplaza esa carpeta en cada update**. Hoy
`studio_config.json`, `reel_studio.log` y la carpeta de videos por defecto viven junto al `.exe` → se perderían.

- `rutas.datos()` → si `sys.frozen`: `%LOCALAPPDATA%\ReelStudio\datos` (se crea); si no: carpeta del script (sin cambio
  en desarrollo).
- `rutas.migrar_datos()` → solo congelado: si `datos/studio_config.json` no existe y existe junto al exe, lo copia
  (una vez). No borra nada.
- `studio_web.BASE`, `ReelStudio.pyw` (log) y `reel_studio.AQUI` (carpeta de videos por defecto) usan `rutas.datos()`.
  Los recursos empaquetados siguen en `RES = sys._MEIPASS`. `reel_studio.py:933` (fuentes) sigue apuntando a recursos
  de la app, no a datos.

### C. Empaquetado y publicación
- `ReelStudio.spec`: agrega `version.py` implícito (es import), `ollama_curados.json` a `datas`, `velopack` a
  hiddenimports si hace falta.
- `ReelStudio.pyw`: `velopack.App().run()` como **primera** instrucción de `main()` (maneja hooks de instalación /
  desinstalación); en `try/except` para que en desarrollo no falle.
- `Crear_instalador.bat` (local): pyinstaller con el spec + `vpk pack` → `Releases\` (para probar el Setup.exe sin
  publicar).
- `.github/workflows/release.yml`: en push de tag `v*`, `windows-latest`:
  checkout de este repo en `reel-capcut/` y de pyCapCut (commit fijado) en `pyCapCut/`; Python 3.10; instala
  requirements + pyinstaller + velopack; verifica tag == versión; `pyinstaller --noconfirm ReelStudio.spec`;
  `dotnet tool install -g vpk`; `vpk download github` (para deltas, tolera que no haya releases previos);
  `vpk pack --packId ReelStudio --packVersion <ver> --packDir dist/ReelStudio --mainExe ReelStudio.exe
  --packTitle "Reel Studio" --icon icon.ico --releaseNotes notas.md` (notas = `git log` entre el tag anterior y este);
  `vpk upload github --repoUrl https://github.com/Dan178A/dropaudio-reel-studio --publish --tag v<ver>
  --releaseName "Reel Studio v<ver>" --token ${{ secrets.GITHUB_TOKEN }}`. `permissions: contents: write`.
- README.es.md: sección corta «Publicar una versión».

### D. Actualizador — `actualizador.py`
- `estado()` → `{"instalada": bool, "actual": str, "nueva": str|None, "notas": str, "error": str|None}`.
  `instalada=False` cuando la app no corre desde una instalación Velopack (desarrollo / carpeta dist suelta): nunca
  falla, solo no ofrece updates.
- `buscar()` → usa `velopack.UpdateManager` con la fuente de GitHub (`GithubSource` si el paquete la expone; si no,
  URL `https://github.com/Dan178A/dropaudio-reel-studio/releases/latest/download`). Notas: las del paquete
  (markdown) si vienen; si no, `body` de `api.github.com/repos/Dan178A/dropaudio-reel-studio/releases/latest`.
- `aplicar(progreso)` → descarga reportando 0–100 y llama `apply_updates_and_restart`.
- `studio_web.py`: hilo que, 5 s después de arrancar, llama `buscar()` una vez y guarda `ESTADO["update"]`.
  `/api/estado` incluye `version` y `update`. `POST /api/actualizar` → `lanzar("actualizar", …)`.
- `studio.html`: banner arriba («Hay una versión nueva: vX.Y.Z» · «Ver notas» · «Actualizar y reiniciar» ·
  «Más tarde» que lo oculta en la sesión). La versión actual se muestra en la barra lateral.

### E. Catálogo ollama.com — `ollama_catalogo.py`
- `buscar(q="", filtro="")` con `filtro ∈ {"", "vision", "cloud", "tools", "embedding", "thinking"}` →
  `{"fuente": "web"|"lista", "modelos": [{"nombre","descripcion","capacidades":[...],"cloud":bool,"tamanos":[...],"pulls":str}]}`.
  GET `https://ollama.com/search?q=<q>&c=<filtro>` (timeout 8 s, User-Agent propio). Parseo de cada `<li>` con
  `href="/library/<nombre>"`: descripción del `<p>`; spans `bg-indigo-50` → capacidades; span `bg-cyan-50` con «cloud»
  → `cloud=True`; spans `bg-[#ddf4ff]` → tamaños; «Pulls» → pulls (mejor esfuerzo). Cache en memoria 10 min por
  (q, filtro). Si hay excepción o 0 resultados parseados con `q` vacío → lista curada filtrada (`fuente: "lista"`).
- `ollama_curados.json` (~12 modelos útiles para la app: gemma3, qwen2.5vl, llava, llama3.2-vision, glm-5.3,
  deepseek-v4.1-flash, qwen3, gpt-oss, etc.) con el mismo esquema.
- `descargar(modelo, progreso)` → POST `/api/pull` con `stream: true`, lee NDJSON y llama `progreso(completed, total,
  status)`; si una línea trae `error` lanza `RuntimeError` (si menciona autorización: «Inicia sesión en Ollama:
  ejecuta `ollama signin`»). Valida el nombre con `^[a-z0-9][a-z0-9._/-]*(:[a-z0-9._-]+)?$`.
- `studio_web.py`: `GET /api/ollama/buscar?q=&c=` → JSON; `POST /api/ollama/descargar {"modelo": "..."}` →
  `lanzar("descargar_modelo", …)`, al terminar refresca `ESTADO["modelos"] = core.modelos()`.

### F. UI del buscador — `studio.html`
Botón «Buscar en ollama.com» bajo «Actualizar lista». Abre un `<dialog>` (mismo estilo que `dialog#visor`):
input de búsqueda (debounce 400 ms), chips de filtro (Todos · Visión · Cloud · Tools · Embedding), resultados con
nombre, descripción, etiquetas, chips de tamaño seleccionables (+ «cloud» si aplica), botón «Descargar»
(«Agregar» para cloud) y «Instalado» si ya está en `d.modelos`. Aviso cuando `fuente == "lista"`. El progreso usa la
barra de tarea existente; al terminar se recargan los selectores.

## Manejo de errores
- Sin internet / ollama.com cambia su HTML → lista curada, nunca error en pantalla.
- Ollama apagado → mensaje claro en la tarea («No se pudo conectar con Ollama en …»).
- Update falla al descargar → `JOB.ok=False` con mensaje; la app sigue funcionando.

## Pruebas
- `tests/test_rutas.py`, `tests/test_ollama_catalogo.py` (parser contra fixture real, filtros, fallback, validación de
  nombre, NDJSON de pull con respuesta falsa), `tests/test_actualizador.py` (modo no instalado, estado con
  UpdateManager falso). Comando: `..\reel-capcut\venv\Scripts\python.exe -m pytest -q`.
- La Action no se ejecuta en esta rama; se valida con `actionlint` si está disponible o revisión manual.

## Fuera de alcance
Firma de código (certificado), canal beta, actualización silenciosa, macOS/Linux.
