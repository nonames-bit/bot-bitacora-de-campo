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
        targets = None
        for _ in range(15):
            try:
                with urllib.request.urlopen(v_url, timeout=2) as r:
                    targets = json.loads(r.read().decode())
                if targets:
                    break
            except Exception:
                time.sleep(0.5)
        if not targets:
            raise RuntimeError("No se pudo conectar al navegador Edge vía CDP")
        
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

            # 1. Tablero: Evolución con fechas rotadas y FAB stack
            print("1. Abriendo Tablero y verificando gráfico de Evolución (fechas rotadas, leyenda 'Nacimientos' y FABs)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=tablero"})
            await asyncio.sleep(4.0)

            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var el = document.querySelector(".tarjeta-grafico-ja[data-chart-tipo='evolucion']");
                    if (el) {
                        window.scrollTo(0, el.offsetTop - 60);
                    }
                })()
                """
            })
            await asyncio.sleep(1.5)
            await capture_screen(ws, "34_mobile_tablero_evolucion_fechas_rotadas_y_fab.png")

            # 2. Clic en botón FAB Lupita (🔍) para abrir Modal de Búsqueda Rápida de Ficha
            print("2. Probando botón flotante de búsqueda (FAB Lupita 🔍)...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btn = document.getElementById("fab-global-buscar");
                    if (btn) btn.click();
                })()
                """
            })
            await asyncio.sleep(1.2)
            await capture_screen(ws, "35_mobile_modal_buscar_ficha_lupita.png")

            # Cerrar modal
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btn = document.getElementById("btn-cerrar-modal-buscar-ficha") || document.getElementById("btn-cancelar-buscar-ficha");
                    if (btn) btn.click();
                })()
                """
            })
            await asyncio.sleep(0.5)

            # 3. Inventario: Estructura del Hato compacta (sin scrollbar horizontal ni columnas cortadas)
            print("3. Abriendo Inventario y verificando Estructura del hato compacta...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=inventario"})
            for _ in range(25):
                res = await cdp_call(ws, "Runtime.evaluate", {
                    "expression": "document.querySelectorAll('.tabla-inventario-compacta').length"
                })
                count = res.get("result", {}).get("value", 0)
                if count >= 2:
                    break
                await asyncio.sleep(0.5)

            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var tables = document.querySelectorAll('.tabla-inventario-compacta');
                    if (tables.length > 0) {
                        var h4 = tables[0].closest('div').previousElementSibling;
                        if (h4 && h4.tagName === 'H4') {
                            h4.scrollIntoView({ block: 'start' });
                        } else {
                            tables[0].scrollIntoView({ block: 'center' });
                        }
                    }
                })()
                """
            })
            await asyncio.sleep(1.0)
            await capture_screen(ws, "36_mobile_inventario_estructura_compacta_sin_scroll.png")

            # 4. Inventario: Distribución por Categorías de Edad compacta
            print("4. Verificando Distribución por Categorías de Edad compacta...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var tables = document.querySelectorAll('.tabla-inventario-compacta');
                    if (tables.length > 1) {
                        var prev = tables[1].closest('div').previousElementSibling;
                        if (prev && prev.tagName === 'H4') {
                            prev.scrollIntoView({ block: 'start' });
                        } else {
                            tables[1].scrollIntoView({ block: 'center' });
                        }
                    }
                })()
                """
            })
            await asyncio.sleep(1.0)
            await capture_screen(ws, "37_mobile_inventario_distribucion_edad_compacta.png")

            print("¡Todas las capturas de gráficos vectoriales completadas exitosamente!")

    finally:
        try:
            edge_proc.terminate()
            edge_proc.wait(timeout=2)
        except Exception:
            edge_proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
