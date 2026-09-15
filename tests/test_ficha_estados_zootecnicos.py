# -*- coding: utf-8 -*-
"""Pruebas unitarias para estados fisiológicos y reproductivos zootécnicos."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.engine.dashboard_data import calcular_estados_zootecnicos


def test_calcular_estados_zootecnicos_vaca_recien_parida():
    """Vaca con parto reciente: Vaca en ordeño, Vacía/Abierta con DEL y días abiertos."""
    f = {
        "sexo": "Hembra",
        "edad_dias": 1500,
        "edad_str": "4 años",
        "tag": "VACA_01",
        "lactancia": {"del_dias": 20, "estado": "En ordeño"},
        "ultimo_parto": {"fecha": "2026-08-25"},
        "servicios": [],
        "diagnosticos": [],
    }
    res = calcular_estados_zootecnicos(f)
    assert res["fisiologico"]["codigo"] == "VACA_ORDENO"
    assert "En Ordeño" in res["fisiologico"]["badge"]
    assert res["reproductivo"]["codigo"] == "VACIA_SIN_PALPAR"
    assert res["reproductivo"]["dias_abiertos"] is not None
    assert res["reproductivo"]["color"] == "gris"


def test_calcular_estados_zootecnicos_vaca_servida():
    """Vaca inseminada después de parir: Servida sin palpar."""
    f = {
        "sexo": "Hembra",
        "edad_dias": 1800,
        "tag": "VACA_02",
        "lactancia": {"del_dias": 60, "estado": "En ordeño"},
        "ultimo_parto": {"fecha": "2026-07-01"},
        "servicios": [
            {"fecha": "2026-08-10", "fep_calculada": "2027-05-17", "toro_pajilla": "TORO_TEST"}
        ],
        "diagnosticos": [],
    }
    res = calcular_estados_zootecnicos(f)
    assert res["reproductivo"]["codigo"] == "SERVIDA_SIN_PALPAR"
    assert res["reproductivo"]["color"] == "ambar"


def test_calcular_estados_zootecnicos_vaca_prenada():
    """Vaca con diagnóstico positivo en ciclo vigente."""
    f = {
        "sexo": "Hembra",
        "edad_dias": 2000,
        "tag": "VACA_03",
        "lactancia": {"del_dias": 120, "estado": "En ordeño"},
        "ultimo_parto": {"fecha": "2026-05-01"},
        "servicios": [
            {"fecha": "2026-06-15", "fep_calculada": "2027-03-22", "toro_pajilla": "TORO_TEST"}
        ],
        "diagnosticos": [
            {"fecha": "2026-08-01", "resultado": "PREÑADA", "dias_gestacion": 47}
        ],
    }
    res = calcular_estados_zootecnicos(f)
    assert res["reproductivo"]["codigo"] == "PREÑADA"
    assert res["reproductivo"]["color"] == "verde"


def test_calcular_estados_zootecnicos_cria_ternero():
    """Macho menor a 1 año: Cría (Ternero)."""
    f = {
        "sexo": "Macho",
        "edad_dias": 30,
        "edad_str": "1 mes",
        "tag": "CRIA_M01",
    }
    res = calcular_estados_zootecnicos(f)
    assert res["fisiologico"]["codigo"] == "CRIA_MACHO"
    assert "Cría" in res["fisiologico"]["badge"]


def test_calcular_estados_zootecnicos_toro_reproductor():
    """Toro reproductor (código T01)."""
    f = {
        "sexo": "Macho",
        "edad_dias": 1500,
        "tag": "T01",
        "notas": "Toro reproductor de la finca",
    }
    res = calcular_estados_zootecnicos(f)
    assert res["fisiologico"]["codigo"] == "TORO"
    assert res["reproductivo"]["codigo"] == "TORO_REPRODUCTOR"


if __name__ == "__main__":
    test_calcular_estados_zootecnicos_vaca_recien_parida()
    test_calcular_estados_zootecnicos_vaca_servida()
    test_calcular_estados_zootecnicos_vaca_prenada()
    test_calcular_estados_zootecnicos_cria_ternero()
    test_calcular_estados_zootecnicos_toro_reproductor()
    print("ALL TESTS PASSED SUCCESSFULLY!")
