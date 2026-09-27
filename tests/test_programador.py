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


def test_ciclo_salud_avisa_una_vez_y_cuando_se_resuelve(monkeypatch):
    enviados = []
    monkeypatch.setattr(programador, "avisar", enviados.append)
    estado = {"actual": {"bot": "bot caído"}}
    monkeypatch.setattr(programador, "revisar_salud", lambda: dict(estado["actual"]))
    avisados: dict = {}
    programador.ciclo_salud(avisados)
    programador.ciclo_salud(avisados)  # sigue caído: no repite
    assert len(enviados) == 1 and "bot caído" in enviados[0]
    estado["actual"] = {}
    programador.ciclo_salud(avisados)
    assert len(enviados) == 2 and enviados[1].startswith("✅") and "bot caído" in enviados[1]


def test_revisar_salud_bot_sin_latido_base_vieja_y_sin_respaldo(tmp_path, monkeypatch):
    import os
    db = tmp_path / "b.db"
    db.write_bytes(b"x")
    os.utime(db, (0, 0))
    latido = tmp_path / ".latido_bot"
    monkeypatch.setattr(programador, "DB", db)
    monkeypatch.setattr(programador, "BACKUPS", tmp_path / "backups")
    monkeypatch.setattr(programador, "LATIDO_BOT", latido)
    monkeypatch.setattr(programador, "_responde", lambda url: True)
    monkeypatch.setenv("TELEGRAM_TOKEN", "t")
    monkeypatch.delenv("DOMINIO", raising=False)
    p = programador.revisar_salud()
    assert {"bot", "base", "respaldo"} <= set(p) and "app" not in p
    latido.write_text("ahora")
    (tmp_path / "backups").mkdir()
    (tmp_path / "backups" / "hoy.db").write_bytes(b"x")
    db.touch()
    assert programador.revisar_salud() == {}


def test_avisar_solo_a_owners(tmp_path, monkeypatch):
    import json
    users = tmp_path / "u.json"
    users.write_text(json.dumps([{"user_id": 1, "rol": "OWNER"}, {"user_id": 2, "rol": "TRABAJADOR"}]))
    monkeypatch.setattr(programador, "USERS_FILE", users)
    monkeypatch.setenv("TELEGRAM_TOKEN", "t")
    llamadas = []
    monkeypatch.setattr(programador.request, "urlopen", lambda url, data=None, timeout=0: llamadas.append(data))
    programador.avisar("hola")
    assert len(llamadas) == 1 and b"chat_id=1" in llamadas[0]
