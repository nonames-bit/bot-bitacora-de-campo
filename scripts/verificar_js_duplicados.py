#!/usr/bin/env python3
"""Puerta de calidad JS: detecta funciones duplicadas en el mismo ámbito (P2.8).

Motivo (incidente real 2026-09-10): una función `renderMercado()` quedó pegada
dos veces en `app.js`. ES5 permite redeclarar funciones en el mismo ámbito (gana
la última) SIN error, así que `node --check` (sintaxis) no lo detecta, y la PWA
quedó en blanco en producción.

Este chequeo cuenta la profundidad de llaves (ignorando strings, plantillas,
comentarios y regex) y marca `function <nombre>` repetido **en el mismo nivel de
profundidad**. En `src/pwa/static/*.js` todo cuelga de un único IIFE, así que el
nivel 1 es un mismo ámbito: un nombre repetido ahí es exactamente la clase del
incidente. Duplicados en ámbitos distintos (nivel ≥2) no se marcan.

Uso:  python scripts/verificar_js_duplicados.py
Exit 1 si hay duplicados.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS = sorted((RAIZ / "src" / "pwa" / "static").glob("*.js"))

_RE_FUNCTION = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)")
# Caracteres tras los cuales una `/` arranca una regex literal (no división).
_PREV_REGEX = set("(,=:[!&|?{};+-*%~^<>")
_PALABRA_REGEX = ("return", "typeof", "instanceof", "in", "of", "new", "delete",
                  "void", "case", "do", "else", "yield", "await")


def _limpiar(texto: str) -> tuple[str, list[int]]:
    """Devuelve el texto con strings/comentarios/regex en blanco y, por índice de
    carácter, la profundidad de llaves."""
    salida = list(texto)
    profundidades = []
    prof = 0
    i = 0
    n = len(texto)
    prev_sig = ""  # último carácter significativo (para decidir regex)
    while i < n:
        c = texto[i]
        if c == "/" and i + 1 < n and texto[i + 1] == "/":
            j = texto.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                salida[k] = " "
            i = j
            continue
        if c == "/" and i + 1 < n and texto[i + 1] == "*":
            j = texto.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                salida[k] = " "
            i = j
            continue
        if c in ('"', "'", "`"):
            comilla = c
            inicio = i
            i += 1
            while i < n:
                if texto[i] == "\\":
                    i += 2
                    continue
                if texto[i] == comilla:
                    i += 1
                    break
                if comilla == "`" and texto[i] == "$" and i + 1 < n and texto[i + 1] == "{":
                    # plantilla con interpolación: se conserva el contenido ${...}
                    # para no perder llaves/identificadores reales.
                    salida[i] = " "
                    salida[i + 1] = " "
                    i += 2
                    continue
                salida[i] = " "
                i += 1
            salida[inicio] = " "
            prev_sig = "`" if comilla == "`" else "x"
            continue
        if c == "/":
            # ¿regex o división?
            palabra_previa = re.search(r"([A-Za-z_$][\w$]*)\s*$", texto[:i])
            es_regex = (
                prev_sig in _PREV_REGEX
                or prev_sig == ""
                or (palabra_previa and palabra_previa.group(1) in _PALABRA_REGEX)
                or prev_sig in _PALABRA_REGEX
            )
            if es_regex:
                i += 1
                en_clase = False
                while i < n:
                    if texto[i] == "\\":
                        salida[i] = " "
                        i += 2
                        continue
                    if texto[i] == "[":
                        en_clase = True
                    elif texto[i] == "]":
                        en_clase = False
                    elif texto[i] == "/" and not en_clase:
                        salida[i] = " "
                        i += 1
                        break
                    elif texto[i] == "\n":
                        break
                    salida[i] = " "
                    i += 1
                prev_sig = "x"
                continue
        if c == "{":
            prof += 1
        elif c == "}":
            prof = max(0, prof - 1)
        if not c.isspace():
            prev_sig = c
        i += 1

    # profundidad por índice
    prof = 0
    for idx, ch in enumerate(salida):
        profundidades.append(prof)
        if ch == "{":
            prof += 1
        elif ch == "}":
            prof = max(0, prof - 1)
    return "".join(salida), profundidades


def buscar_duplicados(texto: str) -> list[str]:
    limpio, profundidades = _limpiar(texto)
    vistos: dict[tuple[int, str], int] = {}
    hallazgos: list[str] = []
    for m in _RE_FUNCTION.finditer(limpio):
        nombre = m.group(1)
        prof = profundidades[m.start()]
        if prof != 1:
            continue
        if (prof, nombre) in vistos:
            linea = limpio.count("\n", 0, m.start()) + 1
            prev = vistos[(prof, nombre)]
            hallazgos.append(
                f"'{nombre}' redeclarada en el mismo ámbito (nivel 1): línea {linea} (antes en {prev})"
            )
        else:
            vistos[(prof, nombre)] = limpio.count("\n", 0, m.start()) + 1
    return hallazgos


def main() -> int:
    hubo = False
    for ruta in ARCHIVOS:
        hallazgos = buscar_duplicados(ruta.read_text(encoding="utf-8"))
        if hallazgos:
            hubo = True
            print(f"[js] {ruta.relative_to(RAIZ)}:")
            for h in hallazgos:
                print("   - " + h)
    if hubo:
        print("[js] ABORTADO: función(es) duplicada(s) en el mismo ámbito "
              "(clase del incidente renderMercado del 2026-09-10).")
        return 1
    print(f"[js] OK -- {len(ARCHIVOS)} archivo(s) sin funciones duplicadas en el mismo ámbito.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
