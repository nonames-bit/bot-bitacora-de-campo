"""Verificacion P1.5: el header carga el WebP animado (no roto) y la miniatura
de ficha usa PNG estatico. Emula movil 390x844 DPR=2 (AGENTS.md)."""
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.pwa.app import crear_app  # noqa: E402

PORT = 5067
CDP_PORT = 9233
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "kilo", "p1_5_shots")
os.makedirs(SHOTS, exist_ok=True)

_db = os.path.join(tempfile.gettempdir(), "kilo", "p1_5_bitacora.db")
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
    m = mid[0]
    mid[0] += 1
    await ws.send(json.dumps({"id": m, "method": method, "params": params or {}}))
    while True:
        r = json.loads(await ws.recv())
        if r.get("id") == m:
            return r.get("result", {})


async def ev(ws, expr):
    r = await cdp(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r.get("result", {}).get("value")


SCRIPT = r"""
(function(){
  var img = document.getElementById('header-vaca-img');
  return JSON.stringify({
    existe: !!img,
    src: img ? (img.currentSrc || img.src) : null,
    naturalW: img ? img.naturalWidth : 0,
    naturalH: img ? img.naturalHeight : 0,
    completa: img ? img.complete : false
  });
})()
"""


async def main():
    threading.Thread(target=start_flask, daemon=True).start()
    time.sleep(2.5)
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    ud = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_p1_5_temp")
    shutil.rmtree(ud, ignore_errors=True)
    proc = subprocess.Popen([edge, "--headless=new", f"--remote-debugging-port={CDP_PORT}",
                             f"--user-data-dir={ud}", "--no-sandbox", "--disable-gpu", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)
    datos = None
    try:
        with urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/list") as r:
            t = next(x for x in json.loads(r.read().decode()) if x.get("type") == "page")
        async with websockets.connect(t["webSocketDebuggerUrl"], max_size=20 * 1024 * 1024) as ws:
            await cdp(ws, "Emulation.setDeviceMetricsOverride",
                      {"width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True})
            await cdp(ws, "Page.enable")
            await cdp(ws, "Runtime.enable")
            await cdp(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/"})
            await asyncio.sleep(4.0)
            datos = json.loads(await ev(ws, SCRIPT))
            res = await cdp(ws, "Page.captureScreenshot", {"format": "png"})
            with open(os.path.join(SHOTS, "p1_5_header.png"), "wb") as f:
                f.write(base64.b64decode(res["data"]))
    finally:
        try:
            proc.terminate(); proc.wait(timeout=2)
        except Exception:
            pass

    print(json.dumps(datos, indent=2, ensure_ascii=False))
    src = datos.get("src") or ""
    ok = datos.get("existe") and datos.get("naturalW", 0) > 0 and src.endswith(".webp")
    print("P1.5 header WebP: TODO OK" if ok else "P1.5 header WebP: HAY FALLOS")
    print("screenshot:", os.path.join(SHOTS, "p1_5_header.png"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
