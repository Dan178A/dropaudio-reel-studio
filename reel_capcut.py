"""
reel_capcut.py — DropAudio CCS
Toma los videos y fotos de una carpeta, los analiza con Ollama y arma un borrador de CapCut.

  Paso 1  analizar : un modelo con visión describe un fotograma cada N segundos,
                     y Jev (nimble, /v1/systemone) decide si sirve, qué tipo de toma es y qué tan buena es.
                     -> analisis.json
  Paso 2  elegir   : arma la secuencia del reel con la fórmula (gancho -> contenido -> prueba -> CTA).
                     -> seleccion.json   (puedes editarlo a mano antes del paso 3)
  Paso 3  armar    : crea el borrador 1080x1920 en CapCut con pyCapCut.

Uso (PowerShell):
  python reel_capcut.py analizar "C:\\Users\\DAN_PC\\Downloads\\drive-download-20261001T235408Z-1-001"
  python reel_capcut.py elegir   "C:\\...\\drive-download-..." --gancho "No compres audífonos sin ver esto"
  python reel_capcut.py armar    "C:\\...\\drive-download-..." --nombre reel_real_01 --musica "C:\\ruta\\soundtrack.wav"

Requisitos: ffmpeg y ffprobe en el PATH, Ollama >= 0.35 con `ollama pull nimble` y `ollama pull gemma3:4b`,
y pyCapCut instalado (`pip install -e C:\\Users\\DAN_PC\\Documents\\GitHub\\pyCapCut`). Cierra CapCut antes de armar.
"""
import argparse, base64, json, os, subprocess, sys, tempfile, urllib.request

OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".avi", ".mkv")
FOTO_EXT = (".jpg", ".jpeg", ".png")
CAPCUT_DRAFTS = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")

TIPOS = {
    "producto_detalle": "Primer plano de audífonos, cables, DAC o estuche",
    "unboxing": "Abriendo una caja o sacando el producto del empaque",
    "prueba_sonido": "Alguien probándose o escuchando los audífonos",
    "entrega_moto": "La moto, el trayecto o el momento de entregar al cliente",
    "persona": "Una persona hablando a cámara o mostrando el producto",
    "otro": "Nada de lo anterior o no se distingue",
}

# Fórmula del reel: (tipos aceptados en orden de preferencia, cuántos clips, segundos por clip)
PLAN = [
    (["producto_detalle", "unboxing"], 1, 3.5),   # gancho: el texto va encima
    (["unboxing"], 2, 3.0),
    (["producto_detalle"], 2, 3.0),
    (["prueba_sonido", "persona"], 2, 3.0),
    (["entrega_moto"], 2, 3.0),
    (["producto_detalle", "persona", "entrega_moto", "otro"], 1, 4.5),  # cierre: CTA encima
]


def post(path, body):
    req = urllib.request.Request(OLLAMA + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def duracion(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def fotograma(path, t, destino):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
                    "-vf", "scale=640:-2", destino], check=True)
    return destino


def describir(img_path, modelo):
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    prompt = ("Describe en 2 frases, en español, qué se ve en esta imagen de una tienda de audífonos: "
              "objetos, acciones, personas, si está borrosa, oscura o movida.")
    return post("/api/generate", {"model": modelo, "prompt": prompt, "images": [b64], "stream": False})["response"].strip()


def decidir(descripcion, modelo):
    preguntas = {
        "usable": {"type": "noul",
                   "instructions": "¿La toma se ve nítida, bien iluminada y sin movimiento brusco, apta para un reel?"},
        "tipo": {"type": "choice", "instructions": "¿Qué tipo de toma es?", "criteria": TIPOS},
        "interes": {"type": "score", "instructions": "¿Qué tan atractiva es para detener el scroll en Instagram?",
                    "criteria": ["Relleno", "Normal", "Muy atractiva"]},
    }
    a = post("/v1/systemone", {"model": modelo, "state": {"toma": descripcion}, "questions": preguntas})["answers"]
    interes = a["interes"]["score"] / 2  # ponytail: score viene en índice 0..2 (ver legend); lo paso a 0..1
    return {"usable": round(a["usable"]["noul"], 3), "tipo": a["tipo"]["choice"], "interes": round(interes, 3)}


def analizar(carpeta, paso, vision, jev):
    salida = os.path.join(carpeta, "analisis.json")
    hecho = json.load(open(salida, encoding="utf-8")) if os.path.exists(salida) else []
    vistos = {(v["archivo"], v["inicio"]) for v in hecho}
    tmp = os.path.join(tempfile.gettempdir(), "reel_frame.jpg")

    for nombre in sorted(os.listdir(carpeta)):
        path = os.path.join(carpeta, nombre)
        ext = nombre.lower().endswith
        if ext(FOTO_EXT):
            ventanas, es_foto = [(0.0, 3.0)], True
        elif ext(VIDEO_EXT):
            d = duracion(path)
            ventanas = [(t, min(paso, d - t)) for t in frange(0, d, paso) if d - t >= 1.5]
            es_foto = False
        else:
            continue
        for inicio, dur in ventanas:
            if (nombre, round(inicio, 2)) in vistos:
                continue
            img = path if es_foto else fotograma(path, inicio + dur / 2, tmp)
            desc = describir(img, vision)
            item = {"archivo": nombre, "foto": es_foto, "inicio": round(inicio, 2), "dur": round(dur, 2),
                    "descripcion": desc, **decidir(desc, jev)}
            hecho.append(item)
            print(f"{nombre} @{inicio:6.1f}s  {item['tipo']:<16} usable={item['usable']:.2f} interes={item['interes']:.2f}")
            json.dump(hecho, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)  # guarda en cada paso
    print(f"\nListo: {len(hecho)} tomas en {salida}")


def frange(a, b, s):
    while a < b:
        yield round(a, 2)
        a += s


def elegir(carpeta, gancho, cta, minimo_usable):
    tomas = json.load(open(os.path.join(carpeta, "analisis.json"), encoding="utf-8"))
    buenas = [t for t in tomas if t["usable"] >= minimo_usable]
    buenas.sort(key=lambda t: t["usable"] * t["interes"], reverse=True)
    usadas, clips = set(), []
    for tipos, n, seg in PLAN:
        for _ in range(n):
            cand = next((t for tipo in tipos for t in buenas
                         if t["tipo"] == tipo and (t["archivo"], t["inicio"]) not in usadas), None)
            if cand:
                usadas.add((cand["archivo"], cand["inicio"]))
                clips.append({"archivo": cand["archivo"], "foto": cand["foto"], "desde": cand["inicio"],
                              "segundos": min(seg, cand["dur"]) if not cand["foto"] else seg,
                              "tipo": cand["tipo"], "descripcion": cand["descripcion"]})
    if not clips:
        sys.exit("No hay tomas usables. Baja --minimo o revisa analisis.json.")
    sel = {"gancho": gancho, "cta": cta, "clips": clips}
    json.dump(sel, open(os.path.join(carpeta, "seleccion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total = sum(c["segundos"] for c in clips)
    for c in clips:
        print(f"{c['tipo']:<16} {c['archivo']} desde {c['desde']}s ({c['segundos']}s)")
    print(f"\n{len(clips)} clips, {total:.1f}s. Revisa o edita seleccion.json y luego corre `armar`.")


def armar(carpeta, nombre, drafts, musica, volumen, vol_musica):
    """seleccion.json:
      clips:    [{archivo, foto, desde, segundos|null (= hasta el final), volumen?}]
      overlays: [{png, clip, en, segundos|null (= hasta el fin del clip), zoom?: [inicio, fin]}]  (relativos a su clip)
      voces:    [{audio, clip, en, volumen?}]
      musica:   "auto" (se genera a medida) | ruta a un .wav | ausente
    """
    import pycapcut as cc
    from pycapcut import trange_seconds, tim

    aqui = os.path.dirname(os.path.abspath(__file__))
    ruta = lambda r: r if os.path.isabs(r) else os.path.join(aqui, r)
    sel = json.load(open(os.path.join(carpeta, "seleccion.json"), encoding="utf-8"))
    script = cc.DraftFolder(drafts).create_draft(nombre, 1080, 1920, allow_replace=True)
    script.add_track(cc.TrackType.video).add_track(cc.TrackType.video, "overlays", relative_index=1)
    script.add_track(cc.TrackType.audio, "voces")

    inicio, t = [], 0.0
    for c in sel["clips"]:
        path = os.path.join(carpeta, c["archivo"])
        seg_s = c.get("segundos") or round(duracion(path) - c["desde"] - 0.05, 2)
        c["segundos"] = seg_s
        dest = trange_seconds(t, duration=seg_s)
        if c["foto"]:
            seg = cc.VideoSegment(path, dest)
            # ponytail: zoom lento para que la foto no quede estática (Daniel no quiere fotos quietas)
            seg.add_keyframe(cc.KeyframeProperty.uniform_scale, tim(0), 1.0)
            seg.add_keyframe(cc.KeyframeProperty.uniform_scale, tim(f"{seg_s}s"), 1.15)
        else:
            seg = cc.VideoSegment(path, dest, source_timerange=trange_seconds(c["desde"], duration=seg_s),
                                  volume=c.get("volumen", volumen))
        script.add_segment(seg, "video")
        inicio.append(t)
        t += seg_s

    # Textos y fondos de marca: imágenes 1080x1920 (fuentes Space Grotesk / Plus Jakarta ya horneadas)
    cues, cta = [], None
    for o in sel.get("overlays", []):
        c = sel["clips"][o["clip"]]
        dur = o.get("segundos") or round(c["segundos"] - o["en"], 2)
        start = inicio[o["clip"]] + o["en"]
        seg = cc.VideoSegment(ruta(o["png"]), trange_seconds(start, duration=dur))
        f = min(0.35, dur / 4)  # transición suave: fundido de entrada y salida
        seg.add_keyframe(cc.KeyframeProperty.alpha, tim(0), 0.0)
        seg.add_keyframe(cc.KeyframeProperty.alpha, tim(f"{f}s"), 1.0)
        seg.add_keyframe(cc.KeyframeProperty.alpha, tim(f"{dur - f}s"), 1.0)
        seg.add_keyframe(cc.KeyframeProperty.alpha, tim(f"{dur}s"), 0.0)
        if o.get("zoom"):
            seg.add_keyframe(cc.KeyframeProperty.uniform_scale, tim(0), o["zoom"][0])
            seg.add_keyframe(cc.KeyframeProperty.uniform_scale, tim(f"{dur}s"), o["zoom"][1])
        script.add_segment(seg, "overlays")
        cues.append(start)
        if "cta" in o["png"]:
            cta = start

    for v in sel.get("voces", []):
        start = inicio[v["clip"]] + v["en"]
        script.add_segment(cc.AudioSegment(ruta(v["audio"]), trange_seconds(start, duration=duracion(ruta(v["audio"])) - 0.01),
                                           volume=v.get("volumen", 1.0)), "voces")

    musica = musica or sel.get("musica")
    if musica == "auto":
        from gen_music import music  # misma carpeta que este script
        drop = inicio[2] if len(inicio) > 2 else t / 2
        musica = os.path.join(carpeta, f"musica_{nombre}.wav")
        music(t, cues, drop, cta or t - 3, musica)
    if musica:
        musica = ruta(musica)
        script.add_track(cc.TrackType.audio, "musica")
        script.add_segment(cc.AudioSegment(musica, trange_seconds(0, duration=min(t, duracion(musica) - 0.01)),
                                           volume=vol_musica), "musica")
    script.save()
    for i, c in enumerate(sel["clips"]):
        print(f"{inicio[i]:6.2f}s  {c['archivo']} ({c['segundos']}s)")
    print(f"Borrador '{nombre}' ({t:.1f}s) creado en {drafts}. Abre CapCut (o reinícialo) para verlo.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analizar"); a.add_argument("carpeta")
    a.add_argument("--paso", type=float, default=3.0, help="segundos entre fotogramas analizados")
    a.add_argument("--vision", default="gemma3:4b"); a.add_argument("--jev", default="nimble")
    e = sub.add_parser("elegir"); e.add_argument("carpeta")
    e.add_argument("--gancho", default="No compres audífonos sin ver esto")
    e.add_argument("--cta", default="Revisas. Escuchas. Luego pagas.\nComenta ASESORÍA · 0422-1609357")
    e.add_argument("--minimo", type=float, default=0.5, help="probabilidad mínima de que la toma sirva")
    m = sub.add_parser("armar"); m.add_argument("carpeta")
    m.add_argument("--nombre", default="reel_auto"); m.add_argument("--drafts", default=CAPCUT_DRAFTS)
    m.add_argument("--musica"); m.add_argument("--volumen", type=float, default=0.0, help="volumen del audio original (0-1)")
    m.add_argument("--volumen-musica", type=float, default=0.3, help="volumen de la música (0-1)")
    x = p.parse_args()

    if x.cmd == "analizar":
        analizar(x.carpeta, x.paso, x.vision, x.jev)
    elif x.cmd == "elegir":
        elegir(x.carpeta, x.gancho, x.cta, x.minimo)
    else:
        armar(x.carpeta, x.nombre, x.drafts, x.musica, x.volumen, x.volumen_musica)
