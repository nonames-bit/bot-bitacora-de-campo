"""Regresión P2.11: `JA.chipEstado` no debe inyectar HTML sin escapar.

Antes, cualquier string que empezara con emoji semáforo (🟢/🟡/🔴/⚪) se
inyectaba CRUDO en el chip. `chipEstado` se alimenta con datos de la BD
(p. ej. `p.semaforo + " " + st` o el resultado de un diagnóstico), así que era
una vía de inyección de HTML. Ahora se conserva el emoji y se escapa el resto.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
JA_CORE = (RAIZ / "src" / "pwa" / "static" / "ja-core.js").as_posix()


def _node() -> str:
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node no disponible")
    return exe


def _chipEstado(valor_js: str) -> str:
    script = (
        "global.window={}; global.document={addEventListener:function(){}};"
        "require(%s);"
        "process.stdout.write(window.JA.chipEstado(%s));" % (json.dumps(JA_CORE), valor_js)
    )
    r = subprocess.run([_node(), "-e", script], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_chip_normal_mantiene_emoji_y_texto():
    assert _chipEstado("'🟢 ÓPTIMO'") == "<span class='chip verde'>🟢 ÓPTIMO</span>"


def test_chip_escapa_html_aunque_empiece_con_emoji():
    out = _chipEstado("'🟢 <img src=x onerror=alert(1)>'")
    assert "<img" not in out
    assert "&lt;img" in out


def test_chip_sin_emoji_escapa():
    out = _chipEstado("'hola & <b>x</b>'")
    assert "<b>" not in out
    assert "&lt;b&gt;" in out and "&amp;" in out


def test_chip_vacio():
    assert _chipEstado("null") == "<span class='chip gris'></span>"
