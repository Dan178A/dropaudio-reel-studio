# 4 · Decisiones y lecciones

*Actualizado: 4 oct 2026*

## Decisiones

| Tema | Decisión | Por qué |
|---|---|---|
| Velocidad del análisis | Hilos en paralelo (6), no agentes | El cuello era esperar a Ollama una llamada a la vez; con hilos bastó para ~5× |
| Fotogramas repetidos | Comparar una miniatura gris 24×24 (umbral 5) | En el material real: quieto ≈ 1-4, movimiento > 10. Ahorra ~13 %, menos de lo que se estimó (40-60 %) |
| Extraer fotogramas | Un ffmpeg por fotograma (como antes) | El "un solo ffmpeg por video" no era más rápido en clips cortos y usaba opciones de ffmpeg nuevas |
| Guion | Streaming + esquema JSON + respaldo de formato | El usuario veía el paso "colgado"; glm se desbocaba; los `:cloud` no aceptan todos los formatos |
| Serie de reels | Repartir **archivos**, no tramos | Garantiza que ningún reel repita material de otro |
| Producto | Unboxing/Review/Educativo uno por modelo | Se mezclaban audífonos de $13, $25 y $35 en el mismo video |
| Etiquetas | Se aplican al usarlas, no al analizar | Etiquetar después del análisis no obliga a reanalizar 5 horas |
| Precios | Solo de `productos.json` / catálogo | La IA no debe inventar precios ni modelos |
| Catálogo | Copiado de la landing (`fallbackData.ts`), AM02 a $18 según `CONTEXTO_DROPAUDIO.md` | Una sola fuente de verdad con la tienda |
| HEVC del iPhone | Copia H.264 720p solo para ver; CapCut usa el original | WebView2 no decodifica HEVC sin la extensión de Windows |
| Voz | Texto en la pista "voz" para Nandez en CapCut | No hay forma de generar la voz Nandez desde fuera de CapCut |
| Crítico | Medible primero, luego el modelo; la corrección solo si no empeora lo medible | Evita que el modelo "arregle" algo y lo deje peor |
| Mínimo de material | 35 s de tomas buenas por reel | Los reels de 12-19 s no generan engagement |

## Lecciones

- **Medir antes de prometer:** el ahorro por fotogramas repetidos fue 13 %, no 40-60 %. Lo que más rinde es el paralelo.
- **El .exe es una foto del código:** varios "no funciona" eran un `.exe` armado antes del arreglo. Siempre volver a correr `Crear_exe.bat`.
- **Un respaldo silencioso esconde fallas:** la serie del 3 oct salió entera por reglas y nadie lo notó hasta ver la voz pobre. Ahora el Registro lo dice y el modelo tiene cuatro intentos.
- **La voz tiene que tener presupuesto:** ~2,4 palabras por segundo de clip; si no, la voz dura la mitad del video.
- **El gancho se dice, no solo se lee:** primera frase de la voz en el segundo 0, con una fórmula concreta (precio, error común, curiosidad, comparación, POV).
- **Orden con sentido:** caja cerrada antes que abierta; los chips de pasos tienen que coincidir con lo que se ve.
- **En video hablado, la transcripción manda:** sin ella la IA corta frases. Pero una frase de Whisper muy larga no debe estirar un clip a 50 s (tope de 12 s).
- **Encuadre:** fotos y videos 4:3 dejan bandas negras si no se amplían.
- **Exportar en 1080p:** los primeros reels salieron en 480p desde CapCut.
- **Privacidad:** nunca nombres ni teléfonos de clientes en textos o narración.
- **Git en la VM:** al hacer commit desde la VM quedan `.git/HEAD.lock` y temporales si no hay permiso de borrar; hay que limpiarlos o git falla.
