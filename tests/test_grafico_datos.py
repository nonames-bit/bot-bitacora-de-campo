"""
Pruebas automatizadas para los endpoints de datos vectoriales de gráficos:
GET /api/grafico-datos/<tipo>
"""
import pytest
from src.pwa.app import crear_app
from src.db.database import Database


@pytest.fixture
def pwa_client(tmp_path):
    db_file = str(tmp_path / "test_grafico_db.db")
    db = Database(db_file)
    db.create_tables()

    # Potreros y animales activos para inventario
    p_id = db.registrar_potrero("Potrero 1", codigo="P1")
    db.execute(
        "UPDATE potreros SET area_has = 12.5 WHERE id = ?",
        (p_id,)
    )
    db.registrar_animal("TAG-1", sexo="Hembra", estado="ACTIVO", raza="C", potrero="Potrero 1", fecha_nacimiento="2022-01-01")
    db.registrar_animal("TAG-2", sexo="Macho", estado="ACTIVO", raza="I", potrero="Potrero 1", fecha_nacimiento="2023-01-01")
    db.registrar_animal("TAG-3", sexo="Hembra", estado="VENDIDO", raza="C", potrero="Potrero 1")  # No activo
    db.close()

    app = crear_app(
        db_path=db_file,
        users_file="src/server/users.json",
        password="test-password"
    )
    app.config["TESTING"] = True
    app.config["SESSION_COOKIE_SECURE"] = False

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["autenticado"] = True
            sess["rol"] = "OWNER"
            sess["nombre"] = "Test Owner"
            sess["user_id"] = 1
        yield client


@pytest.mark.parametrize("tipo", [
    "evolucion",
    "reproductivo_hato",
    "ocupacion",
    "aforo",
    "flujo_caja",
    "waterfall_inventario",
    "gmd_hato",
    "composicion_racial",
    "subastas_comparativa",
    "subastas_tendencia",
    "mapa_potreros",
    "carga_animal",
])
def test_api_grafico_datos_todos_los_tipos(pwa_client, tipo):
    resp = pwa_client.get(f"/api/grafico-datos/{tipo}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert data.get("tipo") in (tipo, tipo.replace("_potreros", ""))


def test_api_grafico_datos_tipo_invalido(pwa_client):
    resp = pwa_client.get("/api/grafico-datos/tipo_inexistente_xyz")
    assert resp.status_code == 404
