"""Pruebas unitarias para el ciclo de vida de inventario de pajillas:
inactivación de catálogo histórico, alertas de stock activo, actualización
de estado y endpoints API /api/pajillas.
"""

from src.db.database import Database
from src.pwa.app import crear_app


def test_inactivacion_catalogo_historico(tmp_path):
    db_path = tmp_path / "test_pajillas.db"
    db = Database(str(db_path))
    db.create_tables()

    # Insertamos un registro con fecha antigua (< 2022) simulando el backup SG
    with db.conn:
        db.conn.execute(
            """
            INSERT INTO pajuelas_inventario (
                codigo_toro, raza, canastilla, cantidad, costo, fecha_ingreso, estado
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("TORO-HISTORICO", "Brahman", "SG-CANASTA", 0, 0, "2015-06-01", "ACTIVO"),
        )
        # Y uno reciente (>= 2022)
        db.conn.execute(
            """
            INSERT INTO pajuelas_inventario (
                codigo_toro, raza, canastilla, cantidad, costo, fecha_ingreso, estado
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("TORO-NUEVO", "Guzerat", "C-1", 10, 45000, "2024-01-15", "ACTIVO"),
        )

    # Marcamos el catálogo histórico
    db.marcar_pajuelas_historicas_inactivas()

    # El toro histórico con fecha 2015 debe estar INACTIVO
    inactivas = db.listar_pajuelas_inactivas()
    tags_inactivas = [p["codigo_toro"] for p in inactivas]
    assert "TORO-HISTORICO" in tags_inactivas

    # El toro nuevo debe permanecer ACTIVO
    activas = db.listar_pajuelas(solo_activas=True)
    tags_activas = [p["codigo_toro"] for p in activas]
    assert "TORO-NUEVO" in tags_activas
    assert "TORO-HISTORICO" not in tags_activas


def test_alertas_stock_filtran_inactivas(tmp_path):
    db_path = tmp_path / "test_alertas.db"
    db = Database(str(db_path))
    db.create_tables()

    # 1 activo con stock crítico (1 unid)
    db.registrar_pajuela("TORO-CRITICO", cantidad=1, raza="Nelore")

    # 1 histórico inactivo con 0 unids
    with db.conn:
        db.conn.execute(
            """
            INSERT INTO pajuelas_inventario (codigo_toro, cantidad, fecha_ingreso, estado)
            VALUES (?, ?, ?, ?)
            """,
            ("TORO-AGOTADO-VIEJO", 0, "2016-01-01", "INACTIVO"),
        )

    alertas = db.alertas_stock_pajuelas()
    toros_alertados = [a["codigo_toro"] for a in alertas]

    assert "TORO-CRITICO" in toros_alertados
    # No debe alertar por el toro histórico inactivo
    assert "TORO-AGOTADO-VIEJO" not in toros_alertados


def test_actualizar_estado_pajuela(tmp_path):
    db_path = tmp_path / "test_cambio_estado.db"
    db = Database(str(db_path))
    db.create_tables()

    db.registrar_pajuela("TORO-PRUEBA", cantidad=5, raza="Gyr")
    assert any(p["codigo_toro"] == "TORO-PRUEBA" for p in db.listar_pajuelas(solo_activas=True))

    # Inactivar
    ok = db.actualizar_estado_pajuela("TORO-PRUEBA", "INACTIVO")
    assert ok is True
    assert not any(p["codigo_toro"] == "TORO-PRUEBA" for p in db.listar_pajuelas(solo_activas=True))
    assert any(p["codigo_toro"] == "TORO-PRUEBA" for p in db.listar_pajuelas_inactivas())

    # Reactivar
    ok_re = db.actualizar_estado_pajuela("TORO-PRUEBA", "ACTIVO")
    assert ok_re is True
    assert any(p["codigo_toro"] == "TORO-PRUEBA" for p in db.listar_pajuelas(solo_activas=True))


def test_endpoints_api_pajillas(tmp_path):
    db_path = tmp_path / "test_api_pajillas.db"
    db = Database(str(db_path))
    db.create_tables()
    db.registrar_pajuela("TORO-API", cantidad=10, raza="Brahman")

    test_app = crear_app(db_path=str(db_path), password="clave-de-prueba")
    test_app.config["TESTING"] = True
    client = test_app.test_client()
    client.post("/login", data={"password": "clave-de-prueba"})

    # 1. GET /api/pajillas
    res = client.get("/api/pajillas")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "pajillas" in data
    assert "pajuelas" in data
    assert "inactivas" in data
    assert any(p["codigo_toro"] == "TORO-API" for p in data["pajillas"])

    # 2. POST /api/pajillas/estado para inactivar
    res_est = client.post("/api/pajillas/estado", json={"codigo_toro": "TORO-API", "estado": "INACTIVO"})
    assert res_est.status_code == 200
    data_est = res_est.get_json()
    assert data_est["ok"] is True
    assert data_est["estado"] == "INACTIVO"

    # Verificar que ahora está en inactivas
    res2 = client.get("/api/pajillas")
    data2 = res2.get_json()
    assert not any(p["codigo_toro"] == "TORO-API" for p in data2["pajillas"])
    assert any(p["codigo_toro"] == "TORO-API" for p in data2["inactivas"])
