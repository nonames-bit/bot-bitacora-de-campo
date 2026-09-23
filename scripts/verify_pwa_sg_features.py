"""
Script de verificación visual automatizada para:
1. Pasturas: Tablero Integral Unificado de Potreros (Voisin, Carga, Aforo y Biomasa) sin redundancias + Selector de Gráficos + Barra de descarga PDF/Excel.
2. Reproducción: Banco de Pajuelas de Semen + Termo Criogénico de Nitrógeno Líquido + Diagnósticos enriquecidos + Barra de descarga PDF/Excel.
3. Captura Rápida: Modal de Tacto / Palpación (Software Ganadero) con método (Manual vs Ecógrafo), resultado (P/V/D), días de gestación, FEP reactiva, hallazgos, CC y peso.
4. Ficha de Animal: Acceso directo a Palpación / Ecografía y tabla histórica detallada.

Emula viewport móvil iPhone (390×844 DPR=2) y escritorio (1280×800) según directrices de AGENTS.md.
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

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "screenshots_features")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PORT = 5068
CDP_PORT = 9235

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
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_features_visual_temp")
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
            await cdp_call(ws, "Page.enable")
            await cdp_call(ws, "Runtime.enable")

            # --- VISTA MÓVIL (390x844 DPR=2) ---
            print("\n=== CONFIGURANDO VIEWPORT MÓVIL (390×844 DPR=2) ===")
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

            # 1. Pasturas Móvil: Cabecera, descargas PDF/Excel y Selector de Gráficos
            print("1. Navegando a Pasturas (Móvil)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=pasturas"})
            await asyncio.sleep(3.0)
            shot_past1 = os.path.join(OUTPUT_DIR, "01_movil_pasturas_cabecera.png")
            await capture_screen(ws, shot_past1)

            # Scroll hacia el Tablero Integral Unificado de Potreros
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "window.scrollBy(0, 700);"
            })
            await asyncio.sleep(1.0)
            shot_past2 = os.path.join(OUTPUT_DIR, "02_movil_pasturas_tablero_integral.png")
            await capture_screen(ws, shot_past2)

            # 2. Reproducción Móvil: Cabecera, Banco de Semen & Termo Criogénico
            print("2. Navegando a Reproducción (Móvil)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=repro"})
            await asyncio.sleep(3.0)
            shot_repro1 = os.path.join(OUTPUT_DIR, "03_movil_reproduccion_banco_semen.png")
            await capture_screen(ws, shot_repro1)

            # Scroll hacia la tabla de diagnósticos enriquecidos
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "window.scrollBy(0, 600);"
            })
            await asyncio.sleep(1.0)
            shot_repro2 = os.path.join(OUTPUT_DIR, "04_movil_reproduccion_diagnosticos.png")
            await capture_screen(ws, shot_repro2)

            # 3. Captura Rápida: Modal de Tacto / Palpación (Software Ganadero)
            print("3. Navegando a Captura Rápida: Tacto / Palpación (Móvil)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=captura"})
            await asyncio.sleep(2.0)
            # Seleccionar tipo 'palpacion' y avanzar a paso 2
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btnP = document.querySelector("button[data-cap-tipo='palpacion']");
                    if (btnP) btnP.click();
                    var btnNext = document.getElementById("btn-cap-sig1");
                    if (btnNext) btnNext.click();
                })()
                """
            })
            await asyncio.sleep(1.5)
            # Rellenar con arete hembra de prueba para ver el cálculo reactivo de FEP
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var tagInp = document.getElementById("cap-tag");
                    if (tagInp) tagInp.value = "102";
                    var diasInp = document.getElementById("cap-palp-dias");
                    if (diasInp) {
                        diasInp.value = "60";
                        diasInp.dispatchEvent(new Event("input"));
                    }
                    var hallazgo = document.getElementById("cap-palp-hallazgo");
                    if (hallazgo) hallazgo.value = "CL derecho 24mm, embrión visible";
                    var resp = document.getElementById("cap-palp-responsable");
                    if (resp) resp.value = "Dr. Carlos Rodríguez";
                })()
                """
            })
            await asyncio.sleep(1.0)
            shot_cap_palp = os.path.join(OUTPUT_DIR, "05_movil_captura_palpacion_sg.png")
            await capture_screen(ws, shot_cap_palp)

            # Avanzar a paso 3 (Resumen antes de guardar)
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btnNext2 = document.getElementById("btn-cap-sig2");
                    if (btnNext2) btnNext2.click();
                })()
                """
            })
            await asyncio.sleep(1.0)
            shot_cap_prev = os.path.join(OUTPUT_DIR, "06_movil_captura_preview_palpacion.png")
            await capture_screen(ws, shot_cap_prev)

            # 4. Ficha de Vaca Hembra (Móvil)
            print("4. Navegando a Ficha de Animal (Móvil)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/#ficha/102"})
            await asyncio.sleep(2.5)
            # Abrir tab repro
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btnRepro = document.querySelector("#ficha-tabs button[data-tab='repro']");
                    if (btnRepro) btnRepro.click();
                })()
                """
            })
            await asyncio.sleep(1.5)
            shot_ficha = os.path.join(OUTPUT_DIR, "07_movil_ficha_repro_palpar_btn.png")
            await capture_screen(ws, shot_ficha)

            # --- VISTA ESCRITORIO (1280×800) ---
            print("\n=== CONFIGURANDO VIEWPORT ESCRITORIO (1280×800) ===")
            await cdp_call(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1280,
                "height": 800,
                "deviceScaleFactor": 1,
                "mobile": False
            })
            await cdp_call(ws, "Emulation.setTouchEmulationEnabled", {
                "enabled": False
            })

            print("5. Pasturas Escritorio...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=pasturas"})
            await asyncio.sleep(2.5)
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "window.scrollBy(0, 450);"
            })
            await asyncio.sleep(1.0)
            shot_desk_past = os.path.join(OUTPUT_DIR, "08_desktop_pasturas_tablero.png")
            await capture_screen(ws, shot_desk_past)

            print("6. Reproducción Escritorio...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=repro"})
            await asyncio.sleep(2.5)
            shot_desk_repro = os.path.join(OUTPUT_DIR, "09_desktop_reproduccion_termo_pajuelas.png")
            await capture_screen(ws, shot_desk_repro)

            print("\n✅ Verificación visual completada con éxito. Todos los screenshots generados en docs/screenshots_features/")

    finally:
        print("Cerrando Edge...")
        edge_proc.terminate()

if __name__ == "__main__":
    asyncio.run(main())
