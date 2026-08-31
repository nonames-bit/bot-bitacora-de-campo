"""Pruebas unitarias para el Despacho Matutino (Morning Briefing)."""
from datetime import date
import pytest

from src.db.database import Database
from src.server.formatters import formatear_despacho_matutino
from src.server.keyboards import crear_teclado_despacho_matutino


def test_formatear_despacho_matutino_sin_alertas(db: Database):
    """Prueba que el despacho matutino formatea correctamente cuando la finca está limpia de alertas."""
    hoy = date(2026, 8, 30)
    db.registrar_animal(tag="101", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal(tag="102", sexo="Macho", estado="ACTIVO")

    texto = formatear_despacho_matutino(db, hoy=hoy)

    assert "DESPACHO MATUTINO" in texto
    assert "Domingo, 30 de Agosto de 2026" in texto
    assert "Tanque de Leche Libre" in texto
    assert "Sin servicios de regla AM-PM" in texto
    assert "PASTURAS & ROTACIÓN VOISIN" in texto
    assert "INVENTARIO ACTIVO" in texto
    assert "2 animales totales" in texto


def test_formatear_despacho_matutino_con_retiro_leche(db: Database):
    """Prueba alerta crítica de retiro de leche en el despacho matutino."""
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


def test_formatear_despacho_matutino_con_rotacion_voisin(db: Database):
    """Prueba alertas de sobreocupación de potrero (>=3 días) y recomendación de entrada."""
    hoy = date(2026, 8, 30)
    pid1 = db.registrar_potrero(codigo="P01", nombre="Olegario 1")
    pid2 = db.registrar_potrero(codigo="P02", nombre="Guayabal", dias_reposo=38, aforo_kg_m2=1.45)

    aid = db.registrar_animal(tag="101", sexo="Hembra", estado="ACTIVO", potrero="Olegario 1")
    db.registrar_traslado(
        animal_tag=aid,
        fecha="2026-08-26",
        potrero_origen=None,
        potrero_destino=pid1,
        lote="Lote Ordeño",
    )

    texto = formatear_despacho_matutino(db, hoy=hoy)

    assert "PASTURAS & ROTACIÓN VOISIN" in texto
    assert "Rotar hoy" in texto
    assert "OLEGARIO 1" in texto
    assert "4 días" in texto
    assert "Entrada recomendada" in texto
    assert "Guayabal" in texto
    assert "38 días" in texto


def test_formatear_despacho_matutino_con_calendario_reproductivo(db: Database):
    """Prueba recordatorios de ecografía (d35), palpación (d60) y parto próximo (7d)."""
    hoy = date(2026, 8, 30)
    v1 = db.registrar_animal(tag="101", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag=v1, fecha="2026-07-26", toro_pajilla="Toro 99", tipo_servicio="IA")

    v2 = db.registrar_animal(tag="102", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag=v2, fecha="2026-07-01", toro_pajilla="Toro 99", tipo_servicio="IA")

    v3 = db.registrar_animal(tag="103", sexo="Hembra", estado="ACTIVO")
    # FEP = 2025-11-27 + 283 días = 2026-09-06 (dentro de 7d desde 2026-08-30)
    db.registrar_servicio(vaca_tag=v3, fecha="2025-11-27", toro_pajilla="Toro 99", tipo_servicio="IA", fep_calculada="2026-09-06")

    texto = formatear_despacho_matutino(db, hoy=hoy)

    assert "CALENDARIO REPRODUCTIVO & VETERINARIO" in texto
    assert "Ecografía (Día 35)" in texto
    assert "101" in texto
    assert "Palpación (Día 60)" in texto
    assert "102" in texto
    assert "Parto próximo" in texto
    assert "103" in texto


def test_teclado_despacho_matutino():
    """Prueba que el teclado del despacho matutino tiene los botones correctos."""
    teclado = crear_teclado_despacho_matutino()
    callbacks = [btn.callback_data for row in teclado.inline_keyboard for btn in row]

    assert "cmd:alertas" in callbacks
    assert "cmd:medicamentos" in callbacks
    assert "cmd:potreros" in callbacks
    assert "cmd:status" in callbacks
    assert "cmd:buscar_animal" in callbacks
    assert "menu:principal" in callbacks
