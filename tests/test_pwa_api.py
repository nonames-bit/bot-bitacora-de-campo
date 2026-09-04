"""Tests Etapa D Fase 7: backend PWA (solo lectura, URL de ficha QR)."""
import os

import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.db.database import Database
from src.pwa.app import crear_app, datos_ficha, datos_pasturas, datos_tablero

_WKT_TEST = "POLYGON((-74.07 3.39, -74.06 3.39, -74.06 3.40, -74.07 3.40, -74.07 3.39))"


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
