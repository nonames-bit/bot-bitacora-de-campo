import json
import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.db.database import Database
from src.pwa.app import crear_app, datos_ficha, datos_pasturas, datos_tablero

_WKT_TEST = "POLYGON((-74.07 3.39, -74.06 3.39, -74.06 3.40, -74.07 3.40, -74.07 3.39))"


@pytest.fixture(autouse=True)
def _reportes_dir_aislado(tmp_path, monkeypatch):
    """Aísla la caché de /api/grafico/<tipo> a un directorio temporal por
    test. Sin esto, cualquier test que pida un gráfico genera el PNG con
    datos de prueba (ej. el potrero "Guayabal") directo en
    data/reportes/_pwa_cache_<tipo>.png -- el mismo directorio que usa el
    servidor real corriendo en la máquina del desarrollador -- y ese PNG
    de prueba queda cacheado 10 minutos tapando el mapa/gráficos reales.
    Bug real: el usuario vio "Guayabal" en el mapa de potreros de su PWA
    local después de correr la suite de tests."""
    import src.pwa.app as pwa_app
    monkeypatch.setattr(pwa_app, "REPORTES_DIR_DEFAULT", str(tmp_path / "reportes"))


@pytest.fixture
def db_file(tmp_path):
    ruta = str(tmp_path / "bitacora.db")
    d = Database(ruta)
    d.create_tables()
    pot_id = d.registrar_potrero(nombre="Guayabal", codigo="G1")
    d.execute(
        "UPDATE potreros SET geom_wkt_4326 = ?, centroide_lat = 3.395, centroide_lon = -74.065 "
        "WHERE id = ?",
        (_WKT_TEST, pot_id),
    )
    # Potrero legacy sin geometría real (mismo caso que los códigos numéricos
    # confirmados como no reales, ver docs/PLAN_GEO_SATELITAL_6.2_8.2.md §3.5).
    d.registrar_potrero(nombre="09", codigo="09")
    d.registrar_animal("47", sexo="Hembra", raza="C", estado="ACTIVO",
                       potrero="Guayabal", fecha_nacimiento="2022-01-10")
    d.registrar_animal("99", sexo="Hembra", estado="VENDIDO", potrero="Guayabal")
    d.registrar_parto("47", fecha="2026-08-20", sexo_cria="Macho")
    d.close()
    return ruta


@pytest.fixture
def client(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    assert app is not None
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave-de-prueba"})
    return c


def test_endpoints_sin_sesion_devuelven_401(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    c = app.test_client()
    for ep in ("/api/tablero", "/api/repro", "/api/sanidad", "/api/pasturas", "/api/leche", "/api/ficha/47"):
        r = c.get(ep)
        assert r.status_code == 401, ep


def test_pagina_html_sin_sesion_redirige_a_login(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    c = app.test_client()
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (301, 302, 303, 307, 308)
    assert "/login" in r.headers.get("Location", "")


def test_login_con_clave_incorrecta_no_autentica(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    c = app.test_client()
    c.post("/login", data={"password": "clave-equivocada"})
    r = c.get("/api/tablero")
    assert r.status_code == 401


def test_login_bloquea_tras_muchos_intentos_fallidos(db_file):
    """El PIN individual son solo 4 dígitos guardados en texto plano en
    users.json -- sin límite de intentos, cualquiera con acceso a /login
    (la app está expuesta a internet) podría fuerza-bruta un PIN en
    segundos. Debe bloquear tras varios fallos consecutivos."""
    app = crear_app(db_file, password="clave-de-prueba")
    c = app.test_client()
    for _ in range(8):
        r = c.post("/login", data={"password": "0000"})
        assert r.status_code in (301, 302, 303, 307, 308)
    bloqueado = c.post("/login", data={"password": "clave-de-prueba"})
    assert bloqueado.status_code == 429
    # Ni siquiera la clave CORRECTA debe autenticar mientras está bloqueado.
    assert c.get("/api/tablero").status_code == 401


def test_logout_envia_clear_site_data(client):
    """En un equipo compartido, cerrar sesión debe limpiar la caché offline
    del Service Worker (cachea /api/*, ver static/sw.js) -- sin esto,
    alguien podría desconectarse de internet tras el logout y aún ver los
    datos de la finca que quedaron guardados localmente."""
    r = client.get("/logout")
    assert r.headers.get("Clear-Site-Data") == '"cache", "storage"'


def test_sin_password_configurada_bloquea_todo(db_file):
    app = crear_app(db_file, password="")
    c = app.test_client()
    assert c.get("/api/tablero").status_code == 401
    assert c.get("/login").status_code == 503


def test_import_app_y_tablero_lectura(client):
    r = client.get("/api/tablero")
    assert r.status_code == 200
    d = r.get_json()
    assert d["activos"] == 1  # estricto ACTIVO: 47 sí, 99 no
    assert "por_potrero" in d


def test_repro_fep_30d_excluye_fechas_pasadas(db_file):
    """FEP ≤30d debe ser una ventana hacia ADELANTE (próximos partos), no
    traer las fechas más antiguas de toda la historia por faltar el límite
    inferior (bug real encontrado navegando la PWA en vivo)."""
    from datetime import date, timedelta

    db = Database(db_file)
    db.registrar_animal("200", sexo="Hembra", estado="ACTIVO")
    fep_pasado = (date.today() - timedelta(days=3000)).isoformat()
    fep_futuro = (date.today() + timedelta(days=10)).isoformat()
    db.execute(
        "INSERT INTO servicios (vaca_id, fecha, tipo_servicio, fep_calculada) "
        "VALUES ((SELECT id_animal FROM animales WHERE tag='200'), ?, 'IATF', ?)",
        (fep_pasado, fep_pasado),
    )
    db.execute(
        "INSERT INTO servicios (vaca_id, fecha, tipo_servicio, fep_calculada) "
        "VALUES ((SELECT id_animal FROM animales WHERE tag='200'), ?, 'IATF', ?)",
        (fep_futuro, fep_futuro),
    )
    db.close()

    app = crear_app(db_file, password="clave-de-prueba")
    c = app.test_client()
    c.post("/login", data={"password": "clave-de-prueba"})
    r = c.get("/api/repro")
    fechas = [f["fep_calculada"] for f in r.get_json()["fep_30d"]]
    assert fep_futuro in fechas
    assert fep_pasado not in fechas


def test_endpoints_lectura_repro_sanidad_pasturas_leche(client):
    for ep in ("/api/repro", "/api/sanidad", "/api/pasturas", "/api/leche"):
        r = client.get(ep)
        assert r.status_code == 200, ep
        assert isinstance(r.get_json(), dict)


def test_ficha_qr_url(client, db_file):
    r = client.get("/api/ficha/47")
    assert r.status_code == 200
    d = r.get_json()
    assert d["existe"] is True
    assert d["qr_payload"] == "JA://animal/47"
    assert d["qr_url"] == "/ficha/47"
    # Vista HTML de la ficha QR.
    html = client.get("/ficha/47")
    assert html.status_code == 200
    # Helper directo también respeta el payload.
    assert datos_ficha("47", db_file)["qr_url"] == "/ficha/47"
    assert datos_tablero(db_file)["activos"] == 1


def test_pasturas_excluye_potreros_sin_geometria_real(db_file):
    """Los códigos legacy (sin geom_wkt_4326) no son potreros reales/actuales
    de la finca (confirmado por el usuario) — no deben aparecer en el
    tablero de Pasturas como si lo fueran (bug real encontrado navegando)."""
    r = datos_pasturas(db_file)
    nombres = [p["nombre"] for p in r["potreros"]]
    assert "Guayabal" in nombres
    assert "09" not in nombres


def test_api_grafico_tipo_valido_devuelve_png_o_404_sin_datos(client):
    # No se afirma 200 estricto: sin datos suficientes el generador puede
    # devolver None (comportamiento ya existente de charts.py), y sin
    # matplotlib instalado en CI también sería 404 — lo que sí es un bug es
    # servir un tipo NO whitelisteado.
    r = client.get("/api/grafico/mapa_potreros")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.content_type == "image/png"


def test_api_grafico_tipo_no_whitelisteado_devuelve_404(client):
    r = client.get("/api/grafico/algo_inventado")
    assert r.status_code == 404


def test_api_grafico_usa_cache_en_la_segunda_llamada(client, monkeypatch, tmp_path):
    """Dentro de la ventana de caché, la segunda petición no debe volver a
    invocar al generador (matplotlib) — evita regenerar la misma imagen si
    dos personas abren la misma pestaña casi al tiempo."""
    import src.pwa.app as pwa_app

    # El directorio de reportes ya queda aislado por el fixture autouse
    # _reportes_dir_aislado (arriba); aquí solo falta instrumentar el conteo.
    llamadas = {"n": 0}
    generadores_originales = pwa_app._generadores_graficos_pwa()
    original = generadores_originales["mapa_potreros"]

    def _contador(*a, **k):
        llamadas["n"] += 1
        return original(*a, **k)

    monkeypatch.setattr(
        pwa_app, "_generadores_graficos_pwa",
        lambda: {**generadores_originales, "mapa_potreros": _contador},
    )

    r1 = client.get("/api/grafico/mapa_potreros")
    r2 = client.get("/api/grafico/mapa_potreros")
    if r1.status_code == 200:
        assert r2.status_code == 200
        assert llamadas["n"] == 1  # la segunda vino de la caché, no regeneró


def test_media_sirve_archivo_y_bloquea_path_traversal(db_file, tmp_path):
    media_dir = tmp_path / "media_test"
    media_dir.mkdir()
    (media_dir / "foto.jpg").write_bytes(b"contenido-de-prueba")
    import src.pwa.app as pwa_app

    original_media_dir = pwa_app.MEDIA_DIR_DEFAULT
    original_raiz = pwa_app.RAIZ_PROYECTO
    pwa_app.RAIZ_PROYECTO = str(tmp_path)
    pwa_app.MEDIA_DIR_DEFAULT = "media_test"
    try:
        app = crear_app(db_file, password="clave-de-prueba")
        c = app.test_client()
        c.post("/login", data={"password": "clave-de-prueba"})
        r = c.get("/media/foto.jpg")
        assert r.status_code == 200
        assert r.data == b"contenido-de-prueba"
        r2 = c.get("/media/../app.py")
        assert r2.status_code in (400, 404)
    finally:
        pwa_app.MEDIA_DIR_DEFAULT = original_media_dir
        pwa_app.RAIZ_PROYECTO = original_raiz


# --------------------------------------------------------------------------- #
# WS-X2 / X4 / X5 — Identificar (OCR/RFID), ficha enriquecida y búsqueda
# --------------------------------------------------------------------------- #

def test_api_buscar_autocompletar(client):
    r = client.get("/api/buscar?q=4")
    assert r.status_code == 200
    d = r.get_json()
    tags = [a["tag"] for a in d["animales"]]
    assert "47" in tags
    # Los vendidos (99) no deben aparecer en el autocompletar de activos.
    assert "99" not in tags
    # Potreros buscables.
    p = client.get("/api/buscar?q=Guaya")
    assert any(x["nombre"] == "Guayabal" for x in p.get_json()["potreros"])


def test_api_buscar_potreros_excluye_legacy_sin_geometria(client):
    """El selector de potreros (lista completa con q="" y autocompletar al
    escribir) no debe ofrecer códigos legacy sin geom_wkt_4326 -- son los
    mismos potreros no reales/actuales confirmados por el usuario, no debe
    poder filtrarse el tablero por ellos ni por accidente."""
    r = client.get("/api/buscar?q=")
    nombres = [p["nombre"] for p in r.get_json()["potreros"]]
    assert "Guayabal" in nombres
    assert "09" not in nombres

    r2 = client.get("/api/buscar?q=09")
    nombres2 = [p["nombre"] for p in r2.get_json()["potreros"]]
    assert "09" not in nombres2


def test_api_badges_contadores(client):
    r = client.get("/api/badges")
    assert r.status_code == 200
    d = r.get_json()
    for clave in ("agenda", "repro", "sanidad"):
        assert clave in d, clave
        assert isinstance(d[clave], int)


def test_inventario_unificado_incluye_piramide_y_gmd(client):
    """La vista Inventario absorbió a Población: debe traer tabla SG + pirámide
    + edad promedio + GMD recientes en un único endpoint."""
    r = client.get("/api/inventario")
    assert r.status_code == 200
    d = r.get_json()
    for clave in ("filas", "piramide", "edad_promedio", "gmd_reciente"):
        assert clave in d, clave
    assert isinstance(d["piramide"], list)
    assert isinstance(d["gmd_reciente"], list)
    total_pi = sum(f["hembras"] + f["machos"] for f in d["piramide"])
    assert total_pi <= d["total_activos"]  # nunca mayor que el hato activo
    # Bug real reportado por el usuario: faltaba la tabla de distribución por
    # potrero en la vista unificada (sí existía en Tablero).
    assert "por_potrero" in d
    assert any(p["potrero"] == "Guayabal" for p in d["por_potrero"])


def test_api_poblacion_sigue_disponible_como_alias(client):
    r = client.get("/api/poblacion")
    assert r.status_code == 200
    assert "piramide" in r.get_json()


def test_api_qr_pdf_por_animal(db_file, client):
    pytest.importorskip("reportlab", reason="reportlab no instalado")
    # 47 está ACTIVA en el fixture (con parto); exportar tarjeta QR no debe fallar.
    r = client.get("/api/ficha/47/qr.pdf")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.content_type == "application/pdf"
        assert r.data[:4] == b"%PDF"


def test_api_identificar_por_texto_rfid(client):
    r = client.post("/api/identificar", data={"texto": "0000000000047"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["existe"] is True
    assert d["tag"] == "47"

    r2 = client.post("/api/identificar", data={"texto": "N-069  "})
    assert r2.status_code == 200
    assert r2.get_json()["existe"] is False  # sin error, solo no encontrado


def test_api_identificar_requiere_texto_o_foto(client):
    r = client.post("/api/identificar", data={})
    assert r.status_code == 400


def test_api_identificar_foto_degrada_sin_ocr(client):
    """Sin tesseract/easyocr la foto no debe romper el endpoint: responde
    existe=False con mensaje claro (el pipeline vision/ocr ya degrada)."""
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (8, 8), color=(120, 120, 120)).save(buf, format="PNG")
    buf.seek(0)
    r = client.post(
        "/api/identificar",
        data={"foto": (buf, "arete.png")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    d = r.get_json()
    assert d["existe"] is False


def test_ficha_enriquecida_secciones(client):
    r = client.get("/api/ficha/47")
    d = r.get_json()
    for clave in ("partos", "servicios", "diagnosticos", "controles_leche", "lactancia"):
        assert clave in d, clave
    # lactancia es dict (si la vaca tiene parto) o None (sin lactancia).
    assert d["lactancia"] is None or isinstance(d["lactancia"], dict)
    if d["lactancia"]:
        assert d["lactancia"]["fecha_parto"]
        assert d["lactancia"]["estado"] in ("En ordeño", "Seca")


def test_api_ficha_grafico_whitelist(client):
    # Tipo válido: 200 o 404 (sin datos/matplotlib), nunca 500.
    r = client.get("/api/ficha/47/grafico/peso")
    assert r.status_code in (200, 404)
    # Tipo NO whitelisteado: 404.
    assert client.get("/api/ficha/47/grafico/algo").status_code == 404
    # Animal inexistente: 404.
    assert client.get("/api/ficha/ZZ999/grafico/peso").status_code == 404


def test_autenticacion_pin_roles_y_usuario(tmp_path, db_file):
    users_json = str(tmp_path / "users_test.json")
    import json
    with open(users_json, "w", encoding="utf-8") as f:
        json.dump([
            {"user_id": 100, "nombre": "Don Juan", "rol": "OWNER", "pin": "9999"},
            {"user_id": 200, "nombre": "Pedro Admin", "rol": "ADMIN", "pin": "8888"},
            {"user_id": 300, "nombre": "Carlos Vaquero", "rol": "TRABAJADOR", "pin": "7777"},
        ], f)

    app = crear_app(db_file, users_file=users_json, password="master-password")
    c = app.test_client()

    # Login como TRABAJADOR con PIN
    r = c.post("/login", data={"pin": "7777"})
    assert r.status_code == 302
    u_info = c.get("/api/usuario").get_json()
    assert u_info["autenticado"] is True
    assert u_info["rol"] == "TRABAJADOR"
    assert u_info["nombre"] == "Carlos Vaquero"

    # TRABAJADOR no puede ver /api/sistema (403)
    assert c.get("/api/sistema").status_code == 403
    assert c.get("/api/logs").status_code == 403
    assert c.get("/api/reporte.pdf").status_code == 403

    # Logout
    c.get("/logout")

    # Login como OWNER con PIN
    r = c.post("/login", data={"pin": "9999"})
    assert r.status_code == 302
    u_info = c.get("/api/usuario").get_json()
    assert u_info["rol"] == "OWNER"

    # OWNER sí puede ver /api/sistema y /api/logs
    r_sis = c.get("/api/sistema")
    assert r_sis.status_code == 200
    d_sis = r_sis.get_json()
    assert "vps" in d_sis and "db" in d_sis
    assert "sync_sg" in d_sis
    assert "actividad_reciente" in d_sis
    assert c.get("/api/logs").status_code == 200


def test_api_sync_offline(client):
    eventos = [
        {"tipo": "pesaje", "fecha": "2026-09-01", "payload": {"tag": "47", "peso_kg": 460.5, "evento": "CONTROL"}},
        {"tipo": "tratamiento", "fecha": "2026-09-01", "payload": {"tag": "47", "producto": "Ivermectina", "dosis": "10ml", "via": "SC", "dias_retiro_carne": 28}},
        {"tipo": "leche", "fecha": "2026-09-01", "payload": {"litros": 185.0, "notas": "Ordeño mañana"}},
    ]
    r = client.post("/api/sync", json={"eventos": eventos})
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert d["procesados"] == 3


def test_api_sync_solo_confirma_ids_ok_de_eventos_realmente_guardados(client):
    """Bug real: el cliente borraba TODA su cola offline con un solo HTTP 200,
    aunque un evento individual del lote hubiera fallado -- ese evento
    desaparecía de la cola sin haberse guardado en el servidor (pérdida de
    datos de campo silenciosa). El servidor debe reportar, por id_local,
    cuáles sí se guardaron para que el cliente solo borre esos."""
    eventos = [
        {"tipo": "pesaje", "id_local": "loc_ok", "fecha": "2026-09-01",
         "payload": {"tag": "47", "peso_kg": 460.5, "evento": "CONTROL"}},
        {"tipo": "tipo_no_existe", "id_local": "loc_falla", "fecha": "2026-09-01", "payload": {}},
    ]
    r = client.post("/api/sync", json={"eventos": eventos})
    assert r.status_code == 200
    d = r.get_json()
    assert d["procesados"] == 1
    assert d["ids_ok"] == ["loc_ok"]
    assert "loc_falla" not in d["ids_ok"]
    assert d["errores"]  # el fallo queda reportado, no silenciado


def test_api_sync_con_foto_opcional(client, db_file):
    import base64
    from src.db.database import Database

    # Bytes mínimos de imagen JPEG en base64
    fake_img = base64.b64encode(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9").decode("utf-8")
    b64_data = f"data:image/jpeg;base64,{fake_img}"

    eventos = [
        # 1. Parto con foto opcional
        {
            "tipo": "parto",
            "id_local": "loc_parto_foto",
            "fecha": "2026-09-02",
            "payload": {
                "vaca_tag": "47",
                "id_cria_tag": "CRIA_99",
                "sexo_cria": "HEMBRA",
                "estado_cria": "VIVO",
                "peso_nacimiento": 34.0,
                "notas": "Cría vigorosa",
                "foto_base64": b64_data,
            }
        },
        # 2. Tratamiento con foto opcional
        {
            "tipo": "tratamiento",
            "id_local": "loc_trat_foto",
            "fecha": "2026-09-02",
            "payload": {
                "animal_tag": "47",
                "producto": "Penicilina L.A.",
                "dosis": "15 ml",
                "via": "IM",
                "dias_retiro_leche": 3,
                "foto_base64": b64_data,
            }
        },
        # 3. Muerte con foto opcional
        {
            "tipo": "muerte",
            "id_local": "loc_muerte_foto",
            "fecha": "2026-09-02",
            "payload": {
                "animal_tag": "CRIA_99",
                "causa_presunta": "Timpanismo agudo",
                "foto_base64": b64_data,
            }
        },
        # 4. Evento sin foto (opcionalidad garantizada)
        {
            "tipo": "pesaje",
            "id_local": "loc_sin_foto",
            "fecha": "2026-09-02",
            "payload": {
                "animal_tag": "47",
                "peso_kg": 475.0,
            }
        }
    ]

    r = client.post("/api/sync", json={"eventos": eventos})
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert d["procesados"] == 4

    db = Database(db_file)
    fotos_cria = db.fotos_de("CRIA_99")
    assert len(fotos_cria) >= 1
    fotos_vaca = db.fotos_de("47")
    assert len(fotos_vaca) >= 1
    db.close()


def test_api_manga_pesaje_calcula_gmd(client, db_file):
    # Registrar pesaje previo
    d = Database(db_file)
    d.registrar_pesaje("47", fecha="2026-08-01", peso_kg=400.0)
    d.close()

    # Nuevo pesaje vía API Manga
    r = client.post("/api/manga/pesaje", json={"tag": "47", "peso_kg": 430.0})
    assert r.status_code == 200
    res = r.get_json()
    assert res["ok"] is True
    assert res["tag"] == "47"
    assert res["peso_kg"] == 430.0
    assert res["peso_anterior"] == 400.0
    assert res["gmd_g_dia"] is not None
    assert res["gmd_g_dia"] > 0


def test_api_manga_tratamiento_lote(client):
    r = client.post("/api/manga/tratamiento_lote", json={
        "tags": ["47"],
        "producto": "Oxitetraciclina",
        "dosis": "1ml/10kg",
        "via": "IM",
        "dias_retiro_leche": 3,
        "dias_retiro_carne": 14,
    })
    assert r.status_code == 200
    assert r.get_json()["procesados"] == 1


def test_api_preguntar_lenguaje_natural(client):
    r = client.post("/api/preguntar", json={"pregunta": "¿cuántas vacas hay en Guayabal?"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert "Guayabal" in d["respuesta"] or "47" in d["respuesta"] or "vaca" in d["respuesta"].lower()


def test_api_preguntar_ayuda_sistema(client):
    # Consulta sobre instalación
    r1 = client.post("/api/preguntar", json={"pregunta": "¿Cómo instalo la app en mi celular?"})
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert d1["ok"] is True
    assert "Android" in d1["respuesta"] and "Safari" in d1["respuesta"]

    # Consulta sobre funcionamiento sin internet (offline)
    r2 = client.post("/api/preguntar", json={"pregunta": "¿Cómo funciona la bitácora sin internet?"})
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert d2["ok"] is True
    assert "IndexedDB" in d2["respuesta"] or "offline" in d2["respuesta"].lower()

    # Consulta sobre pesajes en manga
    r3 = client.post("/api/preguntar", json={"pregunta": "¿Cómo se pesa ganado en la manga?"})
    assert r3.status_code == 200
    d3 = r3.get_json()
    assert d3["ok"] is True
    assert "GMD" in d3["respuesta"] or "Manga" in d3["respuesta"]


def test_api_gps_potrero_y_rondas(client):
    # Coordenadas dentro del polígono de prueba Guayabal (-74.065, 3.395)
    r = client.post("/api/gps/potrero", json={"lat": 3.395, "lon": -74.065})
    assert r.status_code == 200
    d = r.get_json()
    assert d["detectado"] is True
    assert d["potrero"]["nombre"] == "Guayabal"
    assert d["total_animales"] >= 1

    # Registrar ronda
    r_ronda = client.post("/api/gps/ronda", json={
        "lat": 3.395, "lon": -74.065, "punto_control": "saladero", "notas": "Saladero lleno y limpio"
    })
    assert r_ronda.status_code == 200
    assert r_ronda.get_json()["ok"] is True

    # Consultar rondas
    r_list = client.get("/api/gps/rondas")
    assert r_list.status_code == 200
    assert len(r_list.get_json()["rondas"]) >= 1


def test_api_usuarios_autenticacion_y_rbac(tmp_path, db_file):
    import json
    users_data = [
        {"user_id": 100, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"},
        {"user_id": 200, "nombre": "Admin", "rol": "ADMIN", "pin": "2222"},
        {"user_id": 300, "nombre": "Trabajador", "rol": "TRABAJADOR", "pin": "3333"},
    ]
    u_path = str(tmp_path / "users_test.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump(users_data, f)

    app = crear_app(db_file, users_file=u_path, password="master-password")
    assert app is not None
    app.config.update({"TESTING": True})

    # 1. Sin sesión: 401
    c_anon = app.test_client()
    r = c_anon.get("/api/usuarios")
    assert r.status_code == 401

    # 2. Trabajador: 403
    c_trab = app.test_client()
    c_trab.post("/login", data={"pin": "3333"})
    r_trab = c_trab.get("/api/usuarios")
    assert r_trab.status_code == 403
    r_trab_post = c_trab.post("/api/usuarios", json={"nombre": "X", "rol": "TRABAJADOR", "pin": "5555"})
    assert r_trab_post.status_code == 403

    # 3. Admin: Puede listar pero PIN de OWNER está enmascarado
    c_adm = app.test_client()
    c_adm.post("/login", data={"pin": "2222"})
    r_adm = c_adm.get("/api/usuarios")
    assert r_adm.status_code == 200
    us = r_adm.get_json()["usuarios"]
    owner_entry = next(u for u in us if u["user_id"] == 100)
    assert owner_entry["pin"] == "****"

    # Admin no puede crear OWNER
    r_adm_owner = c_adm.post("/api/usuarios", json={"nombre": "Nuevo Dueño", "rol": "OWNER", "pin": "7777"})
    assert r_adm_owner.status_code == 403

    # Admin puede crear TRABAJADOR
    r_adm_create = c_adm.post("/api/usuarios", json={"nombre": "Pepe", "rol": "TRABAJADOR", "pin": "7777"})
    assert r_adm_create.status_code == 200
    assert r_adm_create.get_json()["ok"] is True

    # No se puede repetir PIN (colisión)
    r_colision = c_adm.post("/api/usuarios", json={"nombre": "Repetido", "rol": "TRABAJADOR", "pin": "7777"})
    assert r_colision.status_code == 400
    assert "7777" in r_colision.get_json()["error"] and "Pepe" in r_colision.get_json()["error"]

    # Admin no puede eliminar OWNER
    r_adm_del_owner = c_adm.post("/api/usuarios/100/eliminar")
    assert r_adm_del_owner.status_code == 403

    # 4. Owner: Control total
    c_owner = app.test_client()
    c_owner.post("/login", data={"pin": "1234"})
    r_owner_list = c_owner.get("/api/usuarios")
    assert r_owner_list.status_code == 200
    us_owner = r_owner_list.get_json()["usuarios"]
    owner_u = next(u for u in us_owner if u["user_id"] == 100)
    assert owner_u["pin"] == "1234"  # Owner sí ve los PINs

    # Cambiar PIN de un usuario
    pepe_uid = r_adm_create.get_json()["usuario"]["user_id"]
    r_chg_pin = c_owner.post(f"/api/usuarios/{pepe_uid}/pin", json={"pin": "8888"})
    assert r_chg_pin.status_code == 200

    # Eliminar usuario creado
    r_del = c_owner.post(f"/api/usuarios/{pepe_uid}/eliminar")
    assert r_del.status_code == 200

    # No se puede eliminar al último OWNER
    r_del_owner = c_owner.post("/api/usuarios/100/eliminar")
    assert r_del_owner.status_code == 400

    # Crear usuario con telegram_id y avatar temático
    r_avatar_user = c_owner.post("/api/usuarios", json={
        "nombre": "Dra. Veterinaria",
        "rol": "ADMIN",
        "pin": "9999",
        "telegram_id": 9876543210,
        "avatar": "veterinaria"
    })
    assert r_avatar_user.status_code == 200
    res_data = r_avatar_user.get_json()["usuario"]
    assert res_data["telegram_id"] == 9876543210
    assert res_data["avatar"] == "veterinaria"

    # Login con ese nuevo usuario y verificar /api/usuario
    c_vet = app.test_client()
    c_vet.post("/login", data={"pin": "9999"})
    r_vet_info = c_vet.get("/api/usuario")
    assert r_vet_info.status_code == 200
    info = r_vet_info.get_json()
    assert info["telegram_id"] == 9876543210
    assert info["avatar"] == "veterinaria"
    assert info["rol"] == "ADMIN"


def test_telemetria_gps_ping_y_rutas(tmp_path):
    users_data = [
        {"user_id": 100, "nombre": "Patron", "rol": "OWNER", "pin": "1234"},
        {"user_id": 200, "nombre": "Capataz", "rol": "ADMIN", "pin": "2222"},
        {"user_id": 300, "nombre": "Juan Peon", "rol": "TRABAJADOR", "pin": "3333"},
    ]
    uf = tmp_path / "users.json"
    uf.write_text(json.dumps(users_data), encoding="utf-8")

    db_path = str(tmp_path / "bitacora.db")
    d = Database(db_path)
    d.create_tables()
    pot_id = d.registrar_potrero(nombre="Guayabal", codigo="G1")
    d.execute(
        "UPDATE potreros SET geom_wkt_4326 = ?, centroide_lat = 3.395, centroide_lon = -74.065 WHERE id = ?",
        (_WKT_TEST, pot_id),
    )
    d.close()

    app = crear_app(db_path=db_path, users_file=str(uf))
    app.config.update({"TESTING": True})

    # 1. Trabajador envía ping de telemetría en segundo plano
    c_trab = app.test_client()
    c_trab.post("/login", data={"pin": "3333"})

    r_ping = c_trab.post("/api/telemetria/ping", json={
        "lat": 3.395,
        "lon": -74.065,
        "precision_m": 4.5,
        "evento_origen": "apertura_app"
    })
    assert r_ping.status_code == 200
    res_ping = r_ping.get_json()
    assert res_ping["ok"] is True
    assert res_ping["potrero"]["nombre"] == "Guayabal"

    # Ping fuera de la finca es ignorado y no registrado
    r_fuera = c_trab.post("/api/telemetria/ping", json={
        "lat": 10.5,
        "lon": -70.5,
        "precision_m": 5.0,
        "evento_origen": "apertura_app"
    })
    assert r_fuera.status_code == 200
    assert r_fuera.get_json()["ignorado"] is True

    # 2. Trabajador NO tiene acceso a /api/telemetria/rutas (403)
    r_rutas_trab = c_trab.get("/api/telemetria/rutas")
    assert r_rutas_trab.status_code == 403

    # 3. Admin tampoco tiene acceso a rutas (restringido a OWNER)
    c_adm = app.test_client()
    c_adm.post("/login", data={"pin": "2222"})
    r_rutas_adm = c_adm.get("/api/telemetria/rutas")
    assert r_rutas_adm.status_code == 403

    # 4. Owner sí tiene acceso y ve la ruta del trabajador
    c_owner = app.test_client()
    c_owner.post("/login", data={"pin": "1234"})
    r_rutas_owner = c_owner.get("/api/telemetria/rutas")
    assert r_rutas_owner.status_code == 200
    res_rutas = r_rutas_owner.get_json()
    assert res_rutas["ok"] is True
    assert len(res_rutas["rutas"]) == 1
    ruta_juan = res_rutas["rutas"][0]
    assert ruta_juan["usuario_nombre"] == "Juan Peon"
    assert ruta_juan["total_puntos"] == 1
    assert ruta_juan["secuencia_potreros"][0]["potrero"] == "Guayabal"

    # 5. Sincronización offline de telemetría ping vía /api/sync
    r_sync = c_trab.post("/api/sync", json={
        "eventos": [{
            "tipo": "telemetria_ping",
            "payload": {
                "lat": 3.3951,
                "lon": -74.0651,
                "precision_m": 6.0,
                "evento_origen": "pesaje_manga",
                "hora": "14:20:00"
            },
            "fecha": "2026-09-05"
        }]
    })
    assert r_sync.status_code == 200
    assert r_sync.get_json()["procesados"] == 1


def test_manifest_pwa_instalable(client):
    r = client.get("/manifest.json")
    assert r.status_code == 200
    data = r.get_json()
    assert data["name"] == "Bitácora JA"
    assert data["short_name"] == "Bitácora JA"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/?source=pwa"
    assert len(data["icons"]) >= 2
    assert any(i.get("purpose") == "maskable" for i in data["icons"])


def test_login_incluye_manifest_y_boton_instalar(client):
    r = client.get("/login")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'rel="manifest"' in html
    assert 'id="box-instalar-login"' in html
    assert 'btn-instalar-login' in html


def test_ficha_genealogia_3g_y_crias(client, db_file):
    from src.db.database import Database
    db = Database(db_file)
    db.registrar_animal("MADRE_01", sexo="Hembra")
    db.registrar_animal("TORO_01", sexo="Macho")
    db.registrar_animal("VACA_TEST", sexo="Hembra", madre_tag="MADRE_01", padre_tag="TORO_01")
    db.registrar_animal("CRIA_01", sexo="Macho", madre_tag="VACA_TEST", padre_tag="TORO_01")
    db.registrar_parto("VACA_TEST", "2026-03-22", id_cria_tag="CRIA_01", sexo_cria="Macho")

    r = client.get("/api/ficha/VACA_TEST")
    assert r.status_code == 200
    d = r.get_json()
    assert d["existe"] is True
    assert "genealogia_3g" in d
    g = d["genealogia_3g"]
    assert g["padre"]["tag"] == "TORO_01"
    assert g["madre"]["tag"] == "MADRE_01"
    assert len(g["crias"]) >= 1
    assert any(c.get("tag") == "CRIA_01" or c.get("cria_tag") == "CRIA_01" for c in g["crias"])
    assert "consanguinidad" in g
    assert "texto_arbol" in g
    assert "ÁRBOL GENEALÓGICO & TRAZABILIDAD (3G)" in g["texto_arbol"]
