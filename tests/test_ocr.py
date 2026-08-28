"""Pruebas unitarias y de integración del módulo OCR (aretes, tags y frascos de medicamentos)."""
from datetime import date
import os
import pytest

from src.bot.bot_interface import Bot
from src.db.database import Database
from src.ocr import OCREngine, detect_medicamento, detect_tags
from src.parsers.media_handler import ImageInfo, MediaError, extract_image_info


def test_ocr_availability_and_backend():
    """Verifica la detección de disponibilidad y fallback graceful."""
    engine = OCREngine()
    disponible = engine.is_available()
    backend = engine.get_backend()
    assert isinstance(disponible, bool)
    assert backend in ("pytesseract", "easyocr", None)


def test_detect_tags_regex():
    """Verifica la extracción precisa de tags alfanuméricos, numéricos y nombres."""
    # 1. Tags alfanuméricos con letras y números
    t1 = detect_tags("Se identificó el arete N069 en el corral")
    assert "N069" in t1

    t2 = detect_tags("Arete N-069 y N 069")
    assert any("N069" in x or "N-069" in x for x in t2)

    t3 = detect_tags("Vaca con tag JA26 y ternero O-123")
    assert "JA26" in t3
    assert "O-123" in t3

    # 2. Tag numérico puro
    t4 = detect_tags("Foto de la vaca 47")
    assert "47" in t4

    # 3. Tags explícitos con palabras clave
    t5 = detect_tags("tag: 105 caravana #BR88 arete: H-12")
    assert "105" in t5
    assert "BR88" in t5
    assert "H-12" in t5

    # 4. Nombre identificador
    t6 = detect_tags("vaca patricia")
    assert "patricia" in t6

    # 5. Descarte de ruido (fechas, dosis, potreros, lotes)
    t7 = detect_tags("Dosis de 20ml aplicada en potrero 3 lote 2 fecha 2026-08-28 a la 47")
    assert "47" in t7
    assert "20ml" not in t7
    assert "potrero" not in t7
    assert "lote" not in t7


def test_detect_medicamento():
    """Verifica la extracción de fármacos, dosis, vías, lotes y tiempos de retiro."""
    # 1. Frasco completo con todos los metadatos
    texto_frasco = (
        "Oxitetraciclina L.A. 200mg/ml\n"
        "Dosis: 1ml/10kg\n"
        "Vía: IM\n"
        "Lote: LT-9842\n"
        "Vence: 12/2028\n"
        "Retiro: 14 dias carne"
    )
    med = detect_medicamento(texto_frasco)
    assert med["producto"] == "Oxitetraciclina"
    assert med["principio_activo"] == "Oxitetraciclina"
    assert med["dosis"] == "1ml/10kg"
    assert med["via"] == "IM"
    assert med["lote"] == "LT-9842"
    assert med["vencimiento"] == "12/2028"
    assert med["dias_retiro_carne"] == 14
    assert med["dias_retiro"] == 14

    # 2. Ivermectina con vía SC
    med2 = detect_medicamento("Ivermectina 1% inyectable 20ml vía subcutanea lote AB-12")
    assert med2["producto"] == "Ivermectina"
    assert med2["dosis"] == "20ml"
    assert med2["via"] == "SC"
    assert med2["lote"] == "AB-12"

    # 3. Penicilina con retiro en leche
    med3 = detect_medicamento("Penicilina G procaína 10 cc IM 30 dias de retiro en leche")
    assert med3["producto"] == "Penicilina"
    assert med3["dosis"] == "10cc"
    assert med3["via"] == "IM"
    assert med3["dias_retiro_leche"] == 30

    # 4. Texto sin medicamento
    assert detect_medicamento("vaca pastando en potrero norte") == {}


def test_ocr_extract_text_sidecar_and_fallback(tmp_path):
    """Verifica extract_text usando archivos de texto directos y sidecars acompañantes."""
    engine = OCREngine()

    # Archivo .txt directo
    txt_file = tmp_path / "muestra.txt"
    txt_file.write_text("Oxitetraciclina 20ml tag N069", encoding="utf-8")
    extraido = engine.extract_text(str(txt_file))
    assert extraido == "Oxitetraciclina 20ml tag N069"

    # Archivo de imagen simulado con sidecar .txt
    img_file = tmp_path / "foto_arete.jpg"
    img_file.write_text("", encoding="utf-8")
    (tmp_path / "foto_arete.jpg.txt").write_text("Arete JA26", encoding="utf-8")
    extraido_sc = engine.extract_text(str(img_file))
    assert "JA26" in extraido_sc

    # Imagen inexistente
    assert engine.extract_text(str(tmp_path / "inexistente.jpg")) == ""


def test_media_handler_extract_image_info_integration(tmp_path):
    """Verifica la integración entre media_handler y OCREngine con sidecars y callbacks."""
    # 1. Sidecar con líneas estructuradas
    img1 = tmp_path / "frasco1.jpg"
    img1.write_text("", encoding="utf-8")
    (tmp_path / "frasco1.jpg.txt").write_text("tag: 47\nfrasco: oxitetraciclina", encoding="utf-8")
    info1 = extract_image_info(str(img1))
    assert "47" in info1.tags
    assert "oxitetraciclina" in info1.frascos

    # 2. Sidecar con texto libre procesado por OCR
    img2 = tmp_path / "frasco2.jpg"
    img2.write_text("", encoding="utf-8")
    (tmp_path / "frasco2.jpg.txt").write_text(
        "Ivermectina 20ml SC Lote L881 a la vaca N069", encoding="utf-8"
    )
    info2 = extract_image_info(str(img2))
    assert "N069" in info2.tags
    assert "Ivermectina" in info2.frascos
    assert info2.medicamento is not None
    assert info2.medicamento["dosis"] == "20ml"

    # 3. Callback inyectado
    info_mock = ImageInfo(tags=["JA26"], frascos=["Penicilina"])
    info3 = extract_image_info("fake.jpg", ocr=lambda _: info_mock)
    assert info3.tags == ["JA26"]
    assert info3.frascos == ["Penicilina"]

    # 4. Sin sidecar ni OCR real disponible (en archivo inexistente o sin sidecar)
    if not OCREngine().is_available():
        img_sin_ocr = tmp_path / "sin_ocr.jpg"
        img_sin_ocr.write_text("", encoding="utf-8")
        with pytest.raises(MediaError):
            extract_image_info(str(img_sin_ocr))


def test_bot_procesar_imagen_con_ocr_y_persistencia(db, tmp_path):
    """Verifica que el Bot procese imágenes extrayendo OCR, vinculando tags y guardando en BD."""
    foto = tmp_path / "tratamiento_vaca.jpg"
    foto.write_text("", encoding="utf-8")
    (tmp_path / "tratamiento_vaca.jpg.txt").write_text(
        "le puse oxitetraciclina 20ml a la 47 con 14 dias de retiro",
        encoding="utf-8",
    )

    bot = Bot(db)
    resp = bot.procesar_imagen(str(foto))

    # Debe haber ejecutado el evento de tratamiento
    assert "oxitetraciclina" in resp.lower()
    assert "47" in resp

    # Debe haber registrado el tratamiento en la tabla tratamientos
    t = db.query_one("SELECT * FROM tratamientos WHERE producto = 'oxitetraciclina'")
    assert t is not None
    assert t["dias_retiro_carne"] == 14

    # Debe haber registrado la foto en la tabla fotos con el texto OCR
    f = db.query_one("SELECT * FROM fotos WHERE ruta = ?", (str(foto),))
    assert f is not None
    assert f["tag"] == "47"
    assert f["ocr_text"] is not None
    assert "oxitetraciclina" in f["ocr_text"]


def test_db_fotos_ocr_text_persistencia_y_migracion(db):
    """Verifica el campo ocr_text en SQLite y la migración idempotente."""
    db.registrar_animal("N069")
    fid = db.registrar_foto(
        ruta="media/foto_n069.jpg",
        animal_tag="N069",
        caption="Arete lateral",
        ocr_text="TAG N069 2026",
    )
    assert isinstance(fid, int)

    foto = db.query_one("SELECT * FROM fotos WHERE id = ?", (fid,))
    assert foto["tag"] == "N069"
    assert foto["caption"] == "Arete lateral"
    assert foto["ocr_text"] == "TAG N069 2026"

    # Re-ejecutar create_tables no debe fallar ni borrar datos
    db.create_tables()
    foto2 = db.query_one("SELECT * FROM fotos WHERE id = ?", (fid,))
    assert foto2["ocr_text"] == "TAG N069 2026"
