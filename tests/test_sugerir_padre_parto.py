"""Pruebas unitarias para la sugerencia automática de padre en partos y chips de monta natural."""
import pytest
from datetime import date, timedelta
from src.db.database import Database
from src.pwa.app import crear_app


@pytest.fixture
def db(tmp_path):
    """Base de datos en memoria/temporal para tests aislados."""
    db_file = tmp_path / "test_bitacora.db"
    d = Database(str(db_file))
    d.create_tables()
    # Crear potreros
    p1 = d.insert("potreros", {"nombre": "POTRERO MATERNIDAD"})
    p2 = d.insert("potreros", {"nombre": "ORDENO SANTA MARTHA"})
    p3 = d.insert("potreros", {"nombre": "LOTE REPRODUCCION"})
    return d


def test_sugerir_padre_por_servicio_previo(db):
    """Si hay un servicio registrado en la ventana de 283 +/- 15 días, sugiere ese toro."""
    # Crear vaca y toro
    vaca_id = db.resolve_animal("VACA01", crear=True, sexo="Hembra")
    toro_id = db.resolve_animal("T01", crear=True, sexo="Macho", nombre="BRUNO")

    # Registrar servicio 280 días antes
    f_parto = date.today()
    f_servicio = f_parto - timedelta(days=280)
    db.registrar_servicio(
        vaca_tag="VACA01",
        fecha=f_servicio.isoformat(),
        tipo_servicio="MONTA",
        toro_pajilla="T01",
    )

    res = db.sugerir_padre_parto("VACA01", f_parto.isoformat())
    assert res["ok"] is True
    assert res["sugerencia"] is not None
    sug = res["sugerencia"]
    assert sug["toro_tag"] == "T01"
    assert sug["metodo"] == "SERVICIO_REGISTRADO"
    assert sug["tipo_servicio"] == "MONTA"
    assert sug["confianza"] == "MUY_ALTA"
    assert "BRUNO" in sug["explicacion"]


def test_sugerir_padre_por_potrero_compartido(db):
    """Si no hay servicio registrado, sugiere el toro que compartía potrero en la concepción (~283d)."""
    # Potreros
    p_santa_martha = db.query_one("SELECT id FROM potreros WHERE nombre = 'ORDENO SANTA MARTHA'")["id"]
    p_otro = db.query_one("SELECT id FROM potreros WHERE nombre = 'LOTE REPRODUCCION'")["id"]

    # Vaca y Toro T01 en el mismo potrero
    vaca_id = db.resolve_animal("VACA02", crear=True, sexo="Hembra")
    toro1_id = db.resolve_animal("T01", crear=True, sexo="Macho", nombre="BRUNO")
    toro2_id = db.resolve_animal("T02", crear=True, sexo="Macho", nombre="PERLA")

    db.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (p_santa_martha, vaca_id))
    db.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (p_santa_martha, toro1_id))
    db.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (p_otro, toro2_id))

    f_parto = date.today()
    res = db.sugerir_padre_parto("VACA02", f_parto.isoformat())
    assert res["ok"] is True
    assert res["sugerencia"] is not None
    sug = res["sugerencia"]
    assert sug["toro_tag"] == "T01"
    assert sug["toro_nombre"] == "BRUNO"
    assert sug["metodo"] == "MONTA_NATURAL_POTRERO"
    assert sug["potrero_nombre"] == "ORDENO SANTA MARTHA"
    assert sug["confianza"] == "ALTA"
    assert "ORDENO SANTA MARTHA" in sug["explicacion"]


def test_sugerir_padre_por_traslado_historico(db):
    """Detecta el potrero histórico donde estaban la vaca y el toro en la fecha de concepción."""
    p_maternidad = db.query_one("SELECT id FROM potreros WHERE nombre = 'POTRERO MATERNIDAD'")["id"]
    p_santa_martha = db.query_one("SELECT id FROM potreros WHERE nombre = 'ORDENO SANTA MARTHA'")["id"]

    vaca_id = db.resolve_animal("VACA03", crear=True, sexo="Hembra")
    toro1_id = db.resolve_animal("T01", crear=True, sexo="Macho", nombre="BRUNO")

    # Actualmente están en maternidad
    db.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (p_maternidad, vaca_id))
    db.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (p_maternidad, toro1_id))

    # Pero hace 300 días estaban en Santa Martha
    f_parto = date.today()
    f_antigua = f_parto - timedelta(days=320)
    db.execute("""
        INSERT INTO traslados (animal_id, fecha, potrero_destino)
        VALUES (?, ?, ?)
    """, (vaca_id, f_antigua.isoformat(), p_santa_martha))
    db.execute("""
        INSERT INTO traslados (animal_id, fecha, potrero_destino)
        VALUES (?, ?, ?)
    """, (toro1_id, f_antigua.isoformat(), p_santa_martha))

    # Y se mudaron a maternidad hace solo 10 días antes del parto
    f_reciente = f_parto - timedelta(days=10)
    db.execute("""
        INSERT INTO traslados (animal_id, fecha, potrero_destino)
        VALUES (?, ?, ?)
    """, (vaca_id, f_reciente.isoformat(), p_maternidad))

    res = db.sugerir_padre_parto("VACA03", f_parto.isoformat())
    assert res["ok"] is True
    assert res["sugerencia"] is not None
    sug = res["sugerencia"]
    # Durante la concepción (~283d atrás) estaban en Santa Martha
    assert sug["toro_tag"] == "T01"
    assert sug["potrero_nombre"] == "ORDENO SANTA MARTHA"


def test_registrar_parto_autocompleta_padre_sugerido(db):
    """Si no se pasa padre_tag a registrar_parto, hereda el padre sugerido."""
    p_santa_martha = db.query_one("SELECT id FROM potreros WHERE nombre = 'ORDENO SANTA MARTHA'")["id"]
    vaca_id = db.resolve_animal("VACA04", crear=True, sexo="Hembra")
    toro_id = db.resolve_animal("T01", crear=True, sexo="Macho", nombre="BRUNO")

    db.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (p_santa_martha, vaca_id))
    db.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (p_santa_martha, toro_id))

    parto_id = db.registrar_parto(
        vaca_tag="VACA04",
        fecha=date.today().isoformat(),
        id_cria_tag="CRIA_04",
        sexo_cria="Macho",
        padre_tag=None,  # No se especifica padre
    )

    assert parto_id is not None
    cria = db.query_one("SELECT padre_id FROM animales WHERE tag = 'CRIA_04'")
    assert cria is not None
    assert cria["padre_id"] == toro_id


def test_api_parto_sugerir_padre(tmp_path):
    """Endpoint REST /api/parto/sugerir-padre responde correctamente."""
    import json
    db_file = tmp_path / "test_api_bitacora.db"
    d = Database(str(db_file))
    d.create_tables()
    p1 = d.insert("potreros", {"nombre": "POTRERO SANTA MARTHA"})
    vaca_id = d.resolve_animal("VACA05", crear=True, sexo="Hembra")
    toro_id = d.resolve_animal("T01", crear=True, sexo="Macho", nombre="BRUNO")
    d.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (p1, vaca_id))
    d.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (p1, toro_id))
    d.close()

    u_path = str(tmp_path / "users_test.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump([{"user_id": 1, "nombre": "T", "rol": "TRABAJADOR", "pin": "1111"}], f)

    app = crear_app(str(db_file), users_file=u_path, password="x")
    app.config.update({"TESTING": True})
    client = app.test_client()

    # Sin auth debe dar 401
    assert client.get("/api/parto/sugerir-padre?vaca=VACA05").status_code == 401

    # Con login
    client.post("/login", data={"pin": "1111"})
    resp = client.get(f"/api/parto/sugerir-padre?vaca=VACA05&fecha={date.today().isoformat()}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["sugerencia"]["toro_tag"] == "T01"
    assert data["sugerencia"]["metodo"] == "MONTA_NATURAL_POTRERO"
