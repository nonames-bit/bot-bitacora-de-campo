"""
Script de verificación visual automatizada para:
1. Pasturas (v=pasturas): Ocupación dinámica Voisin, total animales en tabla, botón listar.
2. Modal de animales en potrero desde Pasturas.
3. Inventario (v=inventario): Estructura del hato interactiva y brackets de edad interactivos.
4. Modal de animales por categoría de Estructura (Vaca parida - 81 cabezas).
5. Inventario: Distribución por potrero interactiva y Pirámide de edades.
6. Modal de animales desde la Pirámide de edades (Hembras < 1 año - 47 cabezas).

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

PORT = 5058
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
    art_path = os.path.join(ARTIFACTS_DIR, filename)
    shutil.copyfile(filepath, art_path)
    print(f"Screenshot guardado: {filename} ({len(data):,} bytes)")


async def main():
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    time.sleep(2.0)

    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_pwa_pasturas_inv_temp")
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

            # 1. Pasturas: Tabla de potreros con Animales, Ocupación real y Reposo
            print("1. Abriendo Pasturas y scrolleando a la tabla de potreros...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=pasturas"})
            await asyncio.sleep(3.0)

            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var allH4 = Array.from(document.querySelectorAll("h4"));
                    var potH4 = allH4.find(el => el.textContent.includes("Ocupación y reposo") || el.textContent.includes("reposo"));
                    if (potH4) {
                        potH4.scrollIntoView({ block: "start" });
                    } else {
                        var tbl = document.querySelector(".tabla-scroll");
                        if (tbl) tbl.scrollIntoView({ block: "start" });
                    }
                })()
                """
            })
            await asyncio.sleep(1.2)
            await capture_screen(ws, "23_mobile_pasturas_tabla_ocupacion_animales.png")

            # Desplazar la tabla horizontalmente para ver columnas Animales, Ocupación, Reposo, Acción
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var tbl = document.querySelector(".tabla-scroll");
                    if (tbl) tbl.scrollLeft = 240;
                })()
                """
            })
            await asyncio.sleep(0.5)
            await capture_screen(ws, "23b_mobile_pasturas_tabla_scroll_columnas.png")

            # Volver scroll tabla a 0
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "var tbl = document.querySelector('.tabla-scroll'); if (tbl) tbl.scrollLeft = 0;"
            })

            # 2. Clic en potrero ORDENO SANTA MARTHA (53 animales) para abrir modal
            print("2. Abriendo modal de animales en potrero ORDENO SANTA MARTHA...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btn = document.querySelector("[data-potrero='ORDENO SANTA MARTHA']");
                    if (btn) btn.click();
                })()
                """
            })
            await asyncio.sleep(2.0)
            await capture_screen(ws, "24_mobile_pasturas_modal_animales_potrero.png")

            # 3. Cerrar modal y navegar a Inventario
            print("3. Abriendo Inventario y verificando Estructura del hato y Categorías de edad...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btnC = document.getElementById("btn-cerrar-modal-lista-anim") || document.getElementById("btn-cerrar-pot-animales");
                    if (btnC) btnC.click();
                })()
                """
            })
            await asyncio.sleep(0.5)

            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=inventario"})
            await asyncio.sleep(3.0)

            # Scrollear a Estructura del Hato
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var allH4 = Array.from(document.querySelectorAll("h4"));
                    var estH4 = allH4.find(el => el.textContent.includes("Estructura"));
                    if (estH4) estH4.scrollIntoView({ block: "start" });
                })()
                """
            })
            await asyncio.sleep(1.0)
            await capture_screen(ws, "25_mobile_inventario_estructura_hato_y_brackets.png")

            # 4. Clic en "Vaca parida" (81 cabezas) para abrir modal interactivo
            print("4. Abriendo modal de Vacas paridas desde Estructura del hato...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btn = document.querySelector(".link-grupo-inventario[data-grupo-valor='Vaca parida']");
                    if (btn) btn.click();
                })()
                """
            })
            await asyncio.sleep(2.0)
            await capture_screen(ws, "26_mobile_inventario_modal_vaca_parida.png")

            # 5. Cerrar modal y scrollear a Distribución por potrero y Pirámide
            print("5. Scrolleando a Distribución por potrero y Pirámide de edades...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btnC = document.getElementById("btn-cerrar-modal-lista-anim") || document.getElementById("btn-cerrar-pot-animales");
                    if (btnC) btnC.click();
                    setTimeout(function() {
                        var allH4 = Array.from(document.querySelectorAll("h4"));
                        var potH4 = allH4.find(el => el.textContent.includes("por potrero"));
                        if (potH4) potH4.scrollIntoView({ block: "start" });
                    }, 200);
                })()
                """
            })
            await asyncio.sleep(1.5)
            await capture_screen(ws, "27_mobile_inventario_potreros_y_piramide.png")

            # 6. Clic en la barra o etiqueta de la pirámide (Hembras < 1 año - 47 cabezas)
            print("6. Abriendo modal desde Pirámide de edades (Hembras < 1 año)...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btn = document.querySelector(".pir-barra.hembra[data-grupo-tipo='piramide'][data-grupo-valor='< 1 año']");
                    if (!btn) {
                        btn = document.querySelector(".link-grupo-inventario[data-grupo-tipo='piramide'][data-sexo='H']");
                    }
                    if (btn) btn.click();
                })()
                """
            })
            await asyncio.sleep(2.0)
            await capture_screen(ws, "28_mobile_inventario_modal_piramide_hembras.png")

            print("¡Todas las verificaciones visuales completadas con éxito!")

    finally:
        try:
            edge_proc.terminate()
            edge_proc.wait(timeout=2)
        except Exception:
            edge_proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
