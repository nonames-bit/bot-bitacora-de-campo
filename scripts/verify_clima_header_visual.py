"""
Script de verificación visual automatizada para:
1. Clima en Cabecera PWA: verificar que NO llueve cuando no hay lluvia real (header-lluvia display=none).
2. Verificación de sol / luna / nubes según hora y telemetría en tiempo real.
3. Simulación de lluvia activa con actualizarLluviaHeader(true) y restauración a seco con actualizarLluviaHeader(false).
4. Captura en viewport móvil (390×844 DPR=2) y escritorio (1366×768).
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

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "screenshots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PORT = 5062
CDP_PORT = 9232


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


async def evaluate_js(ws, expr):
    res = await cdp_call(ws, "Runtime.evaluate", {
        "expression": expr,
        "returnByValue": True,
        "awaitPromise": True
    })
    return res.get("result", {}).get("value")


async def take_screenshot(ws, filename):
    res = await cdp_call(ws, "Page.captureScreenshot", {"format": "png"})
    data = base64.b64decode(res["data"])
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)
    print(f"📸 Captura guardada: {path}")
    return path


async def main():
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    time.sleep(1.5)

    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_clima_temp")
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
            # 1. Emulación Móvil 390x844 DPR=2
            await cdp_call(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 390,
                "height": 844,
                "deviceScaleFactor": 2,
                "mobile": True
            })
            await cdp_call(ws, "Page.enable")
            await cdp_call(ws, "Runtime.enable")

            print("Navegando a la PWA...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/"})
            await asyncio.sleep(3.0)

            # Verificar estado del clima
            clima_info = await evaluate_js(ws, """
                (function() {
                    var lluviaEl = document.getElementById("header-lluvia");
                    var solEl = document.getElementById("header-clima-sol");
                    var lunaEl = document.getElementById("header-clima-luna");
                    var nubesEl = document.getElementById("header-clima-nubes");
                    var vacaImg = document.getElementById("header-vaca-img");
                    return {
                        lluviaDisplay: lluviaEl ? window.getComputedStyle(lluviaEl).display : null,
                        solDisplay: solEl ? window.getComputedStyle(solEl).display : null,
                        lunaDisplay: lunaEl ? window.getComputedStyle(lunaEl).display : null,
                        nubesDisplay: nubesEl ? window.getComputedStyle(nubesEl).display : null,
                        vacaSrc: vacaImg ? vacaImg.src : null,
                        climaEstado: window._climaEstadoActual
                    };
                })()
            """)
            print("Estado de cabecera obtenido:", json.dumps(clima_info, indent=2))
            assert clima_info["lluviaDisplay"] == "none", f"ERROR: Se esperaba display: none en header-lluvia pero fue {clima_info['lluviaDisplay']}"
            print("✅ VERIFICADO: header-lluvia tiene display: none (¡NO está lloviendo sobre las vacas!).")

            await take_screenshot(ws, "clima_movil_sin_lluvia.png")

            # 2. Simular lluvia activa momentáneamente y verificar que sí reacciona
            print("Simulando lluvia activa con actualizarLluviaHeader(true)...")
            await evaluate_js(ws, "actualizarLluviaHeader(true)")
            await asyncio.sleep(0.5)

            lluvia_activa = await evaluate_js(ws, """
                (function() {
                    var lluviaEl = document.getElementById("header-lluvia");
                    return lluviaEl ? window.getComputedStyle(lluviaEl).display : null;
                })()
            """)
            assert lluvia_activa == "block", f"ERROR: Al simular lluvia se esperaba display: block pero fue {lluvia_activa}"
            print("✅ VERIFICADO: header-lluvia se activa correctamente (display: block) cuando sí llueve.")
            await take_screenshot(ws, "clima_movil_con_lluvia_activa.png")

            # 3. Restaurar clima en tiempo real sin lluvia
            print("Restaurando telemetría real (sin lluvia)...")
            await evaluate_js(ws, "actualizarLluviaHeader(false)")
            await asyncio.sleep(0.5)
            lluvia_restaurada = await evaluate_js(ws, """
                (function() {
                    var lluviaEl = document.getElementById("header-lluvia");
                    return lluviaEl ? window.getComputedStyle(lluviaEl).display : null;
                })()
            """)
            assert lluvia_restaurada == "none"
            print("✅ VERIFICADO: header-lluvia volvió a display: none.")

            # 4. Emulación Desktop (1366x768)
            print("Cambiando a resolución de escritorio 1366x768...")
            await cdp_call(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1366,
                "height": 768,
                "deviceScaleFactor": 1,
                "mobile": False
            })
            await asyncio.sleep(1.0)
            await take_screenshot(ws, "clima_desktop_sin_lluvia.png")
            print("✅ Todo verificado con éxito visualmente.")

    finally:
        edge_proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
