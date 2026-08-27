"""Pruebas de registro, consulta y vinculación de fotos de campo."""
import os
import pytest

from src.db.database import Database
from src.engine.query_engine import QueryEngine


def test_registrar_y_consultar_fotos(db):
    # Registrar un animal
    db.registrar_animal("47", nombre="Mariposa", sexo="Hembra")

    # Registrar foto asociada
    fid1 = db.registrar_foto(
        ruta="media/foto_47_1.jpg",
        animal_tag="47",
        fecha="2026-08-26",
        caption="Vaca 47 en corral",
        user_id=12345,
    )
    assert fid1 is not None

    # Registrar otra foto
    fid2 = db.registrar_foto(
        ruta="media/foto_47_2.jpg",
        animal_tag="47",
        fecha="2026-08-27",
        caption="Vaca 47 con ternero",
        user_id=12345,
    )
    assert fid2 is not None

    # Consultar fotos por tag
    fotos_47 = db.fotos_de("47")
    assert len(fotos_47) == 2
    assert fotos_47[0]["caption"] == "Vaca 47 con ternero"

    # Consultar últimas fotos generales
    ultimas = db.ultimas_fotos(5)
    assert len(ultimas) == 2


def test_query_engine_fotos(db):
    db.registrar_animal("12", nombre="Parda", sexo="Hembra")
    qe = QueryEngine(db)

    # Sin fotos
    resp_vacia = qe.responder("¿hay fotos de la 12?")
    assert "No hay fotos registradas" in resp_vacia

    # Con foto
    db.registrar_foto(
        ruta="media/foto_12.jpg",
        animal_tag="12",
        fecha="2026-08-26",
        caption="Parda en pastoreo",
    )
    resp = qe.responder("¿tienes fotos de la 12?")
    assert "1 foto(s) de la 12" in resp
    assert "/foto 12" in resp


def test_historial_incluye_fotos(db):
    db.registrar_animal("33", sexo="Hembra")
    db.registrar_foto(
        ruta="media/foto_33.jpg",
        animal_tag="33",
        caption="Celo AM",
    )
    h = db.historial("33")
    assert "fotos" in h
    assert len(h["fotos"]) == 1
