"""Fase E: una sola pantalla de Reportes con los PDF y Excel de cada módulo,
y un solo botón "Descargar" por pantalla que lleva a ella."""
import json
from pathlib import Path

from src.db.database import Database
from src.pwa.app import crear_app

RAIZ = Path(__file__).resolve().parent.parent
JS = (RAIZ / "src" / "pwa" / "static" / "app.js").read_text(encoding="utf-8")


def _app(tmp_path):
    db_path = str(tmp_path / "b.db")
    db = Database(db_path).create_tables()
    db.registrar_animal("47", sexo="Hembra", fecha_nacimiento="2019-01-01", potrero="P1", estado="ACTIVO")
    db.close()
    u = tmp_path / "users.json"
    u.write_text(json.dumps([
        {"user_id": 1, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"},
        {"user_id": 4, "nombre": "Pedro", "rol": "TRABAJADOR", "pin": "3333"},
    ]), encoding="utf-8")
    app = crear_app(db_path, users_file=str(u), password="master-password")
    app.config.update({"TESTING": True})
    return app


def test_pantalla_reportes_en_el_menu(tmp_path):
    c = _app(tmp_path).test_client()
    c.post("/login", data={"pin": "1234"})
    html = c.get("/").get_data(as_text=True)
    assert 'id="btn-nav-reportes"' in html and 'id="sheet-item-reportes"' in html
    assert "function renderReportes" in JS and 'actual === "reportes"' in JS


def test_cada_pantalla_tiene_un_solo_boton_descargar():
    # Ya no quedan enlaces sueltos a los reportes fuera de la pantalla Reportes.
    fuera = JS.replace(JS[JS.index("var REPORTES = ["):JS.index("function bindReportes")], "")
    assert "href='/api/reporte.pdf" not in fuera
    assert "href='/api/reporte.xlsx" not in fuera
    for clave in ("general", "reproduccion", "sanidad", "leche", "pasturas", "finanzas"):
        assert f'botonDescargar("{clave}")' in JS or f'barraDescargaSeccion("{clave}"' in JS


def test_reportes_solo_para_owner_y_admin(tmp_path):
    c = _app(tmp_path).test_client()
    c.post("/login", data={"pin": "3333"})
    assert c.get("/api/reporte.xlsx?seccion=inventario").status_code == 403
    assert c.get("/api/reporte.pdf?seccion=inventario").status_code == 403


def test_excel_respeta_el_periodo(tmp_path):
    c = _app(tmp_path).test_client()
    c.post("/login", data={"pin": "1234"})
    r = c.get("/api/reporte.xlsx?seccion=sanidad&dias=30")
    assert r.status_code == 200
    assert r.mimetype.endswith("spreadsheetml.sheet")
