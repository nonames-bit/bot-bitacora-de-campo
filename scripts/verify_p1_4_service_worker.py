"""Verificacion P1.4 (Service Worker) en navegador real via CDP.

Comprueba:
  1. El SW registra e instala (precache no aborta).
  2. El precache no tiene URLs duplicadas (antes GIF/PNG con y sin ?v=).
  3. Una URL /api/...?t=<unico> (volatil) NO se cachea, pero /api/tablero normal SI.
"""
import asyncio
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

PORT = 5066
CDP_PORT = 9232
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_db_tmp = os.path.join(tempfile.gettempdir(), "kilo", "p1_4_bitacora.db")
os.makedirs(os.path.dirname(_db_tmp), exist_ok=True)
shutil.copyfile(os.path.join(RAIZ, "data", "bitacora.db"), _db_tmp)


def start_flask():
    app = crear_app(db_path=_db_tmp, users_file=os.path.join(RAIZ, "src", "server", "users.json"),
                    password="test-master-password")
    app.config["SESSION_COOKIE_SECURE"] = False

    from flask import session

    def test_auto_auth():
        session["autenticado"] = True
        session["rol"] = "OWNER"
        session["nombre"] = "Jaime"
        session["user_id"] = 1

    app.before_request_funcs.setdefault(None, []).insert(0, test_auto_auth)
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


async def cdp_call(ws, method, params=None, msg_id=[1]):
    mid = msg_id[0]
    msg_id[0] += 1
    await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == mid:
            return resp.get("result", {})


async def evaluate(ws, expr, await_promise=False):
    res = await cdp_call(ws, "Runtime.evaluate",
                         {"expression": expr, "returnByValue": True, "awaitPromise": await_promise})
    return res.get("result", {}).get("value"), res.get("exceptionDetails")


SCRIPT = r"""
(async () => {
  const reg = await navigator.serviceWorker.ready;
  const keys = await caches.keys();
  const cacheName = keys.filter(k => k.startsWith('pwa-ja-'))[0] || null;
  if (!cacheName) return JSON.stringify({error: 'sin cache pwa-ja'});
  const cache = await caches.open(cacheName);
  const reqs = await cache.keys();
  const paths = reqs.map(r => new URL(r.url).pathname + new URL(r.url).search);
  const norm = paths.map(p => p.split('?')[0]);
  const dup = norm.filter((v, i) => norm.indexOf(v) !== i);

  const tablaEnCacheAntes = norm.some(p => p === '/api/tablero');
  const uniqueTag = 't=' + Date.now() + '_' + Math.random().toString(36).slice(2);

  // Volatil: /api/tablero?t=<unico> NO debe cachearse
  try { await fetch('/api/tablero?' + uniqueTag); } catch (e) {}
  // Normal: /api/tablero (sin t) SI debe cachearse
  try { await fetch('/api/tablero'); } catch (e) {}
  await new Promise(r => setTimeout(r, 1200));

  const reqs2 = await cache.keys();
  const urls2 = reqs2.map(r => new URL(r.url).pathname + new URL(r.url).search);
  const volatilCacheado = urls2.some(u => u.includes(uniqueTag));
  const tablaCacheado = urls2.some(u => u === '/api/tablero');

  return JSON.stringify({
    cacheName,
    totalCache: norm.length,
    duplicados: dup,
    tablaEnCacheAntes,
    volatilCacheado,
    tablaCacheado
  });
})()
"""


async def main():
    print("1. Flask + Edge headless...")
    threading.Thread(target=start_flask, daemon=True).start()
    time.sleep(2.5)
    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_p1_4_temp")
    shutil.rmtree(user_data, ignore_errors=True)
    proc = subprocess.Popen([
        edge_bin, "--headless=new", f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={user_data}", "--no-sandbox", "--disable-gpu", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)

    datos = None
    try:
        with urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/list") as r:
            target = next(t for t in json.loads(r.read().decode()) if t.get("type") == "page")
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=20 * 1024 * 1024) as ws:
            await cdp_call(ws, "Page.enable")
            await cdp_call(ws, "Runtime.enable")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/"})
            await asyncio.sleep(5.0)  # registro + install + activate del SW
            val, exc = await evaluate(ws, SCRIPT, await_promise=True)
            if exc:
                print("EXCEPCION JS:", exc.get("text"))
            datos = json.loads(val) if val else {}
    finally:
        try:
            proc.terminate(); proc.wait(timeout=2)
        except Exception:
            pass

    print("2. Resultado:")
    print(json.dumps(datos, indent=2, ensure_ascii=False))
    ok = True

    def check(nombre, cond):
        nonlocal ok
        print(f"  [{'OK ' if cond else 'FALLO'}] {nombre}")
        ok = ok and cond

    check("SW activo y cache pwa-ja presente", bool(datos.get("cacheName")))
    check("precache sin URLs duplicadas", datos.get("duplicados") == [])
    check("API normal (/api/tablero sin t) SI se cachea", datos.get("tablaCacheado") is True)
    check("URL volatil (?t=) NO se cachea", datos.get("volatilCacheado") is False)
    print("P1.4: TODO OK" if ok else "P1.4: HAY FALLOS")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
