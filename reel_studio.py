"""
Reel Studio · DropAudio CCS
Interfaz para armar reels en CapCut a partir de una carpeta de videos y fotos.

  1. Analizar : Whisper transcribe lo que se dice; un modelo con visión describe un fotograma cada N segundos
                y Jev (nimble) decide si la toma sirve, qué tipo es y qué tan atractiva es.   -> analisis.json
  2. Guion    : un modelo de texto (glm, qwen, deepseek...) arma el reel con el guion "Así compras" (5 pasos),
                sin cortar frases, y escribe la narración.                                     -> seleccion.json
  3. CapCut   : crea el borrador 1080x1920 con clips, textos de marca, música y la narración como textos
                en la pista "voz": en CapCut los seleccionas todos -> Texto a voz -> Nandez.

Instalar (una vez):  pip install faster-whisper pillow pillow-heif numpy
                     pip install -e C:\\Users\\DAN_PC\\Documents\\GitHub\\pyCapCut
Ejecutar:            python reel_studio.py
"""
import json, os, sys, queue, re, subprocess, threading, time, urllib.request, urllib.error, base64, tempfile

OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
AQUI = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".avi")
FOTO_EXT = (".jpg", ".jpeg", ".png", ".heic", ".webp")
CAPCUT_DRAFTS = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
CREAR = 0x08000000 if os.name == "nt" else 0  # sin ventanas de consola para ffmpeg en Windows

TIPOS = {
    "producto_detalle": "Primer plano de audífonos, cables, DAC, intercom o estuche",
    "unboxing": "Abriendo una caja o sacando el producto del empaque",
    "prueba_sonido": "Alguien conectando, probándose o escuchando los audífonos",
    "entrega_moto": "La moto, el trayecto, el baúl o el momento de entregar al cliente",
    "pago": "El cliente pagando con el teléfono o contando dinero",
    "persona": "Una persona hablando a cámara",
    "otro": "Nada de lo anterior o no se distingue",
}
TIPOS_CORTO = {"producto_detalle": "producto de cerca", "unboxing": "unboxing", "prueba_sonido": "prueba de sonido",
               "entrega_moto": "entrega en moto", "pago": "pago", "persona": "persona a cámara", "otro": "otro"}
PASOS = {"1": "Elige tu modelo", "2": "Escríbenos", "3": "Vamos a ti", "4": "Lo pruebas ahí mismo",
         "5": "Y solo entonces, pagas"}
CTA = "Revisas. Escuchas. Luego pagas."

GUION = """Eres editor de reels de DropAudio CCS (audífonos KZ originales en Venezuela; entrega en moto en Caracas,
Guarenas y Guatire; el cliente revisa y prueba ANTES de pagar; 7 días de garantía; precios solo en $).
Arma UN reel vertical de 30 a 40 segundos de formato «{titulo}» con esta estructura:
  {estructura}
Si no hay tomas para un paso, sáltalo. Usa SOLO los archivos del material.
Reglas:
- El gancho es una frase corta (máx. 7 palabras) que detiene el scroll, en la línea de: "{gancho_ej}".
  Si hay una toma de persona hablando a cámara, úsala para el gancho.
- NUNCA cortes una frase: si un clip tiene habla, 'desde' y 'hasta' deben caer fuera de las frases
  (usa los tiempos de 'habla'). Incluye completas las frases útiles.
- Clips de 2 a 12 s. Fotos: 'desde' 0 y 'hasta' 3 a 5. No repitas el mismo tramo.
- Narración: frases cortas (máx. 12 palabras), tono cercano venezolano, solo sobre clips SIN habla.
  'en' es el segundo dentro del clip. No nombres clientes ni des teléfonos de clientes.
- Prefiere tomas con usable (u) alto e interés (i) alto.
- Productos y precios: usa SOLO los que trae el material («producto: … ($…)»). No inventes modelos ni precios;
  si un archivo no dice producto, no le pongas nombre ni precio.
Responde SOLO con JSON:
{{"gancho": "...", "promesa": "frase corta bajo el gancho",
 "clips": [{{"archivo": "...", "desde": 0.0, "hasta": 0.0, "paso": "gancho|1|2|3|4|5|cta", "motivo": "..."}}],
 "narracion": [{{"clip": 0, "en": 0.3, "texto": "..."}}]}}
"""

# Formatos de la serie. «nucleo»: tipos de toma que definen el formato; «apoyo»: los que lo completan.
# «reglas»: qué tipos buscar en cada paso cuando no hay modelo de texto (o si falla).
FORMATOS = {
    "unboxing": {
        "titulo": "Unboxing", "kicker": "UNBOXING", "por_producto": True, "gancho_ej": "¿Original o réplica? Ábrelo conmigo",
        "gancho_prod": "{p}: ¿original o réplica?",
        "promesa": "Sellado de fábrica ↓",
        "pasos": {"1": "Sellado de fábrica", "2": "Lo abrimos", "3": "Qué trae", "4": "De cerca", "5": "Precio"},
        "estructura": "gancho -> 1 caja sellada -> 2 abriendo -> 3 qué trae (accesorios, cables) -> 4 detalle "
                      "del producto -> 5 precio y garantía -> cta",
        "nucleo": ["unboxing"], "apoyo": ["producto_detalle", "persona"],
        "reglas": [("gancho", ["persona", "unboxing"]), ("1", ["unboxing", "producto_detalle"]), ("2", ["unboxing"]),
                   ("3", ["unboxing", "producto_detalle"]), ("4", ["producto_detalle"]),
                   ("cta", ["producto_detalle", "persona"])]},
    "review": {
        "titulo": "Review", "kicker": "REVIEW", "por_producto": True, "gancho_ej": "¿Unos KZ económicos suenan bien?",
        "gancho_prod": "¿Los {p} suenan bien?",
        "promesa": "Te lo pruebo aquí ↓",
        "pasos": {"1": "Qué es", "2": "Lo conectamos", "3": "Cómo suena", "4": "Detalles", "5": "¿Vale la pena?"},
        "estructura": "gancho -> 1 qué es y para quién -> 2 conectarlo -> 3 prueba de sonido y reacción -> "
                      "4 detalles de construcción -> 5 veredicto con precio -> cta",
        "nucleo": ["prueba_sonido"], "apoyo": ["producto_detalle", "persona", "unboxing"],
        "reglas": [("gancho", ["persona", "prueba_sonido"]), ("1", ["producto_detalle", "persona"]),
                   ("2", ["prueba_sonido", "unboxing"]), ("3", ["prueba_sonido"]), ("4", ["producto_detalle"]),
                   ("5", ["persona", "prueba_sonido"]), ("cta", ["producto_detalle", "persona"])]},
    "entregas": {
        "titulo": "Entregas", "kicker": "ENTREGA", "gancho_ej": "Así llegan tus KZ en Caracas",
        "promesa": "En moto, hasta tu mano ↓",
        "pasos": {"1": "Sale el pedido", "2": "En camino", "3": "Llegamos", "4": "Lo prueba", "5": "Paga después"},
        "estructura": "gancho -> 1 pedido listo -> 2 POV en moto -> 3 llegada -> 4 el cliente prueba -> "
                      "5 paga después de probar -> cta",
        "nucleo": ["entrega_moto", "pago"], "apoyo": ["prueba_sonido", "persona", "producto_detalle"],
        "reglas": [("gancho", ["entrega_moto", "persona"]), ("1", ["producto_detalle", "unboxing"]),
                   ("2", ["entrega_moto"]), ("3", ["entrega_moto"]), ("4", ["prueba_sonido"]), ("5", ["pago"]),
                   ("cta", ["pago", "producto_detalle", "persona"])]},
    "asi_compras": {
        "titulo": "Así compras", "kicker": "PASO", "gancho_ej": "¿Pagas antes y rezas que llegue?",
        "promesa": "Así compras en DropAudio ↓", "pasos": PASOS,
        "estructura": "gancho -> paso 1 Elige tu modelo -> 2 Escríbenos -> 3 Vamos a ti (moto) -> "
                      "4 Lo pruebas ahí mismo -> 5 Y solo entonces, pagas -> cta",
        "nucleo": ["entrega_moto", "prueba_sonido", "pago"], "apoyo": ["producto_detalle", "unboxing", "persona"],
        "reglas": [("gancho", ["persona"]), ("1", ["producto_detalle", "unboxing"]), ("3", ["entrega_moto"]),
                   ("4", ["prueba_sonido", "unboxing"]), ("5", ["pago"]),
                   ("cta", ["producto_detalle", "persona", "otro"])]},
}
ORDEN_FORMATOS = ["unboxing", "review", "entregas", "asi_compras"]


# ---------------------------------------------------------------- Ollama
def ollama(path, body=None, timeout=600):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(OLLAMA + path, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def modelos():
    """[(nombre, ve_imagenes)]"""
    out = []
    for m in ollama("/api/tags")["models"]:
        try:
            caps = ollama("/api/show", {"model": m["name"]}).get("capabilities", [])
        except Exception:
            caps = []
        out.append((m["name"], "vision" in caps))
    return out


def describir(img, modelo, pista=""):
    with open(img, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    p = ("Describe en 2 frases, en español, qué se ve en esta imagen de una tienda de audífonos que entrega en moto: "
         "objetos, acciones, personas, y si está borrosa, oscura o movida." + (f" Dato del dueño: {pista}." if pista else ""))
    return ollama("/api/generate", {"model": modelo, "prompt": p, "images": [b64], "stream": False})["response"].strip()


def decidir(desc, habla, modelo):
    q = {
        "usable": {"type": "noul", "instructions": "¿La toma se ve nítida, con buena luz y estable, apta para un reel?"},
        "tipo": {"type": "choice", "instructions": "¿Qué tipo de toma es?", "criteria": TIPOS},
        "interes": {"type": "score", "instructions": "¿Qué tan atractiva es para detener el scroll en Instagram?",
                    "criteria": ["Relleno", "Normal", "Muy atractiva"]},
    }
    a = ollama("/v1/systemone", {"model": modelo, "state": {"toma": desc, "se_dice": habla or "(nada)"},
                                 "questions": q})["answers"]
    return {"usable": round(a["usable"]["noul"], 3), "tipo": a["tipo"]["choice"],
            "interes": round(a["interes"]["score"] / 2, 3)}  # score viene en índice 0..2


def escribir_guion(material, modelo, log=lambda *a: None, limite=600, formato="asi_compras"):
    """Pide el guion en streaming: se ve el avance (pensando / escribiendo) y nunca se queda colgado sin aviso.
    Desactiva el «razonamiento» largo de los modelos que piensan (think: false) si el modelo lo admite."""
    body = {"model": modelo, "stream": True, "format": ESQUEMA_GUION, "think": False,
            "options": {"num_ctx": 16384, "num_predict": 3000, "temperature": 0.5},
            "messages": [{"role": "system", "content": prompt_formato(formato)}, {"role": "user", "content": material}]}
    inicio, ultimo, txt, pensado = time.time(), 0, [], 0
    for intento in (1, 2):
        try:
            req = urllib.request.Request(OLLAMA + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:  # 180 s sin recibir nada = colgado
                for linea in r:
                    if not linea.strip():
                        continue
                    trozo = json.loads(linea)
                    if trozo.get("error"):
                        raise RuntimeError(trozo["error"])
                    msg = trozo.get("message", {})
                    pensado += len(msg.get("thinking") or "")
                    txt.append(msg.get("content") or "")
                    ahora = time.time()
                    if ahora - inicio > limite:
                        raise TimeoutError(f"{modelo} tardó más de {limite // 60} min")
                    if sum(map(len, txt)) > 15000:  # un guion real ocupa 2-5 mil caracteres: se quedó en bucle
                        raise RuntimeError("la respuesta se desbocó (más de 15 000 caracteres)")
                    if ahora - ultimo > 1:
                        ultimo, n = ahora, sum(map(len, txt))
                        seg = int(ahora - inicio)
                        log("estado", f"{modelo} escribiendo el guion… {n} caracteres · {seg} s" if n else
                                      f"{modelo} pensando… {pensado} caracteres · {seg} s")
                    if trozo.get("done"):
                        break
            break
        except urllib.error.HTTPError as e:
            detalle = e.read().decode(errors="ignore")
            if intento == 1 and "think" in detalle.lower():  # el modelo no acepta think:false → sin esa opción
                body.pop("think"); txt.clear(); continue
            raise RuntimeError(f"Ollama respondió {e.code}: {detalle[:200]}")
    return leer_json("".join(txt))


def leer_json(txt):
    """JSON del modelo, tolerando texto alrededor y comas sobrantes."""
    txt = txt[txt.find("{"): txt.rfind("}") + 1]
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", txt))


# Esquema que Ollama impone a la salida: evita JSON roto y respuestas que no terminan
ESQUEMA_GUION = {
    "type": "object", "required": ["gancho", "promesa", "clips", "narracion"],
    "properties": {
        "gancho": {"type": "string"}, "promesa": {"type": "string"},
        "clips": {"type": "array", "maxItems": 14, "items": {
            "type": "object", "required": ["archivo", "desde", "hasta", "paso"],
            "properties": {"archivo": {"type": "string"}, "desde": {"type": "number"}, "hasta": {"type": "number"},
                           "paso": {"type": "string", "enum": ["gancho", "1", "2", "3", "4", "5", "cta"]},
                           "motivo": {"type": "string"}}}},
        "narracion": {"type": "array", "maxItems": 10, "items": {
            "type": "object", "required": ["clip", "en", "texto"],
            "properties": {"clip": {"type": "integer"}, "en": {"type": "number"}, "texto": {"type": "string"}}}}}}


# ---------------------------------------------------------------- medios
def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, creationflags=CREAR, **kw)


def duracion(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], text=True)
    return float(out.stdout.strip())


def fotograma(path, t, destino):
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
         "-vf", "scale=640:-2", destino], check=True)
    return destino


def foto_compatible(path):
    """HEIC -> JPG (CapCut y el modelo de visión no siempre leen HEIC)."""
    if not path.lower().endswith(".heic"):
        return path
    from PIL import Image
    import pillow_heif
    pillow_heif.register_heif_opener()
    dest = os.path.join(os.path.dirname(path), "_jpg", os.path.splitext(os.path.basename(path))[0] + ".jpg")
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        Image.open(path).convert("RGB").save(dest, quality=92)
    return dest


_whisper = {}
def transcribir(path, tam):
    if tam == "(ninguno)":
        return []
    import numpy as np
    raw = run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]).stdout
    if len(raw) < 16000:
        return []
    if tam not in _whisper:
        from faster_whisper import WhisperModel
        _whisper[tam] = WhisperModel(tam, device="cpu", compute_type="int8")
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    segs, _ = _whisper[tam].transcribe(x, language="es", vad_filter=True)
    return [{"ini": round(s.start, 2), "fin": round(s.end, 2), "texto": s.text.strip()} for s in segs]


# ---------------------------------------------------------------- 1. analizar
def huella(img):
    """Miniatura gris 24x24 para comparar fotogramas sin llamar a ningún modelo."""
    from PIL import Image
    with Image.open(img) as im:
        return list(im.convert("L").resize((24, 24)).getdata())


def parecidos(a, b, umbral):
    return a is not None and b is not None and sum(abs(x - y) for x, y in zip(a, b)) / len(a) < umbral


# ---------------------------------------------------------------- etiquetas del dueño
def leer_etiquetas(carpeta):
    """etiquetas.json: {archivo: {"tipo": "...", "producto": "...", "nota": "..."}} puesto a mano antes o después
    de analizar. El tipo manda sobre lo que decida Jev y el producto evita mezclar modelos y precios."""
    p = os.path.join(carpeta, "etiquetas.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def guardar_etiquetas(carpeta, etiq):
    etiq = {k: {c: v for c, v in e.items() if v not in ("", None, [])} for k, e in etiq.items()}
    etiq = {k: e for k, e in etiq.items() if e}
    tmp = os.path.join(carpeta, "etiquetas.json.tmp")
    json.dump(etiq, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(carpeta, "etiquetas.json"))
    return etiq


def precio_de(producto, catalogo):
    for p in catalogo or []:
        if p.get("nombre", "").strip().lower() == (producto or "").strip().lower():
            return p.get("precio")
    return None


def pista_de(e, catalogo):
    """Texto corto para la visión y el guion: «KZ Castor ($25) · entrega en moto · nota»."""
    if not e:
        return ""
    partes = []
    if e.get("producto"):
        pr = precio_de(e["producto"], catalogo)
        partes.append(f"el producto es {e['producto']}" + (f" (${pr:g})" if isinstance(pr, (int, float)) else ""))
    if e.get("tipo"):
        partes.append(f"es una toma de {TIPOS_CORTO.get(e['tipo'], e['tipo'])}")
    if e.get("nota"):
        partes.append(e["nota"])
    return "; ".join(partes)


def aplicar_etiquetas(datos, etiq, catalogo=None):
    """Copia del análisis con lo que dijo el dueño: tipo fijo en todas las tomas y producto/precio por archivo.
    Se aplica al usarlo, así una etiqueta puesta después del análisis también vale sin reanalizar."""
    out = {}
    for k, d in datos.items():
        e = etiq.get(k) or {}
        if not e:
            out[k] = d; continue
        d = dict(d)
        if e.get("tipo") in TIPOS:
            d["tomas"] = [dict(t, tipo=e["tipo"], tipo_fijo=True) for t in d["tomas"]]
        if e.get("producto"):
            d["producto"] = e["producto"].strip()
            d["precio"] = precio_de(d["producto"], catalogo)
        if e.get("nota"):
            d["nota"] = e["nota"]
        if e.get("marcas"):
            d["marcas"] = e["marcas"]
        out[k] = d
    return out


def analizar(carpeta, cfg, log, rehacer=False):
    """Analiza en paralelo: varios archivos a la vez, Whisper en su propio turno y un solo ffmpeg por video.
    Con «saltar_repetidos», un fotograma casi igual al anterior reutiliza la descripción en vez de llamar a la visión."""
    import shutil
    from concurrent.futures import ThreadPoolExecutor, as_completed
    salida = os.path.join(carpeta, "analisis.json")
    datos = {} if rehacer or not os.path.exists(salida) else json.load(open(salida, encoding="utf-8"))
    archivos = sorted(f for f in os.listdir(carpeta) if f.lower().endswith(VIDEO_EXT + FOTO_EXT))
    for nombre in archivos:
        if nombre in datos:
            log("fila", datos[nombre])
    pendientes = [f for f in archivos if f not in datos]
    n = max(1, int(cfg.get("simultaneos", 6)))
    saltar = bool(cfg.get("saltar_repetidos", True))
    umbral = float(cfg.get("umbral_repetido", 5))  # diferencia media de gris (0-255): quieto ≈ 1-4, con movimiento > 10
    guardar_lock, whisper_lock = threading.Lock(), threading.Lock()
    hechos, ahorradas = [0], [0]
    log("progreso", (0, len(pendientes)))
    if not pendientes:
        return datos
    log("estado", f"Analizando {len(pendientes)} archivos nuevos, {n} a la vez"
                  + (f" ({len(archivos) - len(pendientes)} ya estaban)" if len(pendientes) < len(archivos) else ""))
    llamadas = ThreadPoolExecutor(n)  # tope de llamadas simultáneas a Ollama (visión + Jev)
    etiq, catalogo = leer_etiquetas(carpeta), cfg.get("catalogo", [])

    def ventana(img, desc_previa, dicho, decision_previa, pista="", tipo_fijo=None):
        desc = desc_previa if desc_previa is not None else describir(img, cfg["vision"], pista)
        dec = decision_previa if decision_previa is not None else decidir(desc, dicho, cfg["jev"])
        if tipo_fijo:
            dec = dict(dec, tipo=tipo_fijo)
        return desc, dec

    def uno(nombre):
        path = os.path.join(carpeta, nombre)
        e = etiq.get(nombre) or {}
        pista, tipo_fijo = pista_de(e, catalogo), (e.get("tipo") if e.get("tipo") in TIPOS else None)
        tmp = tempfile.mkdtemp(prefix="reel_studio_")
        try:
            if nombre.lower().endswith(FOTO_EXT):
                foto, dur, habla, ventanas = True, 4.0, [], [(0.0, 4.0)]
                imgs = [foto_compatible(path)]
            else:
                foto, dur = False, duracion(path)
                with whisper_lock:  # un solo Whisper a la vez (CPU); mientras, los demás siguen con la visión
                    habla = transcribir(path, cfg["whisper"])
                ventanas = [(round(t, 2), round(min(cfg["paso"], dur - t), 2))
                            for t in frange(0, dur, cfg["paso"]) if dur - t >= 1.0]
                imgs = [fotograma(path, ini + d / 2, os.path.join(tmp, f"f_{k:04d}.jpg")) for k, (ini, d) in enumerate(ventanas)]
            # decidir qué fotogramas necesitan la visión y cuáles repiten al anterior
            plan, ultima_huella, ref = [], None, None
            for k, ((ini, d), img) in enumerate(zip(ventanas, imgs)):
                dicho = " ".join(h["texto"] for h in habla if h["fin"] > ini and h["ini"] < ini + d)
                h = huella(img) if saltar else None
                repetido = saltar and ref is not None and parecidos(h, ultima_huella, umbral)
                if not repetido:
                    ref, ultima_huella = k, h
                plan.append((ini, d, img, dicho, ref if repetido else None))
            # primero las tomas nuevas (en paralelo), luego las repetidas copian la descripción
            def pista_v(ini, d):  # nota general + marcas del dueño que caen en esta ventana
                ms = [m["texto"] for m in e.get("marcas", []) if ini - 1 <= m["t"] <= ini + d + 1]
                return "; ".join([x for x in [pista] + ms if x])
            futuros = {k: llamadas.submit(ventana, img, None, dicho, None, pista_v(ini, d), tipo_fijo)
                       for k, (ini, d, img, dicho, rep) in enumerate(plan) if rep is None}
            res = {k: f.result() for k, f in futuros.items()}
            for k, (ini, d, img, dicho, rep) in enumerate(plan):
                if rep is not None:
                    desc, dec = res[rep]
                    mismo_dicho = dicho == plan[rep][3]
                    res[k] = (desc, dec) if mismo_dicho else llamadas.submit(ventana, img, desc, dicho, None, pista_v(ini, d), tipo_fijo).result()
                    with guardar_lock:
                        ahorradas[0] += 1
            tomas = []
            for k, (ini, d, img, dicho, rep) in enumerate(plan):
                desc, dec = res[k]
                tomas.append({"inicio": ini, "dur": d, "descripcion": desc, **dec,
                              **({"repetida": True} if rep is not None else {})})
            return {"archivo": nombre, "foto": foto, "dur": round(dur, 2), "habla": habla, "tomas": tomas,
                    "modelos": {k: cfg[k] for k in ("vision", "jev", "whisper")}}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    try:
        with ThreadPoolExecutor(n) as archivos_pool:
            futuros = {archivos_pool.submit(uno, nombre): nombre for nombre in pendientes}
            for f in as_completed(futuros):
                nombre = futuros[f]
                try:
                    fila = f.result()
                    with guardar_lock:
                        datos[nombre] = fila
                        tmpjson = salida + ".tmp"
                        json.dump(datos, open(tmpjson, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                        os.replace(tmpjson, salida)  # guarda en cada archivo, sin dejarlo a medias
                    log("fila", fila)
                except Exception as e:
                    log("error", f"{nombre}: {e}")
                hechos[0] += 1
                log("progreso", (hechos[0], len(pendientes)))
                log("estado", f"Listo {nombre} ({hechos[0]}/{len(pendientes)})")
    finally:
        llamadas.shutdown(wait=False)
    if ahorradas[0]:
        log("estado", f"Se saltaron {ahorradas[0]} fotogramas repetidos (sin llamar a la visión)")
    return datos

def frange(a, b, s):
    while a < b:
        yield a
        a += s


# ---------------------------------------------------------------- 2. guion
def material_para_llm(datos, minimo, por_archivo=4, largo=170):
    """Resumen compacto para el modelo de texto: las mejores tomas de cada archivo, descripciones cortas,
    sin repetir tomas quietas, y lo que se dice. Menos texto = guion más rápido y más enfocado."""
    lineas = []
    for d in datos.values():
        buenas = [t for t in d["tomas"] if t["usable"] >= minimo and not t.get("repetida")]
        if not buenas:
            continue
        buenas = sorted(sorted(buenas, key=lambda t: t["usable"] * t["interes"], reverse=True)[:por_archivo],
                        key=lambda t: t["inicio"])
        prod = ""
        if d.get("producto"):
            prod = f" · producto: {d['producto']}" + (f" (${d['precio']:g})" if isinstance(d.get("precio"), (int, float)) else "")
        lineas.append(f"\n## {d['archivo']} ({'foto' if d['foto'] else 'video'}, {d['dur']} s){prod}"
                      + (f" · nota del dueño: {d['nota']}" if d.get("nota") else ""))
        for t in buenas:
            desc = " ".join(t["descripcion"].split())
            desc = desc if len(desc) <= largo else desc[:largo].rsplit(" ", 1)[0] + "…"
            lineas.append(f"- {t['inicio']}-{t['inicio'] + t['dur']:.1f}s {t['tipo']} u={t['usable']:.2f} "
                          f"i={t['interes']:.2f}: {desc}")
        for h in d["habla"]:
            lineas.append(f"  habla {h['ini']}-{h['fin']}s: \"{h['texto']}\"")
        for m in d.get("marcas", []):
            lineas.append(f"  marca del dueño en {m['t']}s: {m['texto']}")
    return "Material disponible:" + "\n".join(lineas)


def sin_cortar_frases(d, desde, hasta, maximo=12.0):
    """Si un corte cae dentro de una frase, lo mueve al borde de la frase. Primero intenta incluir la frase
    completa; si eso deja el clip más largo que «maximo», la deja fuera (corta antes o después de ella)."""
    a, b = desde, hasta
    for h in d["habla"]:
        if h["ini"] < a < h["fin"]:
            a = h["ini"]
        if h["ini"] < b < h["fin"]:
            b = h["fin"]
    if b - a > maximo and b - a > (hasta - desde) + 0.5:
        a2, b2 = desde, hasta
        for h in d["habla"]:
            if h["ini"] < a2 < h["fin"]:
                a2 = h["fin"]
            if h["ini"] < b2 < h["fin"]:
                b2 = h["ini"]
        # si una sola «frase» de Whisper ocupa todo el tramo (monólogo largo), se respeta el tramo pedido
        a, b = (a2, b2) if b2 - a2 >= 1.5 else (desde, hasta)
    return max(0.0, a), min(d["dur"] - 0.05, b)


def validar(sel, datos, permitidos=None):
    clips = []
    for c in sel.get("clips", []):
        d = datos.get(c.get("archivo"))
        if permitidos is not None and c.get("archivo") not in permitidos:
            continue
        if not d:
            continue
        if d["foto"]:
            desde, hasta = 0.0, min(5.0, max(3.0, float(c.get("hasta", 4)) - float(c.get("desde", 0))))
        else:
            desde, hasta = sin_cortar_frases(d, float(c.get("desde", 0)), float(c.get("hasta", d["dur"])))
        if hasta - desde < 1.0:
            continue
        clips.append({"archivo": d["archivo"], "foto": d["foto"], "desde": round(desde, 2),
                      "segundos": round(hasta - desde, 2), "paso": str(c.get("paso", "")), "motivo": c.get("motivo", "")})
    sel["clips"] = clips
    sel["narracion"] = [n for n in sel.get("narracion", []) if 0 <= int(n.get("clip", -1)) < len(clips) and n.get("texto")]
    f = FORMATOS.get(sel.get("formato"), FORMATOS["asi_compras"])
    if not sel.get("gancho"):
        sel["gancho"] = f["gancho_ej"]
    sel.setdefault("promesa", f["promesa"])
    return sel


def prompt_formato(formato):
    f = FORMATOS.get(formato, FORMATOS["asi_compras"])
    return GUION.format(titulo=f["titulo"], estructura=f["estructura"], gancho_ej=f["gancho_ej"])


def guion_por_reglas(datos, minimo, formato="asi_compras"):
    """Respaldo sin modelo de texto: la mejor toma para cada paso del formato, sin repetir tramos.
    Junta tomas buenas seguidas del mismo archivo (hasta ~6 s) para que el reel no quede demasiado corto."""
    tomas = sorted(((d, t) for d in datos.values() for t in d["tomas"] if t["usable"] >= minimo),
                   key=lambda x: x[1]["usable"] * x[1]["interes"], reverse=True)
    usados, clips = set(), []
    for paso, tipos in FORMATOS.get(formato, FORMATOS["asi_compras"])["reglas"]:
        for d, t in tomas:
            if t["tipo"] in tipos and (d["archivo"], t["inicio"]) not in usados:
                usados.add((d["archivo"], t["inicio"]))
                hasta = t["inicio"] + t["dur"]
                for s in sorted(d["tomas"], key=lambda x: x["inicio"]):  # alargar con las tomas buenas siguientes
                    if s["inicio"] >= hasta - 0.01 and s["inicio"] < hasta + 0.01 and s["usable"] >= minimo \
                            and hasta - t["inicio"] < 6 and (d["archivo"], s["inicio"]) not in usados:
                        usados.add((d["archivo"], s["inicio"])); hasta = s["inicio"] + s["dur"]
                clips.append({"archivo": d["archivo"], "desde": t["inicio"], "hasta": hasta,
                              "paso": paso, "motivo": f"{TIPOS.get(t['tipo'], t['tipo'])} (reglas)"})
                break
    return {"clips": clips, "narracion": []}


def planear_serie(datos, minimo, formatos, max_por=2):
    """Reparte los ARCHIVOS entre varios reels: cada archivo va a un solo reel (no se repite material).
    Cada archivo cuenta como el tipo de toma que más pesa en él (o el que le puso el dueño).
    Unboxing y Review son de UN producto: no mezclan modelos ni precios. Devuelve (planes, avisos)."""
    info = []
    for d in datos.values():
        buenas = [t for t in d["tomas"] if t["usable"] >= minimo]
        if not buenas:
            continue
        peso = {}
        for t in buenas:
            peso[t["tipo"]] = peso.get(t["tipo"], 0) + t["usable"] * (0.5 + t["interes"]) * t["dur"]
        tipo = max(peso, key=peso.get)
        info.append({"archivo": d["archivo"], "tipo": tipo, "peso": peso[tipo], "producto": d.get("producto"),
                     "seg": sum(t["dur"] for t in buenas)})
    info.sort(key=lambda x: x["peso"], reverse=True)
    usados, planes, avisos, cuenta = set(), [], [], {}

    def armar_plan(fk, f, nucleo, apoyo, producto):
        elegidos, seg = [], 0.0
        for x in nucleo:  # el corazón del reel
            if seg >= 20 or len(elegidos) >= 5:
                break
            elegidos.append(x); seg += x["seg"]
        for x in apoyo:  # lo completa hasta tener material de sobra
            if seg >= 50 or len(elegidos) >= 9:
                break
            elegidos.append(x); seg += x["seg"]
        if seg < 20:
            return None, seg
        usados.update(x["archivo"] for x in elegidos)
        cuenta[fk] = cuenta.get(fk, 0) + 1
        return {"formato": fk, "n": cuenta[fk], "producto": producto, "archivos": [x["archivo"] for x in elegidos],
                "segundos_material": round(seg, 1)}, seg

    for ronda in range(max_por):
        for fk in formatos:
            f = FORMATOS.get(fk)
            if not f:
                continue
            libres = [x for x in info if x["archivo"] not in usados]
            nucleo = [x for x in libres if x["tipo"] in f["nucleo"]]
            if not nucleo:
                if ronda == 0:
                    avisos.append(f"{f['titulo']}: no hay tomas de {' / '.join(TIPOS_CORTO[t] for t in f['nucleo'])}. "
                                  "Graba ese tipo de toma o etiqueta un archivo con ese tipo.")
                continue
            if f.get("por_producto"):
                # un reel por producto; los archivos sin producto se juntan solo entre ellos
                for prod in dict.fromkeys(x["producto"] for x in nucleo):
                    nuc = [x for x in nucleo if x["producto"] == prod and x["archivo"] not in usados]
                    apo = [x for x in libres if x["tipo"] in f["apoyo"] and x["producto"] == prod
                           and x["archivo"] not in usados and x not in nuc]
                    plan, seg = armar_plan(fk, f, nuc, apo, prod)
                    if plan:
                        planes.append(plan)
                    elif ronda == 0:
                        avisos.append(f"{f['titulo']} {prod or '(sin producto)'}: solo hay {seg:.0f} s de tomas "
                                      "buenas; hace falta más material de ese modelo.")
            else:
                apo = [x for x in libres if x["tipo"] in f["apoyo"]]
                plan, seg = armar_plan(fk, f, nucleo, apo, None)
                if plan:
                    planes.append(plan)
                elif ronda == 0:
                    avisos.append(f"{f['titulo']}: solo hay {seg:.0f} s de tomas buenas; hace falta más material.")
    return planes, avisos


def hacer_serie(carpeta, cfg, log):
    """Paso 2 en modo serie: varios reels separados por formato, cada uno con su guion y su material."""
    from concurrent.futures import ThreadPoolExecutor
    datos = json.load(open(os.path.join(carpeta, "analisis.json"), encoding="utf-8"))
    datos = aplicar_etiquetas(datos, leer_etiquetas(carpeta), cfg.get("catalogo", []))
    formatos = [f for f in cfg.get("formatos", ORDEN_FORMATOS) if f in FORMATOS] or ORDEN_FORMATOS
    planes, avisos = planear_serie(datos, cfg["minimo"], formatos, int(cfg.get("max_por_formato", 2)))
    for a in avisos:
        log("error", a)
    if not planes:
        raise RuntimeError("No alcanza el material para ningún reel. Revisa el mínimo «usable» o analiza más tomas.")
    prefijo = (cfg.get("nombre") or "reel").strip() or "reel"
    def titulo_de(p):
        return f"{FORMATOS[p['formato']]['titulo']} · {p['producto']}" if p.get("producto") \
            else f"{FORMATOS[p['formato']]['titulo']} {p['n']}"
    log("estado", f"Escribiendo {len(planes)} reels: " + ", ".join(titulo_de(p) for p in planes))
    log("progreso", (0, len(planes)))
    hechos = [0]; lock = threading.Lock()

    def uno(plan):
        sub = {a: datos[a] for a in plan["archivos"]}
        titulo = titulo_de(plan)
        if cfg["escritor"] == "(reglas, sin IA)":
            sel = guion_por_reglas(sub, cfg["minimo"], plan["formato"])
        else:
            try:
                cab = ""
                if plan.get("producto"):
                    pr = precio_de(plan["producto"], cfg.get("catalogo", []))
                    cab = (f"Este reel es SOLO del {plan['producto']}"
                           + (f" (precio ${pr:g})" if isinstance(pr, (int, float)) else "") + ". No nombres otros modelos.\n")
                sel = escribir_guion(cab + material_para_llm(sub, cfg["minimo"]), cfg["escritor"],
                                     lambda t, x: log(t, f"{titulo}: {x}"), formato=plan["formato"])
            except Exception as e:
                log("error", f"{titulo}: el modelo falló ({e}). Uso reglas; puedes editarlo.")
                sel = guion_por_reglas(sub, cfg["minimo"], plan["formato"])
        sel["formato"], sel["titulo"], sel["producto"] = plan["formato"], titulo, plan.get("producto")
        slug = re.sub(r"[^a-z0-9]+", "_", (plan.get("producto") or "").lower()).strip("_")
        sel["nombre"] = f"{prefijo}_{plan['formato']}_{slug + '_' if slug else ''}{plan['n']:02d}"
        prod, f = plan.get("producto"), FORMATOS[plan["formato"]]
        if prod and not sel.get("gancho") and f.get("gancho_prod"):  # reglas: gancho y promesa con el modelo
            sel["gancho"] = f["gancho_prod"].format(p=prod)
            pr = precio_de(prod, cfg.get("catalogo", []))
            sel.setdefault("promesa", f"{prod} · ${pr:g} ↓" if isinstance(pr, (int, float)) else f["promesa"])
        sel = validar(sel, datos, set(plan["archivos"]))
        if not sel["clips"]:  # el modelo devolvió algo inservible: reglas
            sel.update(validar(dict(guion_por_reglas(sub, cfg["minimo"], plan["formato"]), formato=plan["formato"]),
                               datos, set(plan["archivos"])))
        with lock:
            hechos[0] += 1
        log("progreso", (hechos[0], len(planes)))
        return sel

    with ThreadPoolExecutor(min(3, len(planes))) as ex:
        videos = list(ex.map(uno, planes))
    videos = [v for v in videos if v["clips"]]
    for v in videos:
        dur = sum(c["segundos"] for c in v["clips"])
        if dur < 20:
            avisos.append(f"{v['titulo']}: quedó de {dur:.0f} s; le falta material (revísalo o quítalo).")
            log("error", avisos[-1])
    serie = {"videos": videos, "avisos": avisos}
    guardar_serie(carpeta, serie)
    return serie


def guardar_serie(carpeta, serie):
    tmp = os.path.join(carpeta, "serie.json.tmp")
    json.dump(serie, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(carpeta, "serie.json"))


def leer_serie(carpeta, nombre_defecto="reel_auto_01"):
    """serie.json; si solo existe el seleccion.json de antes, lo muestra como un reel «Así compras»."""
    p = os.path.join(carpeta, "serie.json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    p = os.path.join(carpeta, "seleccion.json")
    if os.path.exists(p):
        sel = json.load(open(p, encoding="utf-8"))
        sel.setdefault("formato", "asi_compras"); sel.setdefault("titulo", "Así compras 1")
        sel.setdefault("nombre", nombre_defecto)
        return {"videos": [sel], "avisos": []}
    return None


def hacer_guion(carpeta, cfg, log):
    """Un solo reel «Así compras» (modo clásico; lo usa la interfaz Tkinter)."""
    datos = json.load(open(os.path.join(carpeta, "analisis.json"), encoding="utf-8"))
    if cfg["escritor"] == "(reglas, sin IA)":
        sel = guion_por_reglas(datos, cfg["minimo"])
    else:
        log("estado", f"Enviando las tomas a {cfg['escritor']}…")
        try:
            sel = escribir_guion(material_para_llm(datos, cfg["minimo"]), cfg["escritor"], log)
        except Exception as e:  # nunca dejar el paso colgado: si el modelo falla, guion por reglas
            log("error", f"{cfg['escritor']} no pudo escribir el guion ({e}). Uso el guion por reglas; puedes editarlo.")
            sel = guion_por_reglas(datos, cfg["minimo"])
    sel = validar(sel, datos)
    json.dump(sel, open(os.path.join(carpeta, "seleccion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return sel


# ---------------------------------------------------------------- textos de marca (PNG)
NEG, CARD, ORO, ORO2, HUESO, ROJO = (9, 8, 7), (12, 11, 9), (205, 168, 96), (226, 190, 114), (244, 241, 235), (255, 138, 107)
FUENTES = {"SG.ttf": "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
           "PJ.ttf": "https://github.com/google/fonts/raw/main/ofl/plusjakartasans/PlusJakartaSans%5Bwght%5D.ttf"}


def fuente(nombre, size, peso):
    from PIL import ImageFont
    path = os.path.join(AQUI, "fonts", nombre)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(FUENTES[nombre], path)
    f = ImageFont.truetype(path, size)
    f.set_variation_by_axes([peso])
    return f


def png_gancho(texto, promesa, dest):
    from PIL import Image, ImageDraw, ImageFilter
    W = 1080
    im = Image.new("RGBA", (W, 1920), (0, 0, 0, 0)); d = ImageDraw.Draw(im); ft = fuente("SG.ttf", 88, 700)
    lineas, linea = [], ""
    for p in texto.split():
        if d.textlength((linea + " " + p).strip(), font=ft) > 840 and linea:
            lineas.append(linea); linea = p
        else:
            linea = (linea + " " + p).strip()
    lineas.append(linea)
    ancho = max(d.textlength(l, font=ft) for l in lineas) + 110; alto = 70 + 115 * len(lineas)
    x0, y0 = (W - ancho) / 2, 250
    sombra = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((x0, y0, x0 + ancho, y0 + alto), 34, fill=(0, 0, 0, 150))
    im = Image.alpha_composite(im, sombra.filter(ImageFilter.GaussianBlur(28))); d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, x0 + ancho, y0 + alto), 34, fill=HUESO)
    for i, l in enumerate(lineas):
        d.text((W / 2, y0 + 92 + i * 115), l, font=ft, fill=NEG, anchor="mm")
    xs = W / 2 - d.textlength(lineas[-1], font=ft) / 2; ys = y0 + 92 + (len(lineas) - 1) * 115 + 50
    d.rectangle((xs, ys, xs + d.textlength(lineas[-1].split()[0], font=ft), ys + 10), fill=ROJO)
    if promesa:
        fs = fuente("PJ.ttf", 40, 700); w = d.textlength(promesa, font=fs) + 70; y = y0 + alto + 30
        d.rounded_rectangle(((W - w) / 2, y, (W + w) / 2, y + 80), 40, fill=NEG + (225,), outline=ORO, width=3)
        d.text((W / 2, y + 40), promesa, font=fs, fill=ORO2, anchor="mm")
    im.save(dest)


def png_paso(num, titulo, dest, kicker="PASO"):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    a, b = fuente("PJ.ttf", 30, 700), fuente("SG.ttf", 60, 700)
    w = max(d.textlength(f"{kicker} 0{num}", font=a), d.textlength(titulo, font=b)) + 120
    d.rounded_rectangle((70, 230, 70 + w, 400), 30, fill=CARD + (235,), outline=ORO, width=3)
    d.rectangle((70, 260, 78, 370), fill=ORO)
    d.text((112, 262), f"{kicker} 0{num}", font=a, fill=ORO); d.text((112, 300), titulo, font=b, fill=HUESO)
    im.save(dest)


def png_cta(dest):
    from PIL import Image, ImageDraw
    W = 1080; im = Image.new("RGBA", (W, 1920), (0, 0, 0, 0)); d = ImageDraw.Draw(im); y0 = 1020
    d.rounded_rectangle((90, y0, W - 90, y0 + 500), 40, fill=CARD + (240,), outline=ORO, width=3)
    pts = [(2, 12), (5, 12), (7, 6), (11, 20), (15, 2), (18, 12), (22, 12)]
    d.line([(W / 2 - 33 + x * 3, y0 + 40 + y * 3) for x, y in pts], fill=ORO, width=5, joint="curve")
    d.text((W / 2, y0 + 165), "Revisas. Escuchas.", font=fuente("SG.ttf", 66, 700), fill=HUESO, anchor="mm")
    d.text((W / 2, y0 + 245), "Luego pagas.", font=fuente("SG.ttf", 66, 700), fill=ORO2, anchor="mm")
    d.rounded_rectangle((170, y0 + 305, W - 170, y0 + 400), 26, fill=HUESO)
    d.text((W / 2, y0 + 352), "Comenta ASESORÍA", font=fuente("SG.ttf", 52, 700), fill=NEG, anchor="mm")
    d.text((W / 2, y0 + 450), "o escríbenos al 0422-1609357", font=fuente("PJ.ttf", 38, 600), fill=HUESO, anchor="mm")
    im.save(dest)


# ---------------------------------------------------------------- 3. CapCut
def armar(carpeta, nombre, cfg, log):
    """Modo clásico: un borrador desde seleccion.json."""
    sel = json.load(open(os.path.join(carpeta, "seleccion.json"), encoding="utf-8"))
    return armar_sel(carpeta, sel, nombre, cfg, log)


def armar_serie(carpeta, cfg, log, cuales=None):
    """Un borrador de CapCut por cada reel de serie.json. Devuelve [(nombre, segundos)]."""
    serie = leer_serie(carpeta, cfg.get("nombre", "reel_auto_01"))
    if not serie or not serie["videos"]:
        raise RuntimeError("No hay guiones: primero pulsa «Escribir guiones».")
    hechos = []
    videos = [v for i, v in enumerate(serie["videos"]) if cuales is None or i in cuales]
    for k, sel in enumerate(videos):
        log("progreso", (k, len(videos)))
        log("estado", f"Creando {sel.get('titulo', '')} → «{sel['nombre']}» ({k + 1}/{len(videos)})")
        hechos.append((sel["nombre"], armar_sel(carpeta, sel, sel["nombre"], cfg, log)))
    log("progreso", (len(videos), len(videos)))
    return hechos


def armar_sel(carpeta, sel, nombre, cfg, log):
    import pycapcut as cc
    from pycapcut import trange_seconds, tim

    if not sel.get("clips"):
        raise RuntimeError(f"«{nombre}» no tiene clips.")
    fmt = FORMATOS.get(sel.get("formato"), FORMATOS["asi_compras"])
    out = os.path.join(carpeta, "_reel_studio", re.sub(r"[^\w\-]+", "_", nombre)); os.makedirs(out, exist_ok=True)
    script = cc.DraftFolder(cfg["drafts"]).create_draft(nombre, 1080, 1920, allow_replace=True)
    script.add_track(cc.TrackType.video).add_track(cc.TrackType.video, "textos", relative_index=1)
    script.add_track(cc.TrackType.video, "cta", relative_index=2)
    script.add_track(cc.TrackType.text, "voz")

    def overlay(png, start, dur, pista="textos"):
        seg = cc.VideoSegment(png, trange_seconds(start, duration=dur))
        f = min(0.3, dur / 4)
        for t, a in ((0, 0.0), (f, 1.0), (dur - f, 1.0), (dur, 0.0)):
            seg.add_keyframe(cc.KeyframeProperty.alpha, tim(f"{t}s"), a)
        script.add_segment(seg, pista)

    inicio, t, paso_visto = [], 0.0, set()
    for c in sel["clips"]:
        path = os.path.join(carpeta, c["archivo"])
        if c["foto"]:
            path = foto_compatible(path)
            seg = cc.VideoSegment(path, trange_seconds(t, duration=c["segundos"]))
            seg.add_keyframe(cc.KeyframeProperty.uniform_scale, tim(0), 1.0)  # zoom lento: nada de fotos quietas
            seg.add_keyframe(cc.KeyframeProperty.uniform_scale, tim(f"{c['segundos']}s"), 1.15)
        else:
            seg = cc.VideoSegment(path, trange_seconds(t, duration=c["segundos"]), volume=cfg["vol_clips"],
                                  source_timerange=trange_seconds(c["desde"], duration=c["segundos"]))
        script.add_segment(seg, "video")
        inicio.append(t)
        t += c["segundos"]

    # Gancho (primer clip), chip de cada paso (primer clip del paso) y CTA (último clip)
    png_gancho(sel["gancho"], sel.get("promesa", ""), g := os.path.join(out, "gancho.png"))
    overlay(g, 0, min(4.0, sel["clips"][0]["segundos"]))
    cues = []
    for i, c in enumerate(sel["clips"]):
        p = c.get("paso", "")
        if p in fmt["pasos"] and p not in paso_visto and i > 0:
            paso_visto.add(p)
            png_paso(p, fmt["pasos"][p], png := os.path.join(out, f"paso{p}.png"), fmt["kicker"])
            overlay(png, inicio[i], min(3.5, c["segundos"]))
            cues.append(inicio[i])
    ult = sel["clips"][-1]["segundos"]
    png_cta(cta := os.path.join(out, "cta.png"))
    cta_ini = t - min(ult, 4.0)
    overlay(cta, cta_ini, t - cta_ini, "cta")

    # Narración como texto: en CapCut -> seleccionar los textos de la pista "voz" -> Texto a voz -> Nandez
    estilo = cc.TextStyle(size=7, bold=True, color=(0.94, 0.93, 0.91), align=1, auto_wrapping=True)
    fin_ocupado = 0.0
    for n in sel.get("narracion", []):
        start = max(inicio[int(n["clip"])] + float(n.get("en", 0.3)), fin_ocupado)
        dur = max(1.5, len(n["texto"].split()) * 0.38)  # ~2,6 palabras por segundo
        if start + dur > t:
            continue
        script.add_segment(cc.TextSegment(n["texto"], trange_seconds(start, duration=dur), style=estilo,
                                          background=cc.TextBackground(color="#090807", alpha=0.6, round_radius=0.3),
                                          clip_settings=cc.ClipSettings(transform_y=-0.42)), "voz")
        fin_ocupado = start + dur + 0.1

    if cfg["musica"]:
        try:
            from gen_music import music  # está en la carpeta reel-capcut
            drop = next((inicio[i] for i, c in enumerate(sel["clips"]) if c.get("paso") == "3"), t / 3)
            music(t, cues, drop, cta_ini, mus := os.path.join(out, f"musica_{nombre}.wav"))
            script.add_track(cc.TrackType.audio, "musica")
            script.add_segment(cc.AudioSegment(mus, trange_seconds(0, duration=min(t, duracion(mus) - 0.01)),
                                               volume=cfg["vol_musica"]), "musica")
        except ImportError:
            log("error", "No encontré gen_music.py junto al programa: el borrador va sin música.")
    script.save()
    return t


# ---------------------------------------------------------------- interfaz
def interfaz():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk(); root.title("Reel Studio · DropAudio CCS"); root.geometry("1280x800"); root.configure(bg="#0C0B09")
    st = ttk.Style(); st.theme_use("clam")
    for w in ("TFrame", "TLabel", "TCheckbutton"):
        st.configure(w, background="#0C0B09", foreground="#F0EDE8")
    st.configure("TButton", background="#CDA860", foreground="#090807", font=("Segoe UI", 10, "bold"), padding=6)
    st.map("TButton", background=[("active", "#E2BE72"), ("disabled", "#5a4d33")])
    st.configure("Treeview", background="#15130f", fieldbackground="#15130f", foreground="#F0EDE8", rowheight=24)
    st.configure("Treeview.Heading", background="#967337", foreground="#090807", font=("Segoe UI", 9, "bold"))
    st.configure("TNotebook", background="#0C0B09"); st.configure("TNotebook.Tab", padding=(14, 6))

    cola = queue.Queue()
    v = {k: tk.StringVar(value=x) for k, x in {
        "carpeta": os.path.join(AQUI, "Videos Dropaudioccs"), "vision": "gemma3:4b", "jev": "nimble:latest",
        "escritor": "glm-5.3:cloud", "whisper": "small", "nombre": "reel_auto_01", "drafts": CAPCUT_DRAFTS,
        "estado": "Elige una carpeta y pulsa Analizar."}.items()}
    paso, minimo = tk.DoubleVar(value=3.0), tk.DoubleVar(value=0.5)
    vol_clips, vol_musica = tk.DoubleVar(value=1.0), tk.DoubleVar(value=0.25)
    rehacer, con_musica = tk.BooleanVar(value=False), tk.BooleanVar(value=True)

    # --- barra superior
    top = ttk.Frame(root, padding=10); top.pack(fill="x")
    ttk.Label(top, text="Carpeta").grid(row=0, column=0, sticky="w")
    ttk.Entry(top, textvariable=v["carpeta"], width=70).grid(row=0, column=1, columnspan=4, sticky="we", padx=6)
    ttk.Button(top, text="Elegir…", command=lambda: v["carpeta"].set(filedialog.askdirectory() or v["carpeta"].get())
               ).grid(row=0, column=5, sticky="w")
    combos = {}
    for i, (k, txt) in enumerate((("vision", "Visión"), ("jev", "Decisión (Jev)"), ("escritor", "Guion"), ("whisper", "Whisper"))):
        ttk.Label(top, text=txt).grid(row=1, column=i * 2 % 6, sticky="w", pady=(8, 0)) if i < 3 else \
            ttk.Label(top, text=txt).grid(row=2, column=0, sticky="w", pady=(8, 0))
        cb = ttk.Combobox(top, textvariable=v[k], width=24)
        cb.grid(row=1 if i < 3 else 2, column=(i * 2 + 1) % 6 if i < 3 else 1, sticky="w", padx=6, pady=(8, 0))
        combos[k] = cb
    combos["whisper"]["values"] = ["(ninguno)", "tiny", "base", "small", "medium"]
    ttk.Label(top, text="Seg. entre fotogramas").grid(row=2, column=2, sticky="w", pady=(8, 0))
    ttk.Spinbox(top, from_=1, to=10, increment=0.5, textvariable=paso, width=6).grid(row=2, column=3, sticky="w", padx=6)
    ttk.Checkbutton(top, text="Rehacer análisis", variable=rehacer).grid(row=2, column=4, sticky="w")
    ttk.Button(top, text="↻ Modelos", command=lambda: hilo(cargar_modelos, silencioso=True)).grid(row=2, column=5, sticky="w")
    ttk.Label(top, text="Borradores CapCut").grid(row=3, column=0, sticky="w", pady=(8, 0))
    ttk.Entry(top, textvariable=v["drafts"], width=70).grid(row=3, column=1, columnspan=4, sticky="we", padx=6, pady=(8, 0))

    # --- botones de pasos
    bar = ttk.Frame(root, padding=(10, 0)); bar.pack(fill="x")
    b1 = ttk.Button(bar, text="1 · Analizar", command=lambda: hilo(t_analizar))
    b2 = ttk.Button(bar, text="2 · Escribir guion", command=lambda: hilo(t_guion))
    b3 = ttk.Button(bar, text="3 · Crear en CapCut", command=lambda: hilo(t_armar))
    for b in (b1, b2, b3):
        b.pack(side="left", padx=(0, 8))
    ttk.Label(bar, text="  Nombre").pack(side="left"); ttk.Entry(bar, textvariable=v["nombre"], width=18).pack(side="left", padx=4)
    ttk.Label(bar, text=" Vol. clips").pack(side="left"); ttk.Spinbox(bar, from_=0, to=1, increment=0.1, textvariable=vol_clips, width=4).pack(side="left")
    ttk.Label(bar, text=" Mín. usable").pack(side="left"); ttk.Spinbox(bar, from_=0, to=1, increment=0.05, textvariable=minimo, width=5).pack(side="left")
    ttk.Checkbutton(bar, text="Música", variable=con_musica).pack(side="left", padx=(8, 0))
    ttk.Spinbox(bar, from_=0, to=1, increment=0.05, textvariable=vol_musica, width=5).pack(side="left")
    barra = ttk.Progressbar(bar, mode="indeterminate", length=180); barra.pack(side="right")

    # --- pestañas
    nb = ttk.Notebook(root); nb.pack(fill="both", expand=True, padx=10, pady=8)
    f1, f2, f3 = ttk.Frame(nb), ttk.Frame(nb), ttk.Frame(nb)
    nb.add(f1, text="Decisiones por toma"); nb.add(f2, text="Guion (editable)"); nb.add(f3, text="Registro")
    cols = ("archivo", "tiempo", "tipo", "usable", "interes", "habla", "descripcion")
    tv = ttk.Treeview(f1, columns=cols, show="headings")
    for c, w in zip(cols, (210, 80, 130, 65, 65, 260, 460)):
        tv.heading(c, text=c.capitalize()); tv.column(c, width=w, anchor="w")
    tv.tag_configure("buena", foreground="#E2BE72"); tv.tag_configure("mala", foreground="#7a7368")
    sb = ttk.Scrollbar(f1, command=tv.yview); tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
    guion = tk.Text(f2, bg="#15130f", fg="#F0EDE8", insertbackground="#CDA860", font=("Consolas", 10), wrap="word")
    guion.pack(fill="both", expand=True)
    ttk.Button(f2, text="Guardar cambios del guion", command=lambda: guardar_guion()).pack(anchor="e", pady=4)
    reg = tk.Text(f3, bg="#15130f", fg="#F0EDE8", font=("Consolas", 9)); reg.pack(fill="both", expand=True)
    ttk.Label(root, textvariable=v["estado"], padding=(10, 0, 10, 8), font=("Segoe UI", 10, "bold")).pack(fill="x")

    # --- lógica
    def log(tipo, x):
        cola.put((tipo, x))

    def cfg():
        return {"vision": v["vision"].get(), "jev": v["jev"].get(), "escritor": v["escritor"].get(),
                "whisper": v["whisper"].get(), "paso": float(paso.get()), "minimo": float(minimo.get()),
                "drafts": v["drafts"].get(), "vol_clips": float(vol_clips.get()), "vol_musica": float(vol_musica.get()),
                "musica": con_musica.get()}

    def hilo(fn, silencioso=False):
        for b in (b1, b2, b3):
            b.state(["disabled"])
        barra.start(12)

        def correr():
            t0 = time.time()
            try:
                msg = fn()
                log("silencio" if silencioso else "listo", f"{msg}  ({time.time() - t0:.0f} s)")
            except Exception as e:
                log("fallo", str(e))
        threading.Thread(target=correr, daemon=True).start()

    def cargar_modelos():
        ms = modelos()
        log("modelos", ms)
        return f"{len(ms)} modelos de Ollama cargados"

    def t_analizar():
        log("limpiar", None)
        datos = analizar(v["carpeta"].get(), cfg(), log, rehacer.get())
        tomas = sum(len(d["tomas"]) for d in datos.values())
        return f"✅ Análisis listo: {len(datos)} archivos, {tomas} tomas. Ahora pulsa 2 · Escribir guion."

    def t_guion():
        sel = hacer_guion(v["carpeta"].get(), cfg(), log)
        log("guion", sel)
        dur = sum(c["segundos"] for c in sel["clips"])
        return f"✅ Guion listo: {len(sel['clips'])} clips, {dur:.1f} s. Revísalo en la pestaña Guion y pulsa 3."

    def t_armar():
        t = armar(v["carpeta"].get(), v["nombre"].get(), cfg(), log)
        return (f"✅ Borrador '{v['nombre'].get()}' ({t:.1f} s) creado en CapCut. Ábrelo, selecciona los textos de la "
                f"pista 'voz' → Texto a voz → Nandez.")

    def guardar_guion():
        try:
            sel = json.loads(guion.get("1.0", "end"))
            json.dump(sel, open(os.path.join(v["carpeta"].get(), "seleccion.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            v["estado"].set("Guion guardado. Pulsa 3 · Crear en CapCut.")
        except Exception as e:
            messagebox.showerror("Guion", f"El JSON tiene un error: {e}")

    def bombear():
        while not cola.empty():
            tipo, x = cola.get()
            if tipo == "estado":
                v["estado"].set(x)
            elif tipo == "fila":
                habla = " ".join(h["texto"] for h in x["habla"])[:120]
                for t in x["tomas"]:
                    tag = "buena" if t["usable"] >= minimo.get() else "mala"
                    tv.insert("", "end", tags=(tag,), values=(x["archivo"], f"{t['inicio']}s", t["tipo"], t["usable"],
                                                              t["interes"], habla, t["descripcion"]))
                tv.yview_moveto(1)
            elif tipo == "limpiar":
                tv.delete(*tv.get_children())
            elif tipo == "guion":
                guion.delete("1.0", "end"); guion.insert("1.0", json.dumps(x, ensure_ascii=False, indent=1)); nb.select(f2)
            elif tipo == "modelos":
                todos = [n for n, _ in x]; vision = [n for n, vis in x if vis] or todos
                combos["vision"]["values"] = vision; combos["jev"]["values"] = todos
                combos["escritor"]["values"] = ["(reglas, sin IA)"] + todos
            if tipo in ("error", "fallo", "listo", "estado"):
                reg.insert("end", f"[{time.strftime('%H:%M:%S')}] {x}\n"); reg.see("end")
            if tipo == "silencio":
                barra.stop(); v["estado"].set(x)
                for b in (b1, b2, b3):
                    b.state(["!disabled"])
            if tipo in ("listo", "fallo"):
                barra.stop()
                for b in (b1, b2, b3):
                    b.state(["!disabled"])
                v["estado"].set(x if tipo == "listo" else f"❌ {x}")
                root.bell()
                (messagebox.showinfo if tipo == "listo" else messagebox.showerror)("Reel Studio", x)
        root.after(150, bombear)

    # si ya hay análisis o guion en la carpeta, mostrarlos
    def cargar_previos():
        c = v["carpeta"].get()
        if os.path.exists(os.path.join(c, "analisis.json")):
            for d in json.load(open(os.path.join(c, "analisis.json"), encoding="utf-8")).values():
                log("fila", d)
        if os.path.exists(os.path.join(c, "seleccion.json")):
            log("guion", json.load(open(os.path.join(c, "seleccion.json"), encoding="utf-8")))
    v["carpeta"].trace_add("write", lambda *a: (log("limpiar", None), cargar_previos()))

    cargar_previos(); bombear(); hilo(cargar_modelos, silencioso=True)
    root.mainloop()


if __name__ == "__main__":
    interfaz()
