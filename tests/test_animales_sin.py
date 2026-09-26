"""'Animales sin…' (calidad de datos del hato): solo cuenta animales ACTIVOS."""
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.dashboard_data import (
    animales_por_grupo_inventario,
    datos_animales_sin,
    ids_animales_sin,
)

HOY = date(2026, 9, 26)


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "b.db")).create_tables()
    d.registrar_potrero(nombre="Guayabal", codigo="G1")
    d.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", potrero="Guayabal", fecha_nacimiento="2020-01-01", raza="Gyr")
    d.execute("UPDATE animales SET hierro = 'JA', color = 'Blanco', chip = '985' WHERE tag = 'V1'")
    d.registrar_animal("V2", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2021-01-01")
    d.registrar_animal("M1", sexo="Hembra", estado="MUERTO", fecha_nacimiento="2021-01-01")  # nunca cuenta
    # Parto reciente de V2 con cría registrada sin madre... y otro sin cría asociada
    d.registrar_parto("V1", fecha=(HOY - timedelta(days=40)).isoformat(), sexo_cria="Macho",
                      id_cria_tag="C1", peso_nacimiento=32)
    d.registrar_parto("V2", fecha=(HOY - timedelta(days=20)).isoformat(), sexo_cria="Hembra")
    d.execute("UPDATE animales SET estado = 'ACTIVO' WHERE tag = 'C1'")
    d.registrar_animal("C2", sexo="Macho", estado="ACTIVO", fecha_nacimiento=(HOY - timedelta(days=60)).isoformat())
    d.registrar_pesaje("V1", fecha=(HOY - timedelta(days=10)).isoformat(), peso_kg=450)
    d.registrar_foto(ruta="media/v1.jpg", animal_tag="V1")
    d.registrar_condicion_corporal("V1", fecha=(HOY - timedelta(days=5)).isoformat(), valor=3.0)
    yield d
    d.close()


def _tags(db, clave):
    ids = ids_animales_sin(db, clave, hoy=HOY)
    return sorted(r["tag"] for r in db.query("SELECT id_animal, tag FROM animales") if r["id_animal"] in ids)


def test_cada_chequeo_cuenta_solo_activos(db):
    assert _tags(db, "hierro") == ["C1", "C2", "V2"]
    assert _tags(db, "potrero") == ["C1", "C2", "V2"]    # C1 no hereda: Guayabal no tiene geometría
    assert _tags(db, "raza") == ["C1", "C2", "V2"]
    assert _tags(db, "foto") == ["C1", "C2", "V2"]
    assert _tags(db, "madre") == ["C2"]                  # C1 tiene madre por el parto
    assert _tags(db, "vacas_sin_cria") == ["V2"]
    assert _tags(db, "peso_nacer") == ["C2"]
    assert _tags(db, "pesaje") == ["C1", "C2", "V2"]
    assert _tags(db, "cc") == ["V2"]
    assert "M1" not in {t for c in ("hierro", "foto", "pesaje", "raza") for t in _tags(db, c)}


def test_datos_animales_sin_resumen(db):
    d = datos_animales_sin(db, hoy=HOY)
    assert d["total_activos"] == 4
    fila = next(f for f in d["filas"] if f["clave"] == "hierro")
    assert fila["total"] == 3 and fila["pct"] == 75.0


def test_drill_down_lista_los_animales(db):
    res = animales_por_grupo_inventario(db, tipo="sin", valor="vacas_sin_cria", hoy=HOY)
    assert [a["tag"] for a in res["animales"]] == ["V2"]
    assert res["titulo"] == "Animales sin: Vacas sin cría"


def test_api_inventario_incluye_animales_sin(db, tmp_path):
    from src.pwa.app import crear_app
    app = crear_app(str(tmp_path / "b.db"), password="clave")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave"})
    d = c.get("/api/inventario").get_json()
    assert "animales_sin" in d and d["animales_sin"]["filas"]
    lista = c.get("/api/inventario/animales?tipo=sin&valor=hierro").get_json()
    assert sorted(a["tag"] for a in lista["animales"]) == ["C1", "C2", "V2"]
