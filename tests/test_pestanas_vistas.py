"""Fase D: Reproducción, Leche y Sistema van en pestañas, y los atajos de los
KPI abren la pestaña donde está la sección a la que saltan."""
from pathlib import Path

JS = (Path(__file__).resolve().parent.parent / "src" / "pwa" / "static" / "app.js").read_text(encoding="utf-8")


def test_vistas_largas_usan_pestanas():
    for vista in ("repro", "leche", "sistema"):
        assert f'armarPestanas("{vista}", h, [' in JS


def test_marcas_tienen_su_pestana():
    import re
    for vista in ("repro", "leche", "sistema"):
        cuerpo = JS.split(f'armarPestanas("{vista}", h, [')[1].split("]);")[0]
        claves = set(re.findall(r'k: ?"([a-z]+)"', cuerpo))
        fn = {"repro": "function renderRepro", "leche": "function renderLeche",
              "sistema": "function renderSistema"}[vista]
        render = JS.split(fn)[1].split(f'armarPestanas("{vista}"')[0]
        marcas = set(re.findall(r'marcaPestana\("([a-z]+)"\)', render))
        assert marcas and marcas <= claves, (vista, marcas - claves)


def test_saltos_de_kpi_abren_la_pestana():
    ir = JS.split("function irASeccion")[1].split("function irADestinoKpi")[0]
    assert ir.count("mostrarPestanaDe(") >= 3


def test_registrar_agrupa_todos_los_tipos():
    import re
    lista = JS.split("function renderCaptura")[1].split("];")[0]
    tipos = set(re.findall(r'\{ id: "([a-z]+)", nom:', lista))
    bloque = JS.split("var GRUPOS_CAPTURA = [")[1].split("];")[0]
    agrupados = re.findall(r'"([a-z]+)"', "".join(re.findall(r"ids: \[([^\]]*)\]", bloque)))
    assert len(agrupados) == len(set(agrupados)), "un tipo está en dos grupos"
    assert tipos and tipos == set(agrupados), tipos ^ set(agrupados)
