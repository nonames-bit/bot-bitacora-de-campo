"""Pruebas de registro, consulta y vinculación de fotos de campo."""

from src.engine.query_engine import QueryEngine


def test_registrar_y_consultar_fotos(db):
    # Registrar un animal
    db.registrar_animal("47", nombre="Mariposa", sexo="Hembra")

    # Registrar foto asociada
    fid1 = db.registrar_foto(
        ruta="media/foto_47_1.jpg",
        animal_tag="47",
        fecha="2026-08-26",
        caption="Vaca 47 en corral",
        user_id=12345,
    )
    assert fid1 is not None

    # Registrar otra foto
    fid2 = db.registrar_foto(
        ruta="media/foto_47_2.jpg",
        animal_tag="47",
        fecha="2026-08-27",
        caption="Vaca 47 con ternero",
        user_id=12345,
    )
    assert fid2 is not None

    # Consultar fotos por tag
    fotos_47 = db.fotos_de("47")
    assert len(fotos_47) == 2
    assert fotos_47[0]["caption"] == "Vaca 47 con ternero"

    # Consultar últimas fotos generales
    ultimas = db.ultimas_fotos(5)
    assert len(ultimas) == 2


def test_query_engine_fotos(db):
    db.registrar_animal("12", nombre="Parda", sexo="Hembra")
    qe = QueryEngine(db)

    # Sin fotos
    resp_vacia = qe.responder("¿hay fotos de la 12?")
    assert "No hay fotos registradas" in resp_vacia

    # Con foto
    db.registrar_foto(
        ruta="media/foto_12.jpg",
        animal_tag="12",
        fecha="2026-08-26",
        caption="Parda en pastoreo",
    )
    resp = qe.responder("¿tienes fotos de la 12?")
    assert "1 foto(s) de la 12" in resp
    assert "/foto 12" in resp


def test_historial_incluye_fotos(db):
    db.registrar_animal("33", sexo="Hembra")
    db.registrar_foto(
        ruta="media/foto_33.jpg",
        animal_tag="33",
        caption="Celo AM",
        ocr_text="TAG: 33 CELO",
    )
    h = db.historial("33")
    assert "fotos" in h
    assert len(h["fotos"]) == 1
    assert h["fotos"][0]["ocr_text"] == "TAG: 33 CELO"


def test_vincular_fotos_huerfanas_y_busqueda_amplia(db):
    # Caso real reportado por usuario: foto subida con caption 'N069 curando nuches' pero tag nulo
    db.registrar_animal("N069", sexo="Hembra", estado="ACTIVO")
    db.execute(
        "INSERT INTO fotos (ruta, caption, fecha) VALUES (?, ?, ?)",
        ("media/foto_6123051140_1787793909.jpg", "N069 curando nuches", "2026-08-27"),
    )

    # 1. Búsqueda directa por fotos_de debe encontrarla incluso antes de la migración por caption LIKE
    encontradas_prev = db.fotos_de("N069")
    assert len(encontradas_prev) >= 1
    assert "curando nuches" in encontradas_prev[0]["caption"]

    # 2. Auto-vinculación de fotos huérfanas
    vinculadas = db.vincular_fotos_huerfanas()
    assert vinculadas >= 1

    # 3. Verificar que ahora tiene tag y animal_id resueltos
    encontradas_post = db.fotos_de("N069")
    assert len(encontradas_post) >= 1
    assert encontradas_post[0]["tag"] is not None
    assert encontradas_post[0]["animal_id"] is not None
