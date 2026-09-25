"""Pruebas del parser nativo de DBF y del importador a SQLite."""
import os
import struct

import pytest

from src.importers.dbf_importer import (
    DBFReader, import_animales, import_causas, import_celos, import_dbfs,
    import_destetes, import_fotos, import_leche, import_partos, import_pesajes,
    import_potreros, import_servicios, import_tactos, import_traslados, import_zip,
)


def build_dbf(fields, records):
    """Construye un archivo DBF III mínimo en memoria."""
    nf = len(fields)
    header_len = 32 + 32 * nf + 1
    record_len = 1 + sum(f[2] for f in fields)
    out = bytearray()
    out += bytes([0x03, 0x52, 0x08, 0x18])  # versión + fecha (irrelevante)
    out += struct.pack("<I", len(records))
    out += struct.pack("<H", header_len)
    out += struct.pack("<H", record_len)
    out += b"\x00" * 20
    for (name, ftype, flen, fdec) in fields:
        out += name.encode("ascii").ljust(11, b"\x00")
        out += ftype.encode("ascii")
        out += b"\x00" * 4
        out += bytes([flen, fdec])
        out += b"\x00" * 14
    out += b"\x0d"
    for rec in records:
        out += b"\x20"  # registro activo
        for (name, ftype, flen, fdec), val in zip(fields, rec):
            if ftype == "N":
                # Datos en latin-1 (convención DBF), igual que decodifica DBFReader.
                out += str(val).encode("latin-1").rjust(flen, b" ")
            elif ftype == "T":
                # Campo DateTime (8 bytes): día juliano + milisegundos.
                if isinstance(val, tuple):
                    out += struct.pack("<II", val[0], val[1])
                else:
                    out += val
            else:
                out += str(val).encode("latin-1").ljust(flen, b" ")
    return bytes(out)


# ---------------------------------------------------------------------------
# Parser nativo DBF
# ---------------------------------------------------------------------------
def test_dbf_reader_campos_y_registros():
    data = build_dbf(
        [("CODANI", "C", 5, 0), ("FECHA", "D", 8, 0), ("PESO", "N", 6, 2)],
        [("47", "20260815", "420.50"), ("48", "20260816", "350")],
    )
    reader = DBFReader(data)
    assert reader.field_names == ["CODANI", "FECHA", "PESO"]
    recs = list(reader.records())
    assert len(recs) == 2
    assert recs[0]["CODANI"] == "47"
    assert recs[0]["FECHA"] == "2026-08-15"
    assert recs[0]["PESO"] == 420.5
    assert recs[1]["PESO"] == 350.0


def test_dbf_datetime_julian():
    """Campo ``T`` (DateTime VFP): día juliano astronómico a fecha ISO."""
    from datetime import date
    jd = date(2000, 1, 1).toordinal() + 1721425  # 2451545 == 2000-01-01
    assert jd == 2451545
    data = build_dbf(
        [("DTCREA", "T", 8, 0)],
        [((jd, 0),)],
    )
    reader = DBFReader(data)
    recs = list(reader.records())
    assert len(recs) == 1
    assert recs[0]["DTCREA"] == "2000-01-01"


# ---------------------------------------------------------------------------
# Mapeo de tablas (registros sintéticos como dicts)
# ---------------------------------------------------------------------------
def test_import_causas(db):
    causas = import_causas(db, [{"CODIGO": "19", "DESC": "ACCIDENTE", "TIPO": "D"}])
    assert causas == {"19": "ACCIDENTE"}


def test_import_potreros(db):
    res = import_potreros(db, [{"CODPOT": "01", "NOMPOT": "Norte", "HAS": 10.0,
                                "KGHA": 5000.0, "PASTO1": "", "TIPO": "L",
                                "FEC_ENT": "2026-01-01", "FEC_SAL": None, "DIA_OCU": 30}])
    assert res == {"nuevos": 1, "duplicados": 0}
    pot = db.query_one("SELECT * FROM potreros WHERE codigo = '01'")
    assert pot is not None
    assert pot["area_has"] == 10.0
    assert pot["aforo_kg_m2"] == pytest.approx(0.5)
    # 2ª Ley de Voisin: DIA_OCU es ocupación (no reposo).
    assert pot["dias_ocupacion"] == 30
    # 1ª Ley de Voisin: sin fecha de salida no hay reposo acumulado.
    assert pot["dias_reposo"] is None


def test_import_animales_y_muertes(db):
    causas = {"19": "ACCIDENTE"}
    conteos = import_animales(db, [
        {"CODANI": "47", "NOMANI": "Mariposa", "SEXO": "H", "TIPORAZA": "T",
         "FECNACE": "20200101", "CODPOT": "01", "ESTADO": "1", "OBS": "",
         "MADRE": "", "PADRE": "", "TIPO": "M", "FECMUERTE": "20260507",
         "CAU": "19", "MOTIVO": "se rodo"},
    ], causas)
    assert conteos["animales"] == {"nuevos": 1, "duplicados": 0, "ventas_registradas": 0, "ventas_fecha_aproximada": 0, "traslados_detectados": 0}
    assert conteos["muertes"] == {"nuevos": 1, "duplicados": 0}
    animal = db.get_animal("47")
    assert animal["sexo"] == "Hembra"
    muerte = db.query_one("SELECT * FROM muertes")
    assert muerte["causa_presunta"] == "ACCIDENTE"


def test_import_animales_detecta_cambio_potrero_sin_traslado_dbf(db):
    """hoja.dbf trae solo el potrero ACTUAL del animal (sin historial): si
    cambió respecto a la importación previa y no vino explicado por un
    traslado.dbf (import_traslados, probado aparte), igual debe quedar un
    registro en `traslados` para que aparezca en "Últimos Eventos" del
    Tablero -- sin esto, Inventario/Mapa (que leen animales.potrero_id
    directo) muestran el cambio pero el feed de eventos queda mudo."""
    causas = {}
    # registrar_animal() no crea el potrero al vuelo (resolve_potrero sin
    # crear=True) -- en producción potrero.dbf siempre se importa antes que
    # hoja.dbf (ver DBF_REQUERIDOS / import_dbfs), así que el potrero ya
    # existe cuando llega este cambio.
    db.registrar_potrero(nombre="A01", codigo="A01")
    db.registrar_potrero(nombre="B02", codigo="B02")
    base = {"NOMANI": "Mariposa", "SEXO": "H", "TIPORAZA": "T", "FECNACE": "20200101",
            "ESTADO": "1", "OBS": "", "MADRE": "", "PADRE": "", "TIPO": "",
            "FECMUERTE": "", "CAU": "", "MOTIVO": ""}
    # Primera importación: potrero A01 (nomenclatura activa, no legacy numérico).
    conteos1 = import_animales(db, [{**base, "CODANI": "47", "CODPOT": "A01"}], causas)
    assert conteos1["animales"]["traslados_detectados"] == 0
    assert db.query(("SELECT * FROM traslados")) == []

    # Segunda importación (otro backup): SG ya muestra a la 47 en B02, sin
    # que nadie haya usado la pantalla de Traslados en SG.
    conteos2 = import_animales(db, [{**base, "CODANI": "47", "CODPOT": "B02"}], causas)
    assert conteos2["animales"]["traslados_detectados"] == 1
    traslado = db.query_one("SELECT * FROM traslados WHERE animal_id = (SELECT id_animal FROM animales WHERE tag = '47')")
    assert traslado is not None
    assert traslado["motivo"] == "Detectado en import SG (cambio de potrero en hoja.dbf)"
    pot_origen = db.get_potrero(traslado["potrero_origen"])
    pot_destino = db.get_potrero(traslado["potrero_destino"])
    assert pot_origen["codigo"] == "A01"
    assert pot_destino["codigo"] == "B02"
    # animales.potrero_id (lo que leen Inventario/Mapa) también queda al día.
    assert db.get_animal("47")["potrero_id"] == traslado["potrero_destino"]

    # Tercera importación con el MISMO potrero: no debe generar un traslado
    # duplicado por cada backup diario mientras el animal no se mueva.
    conteos3 = import_animales(db, [{**base, "CODANI": "47", "CODPOT": "B02"}], causas)
    assert conteos3["animales"]["traslados_detectados"] == 0
    assert db.count("traslados") == 1


def test_import_animales_estado_desde_tipo(db):
    """El campo TIPO de SG determina el estado del animal (no ESTADO)."""
    base = {"NOMANI": "", "SEXO": "H", "TIPORAZA": "T", "FECNACE": "20200101",
            "CODPOT": "", "ESTADO": "", "OBS": "", "MADRE": "", "PADRE": "",
            "FECMUERTE": "", "CAU": "", "MOTIVO": ""}
    registros = [
        {**base, "CODANI": "1", "TIPO": "V"},
        {**base, "CODANI": "2", "TIPO": "M"},
        {**base, "CODANI": "3", "TIPO": "T"},
        {**base, "CODANI": "4", "TIPO": "O"},
        {**base, "CODANI": "5", "TIPO": ""},
        {**base, "CODANI": "6", "TIPO": "x"},  # desconocido -> ACTIVO
    ]
    import_animales(db, registros, {})
    esperados = {"1": "VENDIDO", "2": "MUERTO", "3": "TRASLADADO",
                 "4": "OTRO", "5": "ACTIVO", "6": "ACTIVO"}
    for tag, estado in esperados.items():
        assert db.get_animal(tag)["estado"] == estado, f"tag {tag}"


def test_import_venta_sin_fecha_crea_movimiento_aproximado(db):
    """SG marca TIPO='V' sin ninguna fecha de venta en el respaldo -- sin un
    evento fechado, la venta queda invisible para el tablero de "Últimos
    Eventos" y para cualquier reporte por periodo. El importador debe crear
    un movimiento VENTA usando la fecha de la importación como aproximación."""
    base = {"NOMANI": "", "SEXO": "H", "TIPORAZA": "T", "FECNACE": "20200101",
            "CODPOT": "", "ESTADO": "", "OBS": "", "MADRE": "", "PADRE": "",
            "FECMUERTE": "", "VENDIDOA": "", "VALOR": None, "CAU": "", "MOTIVO": ""}
    conteos = import_animales(db, [{**base, "CODANI": "V089", "TIPO": "V"}], {})
    assert conteos["animales"]["ventas_registradas"] == 1
    assert conteos["animales"]["ventas_fecha_aproximada"] == 1

    mov = db.query_one(
        "SELECT m.* FROM movimientos m JOIN animales a ON a.id_animal = m.animal_id WHERE a.tag = 'V089'"
    )
    assert mov is not None
    assert mov["tipo_movimiento"] == "VENTA"
    assert mov["fecha"] is not None
    assert "aproximada" in (mov["notas"] or "").lower()

    # Reimportar el mismo backup no debe duplicar el movimiento de venta.
    conteos2 = import_animales(db, [{**base, "CODANI": "V089", "TIPO": "V"}], {})
    assert conteos2["animales"]["ventas_registradas"] == 0
    n_ventas = db.query_one(
        "SELECT COUNT(*) AS n FROM movimientos m JOIN animales a ON a.id_animal = m.animal_id "
        "WHERE a.tag = 'V089' AND UPPER(m.tipo_movimiento) = 'VENTA'"
    )
    assert n_ventas["n"] == 1


def test_import_venta_con_fecmuerte_usa_fecha_real_de_sg(db):
    """FECMUERTE es, pese al nombre, el campo genérico de "fecha de baja" que
    SG llena también para TIPO='V' -- confirmado en un respaldo real (el
    informe de indicadores de ventas de SG agrupa por esa fecha). Si viene
    poblado, debe usarse tal cual (fecha real), no la fecha de importación."""
    base = {"NOMANI": "", "SEXO": "H", "TIPORAZA": "T", "FECNACE": "20200101",
            "CODPOT": "", "ESTADO": "", "OBS": "", "MADRE": "", "PADRE": "",
            "CAU": "", "MOTIVO": ""}
    conteos = import_animales(db, [
        {**base, "CODANI": "V090", "TIPO": "V", "FECMUERTE": "20260903",
         "VENDIDOA": "Frigorifico X", "VALOR": 1500000.0},
    ], {})
    assert conteos["animales"]["ventas_registradas"] == 1
    assert conteos["animales"]["ventas_fecha_aproximada"] == 0

    mov = db.query_one(
        "SELECT m.* FROM movimientos m JOIN animales a ON a.id_animal = m.animal_id WHERE a.tag = 'V090'"
    )
    assert mov is not None
    assert mov["fecha"] == "2026-09-03"
    assert mov["procedencia_destino"] == "Frigorifico X"
    assert mov["precio"] == 1500000.0
    assert "aproximada" not in (mov["notas"] or "").lower()


def test_import_venta_backfills_movimiento_si_animal_ya_era_vendido_en_db(db):
    """Si el animal ya existía en la DB con estado='VENDIDO' (por ejemplo de
    un respaldo viejo o importación previa sin módulo de movimientos), la
    reimportación debe completar el registro en la tabla movimientos."""
    base = {"NOMANI": "", "SEXO": "H", "TIPORAZA": "T", "FECNACE": "20200101",
            "CODPOT": "", "ESTADO": "", "OBS": "", "MADRE": "", "PADRE": "",
            "CAU": "", "MOTIVO": ""}
    # Simular estado previo: animal ya registrado en la DB como VENDIDO pero sin fila en movimientos
    db.registrar_animal(tag="A100", estado="VENDIDO")
    assert db.query_one("SELECT COUNT(*) AS n FROM movimientos")["n"] == 0

    conteos = import_animales(db, [
        {**base, "CODANI": "A100", "TIPO": "V", "FECMUERTE": "20260905",
         "VENDIDOA": "Comprador Y", "VALOR": 2000000.0},
    ], {})
    assert conteos["animales"]["ventas_registradas"] == 1

    mov = db.query_one(
        "SELECT m.* FROM movimientos m JOIN animales a ON a.id_animal = m.animal_id WHERE a.tag = 'A100'"
    )
    assert mov is not None
    assert mov["fecha"] == "2026-09-05"
    assert mov["procedencia_destino"] == "Comprador Y"
    assert mov["precio"] == 2000000.0


def test_import_muerte_sin_fecmuerte_crea_muerte_aproximada(db):
    """Igual que con ventas: TIPO='M' sin FECMUERTE debe dejar un evento
    fechado (aproximado) en vez de solo cambiar animales.estado."""
    base = {"NOMANI": "", "SEXO": "H", "TIPORAZA": "T", "FECNACE": "20200101",
            "CODPOT": "", "ESTADO": "", "OBS": "", "MADRE": "", "PADRE": "",
            "FECMUERTE": "", "CAU": "19", "MOTIVO": "se rodo"}
    causas = {"19": "ACCIDENTE"}
    conteos = import_animales(db, [{**base, "CODANI": "M001", "TIPO": "M"}], causas)
    assert conteos["muertes"] == {"nuevos": 1, "duplicados": 0}

    muerte = db.query_one(
        "SELECT mu.* FROM muertes mu JOIN animales a ON a.id_animal = mu.animal_id WHERE a.tag = 'M001'"
    )
    assert muerte is not None
    assert muerte["fecha"] is not None
    assert muerte["causa_presunta"] == "ACCIDENTE"
    assert "aproximada" in (muerte["notas"] or "").lower()

    # Reimportar no debe duplicar la muerte.
    conteos2 = import_animales(db, [{**base, "CODANI": "M001", "TIPO": "M"}], causas)
    assert conteos2["muertes"] == {"nuevos": 0, "duplicados": 1}


def test_import_partos(db):
    res = import_partos(db, [{"CODANI": "47", "FECHA": "2026-05-01", "CRIA": "M",
                              "ABORTO": "", "PESNAC": 35.0, "HIJO": "480", "DETALLE": ""}])
    assert res == {"nuevos": 1, "duplicados": 0}
    parto = db.query_one("SELECT * FROM partos")
    assert parto["sexo_cria"] == "Macho"
    assert parto["estado_cria"] == "VIVO"
    assert db.get_animal("480") is not None


def test_import_partos_ignora_autorreferencia_corrupta(db):
    # Caso donde el DBF corrupto tiene CODANI == HIJO (vaca_tag == cria_tag)
    res = import_partos(db, [{"CODANI": "V009", "FECHA": "2026-03-02", "CRIA": "M",
                              "ABORTO": "", "PESNAC": 33.0, "HIJO": "V009", "DETALLE": "corrupto"}])
    assert res == {"nuevos": 0, "duplicados": 0}
    assert db.count("partos") == 0


def test_import_partos_mismo_dia_con_y_sin_cria_no_colisionan(db):
    # 1. Parto con cría
    r1 = [{"CODANI": "47", "FECHA": "2026-05-01", "CRIA": "M",
           "ABORTO": "", "PESNAC": 35.0, "HIJO": "480", "DETALLE": "con cria"}]
    res1 = import_partos(db, r1)
    assert res1 == {"nuevos": 1, "duplicados": 0}

    # 2. Parto mismo día sin cría (no debe colisionar con el anterior)
    r2 = [{"CODANI": "47", "FECHA": "2026-05-01", "CRIA": "",
           "ABORTO": "S", "PESNAC": 0, "HIJO": "", "DETALLE": "sin cria"}]
    res2 = import_partos(db, r2)
    assert res2 == {"nuevos": 1, "duplicados": 0}

    assert db.count("partos") == 2

    # 3. Re-importar ambos debe dar 0 nuevos y 2 duplicados
    res3 = import_partos(db, r1 + r2)
    assert res3 == {"nuevos": 0, "duplicados": 2}


def test_import_partos_completa_cria_de_parto_huerfano(db):
    """El bot registra el parto sin cría (aún no tiene chapeta); cuando SG
    trae el mismo parto ya con cría, se completa el registro existente en
    vez de duplicarlo -- una vaca no puede parir dos veces el mismo día."""
    db.registrar_animal(tag="A090", sexo="Hembra")
    id_parto_bot = db.registrar_parto(vaca_tag="A090", fecha="2026-08-01", sexo_cria="Hembra")
    assert db.count("partos") == 1

    res = import_partos(db, [
        {"CODANI": "A090", "FECHA": "2026-08-01", "CRIA": "H",
         "ABORTO": "", "PESNAC": 32.0, "HIJO": "A090-6", "DETALLE": ""},
    ])
    assert res == {"nuevos": 0, "duplicados": 1}
    assert db.count("partos") == 1

    parto = db.query_one("SELECT * FROM partos WHERE id = ?", (id_parto_bot,))
    assert parto["peso_nacimiento"] == 32.0
    cria = db.get_animal("A090-6")
    assert cria is not None
    assert cria["madre_id"] == db.animal_id("A090")


def test_import_partos_no_completa_si_hay_ambiguedad_de_huerfanos(db):
    """Si hay más de un parto huérfano (sin cría) de la misma vaca el mismo
    día -- caso raro pero posible con datos sucios -- no arriesga a
    completar el equivocado: crea el parto nuevo con cría."""
    db.registrar_animal(tag="A090", sexo="Hembra")
    # Estado sucio preexistente (anterior a la idempotencia de
    # registrar_parto): se inserta directo para simular dos huérfanos del
    # mismo día, ya que la API hoy no duplicaría el segundo.
    vaca_id = db.animal_id("A090")
    db.insert("partos", dict(vaca_id=vaca_id, fecha="2026-08-01", tipo_evento="PARTO",
                             notas="huerfano 1", creado_en="2026-08-01T00:00:00"))
    db.insert("partos", dict(vaca_id=vaca_id, fecha="2026-08-01", tipo_evento="PARTO",
                             notas="huerfano 2", creado_en="2026-08-01T00:00:00"))
    assert db.count("partos") == 2

    res = import_partos(db, [
        {"CODANI": "A090", "FECHA": "2026-08-01", "CRIA": "H",
         "ABORTO": "", "PESNAC": 32.0, "HIJO": "A090-6", "DETALLE": ""},
    ])
    assert res == {"nuevos": 1, "duplicados": 0}
    assert db.count("partos") == 3


def test_import_animales_preserva_madre_padre_existentes(db):
    db.registrar_animal(tag="100", sexo="Hembra")
    db.registrar_animal(tag="200", sexo="Macho")
    db.registrar_animal(tag="101", sexo="Hembra")
    db.registrar_animal(tag="201", sexo="Macho")
    db.registrar_animal(tag="50", sexo="Hembra")

    id_50 = db.animal_id("50")
    id_100 = db.animal_id("100")
    id_200 = db.animal_id("200")
    db.execute("UPDATE animales SET madre_id = ?, padre_id = ? WHERE id_animal = ?", (id_100, id_200, id_50))

    import_animales(db, [
        {"CODANI": "50", "NOMANI": "Vaca 50", "SEXO": "H", "TIPORAZA": "T",
         "FECNACE": "20200101", "CODPOT": "01", "ESTADO": "1", "OBS": "",
         "MADRE": "101", "PADRE": "201", "TIPO": "", "FECMUERTE": "",
         "CAU": "", "MOTIVO": ""},
    ], {})

    ani = db.query_one("SELECT madre_id, padre_id FROM animales WHERE tag = '50'")
    assert ani["madre_id"] == id_100
    assert ani["padre_id"] == id_200


def test_import_servicios(db):
    res = import_servicios(db, [{"CODANI": "47", "FECHA": "2026-08-15", "TIPO": "IA",
                                 "TORO": "502", "INSEMINA": "01", "EST": ""}])
    assert res == {"nuevos": 1, "duplicados": 0}
    s = db.query_one("SELECT * FROM servicios")
    assert s["tipo_servicio"] == "IA"
    assert s["toro_pajilla"] == "502"
    assert s["fep_calculada"] == "2027-05-25"


def test_import_pesajes_con_gmd(db):
    res = import_pesajes(db, [
        {"CODANI": "12", "FECHA": "2026-01-01", "PESO": 350.0, "EVENTO": "Control"},
        {"CODANI": "12", "FECHA": "2026-03-11", "PESO": 420.0, "EVENTO": "Control"},
    ])
    assert res == {"nuevos": 2, "duplicados": 0}
    pesajes = db.query("SELECT * FROM pesajes ORDER BY fecha")
    assert len(pesajes) == 2
    assert pesajes[1]["gmd_calculada"] == pytest.approx(70.0 / 69.0, rel=1e-3)


def test_import_celos(db):
    res = import_celos(db, [{"CODANI": "47", "FECHA": "2026-03-01",
                             "HORA": "09:00:00 AM", "DETALLE": ""}])
    assert res == {"nuevos": 1, "duplicados": 0}
    celo = db.query_one("SELECT * FROM celos")
    assert celo["am_pm"] == "AM"


def test_import_traslados(db):
    res = import_traslados(db, [{"CODANI": "47", "FECHA": "2026-06-01", "TIPMOV": "S",
                                 "CODPOT": "01", "LOTE": "2", "REGISTROTR": ""}])
    assert res == {"nuevos": 1, "duplicados": 0}
    tr = db.query_one("SELECT * FROM traslados")
    assert tr["lote"] == "2"


def test_import_destetes_resuelve_cria_activa_de_la_vaca(db):
    """destete.dbf de SG trae CODANI = la VACA (no la cría, no hay campo de
    arete de cría) -- el importador debe resolver la cría activa sin
    destetar de esa vaca vía cria_activa_de_madre()."""
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("47", fecha="2026-01-01", sexo_cria="Hembra", id_cria_tag="47-1")

    res = import_destetes(db, [
        {"CODANI": "47", "FECHA": "2026-07-01", "MOTIVO": "Secado programado",
         "DETALLE": "", "CODPOT": "VS"},
    ])
    assert res == {"nuevos": 1, "duplicados": 0, "sin_cria": 0}

    fila = db.query_one(
        "SELECT d.*, a.tag FROM destetes d JOIN animales a ON a.id_animal = d.animal_id"
    )
    assert fila["tag"] == "47-1"
    assert fila["notas"] == "Secado programado"


def test_import_destetes_sin_cria_activa_se_cuenta_aparte(db):
    """Vaca sin ningún parto/cría activa importada: no se pierde en
    silencio, se cuenta en 'sin_cria' para revisión manual."""
    db.registrar_animal("99", sexo="Hembra", estado="ACTIVO")
    res = import_destetes(db, [
        {"CODANI": "99", "FECHA": "2026-07-01", "MOTIVO": "", "DETALLE": "", "CODPOT": ""},
    ])
    assert res == {"nuevos": 0, "duplicados": 0, "sin_cria": 1}
    assert db.count("destetes") == 0


def test_import_destetes_es_idempotente(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("47", fecha="2026-01-01", sexo_cria="Hembra", id_cria_tag="47-1")
    r = [{"CODANI": "47", "FECHA": "2026-07-01", "MOTIVO": "", "DETALLE": "", "CODPOT": ""}]
    import_destetes(db, r)
    res2 = import_destetes(db, r)
    assert res2 == {"nuevos": 0, "duplicados": 1, "sin_cria": 0}
    assert db.count("destetes") == 1


def test_import_tactos_prenada_calcula_dias_gestacion(db):
    res = import_tactos(db, [
        {"CODANI": "47", "FECHA": "2026-08-27", "ESTADO": "P",
         "PRENEZ": "2026-07-17", "DETALLE": ""},
    ])
    assert res == {"nuevos": 1, "duplicados": 0}
    diag = db.query_one("SELECT * FROM diagnosticos_gestacion")
    assert diag["resultado"] == "PREÑADA"
    assert diag["dias_gestacion"] == 41


def test_import_tactos_negativa_y_repite_son_vacia(db):
    res = import_tactos(db, [
        {"CODANI": "47", "FECHA": "2026-08-01", "ESTADO": "N", "PRENEZ": None, "DETALLE": ""},
        {"CODANI": "48", "FECHA": "2026-08-01", "ESTADO": "R", "PRENEZ": None, "DETALLE": ""},
    ])
    assert res == {"nuevos": 2, "duplicados": 0}
    resultados = {d["resultado"] for d in db.query("SELECT resultado FROM diagnosticos_gestacion")}
    assert resultados == {"VACIA"}


def test_import_tactos_es_idempotente(db):
    r = [{"CODANI": "47", "FECHA": "2026-08-27", "ESTADO": "P", "PRENEZ": "2026-07-17", "DETALLE": ""}]
    import_tactos(db, r)
    res2 = import_tactos(db, r)
    assert res2 == {"nuevos": 0, "duplicados": 1}
    assert db.count("diagnosticos_gestacion") == 1


def test_import_leche_suma_am_pm(db):
    res = import_leche(db, [
        {"CODANI": "47", "FECHA": "2026-08-01", "AM": 6.0, "PM": 4.5},
    ])
    assert res == {"nuevos": 1, "duplicados": 0}
    control = db.query_one("SELECT * FROM produccion_leche")
    assert control["litros"] == 10.5


def test_import_leche_ignora_filas_sin_muestra(db):
    res = import_leche(db, [
        {"CODANI": "47", "FECHA": "2026-08-01", "AM": 0.0, "PM": 0.0},
    ])
    assert res == {"nuevos": 0, "duplicados": 0}
    assert db.count("produccion_leche") == 0


def test_import_leche_es_idempotente(db):
    r = [{"CODANI": "47", "FECHA": "2026-08-01", "AM": 6.0, "PM": 0.0}]
    import_leche(db, r)
    res2 = import_leche(db, r)
    assert res2 == {"nuevos": 0, "duplicados": 1}
    assert db.count("produccion_leche") == 1


def test_import_doble_deduplicacion_completa(db):
    """Importar dos veces el mismo set de DBFs debe dar en la 2da pasada 0 nuevos y todo duplicados."""
    causas_dbf = build_dbf(
        [("CODIGO", "C", 5, 0), ("DESC", "C", 30, 0)],
        [("19", "ACCIDENTE")],
    )
    potrero_dbf = build_dbf(
        [("CODPOT", "C", 5, 0), ("NOMPOT", "C", 20, 0), ("HAS", "N", 6, 2), ("KGHA", "N", 8, 2),
         ("PASTO1", "C", 10, 0), ("TIPO", "C", 5, 0), ("FEC_ENT", "D", 8, 0), ("FEC_SAL", "D", 8, 0), ("DIA_OCU", "N", 4, 0)],
        [("01", "Norte", 10.0, 5000.0, "Brachiaria", "L", "20260101", "", 30)],
    )
    hoja_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("NOMANI", "C", 20, 0), ("SEXO", "C", 1, 0), ("TIPORAZA", "C", 10, 0),
         ("FECNACE", "D", 8, 0), ("CODPOT", "C", 5, 0), ("ESTADO", "C", 5, 0), ("OBS", "C", 30, 0),
         ("MADRE", "C", 10, 0), ("PADRE", "C", 10, 0), ("TIPO", "C", 1, 0), ("FECMUERTE", "D", 8, 0),
         ("CAU", "C", 5, 0), ("MOTIVO", "C", 30, 0)],
        [("47", "Mariposa", "H", "Cebú", "20200101", "01", "1", "", "", "", "M", "20260507", "19", "accidente")],
    )
    partos_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("FECHA", "D", 8, 0), ("CRIA", "C", 1, 0),
         ("ABORTO", "C", 1, 0), ("PESNAC", "N", 6, 2), ("HIJO", "C", 10, 0), ("DETALLE", "C", 30, 0)],
        [("47", "20260501", "M", "", 35.0, "480", "parto normal")],
    )
    celos_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("FECHA", "D", 8, 0), ("HORA", "C", 15, 0), ("DETALLE", "C", 30, 0)],
        [("47", "20260301", "09:00:00 AM", "celo detectado")],
    )
    iamn_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("FECHA", "D", 8, 0), ("TIPO", "C", 2, 0),
         ("TORO", "C", 10, 0), ("INSEMINA", "C", 10, 0), ("EST", "C", 5, 0)],
        [("47", "20260815", "IA", "502", "01", "")],
    )
    pesos_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("FECHA", "D", 8, 0), ("PESO", "N", 6, 2), ("EVENTO", "C", 20, 0)],
        [("47", "20260101", 350.0, "Control"), ("47", "20260311", 420.0, "Control")],
    )
    traslado_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("FECHA", "D", 8, 0), ("TIPMOV", "C", 1, 0),
         ("CODPOT", "C", 5, 0), ("LOTE", "C", 5, 0), ("REGISTROTR", "C", 30, 0)],
        [("47", "20260601", "S", "01", "2", "rotacion")],
    )

    dbf_data = {
        "causas.dbf": causas_dbf,
        "potrero.dbf": potrero_dbf,
        "hoja.dbf": hoja_dbf,
        "partos.dbf": partos_dbf,
        "celos.dbf": celos_dbf,
        "iamn.dbf": iamn_dbf,
        "pesos.dbf": pesos_dbf,
        "traslado.dbf": traslado_dbf,
    }

    # Primera pasada: todo nuevo
    p1 = import_dbfs(db, dbf_data)
    for tabla, res in p1.items():
        assert res["nuevos"] > 0, f"Tabla {tabla} no insertó registros nuevos en pasada 1"
        assert res["duplicados"] == 0, f"Tabla {tabla} reportó duplicados en pasada 1"

    conteo_animales_p1 = db.count("animales")
    conteo_partos_p1 = db.count("partos")
    conteo_celos_p1 = db.count("celos")
    conteo_servicios_p1 = db.count("servicios")
    conteo_pesajes_p1 = db.count("pesajes")
    conteo_traslados_p1 = db.count("traslados")
    conteo_muertes_p1 = db.count("muertes")
    conteo_potreros_p1 = db.count("potreros")

    # Segunda pasada: todo duplicado, cero filas nuevas
    p2 = import_dbfs(db, dbf_data)
    for tabla, res in p2.items():
        assert res["nuevos"] == 0, f"Tabla {tabla} insertó filas nuevas en pasada 2"
        assert res["duplicados"] > 0, f"Tabla {tabla} no contó duplicados en pasada 2"

    # Los conteos en base de datos deben ser exactamente iguales
    assert db.count("animales") == conteo_animales_p1
    assert db.count("partos") == conteo_partos_p1
    assert db.count("celos") == conteo_celos_p1
    assert db.count("servicios") == conteo_servicios_p1
    assert db.count("pesajes") == conteo_pesajes_p1
    assert db.count("traslados") == conteo_traslados_p1
    assert db.count("muertes") == conteo_muertes_p1
    assert db.count("potreros") == conteo_potreros_p1


# ---------------------------------------------------------------------------
# Importación del Zip real (se omite si el archivo no está presente)
# ---------------------------------------------------------------------------
def test_import_zip_real(db):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zip_path = os.path.join(root, "docs", "Datos20260823.Zip")
    if not os.path.exists(zip_path):
        pytest.skip("Archivo de datos DBF no disponible")
    conteos = import_zip(db, zip_path)
    assert db.count("animales") > 0
    assert db.count("partos") > 0
    assert "animales" in conteos
    assert conteos["animales"]["nuevos"] > 0

    conteo_partos_p1 = db.count("partos")
    conteo_diag_p1 = db.count("diagnosticos_gestacion")
    conteo_leche_p1 = db.count("produccion_leche")

    # Segunda pasada sobre el mismo archivo zip: cero nuevos
    conteos2 = import_zip(db, zip_path)
    assert conteos2["animales"]["nuevos"] == 0
    assert conteos2["animales"]["duplicados"] > 0

    # tactos.dbf / leche.dbf (si el zip los trae) también deben quedar
    # estables en la segunda pasada -- ninguna fila nueva, todo duplicado.
    if "diagnosticos_gestacion" in conteos2:
        assert conteos2["diagnosticos_gestacion"]["nuevos"] == 0
    if "produccion_leche" in conteos2:
        assert conteos2["produccion_leche"]["nuevos"] == 0
    assert db.count("partos") == conteo_partos_p1
    assert db.count("diagnosticos_gestacion") == conteo_diag_p1
    assert db.count("produccion_leche") == conteo_leche_p1


def test_import_zip_registra_en_import_sg_historial(db):
    # Regresión real: no había forma de saber si el bot estaba usando el
    # backup de hoy sin adivinar por la fecha de modificación del archivo
    # .db. import_zip() debe dejar un registro consultable por /sistema
    # cada vez que se importa un backup (manual o por el vigilante).
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zip_path = os.path.join(root, "docs", "Datos20260823.Zip")
    if not os.path.exists(zip_path):
        pytest.skip("Archivo de datos DBF no disponible")

    assert db.ultimo_import_sg() is None
    import_zip(db, zip_path)
    ultimo = db.ultimo_import_sg()
    assert ultimo is not None
    assert ultimo["archivo"] == "Datos20260823.Zip"
    assert ultimo["nuevos"] > 0
    assert ultimo["fecha_iso"] is not None


def test_import_fotos_directo_e_idempotente(db, tmp_path):
    import io
    import zipfile

    # Crear ZIP en memoria con fotos simuladas
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a001.jpg", b"fake_jpg_content_1")
        zf.writestr("4145-8.jpg", b"fake_jpg_content_2")
        zf.writestr("subfolder/c99.png", b"fake_png_content_3")
        zf.writestr("ignore.txt", b"not_an_image")
    fotos_zip_bytes = buf.getvalue()

    media_dir = str(tmp_path / "media_test")

    # Primera pasada: 3 fotos nuevas (a001, 4145-8, c99)
    res1 = import_fotos(db, fotos_zip_bytes, media_dir=media_dir)
    assert res1["nuevos"] == 3
    assert res1["duplicados"] == 0
    assert db.count("fotos") == 3

    # Verificar que los archivos existen en disco
    assert os.path.exists(os.path.join(media_dir, "a001.jpg"))
    assert os.path.exists(os.path.join(media_dir, "4145-8.jpg"))
    assert os.path.exists(os.path.join(media_dir, "c99.png"))

    # Verificar tags derivados
    f_a001 = db.query_one("SELECT * FROM fotos WHERE tag = 'a001'")
    assert f_a001 is not None
    assert "a001.jpg" in f_a001["ruta"]

    f_4145 = db.query_one("SELECT * FROM fotos WHERE tag = '4145-8'")
    assert f_4145 is not None
    assert "4145-8.jpg" in f_4145["ruta"]

    # Segunda pasada: 0 nuevos, 3 duplicados
    res2 = import_fotos(db, fotos_zip_bytes, media_dir=media_dir)
    assert res2["nuevos"] == 0
    assert res2["duplicados"] == 3
    assert db.count("fotos") == 3


def test_import_outer_zip_con_fotos_zip(db, tmp_path):
    import io
    import zipfile

    # 1. Crear Dbf.zip interno
    causas_dbf = build_dbf(
        [("CODIGO", "C", 5, 0), ("DESC", "C", 30, 0)],
        [("19", "ACCIDENTE")],
    )
    hoja_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("NOMANI", "C", 20, 0), ("SEXO", "C", 1, 0), ("TIPORAZA", "C", 10, 0),
         ("FECNACE", "D", 8, 0), ("CODPOT", "C", 5, 0), ("ESTADO", "C", 5, 0), ("OBS", "C", 30, 0),
         ("MADRE", "C", 10, 0), ("PADRE", "C", 10, 0), ("TIPO", "C", 1, 0), ("FECMUERTE", "D", 8, 0),
         ("CAU", "C", 5, 0), ("MOTIVO", "C", 30, 0)],
        [("A001", "Vaca A001", "H", "Brahman", "20200101", "", "1", "", "", "", "", "", "", "")],
    )
    buf_dbf = io.BytesIO()
    with zipfile.ZipFile(buf_dbf, "w") as z_dbf:
        z_dbf.writestr("causas.dbf", causas_dbf)
        z_dbf.writestr("hoja.dbf", hoja_dbf)

    # 2. Crear Fotos.Zip interno
    buf_fotos = io.BytesIO()
    with zipfile.ZipFile(buf_fotos, "w") as z_fotos:
        z_fotos.writestr("a001.jpg", b"jpg_data_a001")
        z_fotos.writestr("4145-8.jpg", b"jpg_data_4145")

    # 3. Crear outer ZIP
    outer_path = str(tmp_path / "BackupCompleto.Zip")
    with zipfile.ZipFile(outer_path, "w") as z_outer:
        z_outer.writestr("Dbf.zip", buf_dbf.getvalue())
        z_outer.writestr("Fotos.Zip", buf_fotos.getvalue())

    media_dir = str(tmp_path / "media_outer")

    # Importar outer zip
    conteos = import_zip(db, outer_path, media_dir=media_dir)
    assert "animales" in conteos
    assert conteos["animales"]["nuevos"] == 1
    assert "fotos" in conteos
    assert conteos["fotos"]["nuevos"] == 2
    assert conteos["fotos"]["duplicados"] == 0

    # Re-importar: todo duplicado
    conteos2 = import_zip(db, outer_path, media_dir=media_dir)
    assert conteos2["animales"]["nuevos"] == 0
    assert conteos2["fotos"]["nuevos"] == 0
    assert conteos2["fotos"]["duplicados"] == 2


def test_import_animales_reactivado_en_sg_elimina_venta_obsoleta(db):
    """Si un animal fue importado como VENDIDO pero luego se corrige en SG
    a ACTIVO (como el caso JA457/JA458 truncadas), la nueva importación debe
    marcarlo ACTIVO y eliminar el registro de VENTA obsoleto de movimientos."""
    from src.engine.dashboard_data import datos_ficha_animal

    # 1. Primera importación: marcado como VENDIDO
    r_vendido = [{
        "CODANI": "JA457", "NOMANI": "Vaca 457", "SEXO": "H",
        "TIPORAZA": "I", "FECNACE": "2019-07-09", "CODPOT": "B01",
        "TIPO": "V", "FECMUERTE": "2026-08-27",
    }]
    import_animales(db, r_vendido, causas={})
    a = db.query_one("SELECT id_animal, estado FROM animales WHERE tag = 'JA457'")
    assert a["estado"] == "VENDIDO"
    n_v = db.query_one("SELECT COUNT(*) n FROM movimientos WHERE animal_id = ? AND tipo_movimiento = 'VENTA'", (a["id_animal"],))["n"]
    assert n_v == 1
    ficha1 = datos_ficha_animal(db, "JA457")
    assert ficha1["estado"] == "VENDIDO"
    assert ficha1["venta"] is not None

    # 2. Segunda importación: en SG se corrigió y ahora es ACTIVO
    r_activo = [{
        "CODANI": "JA457", "NOMANI": "Vaca 457", "SEXO": "H",
        "TIPORAZA": "I", "FECNACE": "2020-06-07", "CODPOT": "B02",
        "TIPO": "", "FECMUERTE": None, "OBS": "HIJA SARA",
    }]
    import_animales(db, r_activo, causas={})
    a2 = db.query_one("SELECT id_animal, estado, notas FROM animales WHERE tag = 'JA457'")
    assert a2["estado"] == "ACTIVO"
    assert a2["notas"] == "HIJA SARA"
    # El movimiento de venta obsoleto debe haberse eliminado
    n_v2 = db.query_one("SELECT COUNT(*) n FROM movimientos WHERE animal_id = ? AND tipo_movimiento = 'VENTA'", (a2["id_animal"],))["n"]
    assert n_v2 == 0
    ficha2 = datos_ficha_animal(db, "JA457")
    assert ficha2["estado"] == "ACTIVO"
    assert ficha2["venta"] is None




def test_import_pesajes_desordenados_calcula_gmd_con_el_anterior(tmp_path):
    """Regresión: la GMD usa el pesaje cronológicamente anterior aunque el DBF venga desordenado."""
    from datetime import date as _date
    from src.db.database import Database as _DB
    from src.importers.dbf_importer import import_pesajes
    d = _DB(str(tmp_path / "p.db")).create_tables()
    try:
        registros = [
            {"CODANI": "47", "FECHA": _date(2026, 3, 1), "PESO": 300.0},
            {"CODANI": "47", "FECHA": _date(2026, 1, 1), "PESO": 240.0},
        ]
        import_pesajes(d, registros)
        fila = d.query_one("SELECT gmd_calculada FROM pesajes WHERE fecha = '2026-03-01'")
        assert fila["gmd_calculada"] is not None and fila["gmd_calculada"] > 0
        assert d.query_one("SELECT gmd_calculada FROM pesajes WHERE fecha = '2026-01-01'")["gmd_calculada"] is None
    finally:
        d.close()
