"""Facturas en PDF: leerlas en la app (Registrar → Ingreso / Gasto) y desde el
correo de facturas de la finca, que las deja en "Por revisar"."""
import base64
import io
import json
import os
import zipfile
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from src.db.database import Database
from src.integrations import correo_facturas
from src.vision.recibo_gasto_parser import analizar_factura_gasto, es_pdf_valido, texto_de_pdf


def _pdf(texto="AGROTIENDA EL GANADERO  NIT 900.123.456  Sal mineralizada 300.000  TOTAL 476.000"):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(40, 780, texto)
    c.save()
    return buf.getvalue()


RES_SAL_Y_DROGA = {
    "ok": True, "es_factura": True, "tipo": "EGRESO", "fecha": "2026-10-01",
    "proveedor": "Agrotienda El Ganadero", "concepto": "Sal y droga",
    "categoria_sugerida": "SAL_MINERALES", "monto_total": 476000,
    "desglose": [
        {"categoria": "SAL_MINERALES", "concepto": "Sal mineralizada x3", "monto": 357000},
        {"categoria": "MEDICAMENTOS", "concepto": "Ivermectina", "monto": 119000},
    ],
}


# --------------------------------------------------------------------------- #
# Lectura del PDF
# --------------------------------------------------------------------------- #
def test_es_pdf_valido_y_texto():
    pdf = _pdf()
    assert es_pdf_valido(pdf)
    assert not es_pdf_valido(b"%PDF-1.4 basura")
    assert not es_pdf_valido(b"\xff\xd8\xff jpeg")
    assert "AGROTIENDA" in texto_de_pdf(pdf)


def test_gemini_recibe_el_pdf_tal_cual():
    gemini = MagicMock()
    gemini.is_available.return_value = True
    gemini.generate_vision_structured.return_value = {
        "es_factura": True, "tipo": "EGRESO", "categoria_sugerida": "SAL_MINERALES", "monto_total": 476000}
    b64 = "data:application/pdf;base64," + base64.b64encode(_pdf()).decode()
    with patch("src.vision.recibo_gasto_parser.GeminiClient", return_value=gemini):
        res = analizar_factura_gasto(b64, fecha_referencia="2026-10-01")
    assert res["ok"] and res["monto_total"] == 476000
    assert gemini.generate_vision_structured.call_args.kwargs["mime_type"] == "application/pdf"


def test_sin_gemini_nvidia_recibe_el_texto_del_pdf(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "clave-de-prueba")
    gemini = MagicMock()
    gemini.is_available.return_value = False
    enviado = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            contenido = json.dumps({"es_factura": True, "tipo": "EGRESO", "monto_total": 476000,
                                    "categoria_sugerida": "SAL_MINERALES"})
            return json.dumps({"choices": [{"message": {"content": contenido}}]}).encode()

    def _urlopen(req, timeout=None):
        enviado["payload"] = json.loads(req.data.decode())
        return _Resp()

    with patch("src.vision.recibo_gasto_parser.GeminiClient", return_value=gemini), \
         patch("src.vision.recibo_gasto_parser.urllib.request.urlopen", side_effect=_urlopen):
        res = analizar_factura_gasto(_pdf(), fecha_referencia="2026-10-01")
    assert res["ok"] and res["categoria_sugerida"] == "SAL_MINERALES"
    mensaje_usuario = enviado["payload"]["messages"][1]["content"]
    assert isinstance(mensaje_usuario, str) and "AGROTIENDA" in mensaje_usuario


# --------------------------------------------------------------------------- #
# PWA
# --------------------------------------------------------------------------- #
@pytest.fixture
def app_y_db(tmp_path):
    pytest.importorskip("flask")
    from src.pwa.app import crear_app
    db_path = str(tmp_path / "bitacora.db")
    Database(db_path).create_tables().close()
    u_path = str(tmp_path / "users.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump([{"user_id": 1, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"}], f)
    app = crear_app(db_path, users_file=u_path, password="master-password")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"pin": "1234"})
    return c, db_path, u_path


def _media_abs(ruta_rel):
    from src.pwa import app as base
    return os.path.join(base.RAIZ_PROYECTO, ruta_rel)


def test_analizar_factura_pdf_guarda_el_pdf(app_y_db):
    client, _db_path, _ = app_y_db
    b64 = "data:application/pdf;base64," + base64.b64encode(_pdf()).decode()
    with patch("src.vision.recibo_gasto_parser.analizar_factura_gasto", return_value=dict(RES_SAL_Y_DROGA)):
        r = client.post("/api/finanzas/analizar-factura", json={"foto_base64": b64})
    res = r.get_json()
    try:
        assert res["foto_ruta"].endswith(".pdf")
        assert os.path.basename(res["foto_ruta"]).startswith("factura_")
        with open(_media_abs(res["foto_ruta"]), "rb") as f:
            assert f.read(4) == b"%PDF"
    finally:
        if res.get("foto_ruta"):
            os.remove(_media_abs(res["foto_ruta"]))


def test_analizar_factura_con_pdf_falso_no_guarda_nada(app_y_db):
    client, _db_path, _ = app_y_db
    b64 = base64.b64encode(b"%PDF-1.4 esto no es un pdf").decode()
    with patch("src.vision.recibo_gasto_parser.analizar_factura_gasto", return_value=dict(RES_SAL_Y_DROGA)):
        r = client.post("/api/finanzas/analizar-factura", json={"foto_base64": b64})
    assert r.get_json()["foto_ruta"] is None


def test_gasto_con_pdf_sin_leer_con_ia_guarda_el_pdf(app_y_db):
    client, db_path, _ = app_y_db
    b64 = "data:application/pdf;base64," + base64.b64encode(_pdf()).decode()
    r = client.post("/api/sync", json={"eventos": [{
        "id_local": "g1", "tipo": "gasto", "fecha": "2026-10-02",
        "payload": {"tipo_finanza": "EGRESO", "categoria": "ALIMENTO", "concepto": "Concentrado",
                    "monto": 90000, "foto_base64": b64},
    }]})
    assert r.get_json()["procesados"] == 1
    db = Database(db_path)
    try:
        ruta = db.query_one("SELECT foto_ruta FROM finanzas")["foto_ruta"]
    finally:
        db.close()
    try:
        assert ruta.endswith(".pdf") and os.path.basename(ruta).startswith("gasto_")
    finally:
        os.remove(_media_abs(ruta))


def test_pdf_en_otro_tipo_de_registro_se_descarta(app_y_db):
    client, db_path, _ = app_y_db
    b64 = "data:application/pdf;base64," + base64.b64encode(_pdf()).decode()
    client.post("/api/sync", json={"eventos": [{
        "id_local": "t1", "tipo": "tarea", "fecha": "2026-10-02",
        "payload": {"mensaje": "x", "foto_base64": b64},
    }]})
    db = Database(db_path)
    try:
        assert db.query_one("SELECT COUNT(*) n FROM fotos WHERE ruta LIKE '%.pdf'")["n"] == 0
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Correo de facturas
# --------------------------------------------------------------------------- #
def _correo(adjuntos, message_id="<f1@proveedor.co>"):
    msg = EmailMessage()
    msg["From"] = "Agrotienda <facturas@agrotienda.co>"
    msg["To"] = "facturas.finca@gmail.com"
    msg["Subject"] = "Factura electrónica FE-1234"
    msg["Message-ID"] = message_id
    msg.set_content("Adjuntamos su factura.")
    for nombre, datos, tipo in adjuntos:
        principal, sub = tipo.split("/")
        msg.add_attachment(datos, maintype=principal, subtype=sub, filename=nombre)
    return msg


def _zip_dian(pdf):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ad0900123456.xml", "<AttachedDocument/>")
        zf.writestr("fv0900123456.pdf", pdf)
    return buf.getvalue()


class FakeImap:
    def __init__(self, mensajes):
        self.mensajes = {str(i + 1).encode(): m.as_bytes() for i, m in enumerate(mensajes)}
        self.leidos = set()

    def select(self, carpeta):
        return "OK", [b""]

    def search(self, _charset, criterio):
        ids = [k for k in self.mensajes if k not in self.leidos]
        return "OK", [b" ".join(ids)]

    def fetch(self, num, _partes):
        return "OK", [(b"1 (BODY[] {n}", self.mensajes[num]), b")"]

    def store(self, num, _op, _flag):
        self.leidos.add(num)
        return "OK", []

    def logout(self):
        pass


def test_documentos_de_correo_saca_pdf_suelto_y_dentro_del_zip():
    pdf = _pdf()
    docs = correo_facturas.documentos_de_correo(_correo([
        ("factura.pdf", pdf, "application/pdf"),
        ("fe.zip", _zip_dian(pdf), "application/zip"),
        ("logo.png", b"\x89PNG", "image/png"),  # con PDF, la foto (logo) se ignora
    ]))
    assert [n for n, _ in docs] == ["factura.pdf", "fv0900123456.pdf"]


def test_configurado_ignora_valores_de_ejemplo(monkeypatch):
    monkeypatch.setenv("FACTURAS_IMAP_USUARIO", "facturas.finca@gmail.com")
    monkeypatch.setenv("FACTURAS_IMAP_CLAVE", "pegar_aqui_la_clave_de_aplicacion")
    assert not correo_facturas.configurado()
    monkeypatch.setenv("FACTURAS_IMAP_CLAVE", "abcd efgh ijkl mnop")
    assert correo_facturas.configurado()


def test_factura_del_correo_queda_por_revisar_y_al_aprobar_entra_a_finanzas(app_y_db, tmp_path):
    client, db_path, u_path = app_y_db
    imap = FakeImap([_correo([("fe.zip", _zip_dian(_pdf()), "application/zip")])])
    analizar = MagicMock(return_value=dict(RES_SAL_Y_DROGA))
    media = tmp_path / "media"

    db = Database(db_path)
    try:
        n = correo_facturas.revisar_correo(db, media_dir=str(media), users_file=u_path,
                                           conectar=lambda: imap, analizar=analizar)
        assert n == 1
        assert imap.leidos == {b"1"}
        assert db.query_one("SELECT COUNT(*) n FROM finanzas")["n"] == 0  # nada sin aprobar
        p = db.listar_pendientes("PENDIENTE")[0]
        assert (p["tipo"], p["canal"], p["registrado_por_nombre"]) == ("gasto", "correo", "Correo de facturas")
        assert "Agrotienda El Ganadero" in p["resumen"] and "Drogas / medicamentos" in p["resumen"]
        foto = p["datos"]["foto_ruta"]
        assert foto.startswith("media/factura_correo_") and foto.endswith(".pdf")
        assert (media / os.path.basename(foto)).read_bytes()[:4] == b"%PDF"

        # Otra vuelta (aunque el correo vuelva a aparecer sin leer) no duplica.
        imap.leidos.clear()
        assert correo_facturas.revisar_correo(db, media_dir=str(media), conectar=lambda: imap,
                                              analizar=analizar) == 0
        assert db.contar_pendientes() == 1
    finally:
        db.close()

    lista = client.get("/api/revision/pendientes").get_json()["pendientes"]
    assert lista[0]["foto_ruta"] == foto
    assert "monto" not in [c["clave"] for c in lista[0]["campos"]]  # repartida por categoría
    r = client.post(f"/api/revision/{lista[0]['id']}/aprobar", json={})
    assert r.get_json()["ok"], r.get_json()

    db = Database(db_path)
    try:
        filas = db.query("SELECT categoria, monto, contraparte, foto_ruta FROM finanzas ORDER BY id")
    finally:
        db.close()
    assert [(f["categoria"], f["monto"]) for f in filas] == [("SAL_MINERALES", 357000), ("MEDICAMENTOS", 119000)]
    assert all(f["foto_ruta"] == foto and f["contraparte"] == "Agrotienda El Ganadero" for f in filas)


def test_si_la_ia_falla_el_correo_queda_sin_leer(tmp_path):
    db = Database(str(tmp_path / "b.db")).create_tables()
    imap = FakeImap([_correo([("factura.pdf", _pdf(), "application/pdf")])])
    try:
        n = correo_facturas.revisar_correo(
            db, media_dir=str(tmp_path / "media"), conectar=lambda: imap,
            analizar=lambda raw, fecha: {"ok": False, "error": "sin red"})
        assert n == 0 and imap.leidos == set()
    finally:
        db.close()


def test_correo_sin_factura_se_marca_leido_sin_pendiente(tmp_path):
    db = Database(str(tmp_path / "b.db")).create_tables()
    imap = FakeImap([_correo([("folleto.pdf", _pdf("Promociones"), "application/pdf")]), _correo([])])
    try:
        n = correo_facturas.revisar_correo(
            db, media_dir=str(tmp_path / "media"), conectar=lambda: imap,
            analizar=lambda raw, fecha: {"ok": True, "es_factura": False, "tipo": "EGRESO"})
        assert n == 0 and imap.leidos == {b"1", b"2"}
        assert db.contar_pendientes() == 0
    finally:
        db.close()
