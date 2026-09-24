"""Pruebas unitarias para el Catálogo/Evaluación de Inseminadores y Sincronizaciones IATF."""

import os
import tempfile
import pytest
from datetime import date
from src.db.database import Database
from src.pwa.app import crear_app


@pytest.fixture
def db_temp():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    db.create_tables()
    # Registrar animales de prueba
    db.registrar_animal(tag="V01", nombre="Mariposa", sexo="H", estado="ACTIVO")
    db.registrar_animal(tag="V02", nombre="Paloma", sexo="H", estado="ACTIVO")
    db.registrar_animal(tag="V03", nombre="Estrella", sexo="H", estado="ACTIVO")
    db.registrar_animal(tag="NOV01", nombre="Princesa", sexo="H", estado="ACTIVO")
    # Registrar pajuelas en el termo
    db.registrar_pajuela_inventario(
        codigo_toro="GUZ-01",
        raza="Guzerá",
        canastilla="C1",
        cantidad=10,
        costo=45000,
        procedencia="CRIASUR",
    )
    yield db
    db.close()
    if os.path.exists(path):
        os.remove(path)


def test_inseminadores_catalogo_y_evaluacion(db_temp: Database):
    # Verificar sembrado o registro de inseminadores
    inseminadores = db_temp.listar_inseminadores()
    assert isinstance(inseminadores, list)

    iid = db_temp.registrar_inseminador(
        nombre="Dr. Pedro Martínez",
        telefono="3101234567",
        es_usuario_sistema=True,
        notas="Especialista IATF",
    )
    assert iid > 0

    # Registrar servicios realizados por Dr. Pedro Martínez
    db_temp.registrar_servicio(
        vaca_tag="V01",
        fecha="2026-08-01",
        tipo_servicio="IA",
        toro_pajilla="GUZ-01",
        inseminador="Dr. Pedro Martínez",
    )
    db_temp.registrar_servicio(
        vaca_tag="V02",
        fecha="2026-08-01",
        tipo_servicio="IA",
        toro_pajilla="GUZ-01",
        inseminador="Dr. Pedro Martínez",
    )

    # Diagnósticos posteriores para evaluar fertilidad
    db_temp.registrar_diagnostico(
        vaca_tag="V01",
        fecha="2026-09-10",
        resultado="PREÑADA",
        dias_gestacion=40,
        metodo="ECOGRAFIA",
    )
    db_temp.registrar_diagnostico(
        vaca_tag="V02",
        fecha="2026-09-10",
        resultado="VACIA",
        metodo="ECOGRAFIA",
    )

    evaluacion = db_temp.evaluar_inseminadores()
    pedro = next((e for e in evaluacion if e["inseminador"] == "Dr. Pedro Martínez"), None)
    assert pedro is not None
    assert pedro["total_ias"] == 2
    assert pedro["diagnosticadas"] == 2
    assert pedro["prenadas"] == 1
    assert pedro["vacias"] == 1
    assert pedro["tasa_concepcion_pct"] == 50.0
    assert pedro["servicios_por_concepcion"] == 2.0
    assert pedro["semaforo"] == "AMARILLO"


def test_protocolos_iatf_sembrado_y_lectura(db_temp: Database):
    protocolos = db_temp.listar_protocolos_iatf()
    assert len(protocolos) >= 3
    nombres = [p["nombre"] for p in protocolos]
    assert any("Convencional 8 Días con eCG" in n for n in nombres)
    assert any("Lechería" in n for n in nombres)
    assert any("J-Synch" in n for n in nombres)

    p0 = protocolos[0]
    det = db_temp.obtener_protocolo_iatf(p0["id"])
    assert det is not None
    assert len(det["pasos"]) >= 3


def test_flujo_completo_lote_iatf(db_temp: Database):
    protocolos = db_temp.listar_protocolos_iatf()
    prot_carne = next(p for p in protocolos if "CARNE" in p["categoria"])

    # 1. Crear Lote IATF con 3 vacas
    tags = ["V01", "V02", "V03"]
    lote_id = db_temp.crear_lote_iatf(
        nombre="Lote Test 2026",
        protocolo_id=prot_carne["id"],
        fecha_inicio="2026-09-01",
        animales_tags=tags,
        toro_pajuela="GUZ-01",
        inseminador="Dr. Pedro Martínez",
        hora_iatf="08:30",
        notas="Lote de prueba zootécnica",
    )
    assert lote_id > 0

    # Verificar alertas automáticas de fármacos en recordatorios_programados
    recs = db_temp.listar_recordatorios_pendientes()
    recs_iatf = [r for r in recs if r["tipo_tarea"] == "IATF"]
    assert len(recs_iatf) >= 3  # D0, D8, D10

    # 2. Registrar avance del Paso 0 (Día 0: Dispositivo P4 + Benzoato)
    ok_p0 = db_temp.registrar_avance_paso_iatf(
        lote_id=lote_id,
        paso_index=0,
        producto_aplicado="Dispositivo P4 1g + Benzoato de Estradiol",
        dosis="1 dispositivo + 2.0 ml BE",
        marca="DIB 1g + Sincrodiol",
        realizado_por="Carlos Veterinario",
        notas="Dispositivos insertados sin problemas",
    )
    assert ok_p0 is True

    # 3. Excluir un animal (V03 perdió el dispositivo en el Día 8)
    ok_exc = db_temp.excluir_animal_lote_iatf(
        lote_id=lote_id,
        tag="V03",
        motivo="Pérdida de dispositivo intravaginal",
    )
    assert ok_exc is True

    # 4. Registrar avance del Paso 1 (Día 8: Retiro + Fármacos)
    ok_p1 = db_temp.registrar_avance_paso_iatf(
        lote_id=lote_id,
        paso_index=1,
        producto_aplicado="Retiro P4 + PGF2a + ECP + eCG",
        dosis="2ml Ciclase + 0.5ml ECP + 2ml Novormon",
        marca="Ciclase DL + ECP + Novormon 400UI",
        realizado_por="Carlos Veterinario",
    )
    assert ok_p1 is True

    # 5. Ejecutar Inseminación Masiva a 1-Toque (Día 10)
    # Deben inseminarse V01 y V02 (V03 fue excluida). Stock de GUZ-01 baja de 10 a 8.
    res_ins = db_temp.ejecutar_inseminacion_lote_iatf(
        lote_id=lote_id,
        toro_pajuela="GUZ-01",
        inseminador="Dr. Pedro Martínez",
        fecha="2026-09-11",
        hora="08:30",
    )
    assert res_ins["ok"] is True
    assert res_ins["servicios_creados"] == 2
    assert res_ins["pajuelas_descontadas"] == 2
    assert "V01" in res_ins["animales"]
    assert "V02" in res_ins["animales"]
    assert "V03" not in res_ins["animales"]

    # Verificar que el stock de pajuelas se redujo
    paj_guz = db_temp.obtener_pajuela("GUZ-01")
    assert paj_guz is not None
    assert paj_guz["cantidad"] == 8

    # Verificar estado del lote
    lote_det = db_temp.obtener_detalle_lote_iatf(lote_id)
    assert lote_det is not None
    assert lote_det["estado"] == "IATF_REALIZADA"
    assert len(lote_det["historial_pasos"]) >= 2
    assert lote_det["animales_activos"] == 2


def test_api_rest_inseminadores_e_iatf(db_temp: Database):
    app = crear_app(db_path=db_temp.path, password="clave-de-prueba")
    app.config["TESTING"] = True
    client = app.test_client()
    client.post("/login", data={"password": "clave-de-prueba"})

    # GET /api/inseminadores
    res_insem = client.get("/api/inseminadores")
    assert res_insem.status_code == 200
    data_insem = res_insem.get_json()
    assert data_insem["ok"] is True
    assert "inseminadores" in data_insem

    # POST /api/inseminadores
    res_crear_insem = client.post("/api/inseminadores", json={
        "nombre": "Inseminador API Test",
        "telefono": "3209876543",
        "es_usuario_sistema": False,
        "notas": "Técnico externo",
    })
    assert res_crear_insem.status_code == 200
    assert res_crear_insem.get_json()["ok"] is True

    # GET /api/iatf/protocolos
    res_prots = client.get("/api/iatf/protocolos")
    assert res_prots.status_code == 200
    prots = res_prots.get_json()["protocolos"]
    assert len(prots) >= 3
    prot_id = prots[0]["id"]

    # POST /api/iatf/lotes
    res_crear_lote = client.post("/api/iatf/lotes", json={
        "nombre": "Lote Novillas API",
        "protocolo_id": prot_id,
        "fecha_inicio": "2026-09-20",
        "animales_tags": ["NOV01", "V01"],
        "toro_pajuela": "GUZ-01",
        "inseminador": "Inseminador API Test",
        "hora_iatf": "09:00",
    })
    assert res_crear_lote.status_code == 200
    lid = res_crear_lote.get_json()["id"]
    assert lid > 0

    # GET /api/iatf/lotes/<id>
    res_det = client.get(f"/api/iatf/lotes/{lid}")
    assert res_det.status_code == 200
    lote = res_det.get_json()["lote"]
    assert lote["nombre"] == "Lote Novillas API"
    assert len(lote["animales"]) == 2

    # POST /api/iatf/lotes/<id>/paso
    res_paso = client.post(f"/api/iatf/lotes/{lid}/paso", json={
        "paso_index": 0,
        "producto": "Dispositivo P4 0.5g",
        "marca": "Cronipres",
        "dosis": "1 dispositivo",
        "notas": "Aplicado a tiempo",
    })
    assert res_paso.status_code == 200
    assert res_paso.get_json()["ok"] is True

    # POST /api/iatf/lotes/<id>/excluir
    res_exc = client.post(f"/api/iatf/lotes/{lid}/excluir", json={
        "tag": "NOV01",
        "motivo": "Lesión podal",
    })
    assert res_exc.status_code == 200
    assert res_exc.get_json()["ok"] is True

    # POST /api/iatf/lotes/<id>/inseminar
    res_ins = client.post(f"/api/iatf/lotes/{lid}/inseminar", json={
        "toro_pajuela": "GUZ-01",
        "inseminador": "Inseminador API Test",
        "fecha": "2026-09-30",
        "hora": "09:00",
    })
    assert res_ins.status_code == 200
    assert res_ins.get_json()["ok"] is True
    assert res_ins.get_json()["resultado"]["servicios_creados"] == 1  # Solo V01 activa
