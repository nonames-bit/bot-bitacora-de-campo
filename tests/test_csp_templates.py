"""Regresion de la guarda anti-onclick-inline (auditoria P0.3).

La CSP de produccion de la PWA (``script-src 'self'``, nginx) bloquea los
atributos de evento inline. El 2026-09-23 se encontraron 3 botones muertos por
esta causa. El chequeo vive en ``scripts/verificar_csp_templates.py`` y corre
en pre-push y CI; aqui se blinda con pytest.
"""
import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "verificar_csp_templates", RAIZ / "scripts" / "verificar_csp_templates.py"
)
csp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(csp)


def test_templates_actuales_sin_handlers_inline():
    hallazgos = []
    for ruta in csp.TEMPLATES:
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1):
            if csp.RE_HANDLER_INLINE.search(linea) or csp.RE_JAVASCRIPT_URL.search(linea):
                hallazgos.append(f"{ruta.relative_to(RAIZ)}:{n}")
    assert hallazgos == [], f"Handlers inline bloqueados por CSP: {hallazgos}"


def test_main_retorna_cero_con_templates_actuales():
    assert csp.main() == 0


def test_regex_detecta_handlers_y_no_da_falsos_positivos():
    # Detecta handlers inline reales
    assert csp.RE_HANDLER_INLINE.search('<button onclick="x()">')
    assert csp.RE_HANDLER_INLINE.search('<input onkeydown="y()">')
    assert csp.RE_HANDLER_INLINE.search('<span onchange = "z()">')
    assert csp.RE_JAVASCRIPT_URL.search('<a href="javascript:void(0)">')
    # NO confunde atributos normales ni clases/valores con "on"
    assert not csp.RE_HANDLER_INLINE.search('<meta content="width=device-width">')
    assert not csp.RE_HANDLER_INLINE.search('<button class="on">')
    assert not csp.RE_HANDLER_INLINE.search('<div data-on="x">')
    assert not csp.RE_HANDLER_INLINE.search('<div aria-label="on click">')
