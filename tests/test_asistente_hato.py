"""Preguntas reales del Asistente IA sobre el hato presente (conteos por
categoría, estado reproductivo, listas de Tareas, leche del día y traslados).
Todas cuentan solo animales ACTIVOS, nunca partos ni animales históricos."""
from datetime import date, timedelta

import pytest

from src.engine.query_engine import QueryEngine

HOY = date(2026, 10, 24)


def _d(dias: int) -> str:
    return (HOY - timedelta(days=dias)).isoformat()


@pytest.fixture
def qe(db):
    db.registrar_potrero(nombre="Guayabal")
    db.registrar_potrero(nombre="La Loma")
    for i in range(1, 5):
        tag = f"V{i}"
        db.registrar_animal(tag, sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(2000))
        # Partos viejos con crías que ya no están: no deben contarse.
        db.registrar_parto(tag, fecha=_d(900), sexo_cria="Macho")
        db.registrar_parto(tag, fecha=_d(500), sexo_cria="Macho")
    db.registrar_diagnostico("V1", fecha=_d(10), resultado="PREÑADA", dias_gestacion=60)
    db.registrar_diagnostico("V2", fecha=_d(10), resultado="VACIA")
    db.registrar_animal("V9", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(2000))
    db.registrar_venta("V9", fecha=_d(5), precio=1)
    db.registrar_animal("C1", sexo="Macho", estado="ACTIVO", madre_tag="V1", fecha_nacimiento=_d(100))
    db.registrar_animal("C2", sexo="Hembra", estado="ACTIVO", madre_tag="V2", fecha_nacimiento=_d(100))
    db.registrar_animal("C3", sexo="Macho", estado="MUERTO", madre_tag="V3", fecha_nacimiento=_d(100))
    db.registrar_animal("N1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(900))
    db.registrar_animal("T1", nombre="TORO Rambo", sexo="Macho", estado="ACTIVO", fecha_nacimiento=_d(2000))
    db.registrar_traslado("C1", fecha=_d(3), potrero_origen="Guayabal", potrero_destino="La Loma")
    db.registrar_leche(None, fecha=_d(1), litros=120)
    db.registrar_leche(None, fecha=_d(2), litros=100)
    return QueryEngine(db, hoy=HOY)


def _numero(resp: str, titulo: str) -> str:
    negrita = resp.split(titulo, 1)[1].split("</b>", 1)[0]
    return negrita.rsplit(":", 1)[1].strip()


@pytest.mark.parametrize("pregunta, titulo, esperado", [
    ("cuantos terneros machos hay", "Terneros machos", "1"),
    ("cuantas terneras hay", "Terneras", "1"),
    ("cuantos terneros hay", "Terneros y terneras", "2"),
    ("cuantas vacas hay", "Vacas", "4"),
    ("cuantas novillas hay", "Novillas", "1"),
    ("cuantos toros hay", "Toros reproductores", "1"),
    ("cuantos machos hay", "Machos", "2"),
])
def test_conteos_por_categoria_solo_activos(qe, pregunta, titulo, esperado):
    resp = qe.responder(pregunta)
    assert "nacidas" not in resp and "No entendí" not in resp
    assert _numero(resp, titulo) == esperado


def test_vacas_prenadas_y_vacias(qe):
    resp = qe.responder("cuantas vacas preñadas hay")
    assert _numero(resp, "Vacas preñadas") == "1" and "V1" in resp
    resp = qe.responder("cuantas vacas vacias hay")
    assert "V2" in resp and "V1" not in resp.split("\n")[1]


def test_vacas_paridas_no_busca_potrero(qe):
    resp = qe.responder("vacas paridas hay?")
    assert "no existe" not in resp
    assert "Vacas en ordeño" in resp


@pytest.mark.parametrize("pregunta, titulo", [
    ("vacas a palapar", "Vacas para palpar"),
    ("vacas sin palpar", "Vacas para palpar"),
    ("animales a topizar", "Terneros para topizar"),
    ("cuantos terneros hay que castrar", "Terneros para castrar"),
    ("cuanatas novillas hay para entorar", "Novillas listas para servir"),
    ("animales a sincronizar", "Vacas para servir"),
    ("que tareas hay para hoy", "Tareas pendientes"),
])
def test_listas_de_tareas(qe, pregunta, titulo):
    resp = qe.responder(pregunta)
    assert titulo in resp or "ninguno por ahora" in resp or "No hay tareas" in resp
    assert "No hay registros para la" not in resp and "No entendí" not in resp


def test_tareas_asignadas_remite_a_pantalla(qe):
    resp = qe.responder("tareas completadas")
    assert "Tareas Asignadas al Equipo" in resp


def test_nacimientos_y_traslados_del_mes(qe):
    resp = qe.responder("animales que nacieron este mes")
    assert "Partos este mes" in resp or "No hubo partos" in resp
    resp = qe.responder("movimiento d epotreros este mes")
    assert "Traslados de potrero" in resp and "C1" in resp and "La Loma" in resp


def test_leche_del_hato(qe):
    resp = qe.responder("cuanta leche se produjo ayer")
    assert "120 litros" in resp
    resp = qe.responder("cual es la produccion de leche")
    assert "120 litros" in resp and "110 litros/día" in resp


def test_peso_y_dias_abiertos_de_un_animal(qe, db):
    db.registrar_pesaje("V3", fecha=_d(5), peso_kg=450)
    assert "450" in qe.responder("cuanto pesa la V3")
    resp = qe.responder("cuantos dias abiertos tiene la V3")
    assert "500 días abiertos" in resp
