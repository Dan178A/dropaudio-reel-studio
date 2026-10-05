import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import studio_web


def _post(puerto, origen):
    c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
    h = {"Content-Type": "application/json"}
    if origen is not None:
        h["Origin"] = origen
    c.request("POST", "/api/ruta_inexistente", body=json.dumps({}), headers=h)
    r = c.getresponse()
    r.read()
    c.close()
    return r.status


def test_post_rechaza_origen_ajeno():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), studio_web.H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        p = srv.server_address[1]
        assert _post(p, "https://evil.example") == 403
        assert _post(p, f"http://127.0.0.1:{p + 1}") == 403
        assert _post(p, f"http://127.0.0.1:{p}") != 403
        assert _post(p, f"http://localhost:{p}") != 403
        assert _post(p, None) != 403  # sin Origin (pywebview/herramientas locales)
    finally:
        srv.shutdown()
        srv.server_close()
