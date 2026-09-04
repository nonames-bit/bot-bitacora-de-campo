"""Tests Etapa A Fase 7: fichas QR por lote (PDF A4, 6 por hoja)."""
import os

import pytest

from src.db.database import Database
from src.reports.qr_fichas import generar_fichas_lote, listar_animales_lote, qr_payload


@pytest.fixture
def db_lote():
    d = Database(":memory:")
    d.create_tables()
    d.registrar_potrero(nombre="Guayabal", codigo="G1")
    pid = d.potrero_id("Guayabal")
    d.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero="Guayabal",
                       fecha_nacimiento="2022-01-10")
    d.registrar_animal("48", sexo="Hembra", estado="ACTIVO", potrero="Guayabal")
    d.registrar_animal("99", sexo="Hembra", estado="VENDIDO", potrero="Guayabal")
    # Lote vía traslados (animal creado ACTIVO explícito: el inventario es estricto).
    d.registrar_animal("60", sexo="Macho", estado="ACTIVO")
    d.registrar_traslado("60", fecha="2026-08-20", lote="LOTE-A",
                         potrero_destino=pid)
    yield d
    d.close()


def test_genera_pdf_por_potrero(tmp_path, db_lote):
    ruta = str(tmp_path / "fichas.pdf")
    out = generar_fichas_lote(db_lote, "Guayabal", salida=ruta, media_dir="media")
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0
    with open(out, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_qr_legible_y_activo_estricto(tmp_path, db_lote):
    # Payload esperado del QR.
    payload, url = qr_payload("47")
    assert payload == "JA://animal/47"
    assert url == "/ficha/47"
    # Inventario estricto: el VENDIDO no entra.
    tags = {a["tag"] for a in listar_animales_lote(db_lote, "Guayabal")}
    assert "47" in tags and "99" not in tags
    # Lote vía traslados genera PDF válido.
    ruta = str(tmp_path / "lote.pdf")
    out = generar_fichas_lote(db_lote, "LOTE-A", salida=ruta, media_dir="media")
    assert os.path.exists(out) and os.path.getsize(out) > 0
