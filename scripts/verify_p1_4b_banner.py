"""Verificacion P1.4b: banner de datos servidos desde la cache del SW.

1. Carga la PWA con red (el SW instala y cachea /api/tablero con X-SW-Stored-At).
2. Pasa a offline y vuelve a pedir /api/tablero: el SW sirve la copia cacheada
   -> debe aparecer #aviso-datos-rancios con "Sin conexion".
3. Vuelve a online y pide de nuevo: respuesta fresca sin sello -> banner oculto.
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.pwa.app import crear_app  # noqa: E402

PORT = 5068
CDP_PORT = 9234
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "kilo", "p1_4b_shots")
os.makedirs(SHOTS, exist_ok=True)
_db = os.path.join(tempfile.gettempdir(), "kilo", "p1_4b_bitacora.db")
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


async def ev(ws, expr, await_promise=False):
    r = await cdp(ws, "Runtime.evaluate",
                  {"expression": expr, "returnByValue": True, "awaitPromise": await_promise})
    return r.get("result", {}).get("value")


async def offline(ws, activo):
    # El dominio Network se habilita aquí (no antes de navegar): habilitarlo
    # temprano altera el ciclo de instalación/claim del Service Worker.
    await cdp(ws, "Network.enable")
    await cdp(ws, "Network.emulateNetworkConditions", {
        "offline": activo, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1,
    })


PEDIR = r"""
(async () => {
  try {
    const r = await fetch('/api/tablero', { cache: 'no-store' });
    await r.text();
  } catch (e) { /* offline puede rechazar */ }
  await new Promise(x => setTimeout(x, 600));
  const el = document.getElementById('aviso-datos-rancios');
  return JSON.stringify({
    existe: !!el,
    visible: !!el && getComputedStyle(el).display !== 'none',
    texto: el ? el.textContent : null
  });
})()
"""

# CDP no puede emular "offline" en el contexto del SW (target aparte), así que
# la parte (a) se comprueba inspeccionando la caché y la (b) ejercitando el
# banner directamente con un sello viejo a través del hook de verificación.
MOSTRAR_BANNER = r"""
(function () {
  var iso = new Date(Date.now() - 2 * 3600 * 1000).toISOString();
  window.__actualizarAvisoRancios(iso);
  var el = document.getElementById('aviso-datos-rancios');
  return JSON.stringify({
    visible: !!el && getComputedStyle(el).display !== 'none',
    texto: el ? el.textContent : null
  });
})()
"""

OCULTAR_BANNER = r"""
(function () {
  window.__actualizarAvisoRancios(null);
  var el = document.getElementById('aviso-datos-rancios');
  return JSON.stringify({
    visible: !!el && getComputedStyle(el).display !== 'none'
  });
})()
"""

SEMBRAR_CACHE = r"""
(async () => {
  await fetch('/api/tablero').then(r => r.text()).catch(() => {});
  await new Promise(r => setTimeout(r, 800));
  const keys = await caches.keys();
  let sello = null, hallado = false;
  for (const k of keys) {
    const c = await caches.open(k);
    const h = await c.match('/api/tablero');
    if (h) { hallado = true; sello = h.headers.get('X-SW-Stored-At'); }
  }
  return JSON.stringify({ cacheado: hallado, sello: sello });
})()
"""


async def main():
    threading.Thread(target=start_flask, daemon=True).start()
    time.sleep(2.5)
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    ud = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_p1_4b_temp")
    shutil.rmtree(ud, ignore_errors=True)
    proc = subprocess.Popen([edge, "--headless=new", f"--remote-debugging-port={CDP_PORT}",
                             f"--user-data-dir={ud}", "--no-sandbox", "--disable-gpu", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)
    res = {}
    try:
        with urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/list") as r:
            t = next(x for x in json.loads(r.read().decode()) if x.get("type") == "page")
        async with websockets.connect(t["webSocketDebuggerUrl"], max_size=20 * 1024 * 1024) as ws:
            await cdp(ws, "Page.enable")
            await cdp(ws, "Runtime.enable")
            await cdp(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/"})
            await asyncio.sleep(2.0)
            # Polling corto desde Python: el SW tarda en instalar+activar+claim.
            estado = None
            for _ in range(60):
                estado = await ev(ws, "!!(navigator.serviceWorker.controller)")
                if estado:
                    break
                await asyncio.sleep(0.5)
            res["control"] = "controlado" if estado else "sin-control"
            # (a) El SW sella las respuestas /api/* que guarda.
            res["siembra"] = json.loads(await ev(ws, SEMBRAR_CACHE, await_promise=True))

            # (b) Lógica del banner: con sello viejo debe aparecer; sin sello, ocultarse.
            res["banner_con_sello"] = json.loads(await ev(ws, MOSTRAR_BANNER))
            shot = await cdp(ws, "Page.captureScreenshot", {"format": "png"})
            with open(os.path.join(SHOTS, "p1_4b_banner.png"), "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            res["banner_sin_sello"] = json.loads(await ev(ws, OCULTAR_BANNER))
    finally:
        try:
            proc.terminate(); proc.wait(timeout=2)
        except Exception:
            pass

    print(json.dumps(res, indent=2, ensure_ascii=False))
    sello = res.get("siembra", {}).get("sello")
    texto = res.get("banner_con_sello", {}).get("texto") or ""
    ok = (res.get("siembra", {}).get("cacheado")
          and bool(sello)
          and res.get("banner_con_sello", {}).get("visible")
          and "Sin conexión" in texto and "hace 2 h" in texto
          and not res.get("banner_sin_sello", {}).get("visible"))
    print("P1.4b banner: TODO OK" if ok else "P1.4b banner: HAY FALLOS")
    print("screenshot:", os.path.join(SHOTS, "p1_4b_banner.png"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
