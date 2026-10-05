# 1 · Resumen y logros

*Actualizado: 4 oct 2026*

## Qué es Reel Studio

Reel Studio es la app de escritorio propia de DropAudio CCS que convierte una carpeta de videos y fotos del teléfono en una **serie de reels** listos como borradores de CapCut. Corre en la PC con IA local (Ollama) y no depende de servicios pagos.

- **Entra:** la carpeta con el material crudo (videos del Pixel, del iPhone y de WhatsApp; fotos HEIC/JPG).
- **Sale:** varios reels verticales 1080×1920, uno por formato y producto, con gancho, chips de pasos, CTA, música propia y la voz en off escrita para generarla en CapCut con la voz Nandez.
- **Vive en:** este repo (`reel-capcut`); el ejecutable es `dist\ReelStudio\ReelStudio.exe` (se arma con `Crear_exe.bat`).

## Punto de partida (2 oct 2026)

Ya existía una primera versión que armaba **un solo reel «Así compras» por carpeta**. El material eran ~83 archivos (59 videos, ~28 min, y 20 fotos) en `Videos Dropaudioccs`.

| Problema | Síntoma |
|---|---|
| Análisis lento | ~305 minutos estimados: todo en fila, una llamada a Ollama a la vez |
| Guion "colgado" | El paso 2 no mostraba avance; glm a veces entraba en bucle (128 000 caracteres) |
| Un solo reel | De toda una carpeta salía un video; se mezclaban productos de $13, $25 y $35 |
| Sin contexto | La IA no sabía qué producto era cada toma ni cuál era una entrega |
| Reels flojos | Cortos (12-19 s), unboxings cortados, gancho genérico, voz que no cubría el video |

## Logros

| Área | Antes | Ahora |
|---|---|---|
| Análisis de 79 archivos | ~305 min, en fila | 6 a la vez; ~5× más rápido en prueba (38 s → 8 s); salta fotogramas repetidos |
| Reels por carpeta | 1 «Así compras» | Serie: Unboxing, Review, Educativo, Entregas y Así compras (6 a 11 reels con el material actual) |
| Productos | Mezclados | Unboxing, Review y Educativo de un solo modelo, con su precio real |
| Contexto del dueño | Ninguno | Pestaña Etiquetar: tipo, producto, nota y marcas por segundo, con reproductor |
| Catálogo | A mano | 20 productos y precios traídos de la landing (`productos.json`) |
| Paso del guion | Parecía colgado | Avance en vivo, 4 formatos de respuesta de respaldo, corte a los 10 min, reglas si todo falla |
| Calidad | Sin revisión | Crítico: nota 0-10, problemas medidos y corrección del guion |
| Duración | 12-19 s en varios reels | Mínimo 35 s de material por reel; los de < 20 s se marcan para descartar |
| Voz en off | ~17 s de voz en reels de 35 s | Cubre 84-100 % del reel (prueba por reglas), gancho dicho en el primer segundo |
| Encuadre | Bandas negras en tomas 4:3 | Llena el 9:16; horizontales con fondo desenfocado |
| Videos del iPhone (HEVC) | Solo se oía el audio en el reproductor | Copia H.264 720p automática en segundo plano |
| .exe | Fallaba al crear borradores (`pymediainfo`) | Trae `pymediainfo`, `MediaInfo.dll` y `productos.json` |
| Repo | Carpeta suelta | Repo git con README en inglés/español y video de presentación hecho con HyperFrames |

## Cronología (más reciente primero)

| Fecha | Commit | Qué se hizo |
|---|---|---|
| 4 oct | `bb542e2` | Voz en off que cubre todo el reel, ganchos con fórmulas, respaldo de formato para glm |
| 3 oct | `a92f8e9` | (Daniel) `ReelStudio.spec` con `productos.json` e `imageio` |
| 3 oct | `a99a036` | Crítico, voz en off por defecto, formato Educativo, mínimo 35 s, encuadre 9:16 |
| 3 oct | `626e59c` | Catálogo de la landing y videos HEVC en el reproductor |
| 3 oct | `32f1233` | Etiquetar y anotar: tipo, producto, precio, notas y marcas; reels por producto |
| 3 oct | `917199e` | `pymediainfo` en el .exe y guion que no se desboca (esquema JSON) |
| 3 oct | `00c1b69` | (Daniel) README en inglés, versión ES y licencia MIT |
| 2 oct | `e673d1c` | Serie de reels por formato, un borrador por reel |
| 2 oct | `1b52c34` | Guion en streaming, sin razonamiento largo, respaldo por reglas |
| 2 oct | `0f7a032` | Análisis en paralelo y fotogramas repetidos |
| 2 oct | `6795565` | Repo inicial, `.gitignore` sin videos, README con motion de HyperFrames |

## Estado actual

- El código está completo y probado con el análisis y las etiquetas reales, usando un Ollama simulado y videos de prueba (no se pudo llamar a glm real desde las pruebas).
- La última serie real (3 oct) salió entera **por reglas**: glm no devolvía un guion válido. El arreglo (`bb542e2`) está en el código, pero falta probarlo con `Crear_exe.bat` + «Reescribir guiones». Ver [Pendientes](05-pendientes.md).
