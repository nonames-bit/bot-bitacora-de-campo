"""Seguridad (opción 2): backoff progresivo de login, cuotas en APIs
costosas y exportación solo OWNER.

- CastigoStore: unit con tiempo inyectado (sin dormir de verdad).
- Login: la 9na falla seguida escala a castigo 429; un éxito limpia.
- API: el request 91 a un endpoint con cuota devuelve 429 + Retry-After.
"""
import json

import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.pwa.rate_limit_store import CastigoStore, RateLimitStore


def test_castigo_progresivo_y_tope(tmp_path):
    s = CastigoStore(str(tmp_path / "c.json"))
    assert s.segundos_restantes("1.2.3.4", ahora=1000.0) == 0.0
    assert s.castigar("1.2.3.4", ahora=1000.0) == 60.0
    assert s.segundos_restantes("1.2.3.4", ahora=1059.0) == pytest.approx(1.0)
    assert s.segundos_restantes("1.2.3.4", ahora=1060.0) == 0.0
    # Reincidir duplica: 120, 240... con tope de 1 hora.
    assert s.castigar("1.2.3.4", ahora=1060.0) == 120.0
    assert s.castigar("1.2.3.4", ahora=1060.0) == 240.0
    for _ in range(10):
        d = s.castigar("1.2.3.4", ahora=1060.0)
    assert d == 3600.0
    # Persiste a disco (sobrevive reinicios del servicio).
    s2 = CastigoStore(str(tmp_path / "c.json"))
    assert s2.segundos_restantes("1.2.3.4", ahora=1061.0) > 3500.0


def test_castigo_se_perdona_con_exito(tmp_path):
    s = CastigoStore(str(tmp_path / "c.json"))
    s.castigar("9.9.9.9", ahora=1000.0)
    assert s.segundos_restantes("9.9.9.9", ahora=1010.0) > 0
    s.perdonar("9.9.9.9")
    assert s.segundos_restantes("9.9.9.9", ahora=1010.0) == 0.0


def test_rate_limit_olvidar(tmp_path):
    s = RateLimitStore(str(tmp_path / "r.json"))
    for _ in range(8):
        s.registrar("ip")
    assert s.bloqueado("ip", 8, 60.0) is True
    s.olvidar("ip")
    assert s.bloqueado("ip", 8, 60.0) is False


def _app_con_trabajador(tmp_path):
    from src.db.database import Database
    from src.pwa.app import crear_app

    ruta = str(tmp_path / "seg.db")
    d = Database(ruta)
    d.create_tables()
    d.close()
    u_path = str(tmp_path / "users_seg.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump([{"user_id": 300, "nombre": "T", "rol": "TRABAJADOR", "pin": "1111"}], f)
    app = crear_app(ruta, users_file=u_path, password="x")
    assert app is not None
    app.config.update({"TESTING": True})
    return app


def test_login_escala_a_castigo_y_exito_limpia(tmp_path):
    app = _app_con_trabajador(tmp_path)
    c = app.test_client()
    for _ in range(8):
        r = c.post("/login", data={"password": "0000"})
        assert r.status_code in (301, 302, 303, 307, 308)
    # Ventana agotada: el siguiente intento ya cae en castigo (60 s).
    r9 = c.post("/login", data={"password": "0000"})
    assert r9.status_code == 429
    assert "Espere" in r9.get_data(as_text=True)

    # Tres fallas + un éxito limpian la ventana: hacen falta 8 nuevas
    # fallas para volver a bloquear (sin limpiar serían 5). Nueva app
    # porque el límite es por IP y ambos clientes son localhost.
    app2 = _app_con_trabajador(tmp_path)
    c2 = app2.test_client()
    for _ in range(3):
        c2.post("/login", data={"password": "0000"})
    assert c2.post("/login", data={"pin": "1111"}).status_code in (301, 302, 303, 307, 308)
    for i in range(8):
        r = c2.post("/login", data={"password": "0000"})
        assert r.status_code in (301, 302, 303, 307, 308), i
    assert c2.post("/login", data={"password": "0000"}).status_code == 429


def test_api_mensajes_con_cuota_429(tmp_path):
    app = _app_con_trabajador(tmp_path)
    c = app.test_client()
    c.post("/login", data={"pin": "1111"})
    ultimo = None
    for _ in range(91):
        ultimo = c.get("/api/mensajes-equipo")
    assert ultimo.status_code == 429
    assert ultimo.headers.get("Retry-After") == "60"
    assert ultimo.get_json()["ok"] is False
