"""Pausas temporales de ordeño y su efecto en el promedio litros/vaca/día.

Cubre lo agregado para la vista Leche:

1. ``Database.resumen_ordeno`` cuenta vacas en etapa de ordeño (paridas hace
   <300 días y sin secado confirmado), separando las que están en pausa.
2. La pausa temporal (``pausas_ordeno``) es idempotente, no duplica filas y
   se puede reanudar; no toca el secado real (``secados``).
3. El KPI ``litros_por_vaca_dia`` de ``datos_leche`` divide los litros del
   recibo de quincena entre las vacas que se están ordeñando de verdad.
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.database import Database  # noqa: E402
from src.engine.dashboard_data import datos_leche  # noqa: E402
from src.engine.dashboard_data import conteos_tablero  # noqa: E402

# Recibo de quincena de 16 días (mismo seed que test_produccion_leche_recibos):
# total 5.092 L -> promedio diario 318,2 L/día.
DIAS_RECIBO = [
    ("2026-08-16", 350.0), ("2026-08-17", 321.0), ("2026-08-18", 321.0),
    ("2026-08-19", 288.0), ("2026-08-20", 336.0), ("2026-08-21", 290.0),
    ("2026-08-22", 321.0), ("2026-08-23", 330.0), ("2026-08-24", 368.0),
    ("2026-08-25", 310.0), ("2026-08-26", 276.0), ("2026-08-27", 337.0),
    ("2026-08-28", 316.0), ("2026-08-29", 350.0), ("2026-08-30", 280.0),
    ("2026-08-31", 298.0),
]
NOTAS_RECIBO = "Recibo 16 al 31 de Agosto 2026 (16 días)"
PROMEDIO_DIARIO = 318.2


def _vaca_en_ordeno(db, tag, dias_desde_parto=60):
    """Crea (o reutiliza) una vaca ACTIVO con parto reciente y sin secado."""
    db.registrar_parto(
        vaca_tag=tag,
        fecha=(date.today() - timedelta(days=dias_desde_parto)).isoformat(),
    )
    return db.resolve_animal(tag)


def _sembrar_recibo(db):
    for fecha, litros in DIAS_RECIBO:
        db.execute(
            "INSERT INTO produccion_leche (animal_id, fecha, litros, notas) "
            "VALUES (NULL, ?, ?, ?)",
            (fecha, litros, NOTAS_RECIBO),
        )


def test_resumen_ordeno_solo_cuenta_vacas_en_etapa_de_ordeno(db):
    _vaca_en_ordeno(db, "L01", 60)          # cuenta
    _vaca_en_ordeno(db, "L02", 400)         # parto viejo -> seca
    _vaca_en_ordeno(db, "L03", 60)
    db.registrar_secado("L03", fecha=date.today().isoformat())  # secada -> no cuenta
    _vaca_en_ordeno(db, "L04", 60)
    db.execute("UPDATE animales SET estado = 'VENDIDO' WHERE tag = 'L04'")  # no ACTIVO

    assert db.resumen_ordeno() == {"en_ordeno": 1, "en_pausa": 0, "ordenandose": 1}


def test_pausa_idempotente_no_duplica_y_se_reanuda(db):
    _vaca_en_ordeno(db, "P01")

    pid1 = db.registrar_pausa_ordeno("P01", motivo="Ternero flaco")
    pid2 = db.registrar_pausa_ordeno("P01", motivo="segundo intento")
    assert pid1 is not None
    assert pid1 == pid2, "una pausa ya abierta no debe generar una segunda fila"
    assert db.query_one("SELECT COUNT(*) AS n FROM pausas_ordeno")["n"] == 1

    assert db.resumen_ordeno() == {"en_ordeno": 1, "en_pausa": 1, "ordenandose": 0}

    assert db.reanudar_ordeno("P01") is True
    assert db.reanudar_ordeno("P01") is False, "sin pausa abierta no hay nada que cerrar"
    assert db.pausa_ordeno_abierta("P01") is None
    assert db.resumen_ordeno() == {"en_ordeno": 1, "en_pausa": 0, "ordenandose": 1}
    # El histórico de la pausa se conserva (solo se le puso fecha_fin).
    assert db.query_one("SELECT COUNT(*) AS n FROM pausas_ordeno")["n"] == 1
    assert db.query_one("SELECT fecha_fin FROM pausas_ordeno")["fecha_fin"] is not None


def test_pausa_de_vaca_secada_no_infla_el_conteo_de_pausas(db):
    _vaca_en_ordeno(db, "S01")
    db.registrar_secado("S01", fecha=date.today().isoformat())

    db.registrar_pausa_ordeno("S01", motivo="no aplica")

    # La vaca ya no está en etapa de ordeño: la pausa no debe contarse.
    assert db.resumen_ordeno() == {"en_ordeno": 0, "en_pausa": 0, "ordenandose": 0}


def test_pausa_y_reanudar_con_tag_inexistente(db):
    assert db.registrar_pausa_ordeno("NO-EXISTE") is None
    assert db.reanudar_ordeno("NO-EXISTE") is False
    assert db.pausa_ordeno_abierta("NO-EXISTE") is None


def test_litros_por_vaca_dia_divide_entre_vacas_ordenandose(tmp_path):
    db = Database(str(tmp_path / "pausas_ordeno.db"))
    db.create_tables()
    try:
        _sembrar_recibo(db)
        _vaca_en_ordeno(db, "K01")

        res = datos_leche(db)
        assert res["resumen"]["promedio_diario"] == PROMEDIO_DIARIO
        assert res["resumen_ordeno"] == {"en_ordeno": 1, "en_pausa": 0, "ordenandose": 1}
        # 318,2 L/día entre 1 vaca ordeñándose.
        assert res["resumen"]["litros_por_vaca_dia"] == PROMEDIO_DIARIO

        db.registrar_pausa_ordeno("K01", motivo="Ternero flaco")
        res = datos_leche(db)
        assert res["resumen_ordeno"]["ordenandose"] == 0
        # Sin vacas ordeñándose el KPI queda en None (no se inventa un 0).
        assert res["resumen"]["litros_por_vaca_dia"] is None
        assert not (res.get("errores") or {}).get("resumen_ordeno")
    finally:
        db.close()


def test_muerte_de_cria_mantiene_a_la_vaca_en_produccion(db):
    # Vaca en ordeño con una cría a la que se le registra la muerte.
    _vaca_en_ordeno(db, "M01")
    db.registrar_parto(vaca_tag="M01",
                       fecha=(date.today() - timedelta(days=30)).isoformat(),
                       sexo_cria="Hembra", id_cria_tag="M01-C")
    db.registrar_muerte("M01-C", fecha=date.today().isoformat())
    assert db.get_animal("M01-C")["estado"] == "MUERTO"
    # Perder la cría NO la saca de producción: el criterio de "en etapa de
    # ordeño" solo depende del último parto y del secado, no de tener cría viva.
    assert db.resumen_ordeno() == {"en_ordeno": 1, "en_pausa": 0, "ordenandose": 1}


def test_destete_de_cria_no_secara_la_madre(db):
    _vaca_en_ordeno(db, "D01")
    db.registrar_parto(vaca_tag="D01",
                       fecha=(date.today() - timedelta(days=30)).isoformat(),
                       sexo_cria="Macho", id_cria_tag="D01-C")
    db.registrar_destete("D01-C", fecha=date.today().isoformat())
    # Destetar/apartar la cría es independiente del secado: la madre sigue
    # contada como ordeñándose (no se crea ninguna fila en `secados`).
    assert db.query_one("SELECT COUNT(*) AS n FROM secados")["n"] == 0
    assert db.resumen_ordeno() == {"en_ordeno": 1, "en_pausa": 0, "ordenandose": 1}


def test_pausa_y_reanudar_salen_en_eventos_recientes(db):
    _vaca_en_ordeno(db, "E01")
    db.registrar_pausa_ordeno("E01", motivo="Ternero flaco")
    evs = conteos_tablero(db)["eventos_recientes"]
    pa = [e for e in evs if e["tipo"] == "PAUSA_ORDENO"]
    assert pa, "pausar una vaca debe salir en el feed de eventos del Tablero"
    assert pa[0]["tag"] == "E01"
    assert "Pausa de ordeño" in pa[0]["descripcion"]

    db.reanudar_ordeno("E01")
    evs = conteos_tablero(db)["eventos_recientes"]
    re = [e for e in evs if e["tipo"] == "REANUDAR_ORDENO"]
    assert re, "reanudar una vaca debe salir en el feed de eventos"
    assert re[0]["tag"] == "E01"


def test_eliminar_pausa_restaura_ordenandose(db):
    _vaca_en_ordeno(db, "X01")
    pid = db.registrar_pausa_ordeno("X01", motivo="Ternero flaco")
    assert db.resumen_ordeno() == {"en_ordeno": 1, "en_pausa": 1, "ordenandose": 0}

    res = db.eliminar_evento("pausa_ordeno", pid, user_id=1)
    assert res["ok"]
    # Al borrar la pausa, la vaca vuelve a ser ordeñándose.
    assert db.resumen_ordeno() == {"en_ordeno": 1, "en_pausa": 0, "ordenandose": 1}
    assert db.query_one("SELECT COUNT(*) AS n FROM pausas_ordeno")["n"] == 0