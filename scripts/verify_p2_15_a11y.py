"""Verificacion P2.15 (a11y): touch targets >= 44 px en movil 390x844.

Mide el alto/ancho real de los botones del nav, del header y de los controles
del chat minimizado, y guarda capturas (claro y oscuro) para revisar layout.
"""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import websockets

RAIZ = r"C:\Users\Owner\Documents\projects\finca\2026-08-24-bot-bitacora-de-campo"
sys.path.insert(0, RAIZ)
from src.pwa.app import crear_app  # noqa: E402

PORT = 5072
CDP_PORT = 9238
SHOTS = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "kilo", "p2_15_shots")
os.makedirs(SHOTS, exist_ok=True)
_db = os.path.join(tempfile.gettempdir(), "kilo", "p2_15.db")
os.makedirs(os.path.dirname(_db), exist_ok=True)
shutil.copyfile(os.path.join(RAIZ, "data", "bitacora.db"), _db)


def start_flask():
    app = crear_app(db_path=_db, users_file=os.path.join(RAIZ, "src", "server", "users.json"),
                    password="test-master-password")
    app.config["SESSION_COOKIE_SECURE"] = False
    from flask import session

    def auto():
        session["autenticado"] = True
        session["rol"] = "OWNER"
        session["nombre"] = "Jaime"
        session["user_id"] = 1

    app.before_request_funcs.setdefault(None, []).insert(0, auto)
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


async def cdp(ws, method, params=None, mid=[1]):
    m = mid[0]; mid[0] += 1
    await ws.send(json.dumps({"id": m, "method": method, "params": params or {}}))
    while True:
        r = json.loads(await ws.recv())
        if r.get("id") == m:
            return r.get("result", {})


async def ev(ws, expr, ap=False):
    r = await cdp(ws, "Runtime.evaluate",
                  {"expression": expr, "returnByValue": True, "awaitPromise": ap})
    return r.get("result", {}).get("value")


MEDIR = r"""
(function () {
  function rects(sel) {
    return Array.from(document.querySelectorAll(sel)).map(function (el) {
      var r = el.getBoundingClientRect();
      return { sel: sel, id: el.id || null, w: Math.round(r.width), h: Math.round(r.height),
               visible: r.width > 0 && r.height > 0 };
    });
  }
  var out = []
    .concat(rects('#nav-principal button'))
    .concat(rects('.chat-btn-min'))
    .concat(rects('#header-pasto ~ .acciones button'))
    .concat(rects('.tema-btn'));
  return JSON.stringify(out);
})()
"""


async def main():
    threading.Thread(target=start_flask, daemon=True).start()
    time.sleep(2.5)
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    ud = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_p2_15_temp")
    shutil.rmtree(ud, ignore_errors=True)
    proc = subprocess.Popen([edge, "--headless=new", f"--remote-debugging-port={CDP_PORT}",
                             f"--user-data-dir={ud}", "--no-sandbox", "--disable-gpu", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)
    filas = []
    try:
        with urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/list") as r:
            t = next(x for x in json.loads(r.read().decode()) if x.get("type") == "page")
        async with websockets.connect(t["webSocketDebuggerUrl"], max_size=20 * 1024 * 1024) as ws:
            await cdp(ws, "Emulation.setDeviceMetricsOverride",
                      {"width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True})
            await cdp(ws, "Page.enable")
            await cdp(ws, "Runtime.enable")
            await cdp(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/"})
            await asyncio.sleep(4.5)
            filas = json.loads(await ev(ws, MEDIR))
            s = await cdp(ws, "Page.captureScreenshot", {"format": "png"})
            with open(os.path.join(SHOTS, "p2_15_movil_claro.png"), "wb") as f:
                f.write(base64.b64decode(s["data"]))
            # Tema oscuro
            await ev(ws, "var s=document.getElementById('select-tema'); if(s){s.value='dark'; s.dispatchEvent(new Event('change'));}")
            await asyncio.sleep(1.2)
            s = await cdp(ws, "Page.captureScreenshot", {"format": "png"})
            with open(os.path.join(SHOTS, "p2_15_movil_oscuro.png"), "wb") as f:
                f.write(base64.b64decode(s["data"]))
    finally:
        try:
            proc.terminate(); proc.wait(timeout=2)
        except Exception:
            pass

    visibles = [f for f in filas if f.get("visible")]
    chicos = [f for f in visibles if f["h"] < 44 or (f["sel"] == ".chat-btn-min" and f["w"] < 44)]
    for f in visibles[:14]:
        print(f"  {f['sel']:42s} id={str(f['id'])[:20]:20s} {f['w']}x{f['h']}")
    print(f"total visibles: {len(visibles)} | bajo 44px: {len(chicos)}")
    for f in chicos:
        print(f"   CHICO: {f['sel']} id={f['id']} {f['w']}x{f['h']}")
    print("screenshots:", SHOTS)
    return 0 if not chicos else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
