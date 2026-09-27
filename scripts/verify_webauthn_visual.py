"""
Verificación visual del login con huella / Face ID (WebAuthn) en la PWA.

Emula viewport móvil 390x844 DPR=2 con Edge Headless + CDP (mismo enfoque que
scripts/verify_carne_visual.py) sobre una base temporal con una credencial
sembrada, y valida:
  - el botón "Ingresar con huella / Face ID" aparece en /login,
  - el botón "Huella" del menú de perfil aparece (usuario autenticado),
  - no hay desborde horizontal en móvil.

Uso: python scripts/verify_webauthn_visual.py
"""
import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets  # noqa: E402

from src.db.database import Database  # noqa: E402
from src.pwa.app import crear_app  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "screenshots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PORT = 5072
CDP_PORT = 9227
DB_PATH = os.path.join(tempfile.gettempdir(), "verify_webauthn_visual.db")


def _seed(db_path: str) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    db = Database(db_path)
    db.create_tables()
    db.guardar_credencial_webauthn(
        credencial_id="verify-cred-1",
        clave_publica="dmVyaWZ5LXB1YmtleQ",
        user_id=None,
        nombre_usuario="Propietario",
        nombre_dispositivo="Dispositivo de verificación",
    )
    db.close()


def start_flask() -> None:
    app = crear_app(db_path=DB_PATH, users_file="src/server/users.json",
                    password="test-master-password")
    app.config["SESSION_COOKIE_SECURE"] = False

    from flask import session

    def auto_auth():
        session["autenticado"] = True
        session["rol"] = "OWNER"
        session["nombre"] = "Verificador"
        session["user_id"] = None

    if None in app.before_request_funcs:
        app.before_request_funcs[None].insert(0, auto_auth)
    else:
        app.before_request_funcs[None] = [auto_auth]

    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


async def cdp_call(ws, method, params=None, msg_id=[1]):
    mid = msg_id[0]
    msg_id[0] += 1
    await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == mid:
            return resp.get("result", {})


async def evaluar(ws, expr):
    res = await cdp_call(ws, "Runtime.evaluate",
                         {"expression": expr, "returnByValue": True})
    return res.get("result", {}).get("value")


async def capturar(ws, filepath) -> int:
    res = await cdp_call(ws, "Page.captureScreenshot", {"format": "png"})
    data = base64.b64decode(res["data"])
    with open(filepath, "wb") as f:
        f.write(data)
    return len(data)


async def main() -> int:
    _seed(DB_PATH)
    threading.Thread(target=start_flask, daemon=True).start()
    time.sleep(1.5)

    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_webauthn_visual_temp")
    edge = subprocess.Popen([
        edge_bin, "--headless=new", f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={user_data}", "--no-sandbox", "--disable-gpu", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)
    fallos = []
    try:
        with urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/list") as r:
            targets = json.loads(r.read().decode())
        target = next(t for t in targets if t.get("type") == "page")
        async with websockets.connect(target["webSocketDebuggerUrl"],
                                      max_size=20 * 1024 * 1024) as ws:
            await cdp_call(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True})
            await cdp_call(ws, "Page.enable")
            await cdp_call(ws, "Runtime.enable")
            # Stub de PublicKeyCredential: en headless no hay autenticador, pero
            # la lógica de visibilidad de la UI sí debe activarse.
            await cdp_call(ws, "Page.addScriptToEvaluateOnNewDocument", {
                "source": "window.PublicKeyCredential = window.PublicKeyCredential || function(){};"})

            # 1) Página de login
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/login"})
            await asyncio.sleep(3.0)
            raw = await evaluar(ws, """
(function(){
  var box = document.getElementById("box-huella-login");
  var t = document.body.innerText || "";
  return JSON.stringify({
    boxExiste: !!box,
    visible: !!(box && getComputedStyle(box).display !== "none"),
    texto: t.indexOf("Ingresar con huella") >= 0,
    overflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth)
  });
})()
""")
            ck = json.loads(raw)
            peso = await capturar(ws, os.path.join(OUTPUT_DIR, "webauthn_01_login_mobile.png"))
            print("Login DOM:", ck, "| screenshot", peso, "bytes")
            for k in ("boxExiste", "visible", "texto"):
                if not ck.get(k):
                    fallos.append(f"login:{k}")
            if ck.get("overflow", 0) > 2:
                fallos.append(f"login:overflow={ck['overflow']}")

            # 2) Menú de perfil (usuario autenticado)
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/"})
            await asyncio.sleep(4.0)
            # Se reintenta el clic por si la app aún no había enlazado el botón.
            for _ in range(3):
                await evaluar(ws, "(function(){ var b=document.getElementById('marca-header-btn'); if(b) b.click(); return true; })()")
                await asyncio.sleep(1.5)
                modal_disp = await evaluar(
                    ws, "(function(){ var m=document.getElementById('modal-menu-usuario'); return m?getComputedStyle(m).display:'no-modal'; })()")
                if modal_disp not in (None, "none", "no-modal"):
                    break
            raw2 = await evaluar(ws, """
(function(){
  var btn = document.getElementById("menu-btn-huella");
  var blo = document.getElementById("menu-huella-bloque");
  var m = document.getElementById("modal-menu-usuario");
  return JSON.stringify({
    modalAbierto: !!(m && getComputedStyle(m).display !== "none"),
    btnHuella: !!(btn && btn.offsetParent !== null),
    bloque: !!(blo && blo.offsetParent !== null),
    listado: !!(blo && (blo.textContent || "").indexOf("Acceso con huella") >= 0),
    overflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth)
  });
})()
""")
            ck2 = json.loads(raw2)
            peso2 = await capturar(ws, os.path.join(OUTPUT_DIR, "webauthn_02_menu_mobile.png"))
            print("Menú DOM:", ck2, "| screenshot", peso2, "bytes")
            for k in ("modalAbierto", "btnHuella", "bloque", "listado"):
                if not ck2.get(k):
                    fallos.append(f"menu:{k}")
            if ck2.get("overflow", 0) > 2:
                fallos.append(f"menu:overflow={ck2['overflow']}")
    finally:
        edge.terminate()

    if fallos:
        print("FALLOS:", ", ".join(fallos))
        return 1
    print("OK: UI de huella renderiza sin desborde en 390x844 DPR=2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
