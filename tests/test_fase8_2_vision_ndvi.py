"""Pruebas unitarias para Fase 8.2:
- OCR y Visión Avanzada de Aretes sucios, dañados, tipo botón y paleta.
- Monitoreo Satelital de Pasturas vía NDVI (Sentinel-2 L2A).
- Cálculo de Biomasa Forrajera, Aforo Satelital y Ajuste de Capacidad de Carga.
- Persistencia SQLite de lecturas satelitales y auditoría /deshacer.
- Enrutamiento NLU de consultas sobre índice verde y satélite.
- Formateadores HTML y teclados interactivos de Telegram (/ndvi, /satelite).
"""
import os
import tempfile
from datetime import date

import pytest
from PIL import Image

from src.db.database import Database
from src.engine.query_engine import QueryEngine
from src.gis.sentinel_ndvi import (
    SentinelNDVI,
    ajustar_capacidad_carga_con_ndvi,
    calcular_ndvi,
    clasificar_ndvi,
    estimar_aforo_kg_m2_desde_ndvi,
    estimar_biomasa_ms_ha,
)
from src.parsers.media_handler import extract_image_info
from src.server.formatters import formatear_ndvi_panel
from src.server.keyboards import crear_teclado_clima, crear_teclado_ndvi
from src.vision.arete_detector import (
    AreteDetector,
    clasificar_tipo_arete,
    corregir_caracteres_confusos,
    detectar_arete_avanzado,
    mejorar_imagen_para_ocr,
)


def test_vision_arete_detector_correcciones():
    """Valida la corrección de caracteres ambiguos en aretes de ganado."""
    # 1. Prefijo + O confundida con cero
    assert corregir_caracteres_confusos("NO69") == "N069"
    assert corregir_caracteres_confusos("N-O69") == "N-069"
    assert corregir_caracteres_confusos("JA-2G") == "JA-26"
    assert corregir_caracteres_confusos("A-I05") == "A-105"
    assert corregir_caracteres_confusos("JA2B") == "JA28"

    # 2. Números con letras confundidas
    assert corregir_caracteres_confusos("IO5") == "105"
    assert corregir_caracteres_confusos("4O7") == "407"
    assert corregir_caracteres_confusos("S05") == "505"

    # 3. Clasificación de tipo de arete
    assert clasificar_tipo_arete(100, 90) == "BOTON"
    assert clasificar_tipo_arete(80, 200) == "PALETA"
    assert clasificar_tipo_arete(0, 0) == "DESCONOCIDO"


def test_vision_arete_procesamiento_imagen():
    """Valida la mejora visual y detección de arete sobre archivos de imagen reales/temporales."""
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "arete_test.jpg")
        txt_path = os.path.join(tmpdir, "arete_test.jpg.txt")

        # Crear una imagen sintética pequeña
        img = Image.new("RGB", (400, 300), color=(240, 230, 100))
        img.save(img_path)

        # Crear sidecar simulado de campo
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("arete: N-O69")

        # Realce de imagen
        enhanced = mejorar_imagen_para_ocr(img_path)
        assert enhanced is not None
        assert os.path.isfile(enhanced)

        # Detección avanzada
        res = detectar_arete_avanzado(img_path)
        assert res["tag"] == "N-069"
        assert res["confianza"] > 0.8
        assert res["tipo_arete"] == "PALETA"

        # Media handler integración
        info = extract_image_info(img_path)
        assert "N-069" in info.tags or "N069" in info.tags or "N-O69" in info.tags


def test_sentinel_ndvi_formulas_biofisicas():
    """Valida los modelos matemáticos y clasificaciones del índice NDVI."""
    # 1. Cálculo de NDVI = (NIR - RED) / (NIR + RED)
    ndvi_alto = calcular_ndvi(nir=0.85, red=0.15)
    assert ndvi_alto == pytest.approx(0.70, 0.01)

    ndvi_bajo = calcular_ndvi(nir=0.30, red=0.20)
    assert ndvi_bajo == pytest.approx(0.20, 0.01)

    assert calcular_ndvi(0.0, 0.0) == 0.0

    # 2. Clasificación de vigor
    cls_exc = clasificar_ndvi(0.75)
    assert cls_exc["categoria"] == "EXCELENTE"
    assert cls_exc["emoji"] == "🟢"
    assert not cls_exc["alerta"]

    cls_est = clasificar_ndvi(0.40)
    assert cls_est["categoria"] == "ESTRÉS / BAJA BIOMASA"
    assert cls_est["alerta"] is True

    cls_crit = clasificar_ndvi(0.25)
    assert cls_crit["categoria"] == "CRÍTICO / SUELO DESNUDO"
    assert cls_crit["alerta"] is True

    # 3. Estimación de aforo y biomasa MS
    aforo_est = estimar_aforo_kg_m2_desde_ndvi(0.70)
    assert aforo_est >= 1.30 and aforo_est <= 2.0

    ms_ha = estimar_biomasa_ms_ha(0.70, pct_ms=22.0)
    assert ms_ha > 2000.0  # Más de 2 toneladas de MS/ha

    # 4. Ajuste dinámico de capacidad de carga
    cap_res = ajustar_capacidad_carga_con_ndvi(aforo_kg_m2=1.5, ndvi=0.72, area_has=10.0, dias_rotacion=30)
    assert cap_res["factor_satelital"] == 1.15
    assert cap_res["carga_sostenible_ugg_ha"] > 0
    assert cap_res["capacidad_total_potrero_ugg"] > 0


def test_database_ndvi_persistencia_y_deshacer(db: Database):
    """Valida la persistencia SQLite de lecturas satelitales y soporte /deshacer."""
    pot_id = db.registrar_potrero(nombre="Potrero La Esperanza", area_has=12.5)

    # 1. Registrar lectura satelital
    id_ndvi = db.registrar_lectura_ndvi(
        potrero_id_o_nom=pot_id,
        ndvi_promedio=0.715,
        fecha="2026-08-31",
        biomasa_estimada_kg_ha=3100.0,
        aforo_estimado_kg_m2=1.42,
        cobertura_nubes_pct=2.5,
        fuente="Sentinel-2 L2A",
    )
    assert id_ndvi > 0

    # 2. Consultar historial reciente
    filas = db.obtener_ndvi_reciente(potrero_id=pot_id)
    assert len(filas) == 1
    assert filas[0]["ndvi_promedio"] == pytest.approx(0.715, 0.001)
    assert filas[0]["potrero_nombre"] == "Potrero La Esperanza"

    # 3. Resumen satelital de la finca
    resumen = db.resumen_ndvi_finca()
    assert resumen["total_potreros"] >= 1
    assert resumen["promedio_ndvi"] > 0.0
    assert "EXCELENTE" in resumen["categoria_finca"] or "ÓPTIMO" in resumen["categoria_finca"]

    # 4. Auditoría y /deshacer
    det = db.detalle_registro("monitoreo_satelital_ndvi", id_ndvi)
    assert det is not None
    assert "NDVI 0.715" in det["resumen"]

    # Eliminar con /deshacer
    eliminado = db.eliminar_registro("monitoreo_satelital_ndvi", id_ndvi)
    assert eliminado is True


def test_query_engine_consultas_ndvi(db: Database):
    """Valida el enrutamiento y respuestas de lenguaje natural sobre monitoreo satelital."""
    pot1 = db.registrar_potrero(nombre="Potrero Sabana 1", area_has=15.0, dias_reposo=30)
    pot2 = db.registrar_potrero(nombre="Potrero Bajo Inundable", area_has=8.0, dias_ocupacion=6)

    db.registrar_lectura_ndvi(potrero_id_o_nom=pot1, ndvi_promedio=0.74, fecha="2026-08-31")
    db.registrar_lectura_ndvi(potrero_id_o_nom=pot2, ndvi_promedio=0.31, fecha="2026-08-31")

    qe = QueryEngine(db, hoy=date(2026, 8, 31))

    # Consulta 1: NDVI general
    resp1 = qe.responder("¿cómo está el NDVI de los potreros?")
    assert "MONITOREO SATELITAL DE PASTURAS" in resp1
    assert "Potrero Sabana 1" in resp1
    assert "NDVI: 0.740" in resp1

    # Consulta 2: Índice verde / satélite
    resp2 = qe.responder("¿cuál es el índice verde de la finca?")
    assert "SENTINEL-2" in resp2
    assert "ALERTA DE REPOSO" in resp2 or "Potrero Bajo Inundable" in resp2


def test_telegram_formatters_y_teclados_ndvi(db: Database):
    """Valida los formateadores HTML del panel satelital y los teclados táctiles."""
    pot_id = db.registrar_potrero(nombre="Potrero Alto", area_has=10.0)
    db.registrar_lectura_ndvi(potrero_id_o_nom=pot_id, ndvi_promedio=0.68, fecha="2026-08-31")

    # Formateador
    panel_html = formatear_ndvi_panel(db)
    assert "MONITOREO SATELITAL DE PASTURAS (SENTINEL-2)" in panel_html
    assert "Potrero Alto" in panel_html
    assert "0.680" in panel_html

    # Teclado NDVI
    t_ndvi = crear_teclado_ndvi()
    assert len(t_ndvi.inline_keyboard) >= 2

    # Teclado Clima actualizado con botón satelital
    t_clima = crear_teclado_clima()
    botones_txt = [b.text for row in t_clima.inline_keyboard for b in row]
    assert any("Satélite NDVI" in txt for txt in botones_txt)
