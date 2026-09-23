"""
Script de verificación visual automatizada para:
1. Métricas zootécnicas de Software Ganadero (Índice de Fertilidad, Días Abiertos, IEP, DEL).
2. Modal interactivo de Últimos Eventos Registrados (Deshacer) con reversión inteligente.
Emula viewport móvil iPhone (390×844 DPR=2) y escritorio según AGENTS.md.
"""
import asyncio
import base64
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pwa.app import crear_app

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "screenshots_sg")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PORT = 5064
CDP_PORT = 9230

def start_flask():
    app = crear_app(
        db_path="data/bitacora.db",
        users_file="src/server/users.json",
        password="test-master-password"
    )
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
    req = {"id": mid, "method": method, "params": params or {}}
    await ws.send(json.dumps(req))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == mid:
            return resp.get("result", {})

async def capture_screen(ws, filepath):
    res = await cdp_call(ws, "Page.captureScreenshot", {"format": "png"})
    data = base64.b64decode(res["data"])
    with open(filepath, "wb") as f:
        f.write(data)
    print(f"Screenshot guardado: {filepath} ({len(data):,} bytes)")

async def main():
    print("1. Iniciando servidor Flask...")
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    time.sleep(2.0)

    print("2. Iniciando Edge Headless con CDP...")
    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_sg_visual_temp")
    edge_proc = subprocess.Popen([
        edge_bin,
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={user_data}",
        "--no-sandbox",
        "--disable-gpu",
        "about:blank"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)

    try:
        v_url = f"http://localhost:{CDP_PORT}/json/list"
        with urllib.request.urlopen(v_url) as r:
            targets = json.loads(r.read().decode())
        
        target = next(t for t in targets if t.get("type") == "page")
        ws_url = target["webSocketDebuggerUrl"]
        print(f"Conectando a CDP: {ws_url}")

        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            # Emulación Móvil 390x844 DPR=2
            await cdp_call(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 390,
                "height": 844,
                "deviceScaleFactor": 2,
                "mobile": True
            })
            await cdp_call(ws, "Emulation.setTouchEmulationEnabled", {
                "enabled": True,
                "maxTouchPoints": 5
            })
            await cdp_call(ws, "Page.enable")
            await cdp_call(ws, "Runtime.enable")

            # 1. Pestaña Reproducción (Móvil)
            print("Navegando a PWA y activando pestaña Reproducción (data-v='repro') (Móvil 390x844)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=repro"})
            await asyncio.sleep(2.5)
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btn = document.querySelector("button[data-v='repro']");
                    if (btn) btn.click();
                })()
                """
            })
            await asyncio.sleep(2.0)
            shot1 = os.path.join(OUTPUT_DIR, "01_mobile_reproduccion_sg.png")
            await capture_screen(ws, shot1)

            # Scroll a Días Abiertos y IEP
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "window.scrollBy(0, 360);"
            })
            await asyncio.sleep(1.0)
            shot1b = os.path.join(OUTPUT_DIR, "01b_mobile_reproduccion_da_iep.png")
            await capture_screen(ws, shot1b)

            # Scroll más abajo a IEP
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "window.scrollBy(0, 420);"
            })
            await asyncio.sleep(1.0)
            shot1c = os.path.join(OUTPUT_DIR, "01c_mobile_reproduccion_iep_detalle.png")
            await capture_screen(ws, shot1c)

            # 2. Pestaña Leche (Móvil)
            print("Navegando a ?v=leche (Móvil 390x844)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=leche"})
            await asyncio.sleep(3.0)
            # Scroll al panel de DEL
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "window.scrollBy(0, 300);"
            })
            await asyncio.sleep(0.8)
            shot2 = os.path.join(OUTPUT_DIR, "02_mobile_leche_del.png")
            await capture_screen(ws, shot2)

            # 3. Modal Últimos Eventos (Deshacer)
            print("Abriendo modal de Últimos Eventos (Deshacer)...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "window.mostrarModalUltimosEventos();"
            })
            await asyncio.sleep(1.5)
            shot3 = os.path.join(OUTPUT_DIR, "03_mobile_modal_deshacer.png")
            await capture_screen(ws, shot3)

            # 4. Escritorio (1280x800)
            print("Cambiando a resolución de Escritorio (1280x800)...")
            await cdp_call(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1280,
                "height": 800,
                "deviceScaleFactor": 1,
                "mobile": False
            })
            await asyncio.sleep(0.8)
            shot4 = os.path.join(OUTPUT_DIR, "04_desktop_modal_deshacer.png")
            await capture_screen(ws, shot4)

            # Cerrar modal y ver Reproducción en Desktop
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "var m = document.getElementById('modal-ultimos-eventos'); if (m) m.style.display = 'none';"
            })
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btn = document.querySelector("button[data-v='repro']");
                    if (btn) btn.click();
                })()
                """
            })
            await asyncio.sleep(2.0)
            shot5 = os.path.join(OUTPUT_DIR, "05_desktop_reproduccion_sg.png")
            await capture_screen(ws, shot5)

            print("¡Todas las capturas se guardaron exitosamente en docs/screenshots_sg!")

    finally:
        try:
            edge_proc.terminate()
            edge_proc.wait(timeout=2)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
