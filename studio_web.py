"""
Reel Studio (versión web local) · DropAudio CCS
Abre una interfaz en tu navegador (http://127.0.0.1:8765) que usa el mismo motor de reel_studio.py.
Solo escucha en tu PC (127.0.0.1): nadie más en la red puede abrirla.

Ejecutar:  python studio_web.py      (o doble clic en Reel_Studio.bat)
"""
import json, os, subprocess, sys, threading, time, traceback, webbrowser, hashlib, tempfile
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import reel_studio as core

PUERTO = 8765
# BASE: donde viven tus datos (config, carpeta de videos). RES: archivos de la app (html). Iguales salvo en el .exe.
BASE = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
RES = getattr(sys, "_MEIPASS", BASE)
AQUI = BASE
CFG_FILE = os.path.join(BASE, "studio_config.json")

CFG = {"carpeta": os.path.join(AQUI, "Videos Dropaudioccs"), "vision": "gemma3:4b", "jev": "nimble:latest",
       "escritor": "glm-5.3:cloud", "whisper": "small", "paso": 3.0, "minimo": 0.5, "drafts": core.CAPCUT_DRAFTS,
       "vol_clips": 1.0, "vol_musica": 0.25, "musica": True, "nombre": "reel_auto_01", "rehacer": False,
       "simultaneos": 6, "saltar_repetidos": True, "formatos": list(core.ORDEN_FORMATOS), "max_por_formato": 2, "catalogo": [],
       "voz_en_off": True, "critico": True}
if os.path.exists(CFG_FILE):
    CFG.update(json.load(open(CFG_FILE, encoding="utf-8")))


def productos_tienda():
    """productos.json (modelos y precios sacados de la landing de DropAudio). Primero el que está junto a la app."""
    for base in (BASE, RES):
        p = os.path.join(base, "productos.json")
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8")).get("productos", [])
    return []


def importar_productos(actualizar_precios=False):
    """Suma al catálogo los productos de la tienda que falten. Con actualizar_precios, también corrige precios."""
    cat, nuevos, cambiados = list(CFG.get("catalogo") or []), 0, 0
    for p in productos_tienda():
        ya = next((c for c in cat if c["nombre"].lower() == p["nombre"].lower()), None)
        if not ya:
            cat.append({"nombre": p["nombre"], "precio": p.get("precio")}); nuevos += 1
        elif actualizar_precios and p.get("precio") is not None and ya.get("precio") != p["precio"]:
            ya["precio"] = p["precio"]; cambiados += 1
    CFG["catalogo"] = cat
    return nuevos, cambiados


if importar_productos()[0]:  # la primera vez (o si la tienda tiene modelos nuevos) se cargan solos
    json.dump(CFG, open(CFG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

LOCK = threading.Lock()
JOB = {"tarea": None, "corriendo": False, "hecho": 0, "total": 0, "mensaje": "", "ok": None, "inicio": 0, "fin": 0}
LOG, ESTADO = [], {"analisis_v": 0, "guion_v": 0, "etiq_v": 0, "modelos": [], "borrador": None}


def guardar_cfg():
    json.dump(CFG, open(CFG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def anotar(texto, nivel="info"):
    with LOCK:
        LOG.append({"t": time.strftime("%H:%M:%S"), "nivel": nivel, "texto": texto})
        del LOG[:-300]


def evento(tipo, x):
    with LOCK:
        if tipo == "estado":
            JOB["mensaje"] = x
        elif tipo == "progreso":
            JOB["hecho"], JOB["total"] = x
        elif tipo == "fila":
            ESTADO["analisis_v"] += 1
    if tipo in ("estado", "error"):
        anotar(x, "error" if tipo == "error" else "info")


def leer(nombre):
    p = os.path.join(CFG["carpeta"], nombre)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


_previas = set()


def preparar_copias(carpeta):
    """En segundo plano, una vez por carpeta: copias H.264 de los videos HEVC para que el reproductor abra al instante."""
    if carpeta in _previas:
        return
    _previas.add(carpeta)

    def trabajar():
        for f in sorted(os.listdir(carpeta)):
            if CFG["carpeta"] != carpeta:
                return  # cambiaste de carpeta
            src = os.path.join(carpeta, f)
            if f.lower().endswith(core.VIDEO_EXT):
                try:
                    if es_hevc(src):
                        archivo_media(f, proxy=True)
                except Exception:
                    pass
    threading.Thread(target=trabajar, daemon=True).start()


def lista_archivos():
    c = CFG["carpeta"]
    if not os.path.isdir(c):
        return []
    preparar_copias(c)
    return [{"archivo": f, "foto": f.lower().endswith(core.FOTO_EXT)} for f in sorted(os.listdir(c))
            if f.lower().endswith(core.VIDEO_EXT + core.FOTO_EXT)]


def archivos():
    c = CFG["carpeta"]
    if not os.path.isdir(c):
        return {"videos": 0, "fotos": 0, "existe": False}
    fs = os.listdir(c)
    return {"videos": sum(f.lower().endswith(core.VIDEO_EXT) for f in fs),
            "fotos": sum(f.lower().endswith(core.FOTO_EXT) for f in fs), "existe": True}


# ------------------------------------------------------------------ tareas
def lanzar(tarea, fn):
    with LOCK:
        if JOB["corriendo"]:
            return False
        JOB.update(tarea=tarea, corriendo=True, hecho=0, total=0, mensaje="Empezando…", ok=None, inicio=time.time())

    def correr():
        try:
            msg = fn()
            with LOCK:
                JOB.update(ok=True, mensaje=msg)
            anotar(msg, "ok")
        except Exception as e:
            with LOCK:
                JOB.update(ok=False, mensaje=str(e))
            anotar(f"{e}\n{traceback.format_exc(limit=2)}", "error")
        finally:
            with LOCK:
                JOB.update(corriendo=False, fin=time.time())
    threading.Thread(target=correr, daemon=True).start()
    return True


def t_modelos():
    ESTADO["modelos"] = core.modelos()
    return f"{len(ESTADO['modelos'])} modelos de Ollama disponibles"


def t_analizar():
    datos = core.analizar(CFG["carpeta"], CFG, evento, CFG.get("rehacer"))
    n = sum(len(d["tomas"]) for d in datos.values())
    return f"Análisis listo: {len(datos)} archivos y {n} tomas revisadas."


def cfg_guion():
    return {**CFG, "productos_info": productos_tienda()}


def t_guion():
    serie = core.hacer_serie(CFG["carpeta"], cfg_guion(), evento)
    ESTADO["guion_v"] += 1; ESTADO["borrador"] = None
    return f"Serie lista: {len(serie['videos'])} reels (" + ", ".join(v["titulo"] for v in serie["videos"]) + ")."


def t_armar():
    hechos = core.armar_serie(CFG["carpeta"], CFG, evento)
    ESTADO["borrador"] = {"nombres": [n for n, _ in hechos], "durs": [round(t, 1) for _, t in hechos],
                          "nombre": ", ".join(n for n, _ in hechos), "dur": round(sum(t for _, t in hechos), 1),
                          "carpeta": CFG["carpeta"]}
    return f"{len(hechos)} borradores creados en CapCut: " + ", ".join(n for n, _ in hechos) + "."


def t_revisar():
    serie = core.revisar_serie(CFG["carpeta"], cfg_guion(), evento)
    ESTADO["guion_v"] += 1
    return "Revisión lista: " + ", ".join(f"{v['titulo']} {v.get('revision', {}).get('puntaje', 0):.0f}/10" for v in serie["videos"])


TAREAS = {"analizar": t_analizar, "guion": t_guion, "armar": t_armar, "modelos": t_modelos, "revisar": t_revisar}


# ------------------------------------------------------------------ miniaturas
def miniatura(nombre, t):
    nombre = os.path.basename(nombre)  # nunca salir de la carpeta
    src = os.path.join(CFG["carpeta"], nombre)
    if not os.path.exists(src):
        return None
    cache = os.path.join(CFG["carpeta"], "_reel_studio", "thumbs")
    os.makedirs(cache, exist_ok=True)
    dest = os.path.join(cache, hashlib.md5(f"{nombre}@{t}".encode()).hexdigest() + ".jpg")
    if not os.path.exists(dest) and not nombre.lower().endswith(core.FOTO_EXT):
        try:  # clips más cortos que el segundo pedido (p. ej. 0,5 s): tomar la mitad del clip
            dur = core.duracion(src)
            if t >= dur:
                t = dur / 2
        except Exception:
            pass
    if not os.path.exists(dest):
        if nombre.lower().endswith(core.FOTO_EXT):
            from PIL import Image, ImageOps
            im = ImageOps.exif_transpose(Image.open(core.foto_compatible(src))).convert("RGB")
            im.thumbnail((360, 640)); im.save(dest, quality=82)
        else:
            core.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1",
                      "-vf", "scale=360:-2", "-q:v", "5", dest])
    return dest if os.path.exists(dest) else None


# ------------------------------------------------------------------ reproductor
TIPOS_MIME = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".mkv": "video/x-matroska",
              ".avi": "video/x-msvideo", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
              ".webp": "image/webp"}
_proxy_lock = threading.Lock()


_codecs = {}


def es_hevc(path):
    """Los videos del iPhone vienen en HEVC: el visor de Windows suele dar solo el audio."""
    if path not in _codecs:
        out = core.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name",
                        "-of", "csv=p=0", path], text=True).stdout.strip().lower()
        _codecs[path] = out in ("hevc", "h265")
    return _codecs[path]


def archivo_media(nombre, proxy=False):
    """Ruta servible del archivo. Fotos HEIC -> JPG. Con proxy=True crea (una vez) una copia H.264 liviana
    para videos que el visor no reproduce (p. ej. HEVC del iPhone)."""
    nombre = os.path.basename(nombre)
    src = os.path.join(CFG["carpeta"], nombre)
    if not os.path.exists(src):
        return None
    if nombre.lower().endswith(core.FOTO_EXT):
        return core.foto_compatible(src)
    if not proxy and not es_hevc(src):
        return src
    cache = os.path.join(CFG["carpeta"], "_reel_studio", "preview"); os.makedirs(cache, exist_ok=True)
    dest = os.path.join(cache, os.path.splitext(nombre)[0] + ".mp4")
    with _proxy_lock:
        if not os.path.exists(dest):
            tmp = dest + ".tmp.mp4"
            core.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", "scale=-2:720", "-c:v", "libx264",
                      "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                      "-movflags", "+faststart", tmp])
            if os.path.exists(tmp):
                os.replace(tmp, dest)
    return dest if os.path.exists(dest) else None


def elegir_carpeta():
    """Diálogo nativo de Windows para elegir carpeta (proceso aparte para no chocar con el servidor)."""
    code = ("import tkinter as tk; from tkinter import filedialog; r=tk.Tk(); r.withdraw(); "
            "r.attributes('-topmost', True); print(filedialog.askdirectory(initialdir=%r) or '')" % CFG["carpeta"])
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return out.stdout.strip().replace("/", os.sep)


# ------------------------------------------------------------------ HTTP
class H(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/":
            b = open(os.path.join(RES, "studio.html"), "rb").read()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)
        elif u.path == "/api/estado":
            v = int(q.get("av", ["-1"])[0]); gv = int(q.get("gv", ["-1"])[0]); ev = int(q.get("ev", ["-1"])[0])
            with LOCK:
                job = dict(JOB); log = LOG[-120:]
            out = {"cfg": CFG, "archivos": archivos(), "modelos": ESTADO["modelos"], "job": job, "log": log,
                   "borrador": ESTADO["borrador"], "analisis_v": ESTADO["analisis_v"], "guion_v": ESTADO["guion_v"],
                   "etiq_v": ESTADO["etiq_v"],
                   "ahora": time.time()}
            if v != ESTADO["analisis_v"]:
                a = leer("analisis.json")
                out["analisis"] = core.aplicar_etiquetas(a, core.leer_etiquetas(CFG["carpeta"]), CFG["catalogo"]) if a else a
            if ev != ESTADO["etiq_v"]:
                out["etiquetas"] = core.leer_etiquetas(CFG["carpeta"]) if os.path.isdir(CFG["carpeta"]) else {}
                out["lista"] = lista_archivos()
            if gv != ESTADO["guion_v"]:
                out["guion"] = core.leer_serie(CFG["carpeta"], CFG.get("nombre", "reel_auto_01"))
            if q.get("fmt"):
                out["formatos"] = {k: {"titulo": f["titulo"], "kicker": f["kicker"], "pasos": f["pasos"],
                                       "nucleo": f["nucleo"]} for k, f in core.FORMATOS.items()}
                out["orden_formatos"] = core.ORDEN_FORMATOS
            self._json(out)
        elif u.path == "/media":  # video/foto para el reproductor, con soporte de Range (para adelantar)
            p = archivo_media(q.get("f", [""])[0], q.get("proxy", ["0"])[0] == "1")
            if not p:
                self.send_response(404); self.end_headers(); return
            tam = os.path.getsize(p); ini, fin = 0, tam - 1
            rng = self.headers.get("Range", "")
            if rng.startswith("bytes="):
                a, _, b = rng[6:].split(",")[0].partition("-")
                if a:
                    ini, fin = int(a), (int(b) if b else tam - 1)
                else:
                    ini = max(0, tam - int(b))
                fin = min(fin, tam - 1)
            self.send_response(206 if rng else 200)
            self.send_header("Content-Type", TIPOS_MIME.get(os.path.splitext(p)[1].lower(), "application/octet-stream"))
            self.send_header("Accept-Ranges", "bytes"); self.send_header("Content-Length", str(fin - ini + 1))
            if rng:
                self.send_header("Content-Range", f"bytes {ini}-{fin}/{tam}")
            self.end_headers()
            try:
                with open(p, "rb") as f:
                    f.seek(ini); falta = fin - ini + 1
                    while falta > 0:
                        trozo = f.read(min(1 << 20, falta))
                        if not trozo:
                            break
                        self.wfile.write(trozo); falta -= len(trozo)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # el visor cortó la descarga al adelantar: normal
        elif u.path == "/thumb":
            p = miniatura(q.get("f", [""])[0], float(q.get("t", ["0"])[0]))
            if not p:
                self.send_response(404); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "max-age=86400"); self.end_headers()
            self.wfile.write(open(p, "rb").read())
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/cfg":
                nuevo = self._body()
                cambio_carpeta = nuevo.get("carpeta") and nuevo["carpeta"] != CFG["carpeta"]
                CFG.update({k: v for k, v in nuevo.items() if k in CFG}); guardar_cfg()
                if cambio_carpeta:
                    ESTADO["analisis_v"] += 1; ESTADO["guion_v"] += 1; ESTADO["etiq_v"] += 1; ESTADO["borrador"] = None
                self._json({"ok": True})
            elif u.path == "/api/usar_carpeta":
                c = self._body().get("carpeta", "")
                if c and os.path.isdir(c):
                    CFG["carpeta"] = c; guardar_cfg()
                    ESTADO["analisis_v"] += 1; ESTADO["guion_v"] += 1; ESTADO["etiq_v"] += 1; ESTADO["borrador"] = None
                self._json({"carpeta": CFG["carpeta"]})
            elif u.path == "/api/elegir_carpeta":
                c = elegir_carpeta()
                if c:
                    CFG["carpeta"] = c; guardar_cfg()
                    ESTADO["analisis_v"] += 1; ESTADO["guion_v"] += 1; ESTADO["etiq_v"] += 1; ESTADO["borrador"] = None
                self._json({"carpeta": CFG["carpeta"]})
            elif u.path.startswith("/api/tarea/"):
                nombre = u.path.rsplit("/", 1)[1]
                ok = nombre in TAREAS and lanzar(nombre, TAREAS[nombre])
                self._json({"ok": ok}, 200 if ok else 409)
            elif u.path == "/api/etiquetas":  # {"archivos": [...], "cambios": {"tipo"|"producto"|"nota": valor}}
                b = self._body(); etiq = core.leer_etiquetas(CFG["carpeta"])
                cambios = {k: (v or "").strip() for k, v in b.get("cambios", {}).items() if k in ("tipo", "producto", "nota")}
                if isinstance(b.get("cambios", {}).get("marcas"), list):  # [{"t": 12.3, "texto": "..."}]
                    cambios["marcas"] = sorted(({"t": round(float(m.get("t", 0)), 1), "texto": str(m.get("texto", "")).strip()}
                                                for m in b["cambios"]["marcas"] if str(m.get("texto", "")).strip()),
                                               key=lambda m: m["t"])
                nombres = {x["archivo"] for x in lista_archivos()}
                for a in b.get("archivos", []):
                    if a in nombres:
                        etiq[a] = {**etiq.get(a, {}), **cambios}
                prod = cambios.get("producto")
                if prod and not any(p["nombre"].lower() == prod.lower() for p in CFG["catalogo"]):
                    CFG["catalogo"].append({"nombre": prod, "precio": None}); guardar_cfg()
                etiq = core.guardar_etiquetas(CFG["carpeta"], etiq)
                ESTADO["etiq_v"] += 1; ESTADO["analisis_v"] += 1
                self._json({"ok": True, "etiquetas": etiq})
            elif u.path == "/api/catalogo/importar":  # vuelve a leer productos.json (modelos y precios de la tienda)
                nuevos, cambiados = importar_productos(actualizar_precios=True); guardar_cfg()
                ESTADO["etiq_v"] += 1; ESTADO["analisis_v"] += 1
                self._json({"ok": True, "catalogo": CFG["catalogo"], "nuevos": nuevos, "cambiados": cambiados,
                            "hay_archivo": bool(productos_tienda())})
            elif u.path == "/api/catalogo":  # [{"nombre": "KZ Castor", "precio": 25}]
                cat = []
                for p in self._body().get("catalogo", []):
                    n = (p.get("nombre") or "").strip()
                    if n and not any(c["nombre"].lower() == n.lower() for c in cat):
                        try:
                            pr = float(p["precio"]) if p.get("precio") not in (None, "") else None
                        except (TypeError, ValueError):
                            pr = None
                        cat.append({"nombre": n, "precio": pr})
                CFG["catalogo"] = cat; guardar_cfg()
                ESTADO["etiq_v"] += 1; ESTADO["analisis_v"] += 1
                self._json({"ok": True, "catalogo": cat})
            elif u.path == "/api/guion":  # recibe la serie completa {"videos": [...]}
                serie = self._body()
                datos = leer("analisis.json") or {}
                for sel in serie.get("videos", []):
                    for c in sel.get("clips", []):
                        c["hasta"] = float(c.get("desde", 0)) + float(c.get("segundos", 0))
                    core.validar(sel, datos)
                    sel["nombre"] = (sel.get("nombre") or "reel").strip()
                serie.setdefault("avisos", [])
                core.guardar_serie(CFG["carpeta"], serie)
                ESTADO["guion_v"] += 1
                self._json({"ok": True, "guion": serie, "guion_v": ESTADO["guion_v"]})
            else:
                self.send_response(404); self.end_headers()
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)

    def log_message(self, *a):
        pass


def iniciar_servidor(puerto=PUERTO):
    """Arranca el servidor en un hilo y devuelve la URL (puerto=0 -> uno libre)."""
    srv = ThreadingHTTPServer(("127.0.0.1", puerto), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    lanzar("modelos", t_modelos)
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PUERTO), H)
    url = f"http://127.0.0.1:{PUERTO}/"
    print(f"Reel Studio abierto en {url}  (cierra esta ventana para apagarlo)")
    lanzar("modelos", t_modelos)
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
