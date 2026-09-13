"""
Script de verificación visual automatizada para:
1. Sugerencia automática de tag de cría en Captura -> Parto (ej: JA457 -> JA457-6)
2. Ficha de JA218 con renderizado de Árbol Genealógico sin errores
3. Botón de eliminar eventos visible para OWNER
Emula viewport móvil iPhone 12/13/14 (390×844 DPR=2)
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

PORT = 5057
CDP_PORT = 9228

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
    # También copiar al directorio de artefactos
    art_path = os.path.join(ARTIFACTS_DIR, filename)
    shutil.copyfile(filepath, art_path)
    print(f"Screenshot guardado: {filename} ({len(data):,} bytes)")

async def main():
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    time.sleep(2.0)

    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_pwa_visual_new_temp3")
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

            # 1. Sugerencia de Cría en Parto
            print("1. Probando Captura -> Parto y sugerencia de cría...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=captura"})
            await asyncio.sleep(2.5)

            # Seleccionar Parto, avanzar a paso 2 y escribir JA457
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btnParto = document.querySelector("[data-cap-tipo='parto']");
                    if (btnParto) btnParto.click();
                    var bSig = document.getElementById("btn-cap-sig1");
                    if (bSig) bSig.click();
                    setTimeout(function() {
                        var inpTag = document.getElementById('cap-tag');
                        if (inpTag) {
                            inpTag.value = 'JA457';
                            inpTag.dispatchEvent(new Event('input', { bubbles: true }));
                            inpTag.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }, 400);
                })()
                """
            })
            await asyncio.sleep(1.5)
            await capture_screen(ws, "10_mobile_parto_sugerencia_cria.png")

            # 2. Ficha de JA218 con Árbol Genealógico
            print("2. Abriendo Ficha de JA218...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=ficha&tag=JA218"})
            # Esperar a que la ficha cargue completamente
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                new Promise((resolve) => {
                    var check = setInterval(() => {
                        var el = document.getElementById("ficha-tabs");
                        if (el) {
                            clearInterval(check);
                            resolve(true);
                        }
                    }, 200);
                    setTimeout(() => { clearInterval(check); resolve(false); }, 10000);
                })
                """,
                "awaitPromise": True
            })
            await asyncio.sleep(1.0)

            # Cambiar a la pestaña de Genealogía y scrollear al panel
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    if (typeof window.abrirTabFicha === 'function') {
                        window.abrirTabFicha('genealogia');
                    } else {
                        var b = document.querySelector("#ficha-tabs button[data-tab='genealogia']");
                        if (b) b.click();
                    }
                    setTimeout(function() {
                        var panel = document.getElementById('ficha-panel');
                        if (panel) panel.scrollIntoView({ block: 'start' });
                    }, 300);
                })()
                """
            })
            await asyncio.sleep(2.0)
            await capture_screen(ws, "11_mobile_ficha_ja218_genealogia.png")

            # 3. Tablero Últimos Eventos con botón eliminar visible
            print("3. Verificando botón de eliminar evento para OWNER en Tablero...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=tablero"})
            await asyncio.sleep(3.5)

            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var sec = document.getElementById('tabla-eventos-tablero') || document.querySelector('.tabla-eventos') || document.querySelector('.card');
                    if (sec) sec.scrollIntoView({ block: 'center' });
                })()
                """
            })
            await asyncio.sleep(1.5)
            await capture_screen(ws, "12_mobile_eventos_eliminar_owner.png")

            print("¡Capturas completadas con éxito!")

    finally:
        try:
            edge_proc.terminate()
            edge_proc.wait(timeout=2)
        except Exception:
            edge_proc.kill()

if __name__ == "__main__":
    asyncio.run(main())
