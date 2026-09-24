"""Guarda de funciones JS duplicadas (P2.8, incidente renderMercado 2026-09-10).

`node --check` no detecta funciones redeclaradas en el mismo ámbito (ES5 las
permite y gana la última), que fue lo que tumbó la PWA en producción. El
chequeo real vive en `scripts/verificar_js_duplicados.py` (pre-push + CI); aquí
se blinda con pytest y se fija su comportamiento.
"""
import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "verificar_js_duplicados", RAIZ / "scripts" / "verificar_js_duplicados.py"
)
dup = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dup)


def test_archivos_pwa_actuales_sin_duplicados_en_mismo_ambito():
    problemas = {}
    for ruta in dup.ARCHIVOS:
        hallazgos = dup.buscar_duplicados(ruta.read_text(encoding="utf-8"))
        if hallazgos:
            problemas[str(ruta.relative_to(RAIZ))] = hallazgos
    assert problemas == {}, f"Funciones duplicadas en el mismo ámbito: {problemas}"


def test_main_retorna_cero():
    assert dup.main() == 0


def test_detecta_duplicado_de_nivel_1():
    src = (
        "(function(){\n"
        "  function renderMercado(){ return 1; }\n"
        "  function renderMercado(){ return 2; }\n"
        "})();\n"
    )
    assert dup.buscar_duplicados(src)


def test_no_marca_mismo_nombre_en_ambitos_anidados_distintos():
    src = (
        "(function(){\n"
        "  function a(){ function x(){ return 1; } return x(); }\n"
        "  function b(){ function x(){ return 2; } return x(); }\n"
        "})();\n"
    )
    assert dup.buscar_duplicados(src) == []


def test_ignora_llaves_en_regex_y_strings():
    src = (
        "(function(){\n"
        '  var re = /[{}]/g;\n'
        '  var s = "function falso(){}";\n'
        "  function unica(){ return re.test(s); }\n"
        "})();\n"
    )
    assert dup.buscar_duplicados(src) == []
