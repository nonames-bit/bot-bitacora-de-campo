"""Regresiones de reproducción, alertas push y fusión de chapetas (revisión integral)."""
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.query_engine import QueryEngine

HOY = date(2026, 9, 25)


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "b.db")).create_tables()
    yield d
    d.close()


def _iso(dias_atras: int) -> str:
    return (HOY - timedelta(days=dias_atras)).isoformat()


def _servicio(db, tag, dias_atras, **kw):
    """Servicio con FEP (servicio + 283 días), como lo registra el bot."""
    f = HOY - timedelta(days=dias_atras)
    return db.registrar_servicio(tag, fecha=f.isoformat(),
                                 fep_calculada=(f + timedelta(days=283)).isoformat(), **kw)


def test_palpacion_atrasada_se_lista(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    _servicio(db, "47", 75)  # día 60 fue hace 15 días
    txt = QueryEngine(db, hoy=HOY)._palpacion_pendiente()
    assert "47" in txt and "atrasada 15 días" in txt


def test_eco_dia_35_no_cierra_palpacion(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    _servicio(db, "47", 40)
    db.registrar_diagnostico("47", fecha=_iso(5), resultado="PREÑADA")  # eco día 35
    assert "47" in QueryEngine(db, hoy=HOY)._palpacion_pendiente()
    # Una vacía sí la cierra
    db.registrar_diagnostico("47", fecha=_iso(4), resultado="VACIA")
    assert "47" not in QueryEngine(db, hoy=HOY)._palpacion_pendiente()


def test_palpacion_solo_ultimo_servicio(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    _servicio(db, "47", 200)
    _servicio(db, "47", 10)
    txt = QueryEngine(db, hoy=HOY)._palpacion_pendiente()
    assert txt.count("47") == 1 and "atrasada" not in txt


def test_servicio_fallido_viejo_no_es_parto_atrasado(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    _servicio(db, "47", 630, estado="FALLIDO")
    _servicio(db, "47", 100)  # gestación en curso
    txt = QueryEngine(db, hoy=HOY)._partos_atrasados()
    assert "47" not in txt


def test_vacia_posterior_excluye_de_partos_proximos(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    _servicio(db, "47", 270)  # FEP en 13 días
    qe = QueryEngine(db, hoy=HOY)
    assert "47" in qe._vacas_proximas_parir(30)
    db.registrar_diagnostico("47", fecha=_iso(200), resultado="VACIA")
    assert "47" not in qe._vacas_proximas_parir(30)


def test_push_retiros_y_celos_regla_am_pm(db, monkeypatch):
    import src.db.database as dbmod

    class _Fecha(date):
        @classmethod
        def today(cls):
            return HOY
    monkeypatch.setattr(dbmod, "date", _Fecha)

    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("49", sexo="Hembra", estado="VENDIDO")
    db.registrar_tratamiento("47", fecha=_iso(2), producto="Oxitetraciclina",
                             dias_retiro_carne=28, fecha_fin_retiro_carne=(HOY + timedelta(days=26)).isoformat())
    db.registrar_celo("48", fecha=_iso(1), am_pm="PM")   # ayer PM -> hoy mañana
    db.registrar_celo("47", fecha=_iso(0), am_pm="AM")   # hoy AM -> hoy tarde
    db.registrar_celo("49", fecha=_iso(0), am_pm="AM")   # vendido: no
    db.registrar_celo("48", fecha=_iso(0), am_pm="PM")   # hoy PM -> mañana, no hoy
    alertas = db.alertas_pendientes_push()
    retiro = [a for a in alertas if a["tipo"] == "SANIDAD"]
    assert retiro and "47" in retiro[0]["cuerpo"]
    celos = {a["titulo"]: a["cuerpo"] for a in alertas if a["tipo"] == "REPRO"}
    assert len(celos) == 2
    assert any("48" in t and "mañana" in c for t, c in celos.items())
    assert any("47" in t and "tarde" in c for t, c in celos.items())


def test_fusion_chapeta_con_lote_iatf_y_composicion(db):
    db.registrar_animal("JA83", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("JA88", sexo="Hembra", estado="ACTIVO")
    db.guardar_composicion_racial("JA83", [{"raza": "Gyr", "porcentaje": 100}])
    prot = db.query_one("SELECT id FROM protocolos_iatf LIMIT 1")
    db.crear_lote_iatf("L1", prot["id"], HOY.isoformat(), ["JA83"])
    res = db.rectificar_tag_animal("JA83", "JA88", fusionar_si_existe=True)
    assert res["ok"] is True
    aid = db.animal_id("JA88")
    assert db.query_one("SELECT animal_id, tag FROM lote_iatf_animales")["animal_id"] == aid
    comp = db.obtener_composicion_racial(aid)
    assert [c["raza"] for c in comp] == ["Gyr"]
