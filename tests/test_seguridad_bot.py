"""Regresiones de seguridad del bot de Telegram (revisión integral)."""
from src.db.database import Database
from src.engine.query.helpers import buscar_foto_animal
from src.server.formatters import formatear_pesajes_animal_tab


def test_buscar_foto_no_sale_de_media(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    (media / "a047.jpg").write_bytes(b"x")
    secreto = tmp_path / "secreto.jpg"
    secreto.write_bytes(b"x")
    db = Database(str(tmp_path / "b.db")).create_tables()
    try:
        assert buscar_foto_animal(db, "../secreto", str(media)) is None
        assert buscar_foto_animal(db, str(tmp_path / "secreto"), str(media)) is None
        assert buscar_foto_animal(db, "a047", str(media)) == str(media / "a047.jpg")
    finally:
        db.close()


def test_formatter_escapa_nombre_del_animal(tmp_path):
    db = Database(str(tmp_path / "b.db")).create_tables()
    try:
        db.registrar_animal("47", sexo="Hembra", nombre="<a href='x'>Lola</a>")
        txt = formatear_pesajes_animal_tab(db, "47")
        assert "<a href" not in txt
        assert "&lt;a href" in txt
    finally:
        db.close()

