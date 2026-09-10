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
    for ep in ("/api/tablero", "/api/repro", "/api/sanidad", "/api/pasturas", "/api/leche",
               "/api/ficha/47", "/api/finanzas"):
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


def test_login_rate_limit_no_se_elude_falsificando_x_forwarded_for(db_file):
    """Nginx (el único proxy real delante de waitress) AGREGA la IP real al
    final de X-Forwarded-For en vez de reemplazarlo -- así que un atacante
    puede mandar cualquier prefijo falso y aun así el último valor (el que
    puso Nginx) sigue siendo su IP real. ProxyFix(x_for=1) debe usar ese
    último valor, no el primero, para que rotar el prefijo falso no elida
    el rate-limit de /login."""
    app = crear_app(db_file, password="clave-de-prueba")
    c = app.test_client()
    ip_real = "5.5.5.5"
    for i in range(8):
        xff = f"{i}.{i}.{i}.{i}, {ip_real}"  # prefijo falso distinto cada vez + misma IP real al final
        r = c.post("/login", data={"password": "0000"}, headers={"X-Forwarded-For": xff})
        assert r.status_code in (301, 302, 303, 307, 308)
    # Con un prefijo falso todavía distinto, pero la misma IP real al final,
    # debe seguir bloqueado -- si el bug estuviera presente (leer el PRIMER
    # valor), cada prefijo nuevo resetearía el contador y esto pasaría.
    bloqueado = c.post(
        "/login", data={"password": "clave-de-prueba"},
        headers={"X-Forwarded-For": f"99.99.99.99, {ip_real}"},
    )
    assert bloqueado.status_code == 429


def test_cookies_de_sesion_son_secure_httponly_samesite(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


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
    assert "eventos_recientes" in d
    assert isinstance(d["eventos_recientes"], list)


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


def test_pasturas_incluye_pronostico_del_clima(db_file, tmp_path, monkeypatch):
    """El pronóstico del clima ya está en el Despacho Matutino del bot
    (docs/IDEAS_PROYECTOS.md ítem 1) pero faltaba en la PWA -- usa las
    mismas coordenadas (centroide de Guayabal, ya georreferenciado en el
    fixture) y el mismo cache en disco, sin pegarle a la red en el test."""
    import json as _json
    from datetime import date, datetime

    cache = str(tmp_path / "pron_cache.json")
    monkeypatch.setenv("PRONOSTICO_CACHE", cache)
    dias = [
        {"fecha": f"2026-09-{d:02d}", "temp_max_c": 27.0, "temp_min_c": 17.0,
         "lluvia_mm": 3.0, "prob_lluvia_pct": 20.0}
        for d in range(1, 8)
    ]
    payload = {
        "guardado_en": datetime.now().isoformat(),
        "lat": 3.395, "lon": -74.065,
        "pron": {"lat": 3.395, "lon": -74.065, "dias": dias},
    }
    with open(cache, "w", encoding="utf-8") as f:
        _json.dump(payload, f)

    r = datos_pasturas(db_file)
    assert r["pronostico"] is not None
    assert len(r["pronostico"]["dias"]) == 7
    assert "recomendaciones" in r["pronostico"]


def test_pasturas_incluye_alerta_spi_sequia(db_file):
    """Alerta Temprana de Sequía (docs/IDEAS_PROYECTOS.md ítem 2): una fila
    por ventana de días (30/60/90) con el último SPI calculado."""
    from src.db.database import Database
    db = Database(db_file)
    db.registrar_spi_sequia(dias_ventana=30, mm_actual=10.0, spi_valor=-1.8,
                            clasificacion="Sequía severa", fecha="2026-09-01")
    db.close()

    r = datos_pasturas(db_file)
    assert r["spi_sequia"]
    fila = r["spi_sequia"][0]
    assert fila["dias_ventana"] == 30
    assert fila["clasificacion"] == "Sequía severa"


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


def test_api_grafico_composicion_racial_esta_en_whitelist(client):
    """Donut de razas (Genética) que reemplazó las barras de progreso HTML
    repetidas -- debe estar en la whitelist de /api/grafico/<tipo>."""
    r = client.get("/api/grafico/composicion_racial")
    assert r.status_code in (200, 404)  # 404 solo si no hay datos/matplotlib
    if r.status_code == 200:
        assert r.content_type == "image/png"


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


def test_inventario_incluye_estructura_hato_y_tasa_descarte(client):
    """Estructura del hato (CH/HL/NV/VP/VS/CM/ML/MC/REP con % y UGG) y tasa de
    descarte anual, replicando en la PWA los reportes de SG pero calculados
    con datos que sí se alimentan en tiempo real desde el bot."""
    r = client.get("/api/inventario")
    d = r.get_json()
    assert "estructura_hato" in d
    assert "filas" in d["estructura_hato"]
    assert d["estructura_hato"]["total"] == d["total_activos"]
    for fila in d["estructura_hato"]["filas"]:
        assert fila["ugg"] >= 0
    assert "tasa_descarte" in d
    assert "pct" in d["tasa_descarte"]


def test_repro_incluye_kpis(client):
    """IEP, días abiertos, servicios por concepción y tasa de concepción del
    hato, calculados en el mismo endpoint que ya lista FEP/celos/pendientes."""
    r = client.get("/api/repro")
    d = r.get_json()
    assert "kpis" in d
    for clave in ("iep_promedio_dias", "dias_abiertos_promedio",
                  "servicios_por_concepcion", "tasa_concepcion",
                  "edad_primer_parto_meses"):
        assert clave in d["kpis"], clave


def test_crear_animal_nuevo(client):
    """Hasta ahora un animal solo se creaba implícitamente al registrar un
    evento (parto, pesaje, etc.) -- esta es la primera vía para dar de alta
    un animal directamente, con sus datos maestros, sin pasar por un evento."""
    r = client.post("/api/animal", json={
        "tag": "N500", "nombre": "Test Nueva", "sexo": "Hembra", "raza": "I",
        "fecha_nacimiento": "2024-01-01", "potrero": "Guayabal",
        "hierro": "JA", "chip": "985123456", "color": "Negro",
    })
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    ficha = client.get("/api/ficha/N500").get_json()
    assert ficha["existe"] is True
    assert ficha["nombre"] == "Test Nueva"
    assert ficha["chip"] == "985123456"
    assert ficha["color"] == "Negro"


def test_crear_animal_sin_tag_devuelve_400(client):
    r = client.post("/api/animal", json={"nombre": "Sin tag"})
    assert r.status_code == 400


def test_crear_animal_tag_duplicado_devuelve_409(client):
    """No debe permitir crear silenciosamente sobre un animal ya existente
    -- el tag 47 ya está en el fixture db_file. Usar /api/animal/<tag> (PUT)
    para editar en su lugar."""
    r = client.post("/api/animal", json={"tag": "47", "nombre": "Otra cosa"})
    assert r.status_code == 409


def test_editar_animal_actualiza_campos(client):
    r = client.put("/api/animal/47", json={"nombre": "Renombrada", "chip": "111222333"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    ficha = client.get("/api/ficha/47").get_json()
    assert ficha["nombre"] == "Renombrada"
    assert ficha["chip"] == "111222333"


def test_editar_animal_no_existente_devuelve_404(client):
    r = client.put("/api/animal/NO-EXISTE-999", json={"nombre": "X"})
    assert r.status_code == 404


def test_crear_y_editar_animal_requiere_rol_admin_u_owner(tmp_path, db_file):
    """Datos maestros del animal (identidad, genealogía) son más sensibles
    que registrar un evento de campo -- solo ADMIN/OWNER puede crear o editar,
    igual que la gestión de usuarios."""
    import json as _json
    users_json = str(tmp_path / "users_test.json")
    with open(users_json, "w", encoding="utf-8") as f:
        _json.dump([{"user_id": 300, "nombre": "Carlos Vaquero", "rol": "TRABAJADOR", "pin": "7777"}], f)

    app = crear_app(db_file, users_file=users_json, password="master-password")
    c = app.test_client()
    c.post("/login", data={"pin": "7777"})

    r_crear = c.post("/api/animal", json={"tag": "N600", "nombre": "No debería"})
    assert r_crear.status_code == 403
    r_editar = c.put("/api/animal/47", json={"nombre": "No debería"})
    assert r_editar.status_code == 403


def test_api_poblacion_sigue_disponible_como_alias(client):
    r = client.get("/api/poblacion")
    assert r.status_code == 200
    assert "piramide" in r.get_json()


def test_api_qr_pdf_por_animal(db_file, client):
    pytest.importorskip("reportlab", reason="reportlab no instalado")
    # 47 está ACTIVA en el fixture (con parto); exportar tarjeta QR no debe fallar.
    r = client.get("/api/ficha/47/qr.pdf")
    assert r.status_code == 200
    assert r.content_type == "application/pdf"
    assert r.data[:4] == b"%PDF"

    # 99 está VENDIDO en el fixture; debe poder descargarse igualmente su ficha.
    r_ven = client.get("/api/ficha/99/qr.pdf")
    assert r_ven.status_code == 200
    assert r_ven.content_type == "application/pdf"
    assert r_ven.data[:4] == b"%PDF"

    # Rutas alias
    r_alias1 = client.get("/api/ficha/47/pdf")
    assert r_alias1.status_code == 200
    r_alias2 = client.get("/ficha/47/pdf")
    assert r_alias2.status_code == 200

    # Animal inexistente retorna 404
    r_404 = client.get("/api/ficha/ANIMAL-NO-EXISTENTE/qr.pdf")
    assert r_404.status_code == 404


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


def test_api_sync_destete_mueve_a_la_cria_y_opcionalmente_a_la_madre(client, db_file):
    from src.db.database import Database

    db = Database(db_file)
    pid_levante = db.registrar_potrero(nombre="Levante")
    pid_secas = db.registrar_potrero(nombre="Vacas Secas")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho", id_cria_tag="47-1")
    db.close()

    r = client.post("/api/sync", json={"eventos": [{
        "tipo": "destete", "fecha": "2026-09-08",
        "payload": {
            "cria_tag": "47-1", "peso_kg": 120.0, "potrero_cria": "Levante",
            "potrero_madre": "Vacas Secas", "peso_madre_kg": 410.0, "cond_corporal_madre": 3.0,
            "notas": "Destete normal",
        },
    }]})
    assert r.status_code == 200
    assert r.get_json()["procesados"] == 1

    db2 = Database(db_file)
    cria = db2.get_animal("47-1")
    madre = db2.get_animal("47")
    assert cria["potrero_id"] == pid_levante
    assert madre["potrero_id"] == pid_secas
    db2.close()


def test_api_sync_parto_con_potrero_cria_y_madre(client, db_file):
    from src.db.database import Database

    db = Database(db_file)
    pid_cria = db.registrar_potrero(nombre="Corral Maternidad")
    pid_madre = db.registrar_potrero(nombre="Potrero Postparto")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.close()

    r = client.post("/api/sync", json={"eventos": [{
        "tipo": "parto", "fecha": "2026-09-08",
        "payload": {
            "vaca_tag": "47", "id_cria_tag": "47-2", "sexo_cria": "Hembra",
            "potrero_cria": "Corral Maternidad", "potrero_madre": "Potrero Postparto",
        },
    }]})
    assert r.status_code == 200
    assert r.get_json()["procesados"] == 1

    db2 = Database(db_file)
    cria = db2.get_animal("47-2")
    madre = db2.get_animal("47")
    assert cria["potrero_id"] == pid_cria
    assert madre["potrero_id"] == pid_madre
    db2.close()


def test_tablero_incluye_destete_en_eventos_recientes(client, db_file):
    from src.db.database import Database

    db = Database(db_file)
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho", id_cria_tag="47-1")
    db.registrar_destete("47-1", fecha="2026-09-08", peso_kg=120.0)
    db.close()

    r = client.get("/api/tablero")
    assert r.status_code == 200
    tipos = [e["tipo"] for e in r.get_json()["eventos_recientes"]]
    assert "DESTETE" in tipos


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


def test_api_traslado_masivo_mueve_todos_los_animales_activos(client, db_file):
    from src.db.database import Database

    db = Database(db_file)
    pid_destino = db.registrar_potrero(nombre="Morichal", codigo="M1")
    db.execute(
        "UPDATE potreros SET geom_wkt_4326 = ?, centroide_lat = 3.4, centroide_lon = -74.06 WHERE id = ?",
        (_WKT_TEST, pid_destino),
    )
    db.close()

    r = client.post("/api/traslado/masivo", json={
        "potrero_origen": "Guayabal", "potrero_destino": "Morichal", "fecha": "2026-09-08",
        "motivo": "Rotación Voisin",
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    # db_file fixture: "47" está ACTIVO en Guayabal, "99" está VENDIDO -- no cuenta.
    assert body["movidos"] == 1
    assert body["animales"] == ["47"]
    assert body["potrero_destino"] == "Morichal"

    db2 = Database(db_file)
    fila = db2.query_one("SELECT potrero_id FROM animales WHERE tag = '47'")
    assert fila["potrero_id"] == pid_destino
    trasl = db2.query_one(
        "SELECT * FROM traslados WHERE animal_id = (SELECT id_animal FROM animales WHERE tag = '47')"
    )
    assert trasl is not None
    assert trasl["motivo"] == "Rotación Voisin"
    db2.close()


def test_api_traslado_masivo_sin_animales_activos_devuelve_cero(client, db_file):
    from src.db.database import Database

    db = Database(db_file)
    pid_a = db.registrar_potrero(nombre="Vacio A")
    pid_b = db.registrar_potrero(nombre="Vacio B")
    db.execute("UPDATE potreros SET geom_wkt_4326 = ? WHERE id IN (?, ?)", (_WKT_TEST, pid_a, pid_b))
    db.close()

    r = client.post("/api/traslado/masivo", json={"potrero_origen": "Vacio A", "potrero_destino": "Vacio B"})
    assert r.status_code == 200
    assert r.get_json()["movidos"] == 0


def test_api_traslado_masivo_rechaza_potrero_sin_geometria_real(client):
    """'09' es un potrero legacy de SG sin mapa -- no cuenta como real para
    este flujo, aunque exista en la tabla potreros."""
    r = client.post("/api/traslado/masivo", json={"potrero_origen": "09", "potrero_destino": "Guayabal"})
    assert r.status_code == 404


def test_api_traslado_masivo_rechaza_potrero_inexistente(client):
    r = client.post("/api/traslado/masivo", json={"potrero_origen": "Guayabal", "potrero_destino": "NoExiste"})
    assert r.status_code == 404


def test_api_traslado_masivo_rechaza_campos_faltantes(client):
    assert client.post("/api/traslado/masivo", json={"potrero_origen": "Guayabal"}).status_code == 400
    assert client.post("/api/traslado/masivo", json={"potrero_destino": "Guayabal"}).status_code == 400


def test_api_traslado_masivo_rechaza_mismo_origen_y_destino(client):
    r = client.post("/api/traslado/masivo", json={"potrero_origen": "Guayabal", "potrero_destino": "Guayabal"})
    assert r.status_code == 400


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
    assert owner_entry["pin"] == "····"

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
    # El PIN se guarda hasheado (no recuperable): ni el propio Owner ve el
    # valor crudo en el listado, solo si tiene uno asignado o no.
    assert owner_u["pin"] == "····"

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

    # 1. Desvincular Telegram ID (enviar telegram_id: null o vacío en edición)
    vet_uid = res_data["user_id"]
    r_desvincular_tg = c_owner.post("/api/usuarios", json={
        "user_id": vet_uid,
        "nombre": "Dra. Veterinaria",
        "rol": "ADMIN",
        "pin": "9999",
        "telegram_id": None,
        "avatar": "veterinaria"
    })
    assert r_desvincular_tg.status_code == 200
    assert r_desvincular_tg.get_json()["usuario"]["telegram_id"] is None

    # 2. Verificar que la sesión activa de c_vet se revoca inmediatamente al ser eliminado
    r_del_vet = c_owner.post(f"/api/usuarios/{vet_uid}/eliminar")
    assert r_del_vet.status_code == 200

    # Próximo request de c_vet debe ser rechazado con 401 porque el usuario ya no existe en users.json
    r_vet_revocado = c_vet.get("/api/usuario")
    assert r_vet_revocado.status_code == 401


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

    # 3. Admin sí tiene acceso a rutas (permitido para administradores y dueños)
    c_adm = app.test_client()
    c_adm.post("/login", data={"pin": "2222"})
    r_rutas_adm = c_adm.get("/api/telemetria/rutas")
    assert r_rutas_adm.status_code == 200

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


def test_api_leche_analizar_recibo_y_guardar_quincena(client, db_file):
    from unittest.mock import patch
    sample_parse = {
        "ok": True,
        "es_recibo_leche": True,
        "periodo": "1 al 15 de Mayo 2026",
        "total_litros_calculado": 360.0,
        "dias": [
            {"fecha": "2026-05-01", "dia": 1, "litros": 180.0, "notas": "AM+PM"},
            {"fecha": "2026-05-02", "dia": 2, "litros": 180.0, "notas": "AM+PM"},
        ],
    }

    with patch("src.vision.recibo_leche_parser.analizar_recibo_leche", return_value=sample_parse):
        r = client.post("/api/leche/analizar-recibo", json={"foto_base64": "fake_base64_data"})
        assert r.status_code == 200
        res = r.get_json()
        assert res["ok"] is True
        assert len(res["dias"]) == 2

    # Guardar la quincena
    r_guardar = client.post("/api/leche/guardar-quincena", json={
        "periodo": "1 al 15 de Mayo 2026",
        "dias": res["dias"],
        "observaciones": "Recibo de prueba"
    })
    assert r_guardar.status_code == 200
    g_res = r_guardar.get_json()
    assert g_res["ok"] is True
    assert g_res["guardados"] == 2
    assert g_res["total_litros"] == 360.0

    # Verificar que los datos aparecen en /api/leche
    r_leche = client.get("/api/leche")
    assert r_leche.status_code == 200
    d_leche = r_leche.get_json()
    fechas = [f["fecha"] for f in d_leche["serie_tanque"]]
    assert "2026-05-01" in fechas
    assert "2026-05-02" in fechas


def test_api_leche_analizar_recibo_guarda_la_foto_de_inmediato(client, db_file):
    """Regresión: la foto del recibo es la prueba del pago -- si el usuario
    cierra la pestaña después de analizarla pero antes de "Guardar Quincena",
    no debería perderse. /analizar-recibo debe guardarla ya, sin depender
    del paso final."""
    import base64
    from unittest.mock import patch
    from src.db.database import Database

    fake_img_b64 = base64.b64encode(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    ).decode("utf-8")
    sample_parse = {
        "ok": True, "es_recibo_leche": True, "periodo": "16 al 31 de Agosto",
        "total_litros_calculado": 350.0,
        "dias": [{"fecha": "2026-08-16", "dia": 16, "litros": 350.0, "notas": ""}],
    }

    with patch("src.vision.recibo_leche_parser.analizar_recibo_leche", return_value=sample_parse):
        r = client.post("/api/leche/analizar-recibo", json={
            "foto_base64": f"data:image/jpeg;base64,{fake_img_b64}",
        })
    assert r.status_code == 200
    res = r.get_json()
    assert res["foto_ruta"]  # se guardó, sin necesidad de "Guardar Quincena"

    db = Database(db_file)
    try:
        fila = db.query_one("SELECT * FROM fotos WHERE ruta = ?", (res["foto_ruta"],))
        assert fila is not None
        assert fila["caption"].startswith("Recibo Quincenal")
    finally:
        db.close()


def test_datos_leche_fotos_recibos_excluye_facturas_de_finanzas(db):
    """Regresión: el filtro de fotos_recibos en Leche usaba `caption LIKE
    '%Recibo%'`, que también atrapaba las facturas de Finanzas (caption
    "Factura/Recibo: <concepto>") -- se colaban gastos/compras ajenos a la
    leche en la sección de recibos de leche."""
    from src.engine.dashboard_data import datos_leche

    db.registrar_foto(ruta="media/recibo_leche_1.jpg", fecha="2026-09-08",
                      caption="Recibo Quincenal: 1 al 15 de Septiembre",
                      notas="Foto guardada al momento de analizar con IA (evidencia del pago).")
    db.registrar_foto(ruta="media/factura_1.jpg", fecha="2026-09-08",
                      caption="Factura/Recibo: Compra de sal mineralizada",
                      notas="Foto guardada al momento de analizar con IA (evidencia del gasto/ingreso).")

    datos = datos_leche(db)

    rutas = [f["ruta"] for f in datos["fotos_recibos"]]
    assert "media/recibo_leche_1.jpg" in rutas
    assert "media/factura_1.jpg" not in rutas


def test_api_finanzas_analizar_factura(client):
    """Fase 2 de Finanzas: digitalización de facturas/recibos generales con
    IA, mismo patrón que el recibo de leche -- extrae categoría, concepto,
    monto y proveedor para pre-llenar la captura de gasto/ingreso."""
    import base64
    from unittest.mock import patch
    fake_img_b64 = base64.b64encode(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    ).decode("utf-8")
    sample_parse = {
        "ok": True, "es_factura": True, "tipo": "EGRESO", "fecha": "2026-09-07",
        "proveedor": "Agrotienda El Ganadero", "concepto": "Sal mineralizada 3 bultos",
        "categoria_sugerida": "INSUMO", "monto_total": 450000.0,
        "observaciones": "", "confianza": "alta",
    }
    with patch("src.vision.recibo_gasto_parser.analizar_factura_gasto", return_value=sample_parse):
        r = client.post("/api/finanzas/analizar-factura", json={"foto_base64": fake_img_b64})
    assert r.status_code == 200
    res = r.get_json()
    assert res["ok"] is True
    assert res["categoria_sugerida"] == "INSUMO"
    assert res["monto_total"] == 450000.0
    assert res["foto_ruta"]  # se guarda de inmediato, igual que el recibo de leche


def test_api_finanzas_analizar_factura_sin_foto_devuelve_400(client):
    r = client.post("/api/finanzas/analizar-factura", json={})
    assert r.status_code == 400


def test_api_grafico_flujo_caja_esta_en_whitelist(client):
    r = client.get("/api/grafico/flujo_caja")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.content_type == "image/png"


def test_api_finanzas_incluye_kpis(client):
    r = client.get("/api/finanzas")
    assert r.status_code == 200
    d = r.get_json()
    assert "kpis" in d
    for clave in ("costo_por_litro_leche", "margen_utilidad_pct", "costo_por_cabeza",
                  "costo_por_kg_carne", "flujo_mensual"):
        assert clave in d["kpis"], clave


def test_api_finanzas_editar_y_eliminar_requieren_rol_owner(tmp_path, db_file):
    """Editar/eliminar un movimiento financiero manual queda reservado a
    OWNER -- a diferencia de crearlo, que ADMIN también puede hacer."""
    import json
    from src.db.database import Database

    db = Database(db_file)
    fid = db.registrar_finanza(fecha="2026-09-07", tipo="EGRESO", categoria="INSUMO",
                               concepto="Sal", monto=100000)
    db.close()

    users_data = [
        {"user_id": 100, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"},
        {"user_id": 200, "nombre": "Admin", "rol": "ADMIN", "pin": "2222"},
    ]
    u_path = str(tmp_path / "users_test.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump(users_data, f)

    app = crear_app(db_file, users_file=u_path, password="master-password")
    app.config.update({"TESTING": True})

    # ADMIN: 403 tanto para editar como para eliminar.
    c_adm = app.test_client()
    c_adm.post("/login", data={"pin": "2222"})
    assert c_adm.put(f"/api/finanzas/{fid}", json={"monto": 200000}).status_code == 403
    assert c_adm.delete(f"/api/finanzas/{fid}").status_code == 403

    # OWNER: puede editar...
    c_own = app.test_client()
    c_own.post("/login", data={"pin": "1234"})
    r_edit = c_own.put(f"/api/finanzas/{fid}", json={"monto": 250000, "concepto": "Sal mineralizada"})
    assert r_edit.status_code == 200
    assert r_edit.get_json()["ok"] is True

    db2 = Database(db_file)
    fila = db2.query_one("SELECT * FROM finanzas WHERE id = ?", (fid,))
    assert fila["monto"] == 250000
    assert fila["concepto"] == "Sal mineralizada"
    db2.close()

    # ...y eliminar.
    r_del = c_own.delete(f"/api/finanzas/{fid}")
    assert r_del.status_code == 200
    assert r_del.get_json()["ok"] is True

    db3 = Database(db_file)
    assert db3.query_one("SELECT * FROM finanzas WHERE id = ?", (fid,)) is None
    db3.close()


def test_api_finanzas_editar_id_inexistente_devuelve_404(tmp_path, db_file):
    import json
    users_data = [{"user_id": 100, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"}]
    u_path = str(tmp_path / "users_test.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump(users_data, f)
    app = crear_app(db_file, users_file=u_path, password="master-password")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"pin": "1234"})
    assert c.put("/api/finanzas/99999", json={"monto": 1000}).status_code == 404
    assert c.delete("/api/finanzas/99999").status_code == 404


def test_api_finanzas_editar_monto_invalido_devuelve_400(tmp_path, db_file):
    import json
    from src.db.database import Database
    db = Database(db_file)
    fid = db.registrar_finanza(fecha="2026-09-07", tipo="EGRESO", categoria="INSUMO", monto=100000)
    db.close()
    users_data = [{"user_id": 100, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"}]
    u_path = str(tmp_path / "users_test.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump(users_data, f)
    app = crear_app(db_file, users_file=u_path, password="master-password")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"pin": "1234"})
    assert c.put(f"/api/finanzas/{fid}", json={"monto": -5}).status_code == 400
    assert c.put(f"/api/finanzas/{fid}", json={"monto": "no-numero"}).status_code == 400
    assert c.put(f"/api/finanzas/{fid}", json={"tipo": "ALGO_RARO"}).status_code == 400


def test_api_sync_gasto_con_foto_ruta_no_duplica_foto(client, db_file):
    """Si la factura ya se analizó con IA, la foto quedó guardada en ese
    momento -- el evento final de captura debe enlazarla por ruta en vez de
    volver a subir los mismos bytes (ver /api/finanzas/analizar-factura)."""
    from src.db.database import Database

    db = Database(db_file)
    db.registrar_foto(ruta="media/factura_ya_guardada.jpg", caption="Factura/Recibo: Sal")
    db.close()

    r = client.post("/api/sync", json={"eventos": [{
        "id_local": "x1", "tipo": "gasto", "fecha": "2026-09-07",
        "payload": {
            "tipo_finanza": "EGRESO", "categoria": "INSUMO", "concepto": "Sal",
            "monto": 100000, "foto_ruta": "media/factura_ya_guardada.jpg",
        },
    }]})
    assert r.status_code == 200

    db = Database(db_file)
    try:
        fila = db.query_one("SELECT foto_ruta FROM finanzas WHERE concepto = 'Sal'")
        assert fila["foto_ruta"] == "media/factura_ya_guardada.jpg"
        n_fotos = db.query_one("SELECT COUNT(*) n FROM fotos WHERE ruta = 'media/factura_ya_guardada.jpg'")
        assert n_fotos["n"] == 1  # no se duplicó el registro de foto
    finally:
        db.close()


def test_api_leche_guardar_quincena_con_monto_crea_ingreso_en_finanzas(client, db_file):
    """Guardar la quincena con el monto que pagaron debe crear el ingreso en
    Finanzas (categoría VENTA_LECHE) reusando la misma foto ya guardada al
    analizar -- sin volver a duplicar el archivo."""
    r_guardar = client.post("/api/leche/guardar-quincena", json={
        "periodo": "16 al 31 de Agosto",
        "dias": [
            {"fecha": "2026-08-16", "dia": 16, "litros": 350.0, "notas": ""},
            {"fecha": "2026-08-17", "dia": 17, "litros": 321.0, "notas": ""},
        ],
        "foto_ruta": "media/recibo_leche_ya_guardada.jpg",
        "monto_pagado": 1342000,
        "acopiador": "Sebastian Arcila",
    })
    assert r_guardar.status_code == 200
    g_res = r_guardar.get_json()
    assert g_res["ok"] is True
    assert g_res["ingreso_id"] is not None
    assert g_res["foto_ruta"] == "media/recibo_leche_ya_guardada.jpg"

    r_fin = client.get("/api/finanzas")
    assert r_fin.status_code == 200
    recientes = r_fin.get_json()["recientes"]
    fila = next(f for f in recientes if f["id"] == g_res["ingreso_id"])
    assert fila["categoria"] == "VENTA_LECHE"
    assert fila["monto"] == 1342000
    assert fila["litros"] == 671.0
    assert fila["contraparte"] == "Sebastian Arcila"
    assert fila["foto_ruta"] == "media/recibo_leche_ya_guardada.jpg"


def test_api_leche_guardar_quincena_sin_monto_no_crea_ingreso(client):
    r = client.post("/api/leche/guardar-quincena", json={
        "periodo": "1 al 15 de Junio",
        "dias": [{"fecha": "2026-06-01", "dia": 1, "litros": 200.0, "notas": ""}],
    })
    assert r.status_code == 200
    assert r.get_json()["ingreso_id"] is None


# ---------------------------------------------------------------------------
# Finanzas: libro de ingresos/egresos + resumen de utilidad.
# ---------------------------------------------------------------------------
def test_api_finanzas_crear_valida_tipo_categoria_y_monto(client):
    r = client.post("/api/finanzas", json={"tipo": "X", "categoria": "INSUMO", "monto": 1000})
    assert r.status_code == 400

    r = client.post("/api/finanzas", json={"tipo": "EGRESO", "categoria": "", "monto": 1000})
    assert r.status_code == 400

    r = client.post("/api/finanzas", json={"tipo": "EGRESO", "categoria": "INSUMO", "monto": 0})
    assert r.status_code == 400

    r = client.post("/api/finanzas", json={"tipo": "EGRESO", "categoria": "INSUMO", "monto": "no-numero"})
    assert r.status_code == 400


def test_api_finanzas_crear_y_listar(client):
    r = client.post("/api/finanzas", json={
        "fecha": "2026-09-06", "tipo": "egreso", "categoria": "insumo",
        "concepto": "Sal mineralizada 40kg", "monto": 180000, "contraparte": "Agropecuaria X",
    })
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    r2 = client.post("/api/finanzas", json={
        "fecha": "2026-09-05", "tipo": "ingreso", "categoria": "venta_leche",
        "monto": 2000000, "litros": 1500,
    })
    assert r2.status_code == 200

    r_get = client.get("/api/finanzas")
    assert r_get.status_code == 200
    d = r_get.get_json()
    assert d["resumen"]["total_ingresos"] == 2000000
    assert d["resumen"]["total_egresos"] == 180000
    assert d["resumen"]["utilidad"] == 1820000
    conceptos = [f["concepto"] for f in d["recientes"]]
    assert "Sal mineralizada 40kg" in conceptos


def test_api_finanzas_incluye_venta_compra_de_animales_de_movimientos(client, db_file):
    d = Database(db_file)
    try:
        d.registrar_movimiento("47", fecha="2026-09-06", tipo_movimiento="VENTA", precio=1500000)
    finally:
        d.close()

    r = client.get("/api/finanzas")
    assert r.status_code == 200
    resumen = r.get_json()["resumen"]
    assert resumen["total_ingresos"] == 1500000
    categorias = {(c["tipo"], c["categoria"]) for c in resumen["categorias"]}
    assert ("INGRESO", "VENTA_ANIMAL") in categorias

    ventas_compras = r.get_json()["ventas_compras"]
    assert any(v["animal_tag"] == "47" and v["tipo_movimiento"] == "VENTA" for v in ventas_compras)


def test_api_finanzas_filtra_por_desde_hasta(client):
    client.post("/api/finanzas", json={"fecha": "2026-01-15", "tipo": "INGRESO", "categoria": "VENTA_LECHE", "monto": 100000})
    client.post("/api/finanzas", json={"fecha": "2026-09-15", "tipo": "INGRESO", "categoria": "VENTA_LECHE", "monto": 200000})

    r = client.get("/api/finanzas?desde=2026-09-01&hasta=2026-09-30")
    assert r.status_code == 200
    assert r.get_json()["resumen"]["total_ingresos"] == 200000


def test_api_sync_gasto_con_foto_queda_enlazada_en_finanzas(client, db_file):
    """La foto adjunta a un evento 'gasto' vía /api/sync (cola offline de
    Captura) debe quedar enlazada en finanzas.foto_ruta, no solo en la
    galería general de fotos -- si no, el detalle del movimiento en la
    vista Finanzas nunca puede mostrarla."""
    import base64

    fake_img = base64.b64encode(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    ).decode("utf-8")
    b64_data = f"data:image/jpeg;base64,{fake_img}"

    r = client.post("/api/sync", json={"eventos": [{
        "tipo": "gasto",
        "id_local": "loc_gasto_foto",
        "fecha": "2026-09-07",
        "payload": {
            "tipo_finanza": "EGRESO", "categoria": "INSUMO",
            "concepto": "Alambre de púa 200m", "monto": 250000,
            "foto_base64": b64_data,
        },
    }]})
    assert r.status_code == 200
    assert r.get_json()["procesados"] == 1

    r_fin = client.get("/api/finanzas")
    assert r_fin.status_code == 200
    recientes = r_fin.get_json()["recientes"]
    fila = next(f for f in recientes if f["concepto"] == "Alambre de púa 200m")
    assert fila["foto_ruta"]
    assert fila["foto_ruta"].startswith("media/") or fila["foto_ruta"].startswith("media\\")


def test_ficha_incluye_venta_muerte_e_historial_bajas(db_file, client):
    """Verifica que /api/ficha/<tag> reporte la información estructurada de
    venta y muerte con fechas, comprador, causa, precio y notas."""
    d = Database(db_file)
    # Registrar animal vendido con movimiento de venta
    d.registrar_animal("V01", sexo="Hembra", estado="VENDIDO")
    d.execute(
        "INSERT INTO movimientos (animal_id, fecha, tipo_movimiento, procedencia_destino, precio, notas) "
        "VALUES (?, '2026-09-05', 'VENTA', 'Subasta Ganadera San Martín', 3200000, 'Vendida con cría')",
        (d.animal_id("V01"),),
    )
    # Registrar animal muerto con registro de muerte
    d.registrar_animal("M01", sexo="Hembra", estado="MUERTO")
    d.execute(
        "INSERT INTO muertes (animal_id, fecha, causa_presunta, notas) "
        "VALUES (?, '2026-08-12', 'TIMPANISMO', 'Hallada en potrero 3')",
        (d.animal_id("M01"),),
    )
    d.close()

    # Consultar ficha de V01
    r_v = client.get("/api/ficha/V01")
    assert r_v.status_code == 200
    data_v = r_v.get_json()
    assert data_v["estado"] == "VENDIDO"
    assert data_v["venta"] is not None
    assert data_v["venta"]["fecha"] == "2026-09-05"
    assert data_v["venta"]["procedencia_destino"] == "Subasta Ganadera San Martín"
    assert data_v["venta"]["precio"] == 3200000
    assert len(data_v["historial_bajas"]) >= 1
    assert data_v["historial_bajas"][0]["tipo"] == "VENTA"

    # Consultar ficha de M01
    r_m = client.get("/api/ficha/M01")
    assert r_m.status_code == 200
    data_m = r_m.get_json()
    assert data_m["estado"] == "MUERTO"
    assert data_m["muerte"] is not None
    assert data_m["muerte"]["fecha"] == "2026-08-12"
    assert data_m["muerte"]["causa_presunta"] == "TIMPANISMO"
    assert len(data_m["historial_bajas"]) >= 1
    assert data_m["historial_bajas"][0]["tipo"] == "MUERTE"


def test_ficha_incluye_hierro_y_en_genealogia(db_file, client):
    """Verifica que /api/ficha/<tag> reporte el hierro del animal,
    así como el hierro de sus ancestros y de sus crías."""
    d = Database(db_file)
    # Registrar madre con hierro
    d.registrar_animal("MADRE_HIE", sexo="Hembra", estado="ACTIVO", hierro="17QX")
    # Registrar hija con hierro
    d.registrar_animal(
        "HIJA_HIE", sexo="Hembra", estado="ACTIVO", madre_tag="MADRE_HIE", hierro="49BG"
    )
    # Registrar nieta (cría de HIJA_HIE) con hierro
    d.registrar_animal(
        "CRIA_HIE", sexo="Hembra", estado="ACTIVO", madre_tag="HIJA_HIE", hierro="SJ65"
    )
    d.close()

    # Consultar ficha de HIJA_HIE
    r = client.get("/api/ficha/HIJA_HIE")
    assert r.status_code == 200
    data = r.get_json()
    assert data["tag"] == "HIJA_HIE"
    assert data["hierro"] == "49BG"

    # Verificar que el árbol genealógico incluye el hierro de la madre
    gen = data.get("genealogia_3g") or {}
    madre = gen.get("madre")
    assert madre is not None
    assert madre["tag"] == "MADRE_HIE"
    assert madre["hierro"] == "17QX"
    assert data.get("madre") is not None
    assert data["madre"]["hierro"] == "17QX"

    # Verificar que el listado de crías incluye el hierro de la cría
    crias = data.get("crias") or []
    assert len(crias) >= 1
    cria_entry = next((c for c in crias if c["tag"] == "CRIA_HIE"), None)
    assert cria_entry is not None
    assert cria_entry["hierro"] == "SJ65"


def test_pasturas_incluye_satelite_resumen(client, db_file):
    """Verifica que /api/pasturas incluye el bloque satelite_resumen con soporte Sentinel-1 SAR."""
    from src.db.database import Database

    db = Database(db_file)
    pot_id = db.registrar_potrero(nombre="Potrero Radar Test", area_has=10.0, geom_wkt_4326="POLYGON((-73.1 6.8, -73.0 6.8, -73.0 6.9, -73.1 6.9, -73.1 6.8))")
    db.registrar_lectura_ndvi(
        pot_id,
        ndvi_promedio=0.742,
        fecha="2026-09-01",
        biomasa_estimada_kg_ha=2900.0,
        aforo_estimado_kg_m2=1.35,
        fuente="Sentinel-1 SAR GRD (Radar C-band, vía Google Earth Engine)",
    )
    db.close()

    r = client.get("/api/pasturas")
    assert r.status_code == 200
    data = r.get_json()
    assert "satelite_resumen" in data
    resumen = data["satelite_resumen"]
    assert resumen.get("total_potreros", 0) >= 1
    assert resumen.get("total_sar", 0) >= 1
    assert "Radar SAR" in resumen.get("modo_activo", "")
    assert data["ndvi_reciente"][0]["fuente"].startswith("Sentinel-1 SAR")


def test_api_satelite_actualizar_flujo_completo(client, db_file, monkeypatch):
    """Verifica el endpoint POST /api/satelite/actualizar con mock de Earth Engine."""
    from unittest.mock import MagicMock
    import src.gis.earth_engine_ndvi as gee_ndvi

    mock_lecturas = [
        {
            "potrero_id": 1,
            "potrero_nombre": "Guayabal",
            "area_has": 12.0,
            "fecha": "2026-09-05",
            "ndvi_promedio": 0.78,
            "ndvi_min": 0.65,
            "ndvi_max": 0.85,
            "biomasa_estimada_kg_ha": 3100.0,
            "aforo_estimado_kg_m2": 1.45,
            "categoria": "EXCELENTE",
            "emoji": "🌿",
            "alerta": "normal",
            "cobertura_nubes_pct": 0.0,
            "fuente": "Sentinel-1 SAR GRD (Radar C-band, vía Google Earth Engine)",
            "sensor": "SAR_SENTINEL1",
            "rvi": 0.88,
            "humedad_pct": 78.5,
        }
    ]

    monkeypatch.setattr(gee_ndvi, "actualizar_lecturas_reales", MagicMock(return_value=mock_lecturas))

    # Invocación con modo radar
    r = client.post("/api/satelite/actualizar", json={"modo": "radar"})
    assert r.status_code == 200
    res = r.get_json()
    assert res["ok"] is True
    assert res["actualizados"] == 1
    assert res["sar"] == 1
    assert "Radar SAR Sentinel-1" in res["sensor_principal"]


def test_api_mapa_datos_devuelve_geojson_y_finca(client):
    r = client.get("/api/mapa/datos")
    assert r.status_code == 200
    res = r.get_json()
    assert res["ok"] is True
    assert "finca" in res
    assert "potreros_geojson" in res
    assert res["potreros_geojson"]["type"] == "FeatureCollection"
    assert len(res["potreros_geojson"]["features"]) >= 1
    nombres = [f["properties"]["nombre"] for f in res["potreros_geojson"]["features"]]
    assert "Guayabal" in nombres
    p0 = next(f["properties"] for f in res["potreros_geojson"]["features"] if f["properties"]["nombre"] == "Guayabal")
    assert "color_voisin" in p0
    assert "color_ndvi" in p0


def test_api_push_suscribir_alertas_y_desuscribir(client):
    # Suscribir
    r_sub = client.post("/api/push/suscribir", json={
        "endpoint": "https://push.test.com/token123",
        "keys": {"p256dh": "key1", "auth": "auth1"}
    })
    assert r_sub.status_code == 200
    assert r_sub.get_json()["ok"] is True

    # Consultar alertas push
    r_alt = client.get("/api/push/alertas")
    assert r_alt.status_code == 200
    res_alt = r_alt.get_json()
    assert res_alt["ok"] is True
    assert "alertas" in res_alt

    # Probar endpoint de prueba
    r_prb = client.post("/api/push/probar")
    assert r_prb.status_code == 200
    assert r_prb.get_json()["ok"] is True
    assert "notificacion" in r_prb.get_json()

    # Desuscribir
    r_del = client.post("/api/push/desuscribir", json={
        "endpoint": "https://push.test.com/token123"
    })
    assert r_del.status_code == 200
    assert r_del.get_json()["ok"] is True


def test_api_mapa_datos_restringido_a_trabajador(client):
    with client.session_transaction() as sess:
        sess["rol"] = "TRABAJADOR"
    r = client.get("/api/mapa/datos")
    assert r.status_code == 403


def test_api_mapa_datos_permitido_a_admin(client):
    with client.session_transaction() as sess:
        sess["rol"] = "ADMIN"
    r = client.get("/api/mapa/datos")
    assert r.status_code == 200
    d = r.get_json()
    assert "potreros_geojson" in d
    assert "rutas" in d


def test_api_mercado_precios_retorna_subastas_leche_e_insumos(client):
    r = client.get("/api/mercado/precios")
    assert r.status_code == 200
    d = r.get_json()
    assert "subastas" in d
    assert "leche" in d
    assert "insumos" in d
    assert "fuentes_oficiales" in d
    assert d["ubicacion_finca"] == "Mesetas, Meta (Región Ariari)"

    plazas = [s["plaza_key"] for s in d["subastas"]]
    for esperada in ("GRANADA", "GUAMAL", "SAN_MARTIN", "CATAMA", "BOGOTA", "PROMEDIO_NACIONAL"):
        assert esperada in plazas

    # Alias /api/mercado también debe responder exactamente igual
    r_alias = client.get("/api/mercado")
    assert r_alias.status_code == 200
    assert len(r_alias.get_json()["subastas"]) == len(d["subastas"])


def test_api_mercado_actualizar_permisos_y_guardado(client):
    # TRABAJADOR no puede actualizar precios de mercado
    with client.session_transaction() as sess:
        sess["rol"] = "TRABAJADOR"
    r_no_auth = client.post("/api/mercado/actualizar", json={
        "plaza": "GRANADA",
        "producto": "MACHO_GORDO",
        "precio_promedio": 8700
    })
    assert r_no_auth.status_code == 403
    assert r_no_auth.get_json()["ok"] is False

    # ADMIN u OWNER sí pueden
    with client.session_transaction() as sess:
        sess["rol"] = "ADMIN"
    
    # Error 400 por campos faltantes
    r_bad = client.post("/api/mercado/actualizar", json={"plaza": "GRANADA"})
    assert r_bad.status_code == 400

    # Registro exitoso
    r_ok = client.post("/api/mercado/actualizar", json={
        "plaza": "GRANADA",
        "producto": "MACHO_GORDO",
        "precio_promedio": 8950,
        "precio_maximo": 9300,
        "precio_minimo": 8600,
        "unidad": "$/kg",
        "fuente": "Sugameta Martes Remate Especial",
        "notas": "Lote cebú comercial extraordinario"
    })
    assert r_ok.status_code == 200
    res = r_ok.get_json()
    assert res["ok"] is True
    assert res["id"] > 0

    # Verificar que el precio actualizado aparece en la consulta
    r_get = client.get("/api/mercado/precios")
    d = r_get.get_json()
    granada = next(s for s in d["subastas"] if s["plaza_key"] == "GRANADA")
    macho_gordo = granada["productos"]["MACHO_GORDO"]
    assert macho_gordo["precio_promedio"] == 8950
    assert macho_gordo["precio_maximo"] == 9300






