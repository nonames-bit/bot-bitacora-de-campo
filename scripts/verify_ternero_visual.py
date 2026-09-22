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
ARTIFACTS_DIR = r"C:\Users\Owner\.gemini\antigravity-ide\brain\5cfa8489-8ead-449b-a023-ad119b7bb1d5"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

PORT = 5065
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

    print("Esperando a que Flask arranque...")
    flask_ready = False
    for i in range(40):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1) as resp:
                if resp.status == 200:
                    flask_ready = True
                    break
        except Exception:
            time.sleep(0.5)

    if not flask_ready:
        raise RuntimeError("Flask no arrancó a tiempo en el puerto " + str(PORT))
    print("Flask iniciado y listo en puerto", PORT)

    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_ternero_visual_temp5")
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
        v_url = f"http://127.0.0.1:{CDP_PORT}/json/list"
        targets = None
        for attempt in range(20):
            try:
                with urllib.request.urlopen(v_url, timeout=2) as r:
                    targets = json.loads(r.read().decode())
                    if targets:
                        break
            except Exception:
                time.sleep(0.5)

        if not targets:
            raise RuntimeError(f"No se pudo conectar a Edge CDP en {v_url}")
        
        target = next(t for t in targets if t.get("type") == "page")
        ws_url = target["webSocketDebuggerUrl"]
        print(f"Conectando a CDP: {ws_url}")

        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            # 1. Configuración de Viewport Móvil iPhone (390×844 DPR=2)
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

            # Navegar directamente a la ficha del ternero V068-6
            print("\n1. Navegando a la ficha del ternero V068-6 (Móvil 390x844)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=ficha&tag=V068-6"})
            await asyncio.sleep(3.0)

            test_api = await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                fetch('/api/ficha/V068-6').then(r => r.json()).then(d => ({ ok: true, tag: d.tag, existe: d.existe, cat: d.categoria_sg })).catch(e => ({ ok: false, error: e.toString() }))
                """,
                "awaitPromise": True,
                "returnByValue": True
            })
            print("Test /api/ficha/V068-6 desde browser:", json.dumps(test_api, indent=2))

            # Esperar a que renderice la ficha
            wait_res = await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                new Promise((resolve) => {
                    var check = setInterval(() => {
                        var el = document.querySelector(".ficha-head");
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
            print("Ficha montada:", wait_res)
            diag = await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    return {
                        title: document.title,
                        url: window.location.href,
                        vistaHtml: document.getElementById("vista") ? document.getElementById("vista").innerHTML.substring(0, 500) : "NO VISTA",
                        fTag: document.getElementById("f-tag") ? document.getElementById("f-tag").value : null
                    };
                })()
                """,
                "returnByValue": True
            })
            print("Diagnóstico de la página:", json.dumps(diag, indent=2))
            await asyncio.sleep(1.0)

            # Evaluar y verificar los elementos en el DOM
            eval_res = await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var headerImg = document.getElementById("header-vaca-img");
                    var headerSrc = headerImg ? headerImg.src : null;
                    var headerAlt = headerImg ? headerImg.alt : null;
                    var headerTitle = headerImg ? headerImg.title : null;
                    
                    var fichaHead = document.querySelector(".ficha-head");
                    var miniImg = fichaHead ? fichaHead.querySelector("img") : null;
                    var miniSrc = miniImg ? miniImg.src : null;
                    var miniContainer = miniImg ? miniImg.parentElement : null;
                    var miniTitle = miniContainer ? miniContainer.getAttribute("title") : null;

                    var tagText = document.querySelector(".ficha-head b") ? document.querySelector(".ficha-head b").innerText : null;

                    return {
                        headerSrc: headerSrc,
                        headerAlt: headerAlt,
                        headerTitle: headerTitle,
                        miniSrc: miniSrc,
                        miniTitle: miniTitle,
                        tagText: tagText
                    };
                })()
                """,
                "returnByValue": True
            })

            dom_data = eval_res.get("result", {}).get("value") or eval_res.get("value", {})
            print("Datos obtenidos de la página:", json.dumps(dom_data, indent=2, ensure_ascii=False))

            assert "ternero.gif" in str(dom_data.get("headerSrc")), f"Header src no tiene ternero.gif: {dom_data.get('headerSrc')}"
            assert "ternero.gif" in str(dom_data.get("miniSrc")), f"Miniatura src no tiene ternero.gif: {dom_data.get('miniSrc')}"
            assert "Ternero" in str(dom_data.get("miniTitle")), f"Miniatura title no tiene Ternero: {dom_data.get('miniTitle')}"
            print("VERIFICACION EXITOSA: ternero.gif activo en Header y en Ficha Miniatura!")

            # Tomar screenshot móvil de la Ficha del Ternero
            await capture_screen(ws, "ternero_ficha_movil.png")

            # 2. Probar Easter Egg en Header (tocar ternero en el header)
            print("\n2. Probando Easter Egg del ternero en el Header...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    if (typeof tocarVaquitaHeader === "function") tocarVaquitaHeader();
                })()
                """
            })
            await asyncio.sleep(0.5)

            bubble_res = await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var b = document.getElementById("vaca-bubble");
                    return {
                        visible: b ? (b.style.display !== "none") : false,
                        texto: b ? b.innerText : null
                    };
                })()
                """,
                "returnByValue": True
            })
            bubble_data = bubble_res.get("result", {}).get("value") or bubble_res.get("value", {})
            print("Resultado Easter Egg:", json.dumps(bubble_data, indent=2, ensure_ascii=False))

            await capture_screen(ws, "ternero_easter_egg_movil.png")

            # 3. Abrir ternera hembra JA415-6
            print("\n3. Navegando a ficha de ternera hembra JA415-6...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=ficha&tag=JA415-6"})
            await asyncio.sleep(3.0)
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                new Promise((resolve) => {
                    var check = setInterval(() => {
                        var el = document.querySelector(".ficha-head");
                        if (el && el.innerText.includes("JA415-6")) {
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
            await capture_screen(ws, "ternera_hembra_movil.png")

            # 4. Vista de escritorio (1280x800)
            print("\n4. Capturando vista de escritorio (1280x800)...")
            await cdp_call(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1280,
                "height": 800,
                "deviceScaleFactor": 1,
                "mobile": False
            })
            await asyncio.sleep(1.5)
            await capture_screen(ws, "ternero_ficha_desktop.png")

            print("\nTODAS LAS VERIFICACIONES VISUALES COMPLETADAS CON ÉXITO!")


    finally:
        try:
            edge_proc.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
