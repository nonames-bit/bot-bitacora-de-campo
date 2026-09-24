"""Verificacion funcional de P0.3 (botones que tenian onclick inline).

Los 3 botones migrados a `addEventListener` (bloqueados antes por la CSP
production `script-src 'self'`):
  1. `#marca-header-btn`  -> abre el menu de usuario (header).
  2. `#menu-btn-deshacer` -> cierra el menu y abre "Ultimos eventos".
  3. `#sheet-item-deshacer` -> cierra el sheet "mas modulos" y abre "Ultimos eventos".

Emula movil 390x844 DPR=2 (regla AGENTS.md) + escritorio, contra un Flask local
con auto-auth OWNER y una COPIA temporal de la DB (no toca datos reales).
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

PORT = 5065
CDP_PORT = 9231
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "kilo", "p0_3_shots")
os.makedirs(SHOTS, exist_ok=True)

_db_real = os.path.join(RAIZ, "data", "bitacora.db")
_db_tmp = os.path.join(tempfile.gettempdir(), "kilo", "p0_3_bitacora.db")
os.makedirs(os.path.dirname(_db_tmp), exist_ok=True)
shutil.copyfile(_db_real, _db_tmp)


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

    if None in app.before_request_funcs:
        app.before_request_funcs[None].insert(0, test_auto_auth)
    else:
        app.before_request_funcs[None] = [test_auto_auth]
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


async def cdp_call(ws, method, params=None, msg_id=[1]):
    mid = msg_id[0]
    msg_id[0] += 1
    await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == mid:
            return resp.get("result", {})


async def evaluate(ws, expr):
    res = await cdp_call(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return res.get("result", {}).get("value")


async def shot(ws, name):
    res = await cdp_call(ws, "Page.captureScreenshot", {"format": "png"})
    ruta = os.path.join(SHOTS, name)
    with open(ruta, "wb") as f:
        f.write(base64.b64decode(res["data"]))
    print(f"  screenshot: {ruta}")


SCRIPT = r"""
(function(){
  function vis(el){ return !!el && getComputedStyle(el).display !== 'none'; }
  var out = {};
  var menu = document.getElementById('modal-menu-usuario');
  var eventos = document.getElementById('modal-ultimos-eventos');
  var mas = document.getElementById('modal-mas-modulos');
  if (menu) menu.style.display='none';
  if (eventos) eventos.style.display='none';
  if (mas) mas.style.display='none';

  // 1) Header: marca -> abre menu usuario
  var btnMarca = document.getElementById('marca-header-btn');
  out.header_existe = !!btnMarca;
  if (btnMarca) btnMarca.click();
  out.header_abre_menu = vis(menu);

  // 2) Menu usuario: Deshacer -> cierra menu y abre eventos
  var btnDeshacer = document.getElementById('menu-btn-deshacer');
  out.menu_btn_existe = !!btnDeshacer;
  if (btnDeshacer) btnDeshacer.click();
  out.deshacer_menu_cierra = !vis(menu);
  out.deshacer_menu_abre_eventos = vis(eventos);

  if (eventos) eventos.style.display='none';
  if (menu) menu.style.display='none';

  // 3) Sheet mas modulos: Deshacer -> cierra sheet y abre eventos
  if (window.__abrirModalMas) window.__abrirModalMas();
  out.mas_abre = vis(mas);
  var btnSheet = document.getElementById('sheet-item-deshacer');
  out.sheet_btn_existe = !!btnSheet;
  if (btnSheet) btnSheet.click();
  out.deshacer_sheet_cierra = !vis(mas);
  out.deshacer_sheet_abre_eventos = vis(eventos);

  return JSON.stringify(out);
})()
"""


async def main():
    print("1. Iniciando Flask (copia temporal de la DB)...")
    threading.Thread(target=start_flask, daemon=True).start()
    time.sleep(2.5)

    print("2. Iniciando Edge headless + CDP...")
    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_p0_3_temp")
    proc = subprocess.Popen([
        edge_bin, "--headless=new", f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={user_data}", "--no-sandbox", "--disable-gpu", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)

    resultados = None
    try:
        with urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/list") as r:
            targets = json.loads(r.read().decode())
        target = next(t for t in targets if t.get("type") == "page")
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=20 * 1024 * 1024) as ws:
            await cdp_call(ws, "Emulation.setDeviceMetricsOverride",
                           {"width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True})
            await cdp_call(ws, "Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
            await cdp_call(ws, "Page.enable")
            await cdp_call(ws, "Runtime.enable")

            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/"})
            await asyncio.sleep(3.0)
            await evaluate(ws, "document.getElementById('modal-menu-usuario') && (document.getElementById('modal-menu-usuario').style.display='flex')")
            await asyncio.sleep(0.5)
            await shot(ws, "01_movil_menu_usuario.png")

            raw = await evaluate(ws, SCRIPT)
            resultados = json.loads(raw)
            await asyncio.sleep(0.5)
            await shot(ws, "02_movil_deshacer_eventos.png")

            await cdp_call(ws, "Emulation.setDeviceMetricsOverride",
                           {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False})
            await asyncio.sleep(0.8)
            await shot(ws, "03_desktop_deshacer.png")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass

    print("3. Resultados funcionales:")
    esperado = {
        "header_existe": True, "header_abre_menu": True,
        "menu_btn_existe": True, "deshacer_menu_cierra": True, "deshacer_menu_abre_eventos": True,
        "sheet_btn_existe": True, "mas_abre": True,
        "deshacer_sheet_cierra": True, "deshacer_sheet_abre_eventos": True,
    }
    ok = True
    for k, v in esperado.items():
        got = resultados.get(k)
        marca = "OK " if got == v else "FALLO"
        if got != v:
            ok = False
        print(f"  [{marca}] {k}: esperado={v} got={got}")
    print("P0.3: TODO OK" if ok else "P0.3: HAY FALLOS")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
