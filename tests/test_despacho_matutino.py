"""Pruebas unitarias para el Despacho Matutino (Morning Briefing) y Recordatorios."""
from datetime import date

from src.db.database import Database
from src.server.formatters import formatear_despacho_matutino
from src.server.keyboards import crear_teclado_despacho_matutino


def test_formatear_despacho_matutino_sin_alertas(db: Database):
    """Prueba que el despacho matutino no muestra inventario, ni tanque libre, ni rotación Voisin automática."""
    hoy = date(2026, 8, 30)
    db.registrar_animal(tag="101", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal(tag="102", sexo="Macho", estado="ACTIVO")

    texto = formatear_despacho_matutino(db, hoy=hoy)

    assert "DESPACHO MATUTINO" in texto
    assert "Domingo, 30 de Agosto de 2026" in texto
    assert "Tanque de Leche Libre" not in texto
    assert "Sin servicios de regla AM-PM" in texto
    assert "PASTURAS & ROTACIÓN VOISIN" not in texto
    assert "INVENTARIO ACTIVO" not in texto
    assert "2 animales totales" not in texto
    assert "Sin recordatorios programados" in texto


def test_formatear_despacho_matutino_con_retiro_leche(db: Database):
    """Prueba alerta crítica de retiro de leche en el despacho matutino (sin tanque libre)."""
    hoy = date(2026, 8, 30)
    aid = db.registrar_animal(tag="47", nombre="Margarita", sexo="Hembra", estado="ACTIVO")
    db.registrar_tratamiento(
        animal_tag=aid,
        fecha="2026-08-28",
        producto="Oxitetraciclina",
        dosis="20ml",
        via="IM",
        dias_retiro_leche=5,
        dias_retiro_carne=15,
        diagnostico="Mastitis clínica",
    )

    texto = formatear_despacho_matutino(db, hoy=hoy)

    assert "¡ALERTA DE ORDEÑO! VACAS EN RETIRO (1)" in texto
    assert "NO echar esta leche al tanque" in texto
    assert "47 (Margarita)" in texto
    assert "Oxitetraciclina" in texto
    assert "Retiro de Carne" in texto
    assert "Tanque de Leche Libre" not in texto


def test_formatear_despacho_matutino_con_inseminacion_am(db: Database):
    """Prueba alerta de inseminación matutina por celo detectado ayer en la tarde (Regla AM-PM)."""
    hoy = date(2026, 8, 30)
    aid = db.registrar_animal(tag="JA26", nombre="Patricia", sexo="Hembra", estado="ACTIVO")
    db.registrar_celo(
        vaca_tag=aid,
        fecha="2026-08-29",
        am_pm="PM",
        notas="Celo claro con moco cristalino",
    )

    texto = formatear_despacho_matutino(db, hoy=hoy)

    assert "INSEMINACIONES DE ESTA MAÑANA" in texto
    assert "JA26 (Patricia)" in texto
    assert "Celo observado ayer PM" in texto
    assert "Inseminar antes de las 10:00 AM" in texto


def test_formatear_despacho_matutino_con_recordatorios_programados(db: Database):
    """Prueba que los recordatorios programados del día aparecen en el despacho en lugar de Voisin automático."""
    hoy = date(2026, 8, 30)
    db.registrar_recordatorio(
        mensaje="Rotar potrero Bajo a Guayabal",
        fecha_programada="2026-08-30",
        hora="08:00",
    )
    db.registrar_recordatorio(
        mensaje="Vacunación aftosa Lote 1",
        fecha_programada="2026-08-30",
        hora="10:30",
    )

    texto = formatear_despacho_matutino(db, hoy=hoy)

    assert "RECORDATORIOS PROGRAMADOS (2)" in texto
    assert "Rotar potrero Bajo a Guayabal" in texto
    assert "[08:00]" in texto
    assert "Vacunación aftosa Lote 1" in texto
    assert "[10:30]" in texto
    assert "PASTURAS & ROTACIÓN VOISIN" not in texto
    assert "INVENTARIO ACTIVO" not in texto


def test_formatear_despacho_matutino_con_calendario_reproductivo(db: Database):
    """Prueba recordatorios de ecografía (d35), palpación (d60) y parto próximo (7d)."""
    hoy = date(2026, 8, 30)
    v1 = db.registrar_animal(tag="101", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag=v1, fecha="2026-07-26", toro_pajilla="Toro 99", tipo_servicio="IA")

    v2 = db.registrar_animal(tag="102", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag=v2, fecha="2026-07-01", toro_pajilla="Toro 99", tipo_servicio="IA")

    v3 = db.registrar_animal(tag="103", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag=v3, fecha="2025-11-27", toro_pajilla="Toro 99", tipo_servicio="IA", fep_calculada="2026-09-06")

    texto = formatear_despacho_matutino(db, hoy=hoy)

    assert "CALENDARIO REPRODUCTIVO & VETERINARIO" in texto
    assert "Ecografía (Día 35)" in texto
    assert "101" in texto
    assert "Palpación (Día 60)" in texto
    assert "102" in texto
    assert "Parto próximo" in texto
    assert "103" in texto


def test_crud_recordatorios_programados(db: Database):
    """Prueba inserción, consulta y marcado de recordatorios en la base de datos."""
    r1 = db.registrar_recordatorio("Rotar potrero 3", fecha_programada="2026-08-30", hora="07:30", creado_por=10)
    r2 = db.registrar_recordatorio("Comprar sales", fecha_programada="2026-08-31", hora="09:00", creado_por=10)

    pendientes_hoy = db.listar_recordatorios_pendientes(fecha="2026-08-30")
    assert len(pendientes_hoy) == 1
    assert pendientes_hoy[0]["mensaje"] == "Rotar potrero 3"
    assert pendientes_hoy[0]["hora"] == "07:30"

    todos_pendientes = db.listar_recordatorios_pendientes()
    assert len(todos_pendientes) == 2

    # Marcar enviado
    ok = db.marcar_enviado(r1)
    assert ok is True

    pendientes_despues = db.listar_recordatorios_pendientes(fecha="2026-08-30")
    assert len(pendientes_despues) == 0


def test_registrar_leche_total_hato(db: Database):
    """Prueba registrar producción total diaria de leche sin animal_tag."""
    lid = db.registrar_leche(animal_tag=None, fecha="2026-08-30", litros=475.5, registrado_por=123)
    assert lid is not None

    fila = db.query_one("SELECT * FROM produccion_leche WHERE id = ?", (lid,))
    assert fila["animal_id"] is None
    assert fila["litros"] == 475.5
    assert fila["fecha"] == "2026-08-30"
    assert fila["registrado_por"] == 123


def test_teclado_despacho_matutino():
    """Prueba que el teclado del despacho matutino tiene los botones correctos."""
    teclado = crear_teclado_despacho_matutino()
    callbacks = [btn.callback_data for row in teclado.inline_keyboard for btn in row]

    assert "cmd:registrar_leche" in callbacks
    assert "cmd:programar_recordatorio" in callbacks
    assert "cmd:alertas" in callbacks
    assert "cmd:medicamentos" in callbacks
    assert "cmd:potreros" in callbacks
    assert "cmd:status" in callbacks
    assert "cmd:buscar_animal" in callbacks
    assert "menu:principal" in callbacks
