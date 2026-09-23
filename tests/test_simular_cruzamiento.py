"""Simulador de cruzamiento en 1 toque (Fase 5.2): vaca + toro antes de
servir, con veredicto 3G, ancestros comunes y aviso en PWA/Telegram."""
import json

import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.bot.bot_interface import Bot
from src.db.database import Database
from src.parsers.event_parser import ParsedEvent
from src.pwa.app import crear_app


@pytest.fixture
def db(tmp_path):
    ruta = str(tmp_path / "sim.db")
    d = Database(ruta)
    d.create_tables()
    # Pedigrí de prueba:
    #   ABU1 (macho) x ABU2 (hembra) -> VACA1 (hembra)
    #   ABU1 x OTRA (hembra)          -> TORO1 (macho, medio hermano de VACA1)
    #   TORO2 (macho)                 -> sin padres (línea independiente)
    #   TORO3 (macho)                 -> padre de VACA3 (relación directa)
    d.registrar_animal("ABU1", sexo="Macho", estado="ACTIVO")
    d.registrar_animal("ABU2", sexo="Hembra", estado="ACTIVO")
    d.registrar_animal("OTRA", sexo="Hembra", estado="ACTIVO")
    d.registrar_animal("VACA1", sexo="Hembra", estado="ACTIVO",
                       madre_tag="ABU2", padre_tag="ABU1")
    d.registrar_animal("TORO1", sexo="Macho", estado="ACTIVO",
                       madre_tag="OTRA", padre_tag="ABU1")
    d.registrar_animal("TORO2", sexo="Macho", estado="ACTIVO")
    d.registrar_animal("TORO3", sexo="Macho", estado="ACTIVO")
    d.registrar_animal("MADRE3", sexo="Hembra", estado="ACTIVO")
    d.registrar_animal("VACA3", sexo="Hembra", estado="ACTIVO",
                       madre_tag="MADRE3", padre_tag="TORO3")
    d.registrar_animal("VACA0", sexo="Hembra", estado="ACTIVO")
    d.registrar_animal("TORO0", sexo="Macho", estado="ACTIVO")
    # NIETA (VACA1 x TORO2): ABU1 le llega en nivel 2 (abuelo materno).
    d.registrar_animal("NIETA", sexo="Hembra", estado="ACTIVO",
                       madre_tag="VACA1", padre_tag="TORO2")
    yield d
    d.close()


def test_apto_sin_parentesco(db):
    sim = db.simular_cruzamiento("VACA1", "TORO2")
    assert sim["evaluable"] is True
    assert sim["apto"] is True
    assert sim["veredicto"] == "APTO"
    assert sim["ancestros_comunes"] == []
    assert sim["relacion_directa"] is None


def test_no_apto_por_padre_comun(db):
    # VACA1 (ABU1 x ABU2) y TORO1 (ABU1 x OTRA) son medios hermanos:
    # comparten al padre ABU1 en nivel 1 de ambas ramas.
    sim = db.simular_cruzamiento("VACA1", "TORO1")
    assert sim["evaluable"] is True
    assert sim["apto"] is False
    assert sim["veredicto"] == "NO RECOMENDADO"
    tags = [a["tag"] for a in sim["ancestros_comunes"]]
    assert "ABU1" in tags
    comun = next(a for a in sim["ancestros_comunes"] if a["tag"] == "ABU1")
    assert comun["parentesco_vaca"] == "padre"
    assert comun["parentesco_toro"] == "padre"
    assert "ABU1" in sim["detalle"]


def test_no_apto_por_abuelo_en_segunda_generacion(db):
    # NIETA x TORO1: ABU1 es abuelo materno de NIETA y padre de TORO1.
    sim = db.simular_cruzamiento("NIETA", "TORO1")
    assert sim["evaluable"] is True
    assert sim["apto"] is False
    comun = next(a for a in sim["ancestros_comunes"] if a["tag"] == "ABU1")
    assert comun["parentesco_vaca"] == "abuelo"
    assert comun["parentesco_toro"] == "padre"


def test_no_apto_relacion_directa_padre_hija(db):
    sim = db.simular_cruzamiento("VACA3", "TORO3")
    assert sim["evaluable"] is True
    assert sim["apto"] is False
    assert sim["relacion_directa"] is not None
    assert "TORO3" in sim["relacion_directa"]


def test_no_evaluable_sin_pedigri(db):
    sim = db.simular_cruzamiento("VACA0", "TORO0")
    assert sim["evaluable"] is False
    assert sim["veredicto"] == "NO EVALUABLE"


def test_no_evaluable_toro_externo(db):
    sim = db.simular_cruzamiento("VACA1", "PAJUELA-COMERCIAL-X")
    assert sim["evaluable"] is False
    assert "externo" in sim["detalle"] or "pajuela" in sim["detalle"].lower()


def test_no_evaluable_desconocidos_y_mismo_animal(db):
    assert db.simular_cruzamiento("NOEXISTE", "TORO2")["evaluable"] is False
    assert db.simular_cruzamiento("VACA1", "NOEXISTE")["evaluable"] is False
    assert db.simular_cruzamiento("", "TORO2")["evaluable"] is False
    assert db.simular_cruzamiento("VACA1", "VACA1")["evaluable"] is False


def test_no_crea_animales_fantasma(db):
    antes = db.query_one("SELECT COUNT(*) n FROM animales")["n"]
    db.simular_cruzamiento("TYPO1", "TYPO2")
    despues = db.query_one("SELECT COUNT(*) n FROM animales")["n"]
    assert antes == despues


def test_advertencia_pedigri_parcial(db):
    sim = db.simular_cruzamiento("VACA1", "TORO2")
    assert sim["apto"] is True
    assert sim["advertencia"] is not None
    assert "TORO2" in sim["advertencia"]


def test_endpoint_pwa(tmp_path):
    ruta = str(tmp_path / "sim_pwa.db")
    d = Database(ruta)
    d.create_tables()
    d.registrar_animal("ABU1", sexo="Macho", estado="ACTIVO")
    d.registrar_animal("ABU2", sexo="Hembra", estado="ACTIVO")
    d.registrar_animal("VACA1", sexo="Hembra", estado="ACTIVO",
                       madre_tag="ABU2", padre_tag="ABU1")
    d.registrar_animal("TORO1", sexo="Macho", estado="ACTIVO",
                       madre_tag="ABU2", padre_tag="ABU1")
    d.close()
    u_path = str(tmp_path / "users_sim.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump([{"user_id": 1, "nombre": "T", "rol": "TRABAJADOR", "pin": "1111"}], f)
    app = crear_app(ruta, users_file=u_path, password="x")
    assert app is not None
    app.config.update({"TESTING": True})

    anon = app.test_client()
    assert anon.get("/api/simular-cruzamiento?vaca=VACA1&toro=TORO1").status_code == 401

    c = app.test_client()
    c.post("/login", data={"pin": "1111"})
    r = c.get("/api/simular-cruzamiento?vaca=VACA1&toro=TORO1")
    assert r.status_code == 200
    sim = r.get_json()
    assert sim["ok"] is True and sim["apto"] is False
    assert "pin" not in json.dumps(sim)

    r2 = c.get("/api/simular-cruzamiento?vaca=VACA1")
    assert r2.status_code == 400

    r3 = c.get("/api/simular-cruzamiento?vaca=VACA1&toro=FANTASMA")
    assert r3.status_code == 200
    assert r3.get_json()["evaluable"] is False


def test_confirmacion_telegram_con_veredicto(db):
    bot = Bot(db)
    ev = ParsedEvent(tipo="servicio", texto="x", animal_tag="VACA1",
                     fecha="2026-09-20",
                     datos={"tipo_servicio": "IA", "toro_pajilla": "TORO1"})
    msg = bot._confirmacion(ev)
    assert "Registrado servicio" in msg
    assert "NO RECOMENDADO" in msg

    ev2 = ParsedEvent(tipo="servicio", texto="x", animal_tag="VACA1",
                      fecha="2026-09-20",
                      datos={"tipo_servicio": "IA", "toro_pajilla": "TORO2"})
    msg2 = bot._confirmacion(ev2)
    assert "APTO" in msg2

    ev3 = ParsedEvent(tipo="servicio", texto="x", animal_tag="VACA1",
                      fecha="2026-09-20",
                      datos={"tipo_servicio": "IA", "toro_pajilla": "PAJUELA-X"})
    msg3 = bot._confirmacion(ev3)
    assert "Consanguinidad" not in msg3
