# Reel Studio + CapCut: reels con video real · DropAudio CCS (30/9 – 2/10/2026)

Resumen de lo construido en este chat: cómo pasamos de una carpeta de videos grabados con el teléfono a un borrador de CapCut armado por IA local (Ollama), y la app de escritorio que lo hace todo.

## 1. Punto de partida
- **Material:** carpeta de Drive "Vídeo dropaudioccs" (creada el 30/9) con videos del Pixel (`PXL_…`), videos de WhatsApp (`VID-…-WA00xx`), fotos (`IMG_…`) y más tarde la carpeta local `C:\Users\DAN_PC\Documents\GitHub\reel-capcut\Videos Dropaudioccs` (~80 archivos).
- **Límite del chat:** el conector de Drive no deja ver fotogramas ni audio. Para revisar un video hay que subirlo al chat (ahí sí se sacan fotogramas con ffmpeg y se transcribe con Whisper).
- **Objetivo:** que una IA elija las tomas y arme el reel en **CapCut de Windows**, siguiendo la fórmula de reels de DropAudio (gancho de problema → contenido → prueba → CTA).

## 2. Decisiones técnicas
| Tema | Decisión | Por qué |
|---|---|---|
| CapCut | **pyCapCut** (`github.com/GuanYixuan/pyCapCut`, clonado en `Documents\GitHub\pyCapCut`) escribe borradores que CapCut abre como propios | CapCut no tiene API oficial. Formato no documentado: puede romperse con actualizaciones. Exportar sigue siendo manual en CapCut 7+ |
| Jev | Modelo de decisión **`nimble`** vía `/v1/systemone` de Ollama (≥0.35) | Responde preguntas tipo sí/no (`noul`), elección (`choice`) y puntaje (`score`) con probabilidades. **Solo lee texto**: no ve imágenes |
| Visión | `gemma3:4b` describe un fotograma cada N segundos | Le da a Jev el texto que necesita |
| Voz del video | **faster-whisper** (`small`) | Sin transcripción la IA cortaba frases y ponía la intro al final |
| Guion | Modelo de texto elegible: `glm-5.3:cloud`, `deepseek-v4.1-flash:cloud`, `qwen3.6`, `minimax-m2.5:cloud`… o "reglas, sin IA" | Escribe el reel con los 5 pasos de «Así compras» |
| Voz narrada | Voz **Nandez** de CapCut | No se puede generar desde fuera: la app deja los textos en la pista "voz" y en CapCut se aplica Texto a voz |
| App | **Python + pywebview** (no Tauri) | Todo el motor es Python; pywebview usa el mismo WebView2 de Edge que usaría Tauri, sin Rust ni Node |

Modelos disponibles en la PC (`ollama ls`): deepseek-v4.1-flash:cloud, glm-5.3:cloud, glm-5.3-flash:cloud, gemma3:4b, nimble:latest, minimax-m2.5:cloud, qwen3.6, gemma4:e4b.

## 3. Evolución del flujo
1. **`reel_capcut.py` (línea de comandos):** `analizar` → `analisis.json`, `elegir` → `seleccion.json` (editable), `armar` → borrador en CapCut. Primera corrida: 18 tomas, 12 usables.
2. **reel_real_01:** la IA eligió bien las tomas, pero salió desordenado. Terminaba con "acompáñenme", tenía 6 s de fotos sin audio, el teléfono del CTA salía partido y se exportó en 480p.
3. **reel_real_02:** se reordenó (cara primero, luego las entregas), se quitaron las fotos y se agregaron textos de marca como **PNG transparentes** (Space Grotesk, negro/dorado/hueso), con la música propia `gen_music.py` (128 BPM, golpes en cada cambio).
4. **reel_real_03:** se agregaron fondos de producto a pantalla completa con fundido suave y zoom lento cuando Daniel nombra cada producto (Castor/Castor Pro; AE01 + Y12 Pro). Las entregas van completas, sin cortar frases. Se sumaron el video de la moto con el cliente pagando, la foto del cliente probando el Castor y la voz de prueba.
5. **Guion «Así compras»** (del reel03 motion): gancho → 01 Elige tu modelo → 02 Escríbenos → 03 Vamos a ti → 04 Lo pruebas ahí mismo → 05 Y solo entonces, pagas → CTA. Se entregaron las voces en WAV y los clips animados por paso (`voces_guion_asi_compras.zip`).
6. **Reel final `reel13_asi-entregamos-de-verdad.mp4`** (37,3 s, 1080x1920, 9,5 MB, −16,5 LUFS), montado por Daniel con voces de CapCut. Abre con "un gusto, Daniel, el chico de DropAudio", sigue con las entregas con su voz y cierra con la narración y el CTA. Resultado: natural, con cara en cámara y POV de entrega en moto (lo que la competencia no tiene).
   - Mejoras opcionales que quedaron anotadas: tarjeta del AM02 cuando se nombra (~18 s), estirar el chip "Lo prueba antes de pagar" hasta el CTA y recortar dos pausas.

### Textos de narración usados
- "Llega sellado, en moto, hasta tu mano."
- "Lo conecta, lo escucha ahí mismo... y si le gusta, paga."
- "Comenta asesoría y te ayudamos a elegir." (en minúsculas para que la voz no deletree)
- Guion por pasos: "Paso uno: eliges tu modelo." · "Paso dos: nos escribes por WhatsApp o Marketplace." · "Paso tres: vamos a ti, en moto." · "Paso cuatro: lo pruebas ahí mismo. Original y sellado." · "Y solo entonces, pagas. Con siete días de garantía." · "Revisas. Escuchas. Luego pagas. Comenta asesoría."

### Caption propuesto para el reel13
```
¿Pagas antes y rezas que llegue? Así entregamos de verdad 👇

✅ Te lo llevamos en moto, sellado y original
✅ Lo conectas y lo escuchas ahí mismo
✅ Solo si te gusta, pagas
✅ 7 días de garantía

Hoy salieron: KZ Castor ($25), Castor Pro ($28), DAC AM02 ($18) y módulo AE01 ($35).

🏍️ Caracas, Guarenas y Guatire en moto · 📦 Envíos a toda Venezuela

👉 Comenta ASESORÍA o escríbenos al 0422-1609357

#audifonoskz #kzvenezuela #audifonoscaracas #iem #dropaudioccs
```
Primer comentario para fijar: "¿Cuál te llevarías: Castor o Castor Pro? 👇"

## 4. Reel Studio (la app)
Evolucionó de interfaz Tkinter a interfaz web local y, al final, a **app de escritorio**.

### Qué hace
- **Panel izquierdo:** carpeta (con el conteo de videos y fotos), los 4 modelos con explicación (Visión, Decisión/Jev, Guion, Whisper) y ajustes avanzados (segundos entre fotogramas, mínimo "usable", volúmenes, música, rehacer análisis, carpeta de borradores).
- **3 pasos** con estado, ✓ al terminar y progreso con % y minutos restantes:
  1. **Analizar:** Whisper + visión + Jev por toma. Guarda en `analisis.json` y retoma si se corta.
  2. **Escribir guion:** el modelo arma el reel con «Así compras». El programa **mueve los cortes que caigan en mitad de una frase** (`sin_cortar_frases`).
  3. **Crear en CapCut:** borrador 1080x1920 con clips, gancho de marca, chip "PASO 0X" por sección, CTA, música y narración como textos en la pista **voz**.
- **Pestaña Tomas:** miniaturas, "Sirve/Descartada", barras de usable y engancha, lo que se dice, y filtros por calidad y tipo.
- **Pestaña Guion (editable, se guarda solo):** gancho con vista previa, línea de tiempo por paso, aviso si no dura 30–40 s, reordenar o quitar clips, editar tiempos y narraciones.
- **Aviso al terminar:** sonido, mensaje y título "✅ Reel Studio". Al crear el borrador muestra los pasos para aplicar la voz Nandez.
- **Revisión de diseño (gs-plan-design-review):** identidad 2→9, jerarquía 3→9, interacción 3→8, textos 5→9, accesibilidad 4→8 (teclado, foco visible, botones de 44 px, estado no solo por color).

### Archivos (`C:\Users\DAN_PC\Documents\GitHub\reel-capcut\`)
| Archivo | Para qué |
|---|---|
| `ReelStudio.pyw` | App de escritorio (ventana nativa, diálogo de carpetas, confirma antes de cerrar si hay tarea) |
| `Reel_Studio.bat` | Abre la app con doble clic (pythonw, sin consola) |
| `studio_web.py` | Servidor local (solo 127.0.0.1) que conecta la interfaz con el motor |
| `studio.html` | Interfaz (marca negro/dorado, Space Grotesk + Plus Jakarta Sans) |
| `reel_studio.py` | Motor: analizar, guion, armar en CapCut, PNG de marca, HEIC→JPG |
| `gen_music.py` | Música propia sintetizada (numpy, 128 BPM, sin derechos) |
| `icon.ico` | Ícono de la onda dorada |
| `Crear_exe.bat` | Empaqueta con PyInstaller → `dist\ReelStudio\ReelStudio.exe` (sin probar en Windows) |
| `requirements.txt` | faster-whisper, pillow, pillow-heif, numpy, pywebview |
| `reel_capcut.py` | Versión anterior por línea de comandos (sigue funcionando) |
| `studio_config.json` / `reel_studio.log` | Ajustes guardados / errores (se crean solos) |

Dentro de cada carpeta de videos se generan `analisis.json`, `seleccion.json` y `_reel_studio\` (PNG, música, miniaturas). Las fotos HEIC se convierten en `_jpg\`.

### Instalar y abrir
```powershell
cd C:\Users\DAN_PC\Documents\GitHub\reel-capcut
pip install -e ..\pyCapCut
pip install -r requirements.txt
```
Luego, doble clic en `Reel_Studio.bat`. Necesita Ollama abierto, ffmpeg en el PATH y CapCut cerrado al crear el borrador.

### Aplicar la voz Nandez en CapCut
1. Abrir el borrador (si CapCut estaba abierto, reiniciarlo).
2. Seleccionar los textos de la pista "voz" (clic en el primero, Shift + clic en el último).
3. Texto a voz → Nandez → Generar. Opcional: borrar los textos y dejar solo el audio.

## 5. Lecciones
- En video real hablado, **la transcripción manda**: sin ella la IA elige buenas tomas pero corta frases y desordena la historia.
- **No usar fotos sin audio de relleno** (6 s muertos = la gente se va). Si van fotos, con zoom lento y voz encima.
- **Lo que mejor funciona** es la cara en cámara al inicio, el POV de la entrega en moto y "el cliente prueba y luego paga". Es el diferencial frente a autemtech y Kataipa.
- Las voces de narración van **solo donde no habla Daniel**.
- Exportar siempre en 1080p, 30 fps.
- **Privacidad:** de las capturas de ventas se usan solo los productos, nunca nombres ni teléfonos de clientes.

## 6. Pendientes
1. Probar Reel Studio con los modelos reales en Windows y ajustar tiempos o prompts según el resultado.
2. Probar `Crear_exe.bat` (Whisper y pyCapCut son lo más delicado al empaquetar).
3. Programar o publicar el reel13 con el caption (solo cuando Daniel lo pida).
4. Ideas para la app: tarjetas o fondos de producto automáticos cuando se nombra un producto en la transcripción (como en reel_real_03) y elegir la voz o idioma del guion.
