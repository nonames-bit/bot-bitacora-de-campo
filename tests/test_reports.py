"""Pruebas de la generación de reportes PDF (recolección pura y documento)."""
from datetime import date

from src.reports import generar_pdf, recolectar_datos
from src.server.telegram_bot import parsear_args_reporte


def test_recolectar_datos_inventario_y_periodo(db):
    db.registrar_animal("101", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("102", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("201", sexo="Macho", estado="ACTIVO")
    db.registrar_animal("300", sexo="Hembra", estado="VENDIDO")

    datos = recolectar_datos(db, 7, hoy=date(2026, 8, 26))

    assert datos["inventario"]["activos"] == 3
    assert datos["inventario"]["hembras"] == 2
    assert datos["inventario"]["machos"] == 1
    assert datos["inventario"]["historico_total"] == 4
    assert datos["periodo"] == {"desde": "2026-08-20", "hasta": "2026-08-26"}


def test_recolectar_datos_eventos_filtra_por_periodo(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("47", fecha="2026-08-25", sexo_cria="Macho",
                       estado_cria="VIVO", peso_nacimiento=35.0)
    db.registrar_parto("47", fecha="2026-08-10", sexo_cria="Hembra")

    datos = recolectar_datos(db, 7, hoy=date(2026, 8, 26))

    assert "partos" in datos["eventos"]
    partos = datos["eventos"]["partos"]
    assert len(partos) == 1
    assert partos[0]["fecha"] == "2026-08-25"
    assert partos[0]["tag"] == "47"
    assert "35" in partos[0]["resumen"]
    # Tablas sin filas quedan excluidas.
    assert "muertes" not in datos["eventos"]


def test_recolectar_datos_incluye_finanzas_del_periodo(db):
    """El reporte general debe traer también el resumen financiero del mismo
    período del reporte (no el acumulado anual de la PWA) -- ver Fase 2 de
    Finanzas."""
    db.registrar_finanza(fecha="2026-08-24", tipo="INGRESO", categoria="VENTA_LECHE", monto=500000)
    db.registrar_finanza(fecha="2026-08-25", tipo="EGRESO", categoria="INSUMO", monto=100000)
    db.registrar_finanza(fecha="2026-07-01", tipo="INGRESO", categoria="VENTA_LECHE", monto=999999)  # fuera del período

    datos = recolectar_datos(db, 7, hoy=date(2026, 8, 26))

    resumen = datos["finanzas"]["resumen"]
    assert resumen["total_ingresos"] == 500000
    assert resumen["total_egresos"] == 100000
    assert resumen["utilidad"] == 400000
    assert "margen_utilidad_pct" in datos["finanzas"]["kpis"]


def test_recolectar_datos_incluye_spi_sequia(db):
    db.registrar_spi_sequia(dias_ventana=30, mm_actual=10.0, spi_valor=-1.8,
                            clasificacion="Sequía severa", fecha="2026-08-24")
    datos = recolectar_datos(db, 7, hoy=date(2026, 8, 26))
    assert datos["spi_sequia"]
    assert datos["spi_sequia"][0]["clasificacion"] == "Sequía severa"
    assert "recomendaciones" in datos["clima"]


def test_recolectar_datos_alertas_hasta_hoy_mas_7(db):
    db.registrar_animal("47")
    db.registrar_alerta("47", "ECOGRAFIA", "2026-08-29", descripcion="Ecografía día 35")
    db.registrar_alerta("47", "PALPACION", "2026-09-05", descripcion="Palpación rectal")

    datos = recolectar_datos(db, 7, hoy=date(2026, 8, 26))

    assert len(datos["alertas"]) == 1
    alerta = datos["alertas"][0]
    assert alerta["tipo"] == "ECOGRAFIA"
    assert alerta["fecha"] == "2026-08-29"
    assert alerta["tag"] == "47"


def test_recolectar_datos_traslado_resuelve_potreros(db):
    db.registrar_animal("47")
    db.registrar_potrero(nombre="Norte", codigo="05")
    db.registrar_potrero(nombre="Sur", codigo="06")
    origen = db.potrero_id("Norte")
    destino = db.potrero_id("Sur")

    db.registrar_traslado("47", fecha="2026-08-25",
                          potrero_origen=origen, potrero_destino=destino)

    datos = recolectar_datos(db, 7, hoy=date(2026, 8, 26))

    traslados = datos["eventos"]["traslados"]
    assert len(traslados) == 1
    assert traslados[0]["resumen"] == "Norte -> Sur"


def test_parsear_args_reporte_default_semanal():
    assert parsear_args_reporte([]) == (7, "semanal")


def test_parsear_args_reporte_diario():
    assert parsear_args_reporte(["diario"]) == (1, "diario")


def test_parsear_args_reporte_n_dias():
    assert parsear_args_reporte(["10"]) == (10, "10d")


def test_parsear_args_reporte_invalido():
    assert parsear_args_reporte(["abc"]) is None
    assert parsear_args_reporte(["0"]) is None
    assert parsear_args_reporte(["-3"]) is None
    assert parsear_args_reporte(["diario", "extra"]) is None


def test_generar_pdf_genera_archivo_real(tmp_path, db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("47", fecha="2026-08-24", sexo_cria="Macho", peso_nacimiento=35.0)

    ruta = tmp_path / "reporte.pdf"
    resultado = generar_pdf(db, 7, str(ruta), hoy=date(2026, 8, 26))

    assert resultado == str(ruta)
    assert ruta.exists()
    assert ruta.stat().st_size > 1024
    with open(ruta, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_generar_pdf_incluye_graficos_embebidos(tmp_path, db):
    from src.engine.charts import graficos_disponibles
    if not graficos_disponibles():
        import pytest
        pytest.skip("matplotlib no está instalado en este entorno")

    db.registrar_potrero("Norte")
    for i, tag in enumerate(["V1", "V2", "V3"]):
        db.registrar_animal(tag, sexo="Hembra" if i % 2 == 0 else "Macho",
                            estado="ACTIVO", potrero="Norte", fecha_nacimiento="2024-01-01")
    db.registrar_parto("V1", fecha="2026-08-24", sexo_cria="Macho", peso_nacimiento=35.0)

    ruta = tmp_path / "reporte_con_graficos.pdf"
    generar_pdf(db, 7, str(ruta), hoy=date(2026, 8, 26))

    import pypdf
    r = pypdf.PdfReader(str(ruta))
    total_imagenes = sum(len(list(p.images)) for p in r.pages)
    # Al menos el logo (si existe) + 1 gráfico; con datos de categorías
    # poblado, debe haber por lo menos una imagen PNG de matplotlib.
    nombres = [img.name for p in r.pages for img in p.images]
    assert any(n.endswith(".png") for n in nombres), f"no se embebió ningún gráfico: {nombres}"
    assert total_imagenes >= 1


def test_generar_pdf_incluye_seccion_finanzas(tmp_path, db):
    db.registrar_finanza(fecha="2026-08-24", tipo="INGRESO", categoria="VENTA_LECHE", monto=1500000)
    db.registrar_finanza(fecha="2026-08-25", tipo="EGRESO", categoria="INSUMO", monto=300000)

    ruta = tmp_path / "reporte_finanzas.pdf"
    generar_pdf(db, 7, str(ruta), hoy=date(2026, 8, 26))

    import pypdf
    texto = "".join(p.extract_text() or "" for p in pypdf.PdfReader(str(ruta)).pages)
    assert "FINANZAS" in texto.upper()
    assert "1.500.000" in texto


def test_generar_pdf_incluye_seccion_clima_y_spi(tmp_path, db):
    db.registrar_spi_sequia(dias_ventana=30, mm_actual=10.0, spi_valor=-1.8,
                            clasificacion="Sequía severa", fecha="2026-08-24")

    ruta = tmp_path / "reporte_clima.pdf"
    generar_pdf(db, 7, str(ruta), hoy=date(2026, 8, 26))

    import pypdf
    texto = "".join(p.extract_text() or "" for p in pypdf.PdfReader(str(ruta)).pages)
    assert "SEQUÍA" in texto.upper()
    assert "Sequía severa" in texto


def test_generar_pdf_sin_finanzas_ni_spi_no_agrega_secciones_vacias(tmp_path, db):
    """Sin ningún movimiento financiero ni SPI calculado, esas secciones no
    deben aparecer en blanco -- mismo criterio que el resto del reporte
    (tablas sin filas quedan excluidas)."""
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")

    ruta = tmp_path / "reporte_vacio.pdf"
    generar_pdf(db, 7, str(ruta), hoy=date(2026, 8, 26))

    import pypdf
    texto = "".join(p.extract_text() or "" for p in pypdf.PdfReader(str(ruta)).pages)
    assert "INGRESOS, EGRESOS" not in texto.upper()
    assert "ALERTA TEMPRANA DE SEQUÍA" not in texto.upper()


def test_recolectar_datos_incluye_potreros_sg(db):
    p1 = db.registrar_potrero("ORDENO SANTA MARTHA", "01")
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2020-01-01")
    db.registrar_parto("V1", fecha="2026-06-01")

    datos = recolectar_datos(db, 7, hoy=date(2026, 8, 28))
    assert "potreros_sg" in datos
    assert len(datos["potreros_sg"]) == 1
    assert "ORDENO" in datos["potreros_sg"][0]["display"]
    assert datos["potreros_sg"][0]["vp"] == 1
    assert datos["potreros_sg"][0]["total"] == 1

