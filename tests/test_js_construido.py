"""app.js se genera desde src/pwa/static/js/ (scripts/construir_js.py).

Falla si alguien editó app.js directamente o cambió un fragmento sin
regenerarlo; también revisa la sintaxis de cada fragmento con node."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import construir_js  # noqa: E402


def test_app_js_coincide_con_fragmentos():
    actual = construir_js.SALIDA.read_text(encoding="utf-8")
    assert actual == construir_js.construir(), (
        "src/pwa/static/app.js no coincide con src/pwa/static/js/: edite los fragmentos "
        "y ejecute python scripts/construir_js.py")


@pytest.mark.skipif(shutil.which("node") is None, reason="node no está instalado")
def test_cada_fragmento_es_js_valido(tmp_path):
    for frag in construir_js.fragmentos():
        prueba = tmp_path / frag.name
        prueba.write_text("(function () {\n" + frag.read_text(encoding="utf-8") + "})();\n", encoding="utf-8")
        r = subprocess.run(["node", "--check", str(prueba)], capture_output=True, text=True)
        assert r.returncode == 0, f"{frag.name}: {r.stderr[:500]}"
