"""Informes PDF por sección: cada uno trae su propio contenido."""
from datetime import date, timedelta

import pypdf
import pytest

from src.db.database import Database
from src.reports.pdf_report import generar_pdf
from src.reports.pdf_secciones import ContextoReporte, datos_leche_periodo

HOY = date(2026, 9, 25)


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "b.db")).create_tables()
    d.registrar_potrero(nombre="Guayabal", codigo="G1", area_has=4, aforo_kg_m2=1.4)
    for i in range(1, 6):
        d.registrar_animal(f"V{i}", sexo="Hembra", estado="ACTIVO", potrero="Guayabal", fecha_nacimiento="2020-01-01")
        d.registrar_parto(f"V{i}", fecha="2025-06-01", sexo_cria="Hembra")
        s = HOY - timedelta(days=70 + i)
        d.registrar_servicio(f"V{i}", fecha=s.isoformat(), toro_pajilla="HOL502",
                             fep_calculada=(s + timedelta(days=283)).isoformat())
    for k in range(60):
        d.registrar_produccion_leche(fecha=(HOY - timedelta(days=k)).isoformat(), litros=100 + (0 if k < 30 else -20))
    d.registrar_leche("V1", fecha=HOY.isoformat(), litros=15)  # control individual: no debe sumarse al tanque
    d.registrar_tratamiento("V2", fecha=HOY.isoformat(), producto="Oxitetraciclina", dias_retiro_leche=4,
                            fecha_fin_retiro_leche=(HOY + timedelta(days=4)).isoformat())
    d.registrar_finanza(fecha=HOY.isoformat(), tipo="INGRESO", categoria="LECHE", concepto="Quincena", monto=300000, litros=200)
    yield d
    d.close()


def _texto(ruta) -> str:
    return " ".join((p.extract_text() or "") for p in pypdf.PdfReader(str(ruta)).pages).upper()


def test_informe_leche_tiene_contenido_de_leche(db, tmp_path):
    txt = _texto(generar_pdf(db, ruta_salida=str(tmp_path / "l.pdf"), hoy=HOY, periodo="mensual", seccion="leche"))
    assert "PRODUCCIÓN LECHERA DEL PERÍODO" in txt
    assert "LITROS / VACA / DÍA" in txt
    assert "DETALLE DIARIO DEL TANQUE" in txt
    assert "LECHE BLOQUEADA POR RETIRO" in txt
    assert "REGISTRO DE CELOS" not in txt  # antes todos los informes eran iguales


def test_informe_reproduccion_tiene_indicadores(db, tmp_path):
    txt = _texto(generar_pdf(db, ruta_salida=str(tmp_path / "r.pdf"), hoy=HOY, periodo="mensual", seccion="reproduccion"))
    assert "INDICADORES REPRODUCTIVOS DEL HATO" in txt
    assert "SERVICIOS POR CONCEPCIÓN" in txt
    assert "PALPACIONES PENDIENTES" in txt
    assert "PRODUCCIÓN LECHERA DEL PERÍODO" not in txt


def test_informe_general_tiene_tablero_y_todas_las_areas(db, tmp_path):
    txt = _texto(generar_pdf(db, ruta_salida=str(tmp_path / "g.pdf"), hoy=HOY, periodo="mensual"))
    for marca in ("TABLERO EJECUTIVO DE LA FINCA", "PRODUCCIÓN LECHERA DEL PERÍODO",
                  "INDICADORES REPRODUCTIVOS DEL HATO", "SANIDAD ANIMAL", "FINANZAS"):
        assert marca in txt, marca


@pytest.mark.parametrize("seccion", ["sanidad", "pasturas", "finanzas", "inventario"])
def test_informes_de_otras_secciones_se_generan(db, tmp_path, seccion):
    ruta = generar_pdf(db, ruta_salida=str(tmp_path / f"{seccion}.pdf"), hoy=HOY, periodo="semanal", seccion=seccion)
    assert len(pypdf.PdfReader(ruta).pages) >= 1


def test_seccion_sin_datos_avisa_en_vez_de_fallar(tmp_path):
    d = Database(str(tmp_path / "v.db")).create_tables()
    try:
        txt = _texto(generar_pdf(d, ruta_salida=str(tmp_path / "v.pdf"), hoy=HOY, seccion="leche"))
        assert "NO HAY REGISTROS DE PRODUCCIÓN DE LECHE" in txt
    finally:
        d.close()


def test_datos_leche_periodo_usa_tanque_y_compara(db):
    ctx = ContextoReporte(db=db, hoy=HOY, desde=HOY - timedelta(days=29), hasta=HOY, dias=30, tmp_dir=None, ancho=100)
    d = datos_leche_periodo(ctx)
    assert d["total"] == 3000          # 30 días x 100 L, sin el control individual de 15 L
    assert d["total_ant"] == 2400      # período anterior: 30 días x 80 L
    assert d["precio_litro"] == 1500
    assert [r["tag"] for r in d["retiros"]] == ["V2"]
