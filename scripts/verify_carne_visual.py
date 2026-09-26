"""
Verificación visual de las vistas PWA "Carne" y "Reproducción" (gaps SG).

Emula viewport móvil 390x844 DPR=2 con Edge Headless + CDP (mismo enfoque
que scripts/verify_pwa_visual.py, AGENTS.md) sobre una base SQLite temporal
sembrada con datos mínimos, y valida:
  - la pestaña Carne y sus 5 secciones renderizan,
  - las 6 tarjetas nuevas de Reproducción renderizan,
  - los botones de navegación existen,
  - no hay desborde horizontal en móvil.

Uso: python scripts/verify_carne_visual.py
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
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets  # noqa: E402

from src.db.database import Database  # noqa: E402
from src.pwa.app import crear_app  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "screenshots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PORT = 5071
CDP_PORT = 9226
DB_PATH = os.path.join(tempfile.gettempdir(), "verify_carne_visual.db")


def _seed(db_path: str) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    db = Database(db_path)
    db.create_tables()
    db.registrar_potrero(nombre="GUAYABAL", codigo="G1")
    hoy = date.today()

    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO",
                        fecha_nacimiento="2020-01-01", potrero="GUAYABAL")
    db.registrar_animal("X1", sexo="Hembra", estado="ACTIVO",
                        fecha_nacimiento=(hoy - timedelta(days=210)).isoformat(),
                        madre_tag="V1", potrero="GUAYABAL")
    db.registrar_parto("V1", fecha=(hoy - timedelta(days=210)).isoformat(),
                       id_cria_tag="X1", peso_nacimiento=35)
    db.registrar_destete("X1", fecha=(hoy - timedelta(days=5)).isoformat(), peso_kg=190)

    db.registrar_animal("M1", sexo="Macho", estado="ACTIVO", fecha_nacimiento="2024-01-01")
    db.registrar_pesaje("M1", fecha=(hoy - timedelta(days=60)).isoformat(), peso_kg=200)
    db.registrar_pesaje("M1", fecha=(hoy - timedelta(days=1)).isoformat(), peso_kg=250)

    db.registrar_animal("S1", sexo="Hembra", estado="ACTIVO", potrero="GUAYABAL")
    db.registrar_parto("S1", fecha=(hoy - timedelta(days=200)).isoformat(), sexo_cria="Macho")
    db.registrar_animal("D1", sexo="Hembra", estado="ACTIVO", potrero="GUAYABAL")
    db.registrar_servicio("D1", fecha=(hoy - timedelta(days=300)).isoformat(),
                          tipo_servicio="IA", fep_calculada=(hoy - timedelta(days=17)).isoformat())
    db.registrar_animal("E1", sexo="Hembra", estado="ACTIVO", potrero="GUAYABAL")
    db.registrar_celo("E1", fecha=(hoy - timedelta(days=20)).isoformat())
    db.registrar_animal("T01", sexo="Macho", estado="ACTIVO", notas="[REPRODUCTOR]")
    db.registrar_servicio("V1", fecha=(hoy - timedelta(days=10)).isoformat(),
                          tipo_servicio="MONTA", toro_pajilla="T01")
    db.registrar_animal("C1", sexo="Hembra", estado="ACTIVO",
                        fecha_nacimiento="2020-01-01", potrero="GUAYABAL")
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
        session["user_id"] = 1

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


async def capture(ws, filepath) -> int:
    res = await cdp_call(ws, "Page.captureScreenshot", {"format": "png"})
    data = base64.b64decode(res["data"])
    with open(filepath, "wb") as f:
        f.write(data)
    return len(data)


async def evaluar(ws, expr):
    res = await cdp_call(ws, "Runtime.evaluate",
                         {"expression": expr, "returnByValue": True})
    return res.get("result", {}).get("value")


async def main() -> int:
    _seed(DB_PATH)
    threading.Thread(target=start_flask, daemon=True).start()
    time.sleep(1.5)

    edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "edge_carne_visual_temp")
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
            await cdp_call(ws, "Emulation.setTouchEmulationEnabled",
                           {"enabled": True, "maxTouchPoints": 5})
            await cdp_call(ws, "Page.enable")
            await cdp_call(ws, "Runtime.enable")

            # --- Vista Carne ---
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=carne"})
            await asyncio.sleep(4.0)
            raw = await evaluar(ws, """
(function(){
  var t = document.body.innerText || "";
  return JSON.stringify({
    titulo: t.indexOf("Carne (Pesajes") >= 0,
    sinPesar: t.indexOf("Animales sin pesar") >= 0,
    aPesar: t.indexOf("Animales a pesar por edad") >= 0,
    destete: t.indexOf("Destete / Índice productivo") >= 0,
    proyeccion: t.indexOf("Proyección de destetes") >= 0,
    prueba: t.indexOf("Prueba de comportamiento") >= 0,
    navBtn: !!document.querySelector("#nav-principal button[data-v='carne']"),
    sheetCarne: !!document.querySelector("#modal-mas-modulos .modulo-item[data-v='carne']"),
    formCarne: !!document.getElementById("form-carne-rango"),
    overflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth)
  });
})()
""")
            ck = json.loads(raw)
            peso = await capture(ws, os.path.join(OUTPUT_DIR, "carne_01_mobile.png"))
            print("Carne DOM:", ck, "| screenshot", peso, "bytes")
            for k in ("titulo", "sinPesar", "aPesar", "destete", "proyeccion", "prueba",
                      "navBtn", "sheetCarne", "formCarne"):
                if not ck.get(k):
                    fallos.append(f"carne:{k}")
            if ck.get("overflow", 0) > 2:
                fallos.append(f"carne:overflow={ck['overflow']}")

            # --- Vista Reproducción (gaps) ---
            await cdp_call(ws, "Page.navigate", {"url": f"http://127.0.0.1:{PORT}/?v=repro"})
            await asyncio.sleep(4.0)
            raw2 = await evaluar(ws, """
(function(){
  var t = document.body.innerText || "";
  return JSON.stringify({
    debieron: t.indexOf("debían haber parido") >= 0,
    sinProgramar: t.indexOf("Hembras sin programar") >= 0,
    celos: t.indexOf("Proyección de celos") >= 0,
    servicios: t.indexOf("Servicios realizados") >= 0,
    novillas: t.indexOf("Novillas entoradas") >= 0,
    reproductores: t.indexOf("Reproductores en servicio") >= 0,
    formRepro: !!document.getElementById("form-repro-rango-serv"),
    overflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth)
  });
})()
""")
            ck2 = json.loads(raw2)
            peso2 = await capture(ws, os.path.join(OUTPUT_DIR, "carne_02_mobile_repro.png"))
            print("Repro DOM:", ck2, "| screenshot", peso2, "bytes")
            for k in ("debieron", "sinProgramar", "celos", "servicios", "novillas",
                      "reproductores", "formRepro"):
                if not ck2.get(k):
                    fallos.append(f"repro:{k}")
            if ck2.get("overflow", 0) > 2:
                fallos.append(f"repro:overflow={ck2['overflow']}")
    finally:
        edge.terminate()

    if fallos:
        print("FALLOS:", ", ".join(fallos))
        return 1
    print("OK: vistas Carne y Reproducción renderizan sin desborde en 390x844 DPR=2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
