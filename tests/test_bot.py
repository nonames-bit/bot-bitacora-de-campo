"""Pruebas de integración del bot (texto, audio, imagen y alertas)."""
from datetime import date

import pytest

from src.bot.bot_interface import Bot


def test_procesar_texto_parto(db):
    bot = Bot(db)
    resp = bot.procesar_texto("pario la 47, ternero macho")
    assert "parto" in resp.lower()
    assert db.count("partos") == 1
    assert db.get_animal("47") is not None


def test_procesar_texto_secado(db):
    bot = Bot(db)
    resp = bot.procesar_texto("se seco la 47 por mastitis")
    assert "secado" in resp.lower()
    assert db.count("secados") == 1
    fila = db.query_one("SELECT * FROM secados")
    assert fila["motivo"] == "Mastitis"


def test_procesar_servicio_genera_alertas(db):
    bot = Bot(db)
    bot.procesar_texto("insemine la 47 con toro brahman 502")
    assert db.count("servicios") == 1
    alertas = db.query("SELECT tipo_alerta FROM alertas")
    tipos = {a["tipo_alerta"] for a in alertas}
    assert {"ECOGRAFIA", "PALPACION", "SECADO", "PARTO_ESPERADO"} <= tipos


def test_procesar_celo_genera_alerta_inseminacion(db):
    bot = Bot(db)
    bot.procesar_texto("la 47 esta en celo en la tarde")
    assert db.count("celos") == 1
    alerta = db.query_one(
        "SELECT * FROM alertas WHERE tipo_alerta = 'INSEMINACION_PROGRAMADA'")
    assert alerta is not None
    assert alerta["fecha_programada"] is not None
    assert "mañana" in (alerta["descripcion"] or "")  # celo PM -> inseminar mañana


def test_procesar_tratamiento_retiro(db):
    bot = Bot(db)
    bot.procesar_texto("le puse oxitetraciclina 20ml a la 47 con 14 dias de retiro")
    t = db.query_one("SELECT * FROM tratamientos")
    assert t["producto"] == "oxitetraciclina"
    assert t["dias_retiro_carne"] == 14
    assert t["fecha_fin_retiro_carne"] is not None
    alertas = db.query("SELECT tipo_alerta FROM alertas WHERE tipo_alerta LIKE 'RETIRO%'")
    assert len(alertas) >= 1


def test_procesar_tratamiento_no_bloquea_leche_por_defecto(db):
    bot = Bot(db)
    bot.procesar_texto("le puse oxitetraciclina 20ml a la 47 con 14 dias de retiro")
    t = db.query_one("SELECT * FROM tratamientos")
    assert t["dias_retiro_carne"] == 14
    assert t["dias_retiro_leche"] == 0
    tipos = {a["tipo_alerta"] for a in db.query(
        "SELECT tipo_alerta FROM alertas WHERE tipo_alerta LIKE 'RETIRO%'")}
    assert "RETIRO_CARNE" in tipos
    assert "RETIRO_LECHE" not in tipos


def test_procesar_pesaje_gmd(db):
    bot = Bot(db, hoy=date(2026, 3, 11))
    bot.procesar_texto("pesaje de la 12 peso 350 kg el 2026-01-01")
    bot.procesar_texto("pesaje de la 12 peso 420 kg el 2026-03-11")
    pesajes = db.query("SELECT * FROM pesajes ORDER BY fecha")
    assert len(pesajes) == 2
    assert pesajes[1]["gmd_calculada"] == pytest.approx(70.0 / 69.0, rel=1e-3)


def test_consulta(db):
    bot = Bot(db)
    bot.procesar_texto("pario la 47, ternero macho")
    resp = bot.procesar_texto("¿cuándo parió la 47?")
    assert "47" in resp


def test_procesar_audio(db, tmp_path):
    audio = tmp_path / "nota.wav"
    audio.write_text("", encoding="utf-8")
    (tmp_path / "nota.wav.txt").write_text("pario la 47, ternero macho", encoding="utf-8")
    bot = Bot(db)
    resp = bot.procesar_audio(str(audio))
    assert "parto" in resp.lower()
    assert db.count("partos") == 1


def test_procesar_imagen(db, tmp_path):
    foto = tmp_path / "campo.jpg"
    foto.write_text("", encoding="utf-8")
    (tmp_path / "campo.jpg.txt").write_text(
        "tag:47\nfrasco:oxitetraciclina", encoding="utf-8")
    bot = Bot(db)
    resp = bot.procesar_imagen(str(foto))
    assert "47" in resp
    assert "oxitetraciclina" in resp


def test_procesar_audio_sin_transcripcion(db, tmp_path):
    audio = tmp_path / "sin_nota.wav"
    audio.write_text("", encoding="utf-8")
    bot = Bot(db)
    resp = bot.procesar_audio(str(audio))
    assert "no se pudo transcribir" in resp.lower()


def test_desconocido(db):
    bot = Bot(db)
    # 3 palabras sin sentido → debe seguir siendo desconocido (no confundir con consulta de nombre de 1-2 palabras como "patricia" o "olegario 1")
    resp = bot.procesar_texto("bla bla bla xyz extra")
    assert "no pude interpretar" in resp.lower()
