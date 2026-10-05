# Plan — Versiones, auto-actualización y buscador de ollama.com

Spec: `docs/superpowers/specs/2026-10-04-versiones-actualizaciones-ollama-design.md` (autoridad; leer la sección del
componente indicado en cada tarea).

Worktree: `C:\Users\DAN_PC\Documents\GitHub\reel-capcut-wt` (rama `feat/versiones-actualizaciones-ollama`).
Python: `C:\Users\DAN_PC\Documents\GitHub\reel-capcut\venv\Scripts\python.exe` (el venv vive en el repo principal;
instalar ahí lo que falte con `-m pip install`). pyCapCut está en `C:\Users\DAN_PC\Documents\GitHub\pyCapCut`.

## Global Constraints
- Python 3.10; HTTP/HTML solo con librería estándar. Nueva dependencia runtime: `velopack` (añadir a
  `requirements.txt`). Dev: `pytest` en `requirements-dev.txt`.
- Textos de UI y comentarios en español, mismo estilo que `studio_web.py` / `reel_studio.py` (comentarios cortos,
  nombres en español).
- Servidor solo en 127.0.0.1; ningún endpoint nuevo acepta URLs arbitrarias del cliente.
- Tareas largas con `lanzar(tarea, fn)` y `JOB` existentes.
- Tests sin red (fixtures + monkeypatch). Comando: `<python> -m pytest -q` desde el worktree.
- `ReelStudio.spec` es la única fuente de verdad del empaquetado.
- Repo de releases: `https://github.com/Dan178A/dropaudio-reel-studio`. packId Velopack: `ReelStudio`.
- No ejecutar `git push`, no crear releases ni tags. Commits pequeños en la rama.

### Task 1: Versión única y carpeta de datos estable
Spec: componentes A y B.
- Crear `version.py` con `__version__ = "1.0.0"`.
- Crear `rutas.py` con `datos()` y `migrar_datos()` según spec B (`%LOCALAPPDATA%\ReelStudio\datos` cuando
  `sys.frozen`; carpeta del script en desarrollo; migración copia `studio_config.json` del lado del exe una sola vez,
  sin borrar).
- `studio_web.py`: `BASE = rutas.datos()` (llamar `rutas.migrar_datos()` antes de leer `CFG_FILE`); `RES` sin cambio.
  `/api/estado` agrega `"version": version.__version__`.
- `reel_studio.py`: la carpeta de videos por defecto (línea ~1149, `AQUI`) usa `rutas.datos()`; NO cambiar el uso de
  `AQUI` para fuentes (línea ~933), que son recursos de la app.
- `ReelStudio.pyw`: el log usa `rutas.datos()`; título de ventana `f"Reel Studio {__version__} · DropAudio CCS"`.
- `studio.html`: mostrar la versión en el `<small>` de la cabecera lateral (`DropAudio CCS · v1.0.0`), leída de
  `d.version`.
- Crear `requirements-dev.txt` (`pytest`) e instalar pytest en el venv.
- Tests `tests/test_rutas.py`: desarrollo devuelve la carpeta del módulo; congelado (monkeypatch `sys.frozen`,
  `sys.executable`, `LOCALAPPDATA` a tmp_path) devuelve y crea `…\ReelStudio\datos`; migración copia una vez y no
  sobrescribe un config existente.

### Task 2: Empaquetado con Velopack y GitHub Action de release
Spec: componente C.
- `ReelStudio.spec`: añadir `('ollama_curados.json', '.')` a `datas` (el archivo lo crea la Task 4; crear ya un
  `ollama_curados.json` mínimo `{"modelos": []}` si no existe para que el build no falle) y `'velopack'` a
  `hiddenimports`.
- `Crear_exe.bat`: instala requirements + pyinstaller y ejecuta `pyinstaller --noconfirm ReelStudio.spec` (sin
  flags que regeneren el spec). Mantener mensajes en español.
- `Crear_instalador.bat`: llama a `Crear_exe.bat` (o mismo pyinstaller), lee la versión de `version.py`, instala `vpk`
  si falta (`dotnet tool install -g vpk`) y ejecuta `vpk pack` a `Releases\`. Añadir `Releases/` a `.gitignore`.
- `ReelStudio.pyw`: `velopack.App().run()` como primera instrucción de `main()`, dentro de `try/except Exception`.
- `requirements.txt`: añadir `velopack`.
- `.github/workflows/release.yml` exactamente con los pasos de la spec C (checkout en `reel-capcut/` y pyCapCut fijado
  a `27480a1e954740af50363076e6fea94f2893ae93` en `pyCapCut/`, verificación tag==versión, notas de `git log` desde el
  tag anterior — usar `fetch-depth: 0` —, `vpk download github` tolerante a fallo, `vpk pack`, `vpk upload github`,
  `permissions: contents: write`).
- `README.es.md`: sección «Publicar una versión» (subir `__version__`, commit, `git tag vX.Y.Z`, `git push --tags`).
- Verificación: `python -c "import ast;ast.parse(open('ReelStudio.pyw',encoding='utf-8').read())"`; YAML válido
  (`python -c "import yaml"` si existe, si no revisión); `pyinstaller --noconfirm ReelStudio.spec` compila en el
  worktree (reportar si falla por entorno y por qué). No ejecutar `vpk upload`.

### Task 3: Actualizador (backend + banner)
Spec: componente D.
- Instalar `velopack` en el venv; inspeccionar su API real (`help(velopack)`, `dir(velopack.UpdateManager)`) y
  documentar en el informe qué clases/métodos usaste. Si hay fuente GitHub nativa, úsala; si no, la URL
  `https://github.com/Dan178A/dropaudio-reel-studio/releases/latest/download`.
- `actualizador.py`: `estado()`, `buscar()`, `aplicar(progreso)` según spec. `buscar()` nunca lanza: errores van a
  `"error"`. Si `UpdateManager` falla por no estar instalada → `instalada=False`.
- `studio_web.py`: hilo de chequeo 5 s tras `iniciar_servidor`; `ESTADO["update"]`; `/api/estado` devuelve `update`;
  `POST /api/actualizar` → `lanzar("actualizar", …)` con progreso en `JOB["hecho"]/JOB["total"]` (total=100).
- `studio.html`: banner según spec D (estilo coherente con la paleta existente: variables `--gold`, `--panel`,
  `--line2`, botones `.btn`), oculto si `!update || !update.nueva`; «Más tarde» lo oculta hasta recargar.
- Tests `tests/test_actualizador.py` con un `UpdateManager` falso (monkeypatch): no instalada; hay versión nueva con
  notas; sin novedad; error de red → `error` poblado.

### Task 4: Catálogo de ollama.com y descarga de modelos (backend)
Spec: componente E.
- `ollama_catalogo.py`: `buscar(q, filtro)`, parser `parsear(html)`, cache 10 min, respaldo con
  `ollama_curados.json` (buscar primero junto a `RES`/`sys._MEIPASS` y luego carpeta del módulo), `descargar(modelo,
  progreso)` con NDJSON de `/api/pull` usando `reel_studio.OLLAMA` como host, validación de nombre (regex de la spec),
  mensaje de `ollama signin` en errores de autorización.
- `ollama_curados.json` con ~12 modelos reales y el mismo esquema que devuelve `parsear`.
- `studio_web.py`: `GET /api/ollama/buscar` y `POST /api/ollama/descargar` (nombre inválido → 400 con mensaje).
  Al terminar la descarga: `ESTADO["modelos"] = core.modelos()`.
- Tests `tests/test_ollama_catalogo.py`: `parsear` sobre `tests/fixtures/ollama_search.html` (página real de
  `?q=gemma&c=vision`; el primer resultado es `gemma4` con capacidades `vision, tools, thinking, audio`, `cloud=True`
  y tamaños que incluyen `e2b` y `31b`); fallback cuando `urlopen` lanza; filtro sobre lista curada; validación de
  nombres (válidos: `gemma3:4b`, `glm-5.3:cloud`, `library/x`; inválidos: `../x`, `a b`, `http://x`, vacío); NDJSON de
  pull con respuesta falsa (progreso llamado, error → RuntimeError).

### Task 5: UI del buscador de modelos
Spec: componente F. Depende de los endpoints de la Task 4.
- `studio.html`: botón «Buscar en ollama.com», `<dialog id="ollamaBuscar">` con el estilo de `dialog#visor`, input con
  debounce 400 ms, chips de filtro, tarjetas de resultado, selección de tamaño, botón Descargar/Agregar que hace
  `POST /api/ollama/descargar` con `nombre:tamaño` (o `nombre` si no se eligió tamaño, `nombre:cloud` para cloud),
  marca «Instalado» comparando con `d.modelos`, aviso si `fuente === "lista"`. Al terminar la tarea
  `descargar_modelo` borrar `$("#sVision").dataset.loaded` para recargar selectores. Escapar todo texto con `esc()`.
- Accesible: labels, `aria-pressed` en chips, foco al input al abrir, Esc cierra.
- Verificación: arrancar `python studio_web.py` en un puerto libre desde el worktree, abrir `/` y comprobar con el
  navegador o `curl` que el HTML carga y `/api/ollama/buscar?q=gemma` responde JSON; reportar evidencia.
