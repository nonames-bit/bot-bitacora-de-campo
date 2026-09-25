"""Regresión P2.12: el fallback "potrero real sin polígonos" es explícito.

Antes se activaba por FORMA DE DATOS (`OR NOT EXISTS (… geom IS NOT NULL)`), así
que una DB de producción que perdiera todos los polígonos (restore/import malo)
resucitaba todos los códigos legacy del DBF como potreros presentes. Ahora solo
se activa con `BITACORA_TEST_MODE=1` (que fija `tests/conftest.py`); en
producción la condición es estricta: `geom_wkt_4326 IS NOT NULL`.
"""
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _sql_potrero_real(env_flag: str | None) -> str:
    env = dict(os.environ)
    env.pop("BITACORA_TEST_MODE", None)
    if env_flag is not None:
        env["BITACORA_TEST_MODE"] = env_flag
    r = subprocess.run(
        [sys.executable, "-c", "import src.db.database as d; print(d.SQL_POTRERO_REAL)"],
        cwd=str(RAIZ), capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_sin_flag_la_condicion_es_estricta():
    expr = _sql_potrero_real(None)
    assert "geom_wkt_4326 IS NOT NULL" in expr
    assert "NOT EXISTS" not in expr, expr


def test_con_flag_incluye_fallback():
    expr = _sql_potrero_real("1")
    assert "NOT EXISTS" in expr, expr


def test_potreros_reales_where_estricto_en_produccion(monkeypatch):
    import src.db.database as d
    monkeypatch.setattr(d, "_MODO_TEST", False)
    assert "NOT EXISTS" not in d.potreros_reales_where()
    assert "NOT EXISTS" not in d.potreros_reales_where("p")


def test_potreros_reales_where_con_fallback_en_test(monkeypatch):
    import src.db.database as d
    monkeypatch.setattr(d, "_MODO_TEST", True)
    assert "NOT EXISTS" in d.potreros_reales_where()
    assert "NOT EXISTS" in d.potreros_reales_where("p")


def test_es_potrero_real_estricto_no_acepta_sin_geometria(monkeypatch, db):
    import src.db.database as d
    monkeypatch.setattr(d, "_MODO_TEST", False)
    db.registrar_potrero(nombre="LEGACY", codigo="09")
    fila = db.query_one("SELECT * FROM potreros WHERE nombre = 'LEGACY'")
    assert d.es_potrero_real(db, fila) is False


def test_es_potrero_real_con_fallback_acepta_sin_geometria_en_test(monkeypatch, db):
    import src.db.database as d
    monkeypatch.setattr(d, "_MODO_TEST", True)
    db.registrar_potrero(nombre="SIN_GEO", codigo="S1")
    fila = db.query_one("SELECT * FROM potreros WHERE nombre = 'SIN_GEO'")
    assert d.es_potrero_real(db, fila) is True
