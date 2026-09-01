"""Pruebas unitarias para Fase 5.1 (Puntos 2 y 3):
- Punto 2: Alerta automática de Nitrógeno (Termo N2) en Despacho Matutino, helpers y /termo.
- Punto 3: OCR de facturas de compra de pajuelas, extracción de NIT, Total, Toro, Cantidad y flujo de confirmación.
"""
from datetime import date

from src.db.database import Database
from src.engine.reproductive_engine import (
    ReproductiveEngine,
    calcular_alerta_nitrogeno,
    calcular_proxima_recarga_n2,
)
from src.ocr.factura_parser import (
    detect_cantidad,
    detect_nit,
    detect_toro,
    detect_total,
    parse_factura_pajuelas,
)
from src.parsers.media_handler import extract_image_info
from src.server.formatters import (
    formatear_despacho_matutino,
    formatear_estado_termo,
)
from src.server.keyboards import crear_teclado_confirmar_factura_pajuelas


def test_alerta_nitrogeno_helper_y_despacho(db: Database):
    """Verifica los helpers de recarga N2 y el formato de alerta en el Despacho Matutino."""
    # 1. Verificar helpers puros
    f_rec = "2026-08-10"
    prox = calcular_proxima_recarga_n2(f_rec, 21)
    assert prox == date(2026, 8, 31)

    # Estado con 6 días restantes (no alerta)
    info_ok = calcular_alerta_nitrogeno(f_rec, intervalo_dias=21, hoy=date(2026, 8, 25), umbral_alerta=3)
    assert info_ok["dias_restantes"] == 6
    assert info_ok["alerta"] is False
    assert info_ok["vencido"] is False

    # Estado con 3 días restantes (alerta activa)
    info_alerta = calcular_alerta_nitrogeno(f_rec, intervalo_dias=21, hoy=date(2026, 8, 28), umbral_alerta=3)
    assert info_alerta["dias_restantes"] == 3
    assert info_alerta["alerta"] is True
    assert "Nitrógeno recargar en 3 días" in info_alerta["mensaje"]

    # Estado vencido
    info_vencido = calcular_alerta_nitrogeno(f_rec, intervalo_dias=21, hoy=date(2026, 9, 2), umbral_alerta=3)
    assert info_vencido["dias_restantes"] == -2
    assert info_vencido["vencido"] is True
    assert "Nitrógeno VENCIDO hace 2 días" in info_vencido["mensaje"]

    # ReproductiveEngine métodos estáticos
    assert ReproductiveEngine.proxima_recarga_n2(f_rec, 21) == date(2026, 8, 31)
    assert ReproductiveEngine.alerta_nitrogeno(f_rec, 21, hoy=date(2026, 8, 28))["alerta"] is True

    # 2. Registrar en base de datos y verificar Despacho Matutino
    db.registrar_recarga_nitrogeno(fecha_recarga="2026-08-10", dias_intervalo=21)

    # A 6 días: Despacho matutino no debe mostrar alerta de N2
    despacho_ok = formatear_despacho_matutino(db, hoy=date(2026, 8, 25))
    assert "ALERTA DE TERMO CRIOGÉNICO" not in despacho_ok

    # A 3 días (2026-08-28): Despacho matutino DEBE mostrar alerta
    despacho_alerta = formatear_despacho_matutino(db, hoy=date(2026, 8, 28))
    assert "ALERTA DE TERMO CRIOGÉNICO" in despacho_alerta
    assert "Nitrógeno recargar en 3 días" in despacho_alerta
    assert "2026-08-31" in despacho_alerta

    # A 2 días (2026-08-29): Muestra recargar en 2 días
    despacho_2d = formatear_despacho_matutino(db, hoy=date(2026, 8, 29))
    assert "Nitrógeno recargar en 2 días" in despacho_2d

    # 3. Formateador de /termo
    txt_termo_critico = formatear_estado_termo(db, hoy=date(2026, 8, 28))
    assert "CRÍTICO" in txt_termo_critico
    assert "3 días restantes" in txt_termo_critico


def test_ocr_factura_parser_entidades_y_propuesta():
    """Verifica la extracción precisa de NIT, Total, Cantidad, Toro y mensaje de propuesta."""
    texto_factura = (
        "DISTRIBUIDORA GENÉTICA BOVINA COLOMBIA S.A.S\n"
        "NIT: 900.123.456-7\n"
        "Factura de Venta No. FE-4590\n"
        "Fecha: 2026-08-31\n"
        "Detalle: 20 pajuelas de toro GYR-502\n"
        "Precio Unitario: $45.000\n"
        "Total a Pagar: $900.000 COP\n"
    )

    # 1. Extracción de entidades individuales
    nit = detect_nit(texto_factura)
    assert nit in ("900.123.456-7", "900123456-7")

    cant = detect_cantidad(texto_factura)
    assert cant == 20

    toro = detect_toro(texto_factura)
    assert toro == "GYR-502"

    total_val, total_raw = detect_total(texto_factura)
    assert total_val == 900000.0
    assert "900" in total_raw

    # 2. Parser consolidado
    info = parse_factura_pajuelas(texto_factura)
    assert info.es_factura is True
    assert info.toro == "GYR-502"
    assert info.cantidad == 20
    assert info.total == 900000.0
    assert info.nit is not None
    assert "Detecté compra de 20 pajuelas toro GYR-502, ¿confirmar?" in info.propuesta_mensaje


def test_ocr_factura_formatos_variados():
    """Verifica el parser con diferentes formatos y estructuras de facturas ganaderas."""
    # Caso 2: Formato con 'Cantidad: X' y toro en campo separado
    texto2 = (
        "CENTRO DE INSEMINACION EL TRIUNFO\n"
        "NIT 890123456-1\n"
        "Producto: Semen Bovino\n"
        "Toro: HOLSTEIN KINGBOY\n"
        "Cantidad: 15 pajuelas\n"
        "Total: 750,000 COP"
    )
    info2 = parse_factura_pajuelas(texto2)
    assert info2.es_factura is True
    assert info2.toro == "HOLSTEIN KINGBOY"
    assert info2.cantidad == 15
    assert info2.total == 750000.0
    assert "Detecté compra de 15 pajuelas toro HOLSTEIN KINGBOY, ¿confirmar?" in info2.propuesta_mensaje

    # Caso 3: Nota breve de compra
    texto3 = "Compra de 10 pajuelas de toro JA26 total 500000"
    info3 = parse_factura_pajuelas(texto3)
    assert info3.es_factura is True
    assert info3.toro == "JA26"
    assert info3.cantidad == 10
    assert info3.total == 500000.0

    # Caso 4: Texto ajeno a facturas/pajuelas (no debe clasificar como factura)
    texto_otro = "Vaca 47 parió cría macho en potrero 2"
    info_otro = parse_factura_pajuelas(texto_otro)
    assert info_otro.es_factura is False


def test_media_handler_extract_image_info_con_factura(tmp_path):
    """Verifica que extract_image_info reconozca facturas en sidecars e imágenes."""
    foto_fake = tmp_path / "factura_compra.jpg"
    foto_fake.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)  # Header JPEG mínimo

    sidecar = tmp_path / "factura_compra.jpg.txt"
    sidecar.write_text(
        "GENETICA GANADERA S.A.\nNIT: 800.555.666\nItem: 30 pajuelas toro 105\nTotal: $1.200.000",
        encoding="utf-8",
    )

    img_info = extract_image_info(str(foto_fake))
    assert img_info.factura_pajuelas is not None
    fac = img_info.factura_pajuelas
    assert fac.es_factura is True
    assert fac.toro == "105"
    assert fac.cantidad == 30
    assert fac.total == 1200000.0


def test_teclado_y_confirmacion_factura_pajuela(db: Database):
    """Verifica la generación del teclado de confirmación y el incremento de stock."""
    # 1. Teclado interactivo
    teclado = crear_teclado_confirmar_factura_pajuelas(toro="GYR-502", cantidad=20)
    assert len(teclado.inline_keyboard) == 1
    btn_confirmar, btn_descartar = teclado.inline_keyboard[0]

    assert "Confirmar Carga (+20 GYR-502)" in btn_confirmar.text
    assert btn_confirmar.callback_data == "factura_pajuela:confirmar:GYR-502:20"
    assert "Descartar" in btn_descartar.text
    assert btn_descartar.callback_data == "factura_pajuela:descartar"

    # 2. Carga en base de datos simulando el callback
    db.registrar_pajuela(codigo_toro="GYR-502", cantidad=20)
    paj = db.obtener_pajuela("GYR-502")
    assert paj is not None
    assert paj["cantidad"] == 20

    # Cargar otra factura del mismo toro (acumula stock)
    db.registrar_pajuela(codigo_toro="GYR-502", cantidad=10)
    paj_actualizado = db.obtener_pajuela("GYR-502")
    assert paj_actualizado["cantidad"] == 30
