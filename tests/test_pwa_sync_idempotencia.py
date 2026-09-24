"""Idempotencia de /api/sync (P0.1, auditoría 2026-09-23).

Escenario central de la PWA offline: el cliente encola eventos con un
``id_local`` único (app.js), hace POST, y si la respuesta se pierde (conexión
rural intermitente) reintenta la MISMA cola. Sin idempotencia, cada reintento
duplicaba partos/pesajes/muertes/servicios en la BD.

Fix: tabla ``sync_ids_procesados``; al recibir un evento cuyo ``id_local`` ya
fue procesado, va directo a ``ids_ok`` sin re-registrar nada en dominio.
"""
import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.db.database import Database
from src.pwa.app import crear_app


@pytest.fixture
def db_file_sync(tmp_path):
    ruta = str(tmp_path / "bitacora_sync.db")
    d = Database(ruta)
    d.create_tables()
    d.registrar_potrero(nombre="Potrero A", codigo="A1")
    d.registrar_potrero(nombre="Potrero B", codigo="B1")
    d.registrar_animal("47", sexo="Hembra", estado="ACTIVO",
                       fecha_nacimiento="2021-01-01", potrero="Potrero A")
    d.close()
    return ruta


@pytest.fixture
def client_sync(db_file_sync):
    app = crear_app(db_file_sync, password="clave-de-prueba")
    assert app is not None
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave-de-prueba"})
    return c


def _cola_offline():
    """Cola típica que el cliente encoló sin red (mismos id_local en el reintento)."""
    return {"eventos": [
        {"tipo": "parto", "id_local": "loc_A1", "fecha": "2026-08-20",
         "payload": {"vaca_tag": "47", "sexo_cria": "HEMBRA", "peso_nacimiento": 32.0,
                     "id_cria_tag": "47H1"}},
        {"tipo": "pesaje", "id_local": "loc_A2", "fecha": "2026-08-22",
         "payload": {"animal_tag": "47", "peso_kg": 450.0}},
        {"tipo": "servicio", "id_local": "loc_A3", "fecha": "2026-08-23",
         "payload": {"vaca_tag": "47", "tipo_servicio": "IA", "toro_pajilla": "502"}},
        {"tipo": "traslado", "id_local": "loc_A4", "fecha": "2026-08-24",
         "payload": {"animal_tag": "47", "potrero_origen": "Potrero A",
                     "potrero_destino": "Potrero B"}},
    ]}


def test_doble_post_misma_cola_no_duplica_eventos(client_sync, db_file_sync):
    """El caso de uso central: POST procesado pero respuesta perdida →
    reintento idéntico → la BD debe tener exactamente 1 registro por evento."""
    cola = _cola_offline()

    r1 = client_sync.post("/api/sync", json=cola)
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert d1["ok"] is True
    assert d1["procesados"] == 4
    assert set(d1["ids_ok"]) == {"loc_A1", "loc_A2", "loc_A3", "loc_A4"}
    assert d1["errores"] == []

    # Reintento exacto (misma cola, mismos id_local)
    r2 = client_sync.post("/api/sync", json=cola)
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert d2["ok"] is True
    # El reintento devuelve ids_ok igual (el cliente purga la cola igual).
    assert set(d2["ids_ok"]) == {"loc_A1", "loc_A2", "loc_A3", "loc_A4"}

    db = Database(db_file_sync)
    try:
        assert db.count("partos") == 1
        assert db.count("pesajes") == 1
        assert db.count("servicios") == 1
        assert db.count("traslados") == 1
        n_sync = db.count("sync_ids_procesados")
        assert n_sync == 4
    finally:
        db.close()


def test_tercer_post_tampoco_duplica_ni_rompe(client_sync, db_file_sync):
    """Múltiples reintentos seguidos siguen siendo idempotentes."""
    cola = _cola_offline()
    for _ in range(3):
        r = client_sync.post("/api/sync", json=cola)
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    db = Database(db_file_sync)
    try:
        assert db.count("partos") == 1
        assert db.count("pesajes") == 1
        assert db.count("servicios") == 1
    finally:
        db.close()


def test_evento_con_error_no_marca_id_como_procesado(client_sync, db_file_sync):
    """Si el evento FALLA (payload inválido que lanza), su id_local NO debe
    quedar como procesado: el cliente lo deja en cola y un reintento tras
    corregir datos debe poder registrarlo."""
    # dias_retiro_leche no numérico -> int() lanza dentro del handler.
    cola_mala = {"eventos": [
        {"tipo": "tratamiento", "id_local": "loc_MALA",
         "payload": {"animal_tag": "47", "producto": "Ivermectina",
                     "dias_retiro_leche": "no-es-numero"}},
    ]}
    r1 = client_sync.post("/api/sync", json=cola_mala)
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert "loc_MALA" not in d1["ids_ok"]
    assert len(d1["errores"]) == 1

    db = Database(db_file_sync)
    try:
        fila = db.query_one(
            "SELECT 1 AS ok FROM sync_ids_procesados WHERE id_local = 'loc_MALA'")
        assert fila is None
    finally:
        db.close()

    # Corrección: mismo id_local ahora con retiro numérico -> sí se registra.
    cola_buena = {"eventos": [
        {"tipo": "tratamiento", "id_local": "loc_MALA",
         "payload": {"animal_tag": "47", "producto": "Ivermectina",
                     "dias_retiro_leche": 4}},
    ]}
    r2 = client_sync.post("/api/sync", json=cola_buena)
    assert r2.status_code == 200
    assert "loc_MALA" in r2.get_json()["ids_ok"]

    db = Database(db_file_sync)
    try:
        assert db.count("tratamientos") == 1
        assert db.count("sync_ids_procesados") == 1
    finally:
        db.close()


def test_eventos_sin_id_local_siguen_funcionando(client_sync, db_file_sync):
    """Backward-compat: eventos legacy sin id_local se procesan normal
    (no se puede deduplicar sin clave, y no deben romperse)."""
    cola = {"eventos": [
        {"tipo": "pesaje", "payload": {"animal_tag": "47", "peso_kg": 451.0,
                                       "fecha": "2026-08-25"}},
    ]}
    r = client_sync.post("/api/sync", json=cola)
    assert r.status_code == 200
    assert r.get_json()["procesados"] == 1

    db = Database(db_file_sync)
    try:
        assert db.count("pesajes") == 1
        assert db.count("sync_ids_procesados") == 0
    finally:
        db.close()


def test_misma_cola_parcialmente_procesada_no_duplica_lo_ok(client_sync, db_file_sync):
    """Cola mixta: 1 evento OK + 1 inválido. El reintento no duplica el OK
    y el inválido sigue reportándose en errores."""
    cola = {"eventos": [
        {"tipo": "pesaje", "id_local": "loc_OK1",
         "payload": {"animal_tag": "47", "peso_kg": 452.0, "fecha": "2026-08-26"}},
        {"tipo": "invento_raro", "id_local": "loc_BAD1", "payload": {}},
    ]}
    r1 = client_sync.post("/api/sync", json=cola)
    d1 = r1.get_json()
    assert d1["ids_ok"] == ["loc_OK1"]
    assert len(d1["errores"]) == 1

    r2 = client_sync.post("/api/sync", json=cola)
    d2 = r2.get_json()
    # El OK ya procesado vuelve en ids_ok (idempotente); el tipo inválido
    # vuelve a fallar igual (no es un duplicado de dominio).
    assert d2["ids_ok"] == ["loc_OK1"]
    assert len(d2["errores"]) == 1

    db = Database(db_file_sync)
    try:
        assert db.count("pesajes") == 1
    finally:
        db.close()
