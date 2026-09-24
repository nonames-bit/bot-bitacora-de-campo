#!/usr/bin/env python3
"""Guardas anti-onclick-inline en los templates de la PWA (auditoria P0.3).

Tras el incidente del 2026-09-10, la PWA se sirve en produccion con la CSP
``script-src 'self'`` (nginx). Los atributos de evento inline (``onclick=``,
``onchange=``, etc.) y las URLs ``javascript:`` NO se ejecutan bajo esa CSP:
el boton queda muerto sin error visible. El 2026-09-23 se encontraron 3
botones muertos por esta causa (menu de usuario del header y los modales
Deshacer/mas-modulos).

Este chequeo falla si reaparece cualquier handler inline en
``src/pwa/templates/*.html``. Se corre en ``.githooks/pre-push`` y en CI.

Uso:
    python scripts/verificar_csp_templates.py
Salida: lista de hallazgos ``archivo:linea``; exit 1 si hay alguno.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TEMPLATES = sorted(RAIZ.glob("src/pwa/templates/*.html"))

# Atributos de evento inline que la CSP script-src 'self' bloquea. Se ancla a
# un limite de palabra para NO confundir "content=" con "on...=".
_EVENTOS = (
    "click|dblclick|change|input|submit|reset|focus|blur|load|unload|error|"
    "scroll|resize|keydown|keyup|keypress|mouse[a-z]*|touch[a-z]*|pointer[a-z]*|"
    "drag[a-z]*|drop|contextmenu|animation[a-z]*|transition[a-z]*|wheel|select|"
    "toggle|play|pause|ended|invalid|search"
)
RE_HANDLER_INLINE = re.compile(rf"(?<![\w-])on(?:{_EVENTOS})\s*=", re.IGNORECASE)
RE_JAVASCRIPT_URL = re.compile(r"""(?:href|src)\s*=\s*["']javascript:""", re.IGNORECASE)


def main() -> int:
    hallazgos: list[str] = []
    for ruta in TEMPLATES:
        try:
            lineas = ruta.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            print(f"[csp] No se pudo leer {ruta}: {exc}", file=sys.stderr)
            return 2
        rel = ruta.relative_to(RAIZ).as_posix()
        for n, linea in enumerate(lineas, start=1):
            if RE_HANDLER_INLINE.search(linea) or RE_JAVASCRIPT_URL.search(linea):
                hallazgos.append(f"{rel}:{n}: {linea.strip()[:160]}")

    if hallazgos:
        print("[csp] ABORTADO: handler(s) inline en templates, bloqueados por la CSP")
        print("[csp] produccion (script-src 'self'). Migra a addEventListener().")
        for h in hallazgos:
            print("  - " + h)
        return 1

    print(f"[csp] OK -- {len(TEMPLATES)} template(s) sin handlers inline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
