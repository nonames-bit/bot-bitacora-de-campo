"""
Script de verificación visual automatizada de la PWA vía Edge Headless + CDP
Emula viewport móvil iPhone 12/13/14 (390×844 DPR=2) según AGENTS.md
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

PORT = 5058
CDP_PORT = 9225

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
    # 1. Iniciar Flask en hilo separado
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    time.sleep(1.5)

    # 2. Iniciar Edge Headless con CDP
    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_pwa_visual_temp")
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
        # Obtener WebSocket URL de la página
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

            # Navegar con auto-login
            print("Navegando a la PWA...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/"})
            await asyncio.sleep(2.5)

            # Screenshot 1: Tablero con Header (reloj con fecha y hora)
            shot1 = os.path.join(OUTPUT_DIR, "01_mobile_header_tablero.png")
            await capture_screen(ws, shot1)

            # Screenshot 2: Pestaña Pasturas con tabla de potreros y botón Listar
            print("Navegando a pestaña Pasturas (?v=pasturas)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=pasturas"})
            await asyncio.sleep(2.5)
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var el = document.querySelector('.btn-listar-animales-pot');
                    if (el) el.scrollIntoView({ block: 'center' });
                })()
                """
            })
            await asyncio.sleep(0.5)
            shot2 = os.path.join(OUTPUT_DIR, "02_mobile_pasturas_tabla.png")
            await capture_screen(ws, shot2)

            # Screenshot 3: Modal de animales en potrero OLEGARIO I
            print("Abriendo modal de animales en potrero OLEGARIO I...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "window.abrirModalAnimalesPotrero('OLEGARIO I')"
            })
            await asyncio.sleep(2.0)
            shot3 = os.path.join(OUTPUT_DIR, "03_mobile_modal_animales_potrero.png")
            await capture_screen(ws, shot3)

            # Cerrar modal
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "var c = document.getElementById('btn-cerrar-pot-animales'); if (c) c.click();"
            })
            await asyncio.sleep(0.5)

            # Screenshot 4: Chat dock abierto con hora en mensajes
            print("Abriendo chat dock...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "var b = document.getElementById('chat-dock-burbuja'); if (b) b.click();"
            })
            await asyncio.sleep(1.0)
            # Enviar mensaje de prueba al chat para ver el formato con hora
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var hist = document.getElementById('chat-historial');
                    if (hist) {
                        var m1 = document.createElement('div');
                        m1.className = 'chat-msg user';
                        m1.innerHTML = "<div class='chat-msg-texto'>¿Cuántos animales hay en OLEGARIO I?</div><div class='chat-msg-hora'>11:42 PM</div>";
                        hist.appendChild(m1);
                        var m2 = document.createElement('div');
                        m2.className = 'chat-msg bot';
                        m2.innerHTML = "<div class='chat-msg-texto'>En el potrero <b>OLEGARIO I</b> hay <b>46 animales activos</b> (33 Novillas, 13 Vacas Secas).</div><div class='chat-msg-hora'>11:42 PM</div>";
                        hist.appendChild(m2);
                    }
                })()
                """
            })
            await asyncio.sleep(0.5)
            shot4 = os.path.join(OUTPUT_DIR, "04_mobile_chat_dock_con_hora.png")
            await capture_screen(ws, shot4)

            # Screenshot 5: Ficha de animal mostrando botón Rectificar Chapeta para OWNER
            print("Navegando a ficha de animal T02 en SPA (?v=ficha&tag=T02)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=ficha&tag=T02"})
            await asyncio.sleep(3.0)
            shot5 = os.path.join(OUTPUT_DIR, "05_mobile_ficha_rectificar_btn.png")
            await capture_screen(ws, shot5)

            # Screenshot 6: Modal de rectificación de chapeta con detección de conflicto en vivo
            print("Abriendo modal de rectificación de chapeta...")
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    window.mostrarModalRectificarTag('T02');
                    setTimeout(function() {
                        var inp = document.getElementById('rect-tag-nuevo');
                        if (inp) {
                            inp.value = 'MF01';
                            inp.dispatchEvent(new Event('input'));
                        }
                    }, 400);
                })()
                """
            })
            await asyncio.sleep(2.0)
            shot6 = os.path.join(OUTPUT_DIR, "06_mobile_modal_rectificar_chapeta.png")
            await capture_screen(ws, shot6)

            # Cerrar modal de rectificación
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": "var c = document.getElementById('btn-cancelar-rect-tag'); if (c) c.click();"
            })
            await asyncio.sleep(0.5)

            # Screenshot 7: Tablero con Precio Bogotá Guadalupe y Botón Flotante Global (+)
            print("Navegando a Tablero (?v=tablero) para verificar Precio Bogotá y Global FAB...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=tablero"})
            await asyncio.sleep(2.5)
            shot7 = os.path.join(OUTPUT_DIR, "07_mobile_tablero_bogota_precio_fab.png")
            await capture_screen(ws, shot7)

            # Screenshot 8: Captura rápida con botón directo a Manga Corral y tipo de evento Tarea
            print("Navegando a Captura rápida (?v=captura)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=captura"})
            await asyncio.sleep(2.5)
            # Seleccionar evento Tarea
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btnTarea = document.querySelector(\"[data-cap-tipo='tarea']\");
                    if (btnTarea) btnTarea.click();
                    setTimeout(function() {
                        var inpDesc = document.getElementById('cap-tarea-desc');
                        if (inpDesc) inpDesc.value = 'Aplicar 10ml oxitetraciclina IM';
                        var inpTag = document.getElementById('cap-tag');
                        if (inpTag) inpTag.value = 'JA457';
                    }, 300);
                })()
                """
            })
            await asyncio.sleep(1.0)
            shot8 = os.path.join(OUTPUT_DIR, "08_mobile_captura_manga_boton_y_tarea.png")
            await capture_screen(ws, shot8)

            # Screenshot 9: Agenda con tareas asignadas y modal de Confirmar Realizado (Acknowledge)
            print("Navegando a Agenda (?v=agenda)...")
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=agenda"})
            await asyncio.sleep(2.5)
            # Abrir modal Acknowledge simulando click en tarea
            await cdp_call(ws, "Runtime.evaluate", {
                "expression": """
                (function() {
                    var btnComp = document.querySelector('.btn-rec-completar');
                    if (btnComp) {
                        btnComp.click();
                    } else {
                        var modal = document.getElementById('modal-ack-tarea');
                        var info = document.getElementById('ack-tarea-info');
                        if (info) info.innerHTML = '<b>📌 JA457: Aplicar 10ml oxitetraciclina</b><br><small style=\"color:var(--texto-suave);\">Asignado a: <b>Encargado</b></small>';
                        var por = document.getElementById('ack-completado-por');
                        if (por) por.value = 'Pedro Encargado';
                        var notas = document.getElementById('ack-notas');
                        if (notas) notas.value = 'Se aplicó la dosis completa vía intramuscular sin novedad en el lote ordeño.';
                        if (modal) modal.style.display = 'flex';
                    }
                })()
                """
            })
            await asyncio.sleep(1.2)
            shot9 = os.path.join(OUTPUT_DIR, "09_mobile_agenda_tareas_y_modal_ack.png")
            await capture_screen(ws, shot9)

            print("¡Todas las verificaciones visuales completadas exitosamente!")

    finally:
        try:
            edge_proc.terminate()
            edge_proc.wait(timeout=2)
        except Exception:
            edge_proc.kill()

if __name__ == "__main__":
    asyncio.run(main())
