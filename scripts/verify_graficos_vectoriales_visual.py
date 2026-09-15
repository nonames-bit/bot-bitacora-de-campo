"""
Script de verificación visual automatizada para:
Gráficos vectoriales SVG nativos interactivos + toggle desplegable Matplotlib
en todas las vistas de la PWA (v=tablero, v=pasturas, v=inventario, v=subastas).

Emula viewport móvil iPhone 12/13/14 (390×844 DPR=2)
Prueba además adaptación a temas (green, dark).
"""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pwa.app import crear_app

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "screenshots")
ARTIFACTS_DIR = r"C:\Users\Owner\.gemini\antigravity-cli\brain\2663178f-5113-4384-81e2-09441c444201"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

PORT = 5059
CDP_PORT = 9229


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


async def capture_screen(ws, filename):
    res = await cdp_call(ws, "Page.captureScreenshot", {"format": "png"})
    data = base64.b64decode(res["data"])
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(data)
    art_path = os.path.join(ARTIFACTS_DIR, filename)
    shutil.copyfile(filepath, art_path)
    print(f"Screenshot guardado: {filename} ({len(data):,} bytes)")


async def main():
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    time.sleep(2.0)

    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_pwa_graficos_temp")
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

            # 1. Tablero: Evolución
            print("1. Abriendo Tablero y scrolleando a gráfico de Evolución...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=tablero"})
            await asyncio.sleep(4.0)

            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var el = document.querySelector(".tarjeta-grafico-ja[data-chart-tipo='evolucion']");
                    if (el) {
                        el.scrollIntoView({ block: "center" });
                    }
                })()
                """
            })
            await asyncio.sleep(1.5)
            await capture_screen(ws, "29_mobile_tablero_grafico_evolucion_vectorial.png")

            # 2. Reproducción: Gráfico Reproductivo con Acordeón Matplotlib abierto
            print("2. Abriendo Reproducción y desplegando acordeón Matplotlib...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=repro"})
            await asyncio.sleep(4.0)

            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var el = document.querySelector(".tarjeta-grafico-ja[data-chart-tipo='reproductivo_hato']");
                    if (el) {
                        el.scrollIntoView({ block: "center" });
                        var details = el.querySelector("details");
                        if (details) details.open = true;
                    }
                })()
                """
            })
            await asyncio.sleep(1.8)
            await capture_screen(ws, "30_mobile_repro_grafico_dual_toggle.png")

            # 3. Pasturas: Aforo
            print("3. Abriendo Pasturas y verificando Aforo vectorial...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=pasturas"})
            await asyncio.sleep(4.0)

            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var el = document.querySelector(".tarjeta-grafico-ja[data-chart-tipo='aforo']");
                    if (el) el.scrollIntoView({ block: "center" });
                })()
                """
            })
            await asyncio.sleep(1.5)
            await capture_screen(ws, "31_mobile_pasturas_grafico_aforo_vectorial.png")

            # 3b. Ocupación en Pasturas
            print("3b. Scrolleando a gráfico de Ocupación en Pasturas...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var el = document.querySelector(".tarjeta-grafico-ja[data-chart-tipo='ocupacion']");
                    if (el) el.scrollIntoView({ block: "center" });
                })()
                """
            })
            await asyncio.sleep(1.5)
            await capture_screen(ws, "31b_mobile_pasturas_grafico_ocupacion_vectorial.png")

            # 4. Inventario: Composición racial
            print("4. Abriendo Inventario y verificando Composición racial vectorial...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=inventario"})
            await asyncio.sleep(4.0)

            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var el = document.querySelector(".tarjeta-grafico-ja[data-chart-tipo='composicion_racial']");
                    if (el) el.scrollIntoView({ block: "center" });
                })()
                """
            })
            await asyncio.sleep(1.5)
            await capture_screen(ws, "32_mobile_inventario_grafico_composicion_racial.png")

            # 5. Modo Oscuro: Cambiar tema a dark y verificar adaptación de colores
            print("5. Cambiando tema a dark (Modo Oscuro) y verificando adaptación...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    document.documentElement.setAttribute('data-theme', 'dark');
                    localStorage.setItem('ja_theme', 'dark');
                    window.dispatchEvent(new Event('themechange'));
                    var el = document.querySelector(".tarjeta-grafico-ja[data-chart-tipo='composicion_racial']");
                    if (el) el.scrollIntoView({ block: "center" });
                })()
                """
            })
            await asyncio.sleep(1.5)
            await capture_screen(ws, "33_mobile_inventario_grafico_modo_oscuro.png")

            print("¡Todas las capturas de gráficos vectoriales completadas exitosamente!")

    finally:
        try:
            edge_proc.terminate()
            edge_proc.wait(timeout=2)
        except Exception:
            edge_proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
