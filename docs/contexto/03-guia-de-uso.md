# 3 · Guía de uso

*Actualizado: 4 oct 2026*

## Antes de empezar

- Ollama abierto con los modelos (visión, `nimble`, y un modelo de texto como `glm-5.3-flash:cloud`).
- Opcional: variable de entorno `OLLAMA_NUM_PARALLEL=4` en Windows para que `nimble` atienda varias llamadas a la vez.
- CapCut **cerrado** al crear los borradores.
- Después de cambiar el código: cerrar la app y correr `Crear_exe.bat`. El `.exe` no toma cambios del código hasta que se vuelve a empaquetar.

## El flujo

1. **Abrir** `dist\ReelStudio\ReelStudio.exe` y elegir la carpeta de videos.
2. **Etiquetar** (pestaña Etiquetar):
   - «Traer de la tienda» carga los 20 productos con su precio (ya vienen cargados la primera vez).
   - Seleccionar varios archivos con la casilla → tipo, producto y nota → **Aplicar**.
   - Clic en una miniatura abre el reproductor: tipo, producto, nota y **marcas** por segundo (pausa → escribe qué pasa → «Marcar aquí»). Las flechas pasan al archivo siguiente. Se guarda solo.
   - Los videos del iPhone se convierten solos para verse; la primera vez puede tardar.
3. **Analizar** (paso 1): «Analizar carpeta» o «Analizar archivos nuevos». Lo ya analizado se conserva.
4. **Escribir guiones** (paso 2): elegir formatos con los botones (Unboxing, Review, Educativo, Entregas, Así compras) y pulsar «Escribir guiones». El avance se ve en el paso 2 y en Registro.
5. **Revisar** (pestaña Guion):
   - Cada reel tiene su nota del crítico (verde ≥ 7,5 · dorado ≥ 5 · rojo) y sus problemas.
   - Editar gancho, clips, tiempos, pasos y narración. «Audio original» deja el sonido de un clip (alguien hablando).
   - Mirar «Voz en off: N palabras · cubre X %»; si está bajo, «Completar la voz en off».
   - «Revisar otra vez» tras editar. «Quitar este reel» para los descartados.
6. **Crear borradores** (paso 3): el campo de nombre es el prefijo; sale un borrador por reel.
7. **En CapCut**, por cada borrador:
   - Abrir el borrador (si CapCut estaba abierto, reiniciarlo).
   - Seleccionar todos los textos de la pista **voz** (clic en el primero, Shift + clic en el último) → **Texto a voz → Nandez → Generar**.
   - Revisar, ajustar y **exportar en 1080p, 30 fps**.

## Ajustes avanzados

| Ajuste | Valor por defecto | Qué hace |
|---|---|---|
| Seg. entre fotogramas | 3 | Cada cuánto se describe una toma |
| Mín. «usable» | 0,5 | Desde qué puntaje una toma cuenta como buena |
| Análisis simultáneos | 6 | Archivos y llamadas a Ollama a la vez |
| Máx. reels por formato | 2 | Tope de reels por formato (por producto en Unboxing/Review/Educativo) |
| Voz en off | Sí | Narración continua; el sonido original solo en clips marcados |
| Crítico | Sí | Revisión y corrección de cada guion |
| Saltar fotogramas repetidos | Sí | Tomas quietas reusan la descripción |

## Si algo falla

| Síntoma | Qué mirar |
|---|---|
| Todos los reels salen «por reglas» | Registro: si dice «reintento con un formato más simple» y luego falla, el modelo no está respondiendo bien; probar otro modelo de texto |
| `No module named …` al crear borradores | El `.exe` es viejo: correr `Crear_exe.bat` |
| Video sin imagen en el reproductor | Es HEVC: esperar la copia; si no aparece, revisar ffmpeg |
| El guion tarda mucho | glm piensa de más: usar `glm-5.3-flash:cloud` |
| Un reel queda corto | El crítico lo marca; grabar más tomas de ese tipo o producto, o bajar el mínimo «usable» |
