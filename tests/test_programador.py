"""Tareas programadas del contenedor `tareas` (scripts/programador.py)."""
import sqlite3
from datetime import date, datetime

from scripts import programador


def test_pendientes_respeta_hora_y_una_vez_por_dia():
    lunes = datetime(2026, 9, 28, 6, 10)  # lunes
    nombres = {n for n, _ in programador.pendientes(lunes, {})}
    assert {"precios_mercado", "lluvia_satelital"} <= nombres
    assert "respaldo_local" not in nombres  # 03:00 ya pasó hace más de 1 h
    hechas = {n: lunes.date() for n in nombres}
    assert programador.pendientes(lunes, hechas) == []
    martes = datetime(2026, 9, 29, 6, 10)
    assert "lluvia_satelital" not in {n for n, _ in programador.pendientes(martes, {})}
    assert programador.pendientes(datetime(2026, 9, 28, 5, 59), {}) == []


def test_respaldo_local_copia_y_rota(tmp_path, monkeypatch):
    db = tmp_path / "b.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE t (x)")
        c.execute("INSERT INTO t VALUES (1)")
    backups = tmp_path / "backups"
    backups.mkdir()
    viejo = backups / "2000-01-01.db"
    viejo.write_bytes(b"x")
    import os
    os.utime(viejo, (0, 0))
    monkeypatch.setattr(programador, "DB", db)
    monkeypatch.setattr(programador, "BACKUPS", backups)
    programador.respaldo_local()
    copia = backups / f"{date.today().isoformat()}.db"
    with sqlite3.connect(copia) as c:
        assert c.execute("SELECT x FROM t").fetchone()[0] == 1
    assert not viejo.exists()
