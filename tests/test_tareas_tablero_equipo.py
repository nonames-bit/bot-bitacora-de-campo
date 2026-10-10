"""Pruebas de tareas asignadas al equipo en Tablero, Acknowledge con foto/nota y vaciado de chat."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import pytest
from src.db.database import Database
from src.pwa.app import crear_app

@pytest.fixture
def test_setup(tmp_path):
    db_file = str(tmp_path / "test.db")
    users_file = str(tmp_path / "users.json")
    
    # Crear users.json con Jaime (OWNER) y Sebas (TRABAJADOR)
    with open(users_file, "w", encoding="utf-8") as f:
        json.dump([
            {"user_id": 1, "telegram_id": 111, "nombre": "Jaime", "rol": "OWNER", "pin": "1234", "avatar": "patron"},
            {"user_id": 2, "telegram_id": 222, "nombre": "Sebas", "rol": "TRABAJADOR", "pin": "5678", "avatar": "vaquero"}
        ], f)
    
    db = Database(db_file).create_tables()
    app = crear_app(db_file, users_file=users_file, password="masterkey")
    app.config["TESTING"] = True
    
    yield {"db": db, "users_file": users_file, "app": app}
    db.close()

def test_flujo_tareas_tablero_ack_y_vaciar_chat(test_setup):
    app = test_setup["app"]
    client = app.test_client()
    
    # 1. Login como Jaime (OWNER)
    with client.session_transaction() as sess:
        sess["autenticado"] = True
        sess["user_id"] = 1
        sess["nombre"] = "Jaime"
        sess["rol"] = "OWNER"
    
    # 2. Verificar que /api/equipo/integrantes lista a Jaime y Sebas
    resp = client.get("/api/equipo/integrantes")
    assert resp.status_code == 200
    datos_integ = resp.get_json()
    nombres = [it["nombre"] for it in datos_integ.get("integrantes", [])]
    assert "Jaime" in nombres
    assert "Sebas" in nombres
    
    # 3. Consultar /api/tablero inicial
    resp = client.get("/api/tablero")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "tareas_asignadas" in data
    assert "tareas_realizadas_hoy" in data
    assert len(data["tareas_asignadas"]) == 0
    
    # 4. Crear tarea asignada de Jaime para Sebas
    resp = client.post("/api/agenda/recordatorio", json={
        "tipo_tarea": "Curación y chequeo",
        "asignado_a": "Sebas",
        "creado_por_nombre": "Jaime",
        "mensaje": "JA154: Quitar cachos se está lastimando",
        "fecha": "2026-10-15",
        "prioridad": "Alta",
        "tipo_objetivo": "ANIMAL",
        "animal_tag": "JA154"
    })
    assert resp.status_code == 200
    res_crear = resp.get_json()
    assert res_crear["ok"] is True
    rec_id = res_crear["id"]
    
    # 5. Verificar que aparece en /api/tablero -> tareas_asignadas con los datos correctos
    resp = client.get("/api/tablero")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["tareas_asignadas"]) == 1
    t = data["tareas_asignadas"][0]
    assert t["id"] == rec_id
    assert t["asignado_a"] == "Sebas"
    assert t["creado_por_nombre"] == "Jaime"
    assert t["animal_tag"] == "JA154"
    assert "Quitar cachos" in t["mensaje"]
    
    # 6. Verificar que se publicó aviso en mensajes_equipo
    resp = client.get("/api/mensajes-equipo")
    assert resp.status_code == 200
    msgs = resp.get_json()["mensajes"]
    assert any("Tarea asignada de Jaime a Sebas" in m["texto"] for m in msgs)
    
    # 7. Completar la tarea con nota y foto de soporte (Acknowledge)
    import io
    import base64
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), color="blue").save(buf, format="JPEG")
    foto_b64 = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    resp = client.post(f"/api/agenda/recordatorio/{rec_id}/completar", json={
        "completado_por": "Sebas",
        "notas": "Cachos limados y desinfectados con cicatrizante azul",
        "foto_base64": foto_b64
    })
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    
    # 8. Verificar que ya no está en tareas_asignadas y sí en tareas_realizadas_hoy con su foto y nota
    resp = client.get("/api/tablero")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["tareas_asignadas"]) == 0
    assert len(data["tareas_realizadas_hoy"]) == 1
    tr = data["tareas_realizadas_hoy"][0]
    assert tr["id"] == rec_id
    assert tr["completado_por"] == "Sebas"
    assert "Cachos limados" in tr["notas_completado"]
    assert tr["foto_completado"] is not None
    
    # 9. Verificar que en el chat de equipo se notificó el cumplimiento con foto
    resp = client.get("/api/mensajes-equipo")
    msgs = resp.get_json()["mensajes"]
    assert any("Tarea realizada por Sebas" in m["texto"] and "con foto soporte" in m["texto"] for m in msgs)
    
    # 10. Probar el botón de limpiar / vaciar chat de equipo (POST /api/mensajes-equipo/vaciar)
    resp = client.post("/api/mensajes-equipo/vaciar")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    
    # Verificar que el historial de equipo quedó limpio
    resp = client.get("/api/mensajes-equipo")
    assert resp.status_code == 200
    assert len(resp.get_json()["mensajes"]) == 0
    print(">>> TODOS LOS CHEQUEOS PASARON EXITOSAMENTE (100%) <<<")

if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        setup_dict = test_setup.__wrapped__(Path(td)) if hasattr(test_setup, '__wrapped__') else None
        # O manual:
        db_file = str(Path(td) / "test.db")
        users_file = str(Path(td) / "users.json")
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump([
                {"user_id": 1, "telegram_id": 111, "nombre": "Jaime", "rol": "OWNER", "pin": "1234", "avatar": "patron"},
                {"user_id": 2, "telegram_id": 222, "nombre": "Sebas", "rol": "TRABAJADOR", "pin": "5678", "avatar": "vaquero"}
            ], f)
        db = Database(db_file).create_tables()
        app = crear_app(db_file, users_file=users_file, password="masterkey")
        app.config["TESTING"] = True
        try:
            test_flujo_tareas_tablero_ack_y_vaciar_chat({"db": db, "users_file": users_file, "app": app})
        finally:
            db.close()
