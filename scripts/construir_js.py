"""Arma src/pwa/static/app.js a partir de los fragmentos de src/pwa/static/js/.

app.js es un solo IIFE ("(function () { ... })();") de ~15.000 líneas: todas
las funciones comparten variables del mismo ámbito. Para poder editarlo por
partes sin reescribir esas referencias ni volverlas globales, el código vive
en fragmentos ordenados (NN-nombre.js, sin el envoltorio) y este script los
concatena dentro del IIFE. El navegador sigue recibiendo un único app.js, así
que index.html, ficha.html, el service worker y la CSP no cambian.

Uso:
    python scripts/construir_js.py            # regenera app.js
    python scripts/construir_js.py --verificar  # falla si app.js no coincide
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_FRAGMENTOS = RAIZ / "src" / "pwa" / "static" / "js"
SALIDA = RAIZ / "src" / "pwa" / "static" / "app.js"

AVISO = (
    "/* GENERADO por scripts/construir_js.py desde src/pwa/static/js/*.js -- NO EDITAR ESTE ARCHIVO.\n"
    "   Edite el fragmento correspondiente y ejecute: python scripts/construir_js.py */\n"
)
CABECERA = (
    "/* Dashboard PWA Bitácora JA — JS vainilla (sin framework).\n"
    "   WS-3: KPIs, chips semáforo, skeleton, banner offline, polling 60s,\n"
    "   modo oscuro, errores visibles por sección y ficha con pestañas. */\n"
    "(function () {\n"
    '  "use strict";\n'
)
PIE = "})();\n"


def fragmentos() -> list[Path]:
    return sorted(DIR_FRAGMENTOS.glob("*.js"))


def construir(con_aviso: bool = True) -> str:
    cuerpo = "".join(f.read_text(encoding="utf-8") for f in fragmentos())
    return (AVISO if con_aviso else "") + CABECERA + cuerpo + PIE


def main(argv: list[str]) -> int:
    esperado = construir()
    if "--verificar" in argv:
        actual = SALIDA.read_text(encoding="utf-8") if SALIDA.exists() else ""
        if actual != esperado:
            print("app.js no coincide con src/pwa/static/js/: ejecute python scripts/construir_js.py")
            return 1
        print(f"app.js al día ({len(fragmentos())} fragmentos)")
        return 0
    SALIDA.write_text(esperado, encoding="utf-8")
    print(f"app.js generado desde {len(fragmentos())} fragmentos ({esperado.count(chr(10))} líneas)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
