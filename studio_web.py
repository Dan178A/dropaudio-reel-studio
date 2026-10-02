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
       "simultaneos": 6, "saltar_repetidos": True}
if os.path.exists(CFG_FILE):
    CFG.update(json.load(open(CFG_FILE, encoding="utf-8")))

LOCK = threading.Lock()
JOB = {"tarea": None, "corriendo": False, "hecho": 0, "total": 0, "mensaje": "", "ok": None, "inicio": 0, "fin": 0}
LOG, ESTADO = [], {"analisis_v": 0, "guion_v": 0, "modelos": [], "borrador": None}


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


def t_guion():
    sel = core.hacer_guion(CFG["carpeta"], CFG, evento)
    ESTADO["guion_v"] += 1
    return f"Guion listo: {len(sel['clips'])} clips, {sum(c['segundos'] for c in sel['clips']):.1f} s."


def t_armar():
    t = core.armar(CFG["carpeta"], CFG["nombre"], CFG, evento)
    ESTADO["borrador"] = {"nombre": CFG["nombre"], "dur": round(t, 1), "carpeta": CFG["carpeta"]}
    return f"Borrador «{CFG['nombre']}» creado en CapCut ({t:.1f} s)."


TAREAS = {"analizar": t_analizar, "guion": t_guion, "armar": t_armar, "modelos": t_modelos}


# ------------------------------------------------------------------ miniaturas
def miniatura(nombre, t):
    nombre = os.path.basename(nombre)  # nunca salir de la carpeta
    src = os.path.join(CFG["carpeta"], nombre)
    if not os.path.exists(src):
        return None
    cache = os.path.join(CFG["carpeta"], "_reel_studio", "thumbs")
    os.makedirs(cache, exist_ok=True)
    dest = os.path.join(cache, hashlib.md5(f"{nombre}@{t}".encode()).hexdigest() + ".jpg")
    if not os.path.exists(dest):
        if nombre.lower().endswith(core.FOTO_EXT):
            from PIL import Image, ImageOps
            im = ImageOps.exif_transpose(Image.open(core.foto_compatible(src))).convert("RGB")
            im.thumbnail((360, 640)); im.save(dest, quality=82)
        else:
            core.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1",
                      "-vf", "scale=360:-2", "-q:v", "5", dest])
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
            v = int(q.get("av", ["-1"])[0]); gv = int(q.get("gv", ["-1"])[0])
            with LOCK:
                job = dict(JOB); log = LOG[-120:]
            out = {"cfg": CFG, "archivos": archivos(), "modelos": ESTADO["modelos"], "job": job, "log": log,
                   "borrador": ESTADO["borrador"], "analisis_v": ESTADO["analisis_v"], "guion_v": ESTADO["guion_v"],
                   "ahora": time.time()}
            if v != ESTADO["analisis_v"]:
                out["analisis"] = leer("analisis.json")
            if gv != ESTADO["guion_v"]:
                out["guion"] = leer("seleccion.json")
            self._json(out)
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
                    ESTADO["analisis_v"] += 1; ESTADO["guion_v"] += 1; ESTADO["borrador"] = None
                self._json({"ok": True})
            elif u.path == "/api/usar_carpeta":
                c = self._body().get("carpeta", "")
                if c and os.path.isdir(c):
                    CFG["carpeta"] = c; guardar_cfg()
                    ESTADO["analisis_v"] += 1; ESTADO["guion_v"] += 1; ESTADO["borrador"] = None
                self._json({"carpeta": CFG["carpeta"]})
            elif u.path == "/api/elegir_carpeta":
                c = elegir_carpeta()
                if c:
                    CFG["carpeta"] = c; guardar_cfg()
                    ESTADO["analisis_v"] += 1; ESTADO["guion_v"] += 1; ESTADO["borrador"] = None
                self._json({"carpeta": CFG["carpeta"]})
            elif u.path.startswith("/api/tarea/"):
                nombre = u.path.rsplit("/", 1)[1]
                ok = nombre in TAREAS and lanzar(nombre, TAREAS[nombre])
                self._json({"ok": ok}, 200 if ok else 409)
            elif u.path == "/api/guion":
                sel = self._body()
                datos = leer("analisis.json") or {}
                for c in sel.get("clips", []):
                    c["hasta"] = float(c.get("desde", 0)) + float(c.get("segundos", 0))
                sel = core.validar(sel, datos)
                json.dump(sel, open(os.path.join(CFG["carpeta"], "seleccion.json"), "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
                ESTADO["guion_v"] += 1
                self._json({"ok": True, "guion": sel, "guion_v": ESTADO["guion_v"]})
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
