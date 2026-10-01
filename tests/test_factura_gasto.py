"""Facturas de gasto leídas con IA: anotarlas en Finanzas desde Telegram y
repartirlas por categoría desde la PWA."""
import os

from src.engine.factura_gasto import anotar_factura, partes_factura, pide_leer_factura, texto_propuesta

RES_SAL_Y_DROGA = {
    "ok": True, "es_factura": True, "tipo": "EGRESO", "fecha": "2026-10-01",
    "proveedor": "Agrotienda <El Ganadero>", "concepto": "Sal y droga",
    "categoria_sugerida": "SAL_MINERALES", "monto_total": 476000,
    "desglose": [
        {"categoria": "SAL_MINERALES", "concepto": "Sal mineralizada x3", "monto": 357000},
        {"categoria": "MEDICAMENTOS", "concepto": "Ivermectina", "monto": 119000},
    ],
}


def test_pide_leer_factura_por_pie_de_foto_o_por_ocr():
    assert pide_leer_factura("factura de la sal", "")
    assert pide_leer_factura("Compré droga", "")
    assert pide_leer_factura("", "NIT 900.123 TOTAL $ 45.000")
    assert not pide_leer_factura("la 47 en el potrero", "")
    assert not pide_leer_factura("", "47")


def test_texto_propuesta_lista_cada_categoria_y_escapa_html():
    txt = texto_propuesta(RES_SAL_Y_DROGA)
    assert "Sal y minerales" in txt and "Drogas / medicamentos" in txt
    assert "$357.000" in txt and "$476.000" in txt
    assert "&lt;El Ganadero&gt;" in txt


def test_anotar_factura_crea_un_egreso_por_categoria(db):
    ids = anotar_factura(db, RES_SAL_Y_DROGA, foto_ruta="media/factura_tg_1.jpg", user_id=7)
    assert len(ids) == 2
    filas = db.query("SELECT tipo, categoria, monto, contraparte, foto_ruta, registrado_por FROM finanzas ORDER BY id")
    assert [(f["categoria"], f["monto"]) for f in filas] == [("SAL_MINERALES", 357000), ("MEDICAMENTOS", 119000)]
    assert all(f["tipo"] == "EGRESO" and f["foto_ruta"] == "media/factura_tg_1.jpg" for f in filas)
    assert all(f["contraparte"] == "Agrotienda <El Ganadero>" and str(f["registrado_por"]) == "7" for f in filas)


def test_anotar_factura_sin_desglose_usa_el_total(db):
    res = dict(RES_SAL_Y_DROGA, desglose=[], categoria_sugerida="COMBUSTIBLE", monto_total=80000)
    assert partes_factura(res)[0]["categoria"] == "COMBUSTIBLE"
    anotar_factura(db, res, foto_ruta=None, user_id=None)
    fila = db.query_one("SELECT categoria, monto FROM finanzas")
    assert (fila["categoria"], fila["monto"]) == ("COMBUSTIBLE", 80000)


def test_anotar_factura_sin_total_no_anota_nada(db):
    import pytest
    res = dict(RES_SAL_Y_DROGA, desglose=[], monto_total=None)
    with pytest.raises(ValueError):
        anotar_factura(db, res, foto_ruta=None, user_id=None)
    assert db.query_one("SELECT COUNT(*) n FROM finanzas")["n"] == 0


def _handlers(app):
    out = {}
    for grupo in app.handlers.values():
        for h in grupo:
            out[getattr(h.callback, "__name__", "")] = h.callback
    return out


def test_telegram_foto_de_factura_propone_y_anota_el_gasto(db, tmp_path, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    import pytest
    pytest.importorskip("telegram")
    from src.parsers.media_handler import ImageInfo
    from src.server.auth import Auth
    from src.server.telegram_bot import construir_application

    auth = Auth(str(tmp_path / "users.json"))
    auth.agregar_usuario(111, "Dueño", "OWNER")
    media = tmp_path / "media"
    app = construir_application(token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz", db=db, auth=auth,
                                media_dir=str(media))
    handlers = _handlers(app)

    async def _bajar(ruta):
        with open(ruta, "wb") as f:
            f.write(b"\xff\xd8\xff factura")

    archivo = MagicMock()
    archivo.download_to_drive = AsyncMock(side_effect=_bajar)
    context = MagicMock()
    context.user_data = {}
    context.bot.get_file = AsyncMock(return_value=archivo)

    update = MagicMock()
    update.effective_user.id = 111
    update.effective_user.first_name = "Jaime"
    update.message.caption = "factura agrotienda"
    update.message.photo = [MagicMock(file_id="abc")]
    update.message.reply_text = AsyncMock()

    with patch("src.server.telegram_bot.extract_image_info", return_value=ImageInfo()), \
         patch("src.vision.recibo_gasto_parser.analizar_factura_gasto", return_value=RES_SAL_Y_DROGA):
        asyncio.run(handlers["handle_photo"](update, context))

    texto = update.message.reply_text.call_args.args[0]
    assert "Factura leída" in texto and "Drogas / medicamentos" in texto
    teclado = update.message.reply_text.call_args.kwargs["reply_markup"]
    datos_ok = teclado.inline_keyboard[0][0].callback_data
    assert datos_ok.startswith("gastofac:ok:")
    # La foto se renombra a factura_* (solo OWNER/ADMIN la ven en la PWA).
    pendiente = next(iter(context.user_data["facturas_gasto"].values()))
    assert os.path.basename(pendiente["foto_ruta"]).startswith("factura_tg_")
    assert os.path.exists(pendiente["foto_ruta"])
    assert db.query_one("SELECT COUNT(*) n FROM fotos WHERE ruta = ?", (pendiente["foto_ruta"],))["n"] == 1
    assert db.query_one("SELECT COUNT(*) n FROM finanzas")["n"] == 0  # nada hasta confirmar

    cb = MagicMock()
    cb.effective_user.id = 111
    cb.callback_query.data = datos_ok
    cb.callback_query.answer = AsyncMock()
    cb.callback_query.message.text_html = texto
    cb.callback_query.message.edit_text = AsyncMock()
    asyncio.run(handlers["handle_callback_query"](cb, context))

    assert "Anotado en Finanzas (2 gastos)" in cb.callback_query.message.edit_text.call_args.args[0]
    filas = db.query("SELECT categoria, monto, foto_ruta FROM finanzas ORDER BY id")
    assert [(f["categoria"], f["monto"]) for f in filas] == [("SAL_MINERALES", 357000), ("MEDICAMENTOS", 119000)]
    assert filas[0]["foto_ruta"] == pendiente["foto_ruta"].replace("\\", "/")

    # Tocar otra vez el botón no duplica.
    asyncio.run(handlers["handle_callback_query"](cb, context))
    assert db.query_one("SELECT COUNT(*) n FROM finanzas")["n"] == 2


def test_telegram_foto_normal_no_llama_a_la_ia(db, tmp_path):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    import pytest
    pytest.importorskip("telegram")
    from src.parsers.media_handler import ImageInfo
    from src.server.auth import Auth
    from src.server.telegram_bot import construir_application

    auth = Auth(str(tmp_path / "users.json"))
    auth.agregar_usuario(111, "Dueño", "OWNER")
    app = construir_application(token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz", db=db, auth=auth,
                                media_dir=str(tmp_path / "media"))
    archivo = MagicMock()
    archivo.download_to_drive = AsyncMock()
    context = MagicMock()
    context.user_data = {}
    context.bot.get_file = AsyncMock(return_value=archivo)
    update = MagicMock()
    update.effective_user.id = 111
    update.message.caption = "la vaca en el potrero"
    update.message.photo = [MagicMock(file_id="abc")]
    update.message.reply_text = AsyncMock()

    with patch("src.server.telegram_bot.extract_image_info", return_value=ImageInfo()), \
         patch("src.vision.recibo_gasto_parser.analizar_factura_gasto") as ia:
        asyncio.run(_handlers(app)["handle_photo"](update, context))
    ia.assert_not_called()
    assert "Foto" in update.message.reply_text.call_args.args[0]
