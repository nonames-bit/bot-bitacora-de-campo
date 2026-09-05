"""Pruebas de la capa de datos SQLite y de los modelos."""
from src.db.models import TABLAS


def test_tablas_creadas(db):
    for tabla in TABLAS:
        assert db.query_one(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tabla}'") is not None


def test_registrar_animal(db):
    aid = db.registrar_animal("47", nombre="Mariposa", sexo="Hembra",
                              raza="Brahman", fecha_nacimiento="2020-01-01")
    assert isinstance(aid, int)
    animal = db.get_animal("47")
    assert animal["tag"] == "47"
    assert animal["sexo"] == "Hembra"
    assert animal["fecha_nacimiento"] == "2020-01-01"


def test_resolver_animal_id(db):
    aid = db.registrar_animal("105")
    assert db.animal_id("105") == aid
    assert db.resolve_animal("105") == aid
    assert db.resolve_animal("9999") is None


def test_resolve_animal_crear_asigna_activo_por_defecto(db):
    aid = db.resolve_animal("500", crear=True)
    assert aid is not None
    assert db.get_animal("500")["estado"] == "ACTIVO"


def test_resolve_animal_crear_respeta_estado_explicito(db):
    db.resolve_animal("501", crear=True, estado="MUERTO")
    assert db.get_animal("501")["estado"] == "MUERTO"


def test_registrar_parto_enlaza_cria(db):
    db.registrar_parto(vaca_tag="47", fecha="2026-08-24", sexo_cria="Macho",
                       estado_cria="VIVO", peso_nacimiento=35.0, id_cria_tag="480")
    partos = db.query("SELECT * FROM partos")
    assert len(partos) == 1
    assert partos[0]["peso_nacimiento"] == 35.0
    # La cría quedó creada y vinculada a la madre.
    cria = db.get_animal("480")
    assert cria is not None
    vaca = db.get_animal("47")
    assert cria["madre_id"] == vaca["id_animal"]
    assert cria["sexo"] == "Macho"
    assert cria["fecha_nacimiento"] == "2026-08-24"

    # En historial, la cría no tiene partos propios pero sí registro de nacimiento
    h_cria = db.historial("480")
    assert len(h_cria["partos"]) == 0
    assert len(h_cria["nacimiento"]) == 1


def test_registrar_parto_hereda_potrero_real_de_la_madre(db):
    pid = db.registrar_potrero(nombre="ORDENO SANTA MARTHA", codigo="A24")
    db.execute("UPDATE potreros SET geom_wkt_4326 = ? WHERE id = ?", ("POLYGON((0 0,0 1,1 1,1 0,0 0))", pid))
    db.registrar_animal("JA379", sexo="Hembra", potrero=pid, estado="ACTIVO")
    db.registrar_parto(vaca_tag="JA379", fecha="2026-08-24", sexo_cria="Hembra", id_cria_tag="NO65")
    cria = db.get_animal("NO65")
    assert cria["potrero_id"] == pid


def test_registrar_parto_no_hereda_potrero_legacy_sin_geometria(db):
    # Potrero sin geom_wkt_4326: es un código legacy de Software Ganadero,
    # ya no vigente -- no debe "contaminar" a la cría con una ubicación falsa.
    pid = db.registrar_potrero(nombre="ALTOMONOS", codigo="18")
    db.registrar_animal("JA16", sexo="Hembra", potrero=pid, estado="ACTIVO")
    db.registrar_parto(vaca_tag="JA16", fecha="2018-02-19", sexo_cria="Macho", id_cria_tag="NM_38776")
    cria = db.get_animal("NM_38776")
    assert cria["potrero_id"] is None


def test_registrar_parto_autorreferenciado_proteccion(db):
    # Intentar registrar parto donde vaca_tag == id_cria_tag
    res = db.registrar_parto(vaca_tag="V009", fecha="2026-03-02", sexo_cria="Macho", id_cria_tag="V009")
    assert res == 0
    assert db.count("partos") == 0
    cria = db.get_animal("V009")
    assert cria is not None
    assert cria["madre_id"] is None
    assert cria["sexo"] == "Macho"


def test_registrar_animal_autorreferencia_madre_padre(db):
    aid = db.registrar_animal("A01", madre_tag="A01", padre_tag="A01")
    ani = db.get_animal("A01")
    assert ani["madre_id"] is None
    assert ani["padre_id"] is None


def test_registrar_servicio(db):
    db.registrar_servicio(vaca_tag="47", fecha="2026-08-15",
                          tipo_servicio="IA", toro_pajilla="502",
                          fep_calculada="2027-05-25")
    s = db.ultimo_servicio("47")
    assert s is not None
    assert s["toro_pajilla"] == "502"
    assert s["fep_calculada"] == "2027-05-25"


def test_registrar_tratamiento(db):
    db.registrar_tratamiento(animal_tag="47", fecha="2026-08-20",
                             producto="oxitetraciclina", dias_retiro_carne=14,
                             fecha_fin_retiro_carne="2026-09-03")
    t = db.query_one("SELECT * FROM tratamientos")
    assert t["dias_retiro_carne"] == 14
    assert t["fecha_fin_retiro_carne"] == "2026-09-03"


def test_registrar_potrero_y_resolucion(db):
    pid = db.registrar_potrero(nombre="Norte", codigo="05", area_has=10.0)
    assert db.potrero_id("Norte") == pid
    assert db.potrero_id("05") == pid


def test_historial(db):
    db.registrar_parto(vaca_tag="47", fecha="2026-01-01")
    db.registrar_celo(vaca_tag="47", fecha="2026-03-01")
    h = db.historial("47")
    assert len(h["partos"]) == 1
    assert len(h["celos"]) == 1


def test_ultimos_pesajes(db):
    db.registrar_pesaje(animal_tag="12", fecha="2026-01-01", peso_kg=350.0)
    db.registrar_pesaje(animal_tag="12", fecha="2026-03-01", peso_kg=420.0)
    pesajes = db.ultimos_pesajes("12", 2)
    assert len(pesajes) == 2
    assert pesajes[0]["peso_kg"] == 420.0


def test_parientes_3_generaciones(db):
    db.registrar_animal("G1", sexo="Hembra")            # abuela
    db.registrar_animal("G2", sexo="Hembra", madre_tag="G1")  # madre
    db.registrar_animal("G3", sexo="Hembra", madre_tag="G2")  # nieta
    anc = db.parientes_3_generaciones("G3")
    assert anc == {db.animal_id("G1"), db.animal_id("G2")}


def test_verificar_consanguinidad(db):
    # Toro T es padre directo de la hembra H (cruzamiento consanguíneo).
    db.registrar_animal("T", sexo="Macho")
    db.registrar_animal("H", sexo="Hembra", padre_tag="T")
    assert db.verificar_consanguinidad("H", "T") is True
    # Animales sin parentesco conocido.
    db.registrar_animal("X", sexo="Hembra")
    db.registrar_animal("Y", sexo="Macho")
    assert db.verificar_consanguinidad("X", "Y") is False


def test_registrar_foto_y_consultas(db):
    db.registrar_animal("47")
    fid = db.registrar_foto("media/foto_47_1.jpg", animal_tag="47", fecha="2026-08-25", caption="Ubre sana")
    assert isinstance(fid, int)

    fotos_47 = db.fotos_de("47")
    assert len(fotos_47) == 1
    assert fotos_47[0]["caption"] == "Ubre sana"
    assert fotos_47[0]["ruta"] == "media/foto_47_1.jpg"

    ultimas = db.ultimas_fotos(5)
    assert len(ultimas) == 1
    assert ultimas[0]["tag"] == "47"

    h = db.historial("47")
    assert "fotos" in h
    assert len(h["fotos"]) == 1


def test_resolver_animal_tags_flexibles(db):
    aid = db.registrar_animal("N-069", nombre="Negra")
    assert db.animal_id("N069") == aid
    assert db.animal_id("n069") == aid
    assert db.animal_id("N-069") == aid
    assert db.animal_id("N 069") == aid
    assert db.animal_id("Negra") == aid
    assert db.resolve_animal("n069") == aid


def test_marcar_historicos_sg(db):
    p_viejo = db.registrar_potrero(codigo="01", nombre="LECHERAS")
    p_nuevo = db.registrar_potrero(codigo="A01", nombre="ORDENO SANTA MARTHA")

    db.registrar_animal("VIEJO1", potrero="01", estado="ACTIVO")
    db.registrar_animal("NUEVO1", potrero="A01", estado="ACTIVO")

    db.marcar_historicos_sg()

    h_viejo = db.query_one("SELECT estado FROM animales WHERE tag='VIEJO1'")
    h_nuevo = db.query_one("SELECT estado FROM animales WHERE tag='NUEVO1'")

    assert h_viejo["estado"] == "HISTORICO"
    assert h_nuevo["estado"] == "ACTIVO"


def test_registrar_movimiento_es_idempotente(db):
    """Regresión: JA457 quedó con dos filas VENTA idénticas en producción
    (doble envío/reintento) porque registrar_movimiento insertaba sin
    verificar duplicados, a diferencia del resto de registrar_* con dedup
    natural. Ahora una segunda llamada con los mismos datos no duplica."""
    id1 = db.registrar_movimiento("47", fecha="2026-08-27", tipo_movimiento="VENTA", precio=1000)
    id2 = db.registrar_movimiento("47", fecha="2026-08-27", tipo_movimiento="VENTA", precio=1000)
    assert id1 == id2
    filas = db.query("SELECT * FROM movimientos WHERE animal_id = (SELECT id_animal FROM animales WHERE tag='47')")
    assert len(filas) == 1

    # Un movimiento distinto (otro tipo, u otra fecha) sí debe crear una fila nueva.
    id3 = db.registrar_movimiento("47", fecha="2026-08-27", tipo_movimiento="COMPRA", precio=1000)
    assert id3 != id1


def test_registrar_pesaje_es_idempotente(db):
    id1 = db.registrar_pesaje("47", fecha="2026-08-01", peso_kg=200)
    id2 = db.registrar_pesaje("47", fecha="2026-08-01", peso_kg=200)
    assert id1 == id2
    # Peso distinto el mismo día (corrección real) sí debe crear otra fila.
    id3 = db.registrar_pesaje("47", fecha="2026-08-01", peso_kg=205)
    assert id3 != id1


def test_registrar_tratamiento_es_idempotente_pero_permite_dosis_distinta(db):
    id1 = db.registrar_tratamiento("47", fecha="2026-08-01", producto="Ivermectina", dosis="10ml")
    id2 = db.registrar_tratamiento("47", fecha="2026-08-01", producto="Ivermectina", dosis="10ml")
    assert id1 == id2
    # Mismo día, mismo producto, dosis distinta: dos aplicaciones reales.
    id3 = db.registrar_tratamiento("47", fecha="2026-08-01", producto="Ivermectina", dosis="5ml")
    assert id3 != id1


def test_registrar_traslado_es_idempotente(db):
    p1 = db.registrar_potrero("Norte")
    id1 = db.registrar_traslado("47", fecha="2026-08-01", potrero_destino=p1)
    id2 = db.registrar_traslado("47", fecha="2026-08-01", potrero_destino=p1)
    assert id1 == id2


def test_registrar_celo_es_idempotente_pero_permite_am_y_pm(db):
    id1 = db.registrar_celo("47", fecha="2026-08-01", am_pm="AM")
    id2 = db.registrar_celo("47", fecha="2026-08-01", am_pm="AM")
    assert id1 == id2
    # Celo en la mañana y otro observado en la tarde del mismo día: ambos reales.
    id3 = db.registrar_celo("47", fecha="2026-08-01", am_pm="PM")
    assert id3 != id1


def test_registrar_servicio_es_idempotente_pero_permite_toro_distinto(db):
    id1 = db.registrar_servicio("47", fecha="2026-08-01", tipo_servicio="IA", toro_pajilla="TORO 1")
    id2 = db.registrar_servicio("47", fecha="2026-08-01", tipo_servicio="IA", toro_pajilla="TORO 1")
    assert id1 == id2
    id3 = db.registrar_servicio("47", fecha="2026-08-01", tipo_servicio="IA", toro_pajilla="TORO 2")
    assert id3 != id1


def test_detectar_duplicados_geneticos(db):
    db.registrar_animal("MADRE1", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("PADRE1", sexo="Macho", estado="ACTIVO")
    # Mismo nacimiento (madre+padre+fecha) importado dos veces con tags distintos
    db.registrar_animal("N065", sexo="Hembra", estado="ACTIVO",
                        madre_tag="MADRE1", padre_tag="PADRE1", fecha_nacimiento="2024-11-01")
    db.registrar_animal("NO65", sexo="Hembra", estado="ACTIVO",
                        madre_tag="MADRE1", padre_tag="PADRE1", fecha_nacimiento="2024-11-01")
    # Animal sin relación, no debe aparecer como duplicado
    db.registrar_animal("OTRO1", sexo="Hembra", estado="ACTIVO",
                        madre_tag="MADRE1", padre_tag="PADRE1", fecha_nacimiento="2025-01-01")

    grupos = db.detectar_duplicados_geneticos()
    assert len(grupos) == 1
    assert grupos[0]["madre_tag"] == "MADRE1"
    assert grupos[0]["fecha_nacimiento"] == "2024-11-01"
    assert set(grupos[0]["tags"]) == {"N065", "NO65"}


def test_detectar_duplicados_geneticos_ignora_sin_genealogia(db):
    # Dos animales sin madre_id/fecha_nacimiento no deben marcarse como duplicados
    # entre sí solo por compartir valores NULL.
    db.registrar_animal("A1", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("A2", sexo="Hembra", estado="ACTIVO")
    assert db.detectar_duplicados_geneticos() == []


def test_detectar_duplicados_geneticos_ignora_mellizos_reales(db):
    # Un parto múltiple real (mellizos marcados en notas) no es un duplicado.
    db.registrar_animal("MADRE1", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("PADRE1", sexo="Macho", estado="ACTIVO")
    db.registrar_animal("N003", sexo="Hembra", estado="ACTIVO",
                        madre_tag="MADRE1", padre_tag="PADRE1",
                        fecha_nacimiento="2024-12-26", notas="GEMELA1")
    db.registrar_animal("N025", sexo="Hembra", estado="ACTIVO",
                        madre_tag="MADRE1", padre_tag="PADRE1",
                        fecha_nacimiento="2024-12-26", notas="GEMELA2")
    assert db.detectar_duplicados_geneticos() == []


# ---------------------------------------------------------------------------
# Auditoría y /deshacer: registrado_por, ultimos_registros, detalle_registro,
# eliminar_registro. Regresión real: un trabajador o el ADMIN pueden crear
# un registro por error (ej. "murio la 47" cuando en realidad no murió) y
# hasta ahora no había forma de corregirlo sin restaurar toda la base de
# datos desde un backup diario.
# ---------------------------------------------------------------------------
def test_registrar_muerte_guarda_quien_y_cuando(db):
    mid = db.registrar_muerte("47", fecha="2026-08-20", causa_presunta="culebra", registrado_por=12345)
    fila = db.query_one("SELECT * FROM muertes WHERE id = ?", (mid,))
    assert fila["registrado_por"] == 12345
    assert fila["creado_en"] is not None


def test_ultimos_registros_incluye_varias_tablas_ordenado_por_insercion(db):
    db.registrar_muerte("47", fecha="2026-08-20", causa_presunta="culebra", registrado_por=1)
    db.registrar_parto("48", fecha="2026-08-21", sexo_cria="Macho", registrado_por=2)
    filas = db.ultimos_registros(10)
    tablas = {f["tabla"] for f in filas}
    assert "muertes" in tablas
    assert "partos" in tablas
    # El más reciente (parto) debe ir antes que el más viejo (muerte).
    assert [f["tabla"] for f in filas].index("partos") < [f["tabla"] for f in filas].index("muertes")


def test_detalle_registro_describe_la_fila_correcta(db):
    mid = db.registrar_muerte("47", fecha="2026-08-20", causa_presunta="mordedura de culebra")
    detalle = db.detalle_registro("muertes", mid)
    assert detalle is not None
    assert detalle["tag"] == "47"
    assert "mordedura de culebra" in detalle["resumen"]


def test_detalle_registro_tabla_no_permitida_devuelve_none(db):
    assert db.detalle_registro("animales", 1) is None
    assert db.detalle_registro("potreros", 1) is None


def test_eliminar_registro_borra_solo_esa_fila(db):
    id1 = db.registrar_muerte("47", fecha="2026-08-20")
    id2 = db.registrar_muerte("48", fecha="2026-08-21")
    assert db.eliminar_registro("muertes", id1) is True
    assert db.query_one("SELECT * FROM muertes WHERE id = ?", (id1,)) is None
    assert db.query_one("SELECT * FROM muertes WHERE id = ?", (id2,)) is not None


def test_eliminar_registro_id_inexistente_devuelve_false(db):
    assert db.eliminar_registro("muertes", 999999) is False


def test_eliminar_registro_tabla_no_permitida_lanza_error(db):
    import pytest
    with pytest.raises(ValueError):
        db.eliminar_registro("animales", 1)


# ---------------------------------------------------------------------------
# Condición corporal (BCS)
# ---------------------------------------------------------------------------
def test_registrar_condicion_corporal_y_consultar_ultima(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_condicion_corporal("47", fecha="2026-08-01", valor=3.0)
    db.registrar_condicion_corporal("47", fecha="2026-08-20", valor=3.5, registrado_por=99)

    ultima = db.ultima_condicion_corporal("47")
    assert ultima["valor"] == 3.5
    assert ultima["fecha"] == "2026-08-20"
    assert ultima["registrado_por"] == 99


def test_registrar_condicion_corporal_es_idempotente(db):
    id1 = db.registrar_condicion_corporal("47", fecha="2026-08-20", valor=3.5)
    id2 = db.registrar_condicion_corporal("47", fecha="2026-08-20", valor=3.5)
    assert id1 == id2
    # Mismo animal y fecha, distinto valor: sí debe quedar como fila nueva.
    id3 = db.registrar_condicion_corporal("47", fecha="2026-08-20", valor=4.0)
    assert id3 != id1


def test_condicion_corporal_aparece_en_historial(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_condicion_corporal("47", fecha="2026-08-20", valor=3.5)
    hist = db.historial("47")
    assert len(hist["condicion_corporal"]) == 1
    assert hist["condicion_corporal"][0]["valor"] == 3.5


# ---------------------------------------------------------------------------
# Producción de leche (control semanal)
# ---------------------------------------------------------------------------
def test_registrar_leche_y_consultar_ultima(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_leche("47", fecha="2026-08-01", litros=10.0)
    db.registrar_leche("47", fecha="2026-08-08", litros=12.5, registrado_por=99)

    ultima = db.ultima_leche("47")
    assert ultima["litros"] == 12.5
    assert ultima["fecha"] == "2026-08-08"
    assert ultima["registrado_por"] == 99


def test_registrar_leche_es_idempotente(db):
    id1 = db.registrar_leche("47", fecha="2026-08-08", litros=12.5)
    id2 = db.registrar_leche("47", fecha="2026-08-08", litros=12.5)
    assert id1 == id2
    id3 = db.registrar_leche("47", fecha="2026-08-08", litros=13.0)
    assert id3 != id1


def test_leche_aparece_en_historial(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_leche("47", fecha="2026-08-08", litros=12.5)
    hist = db.historial("47")
    assert len(hist["produccion_leche"]) == 1
    assert hist["produccion_leche"][0]["litros"] == 12.5


def test_historial_leche_devuelve_ordenado_por_fecha(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_leche("47", fecha="2026-08-15", litros=11.0)
    db.registrar_leche("47", fecha="2026-08-01", litros=10.0)
    controles = db.historial_leche("47")
    assert [c["fecha"] for c in controles] == ["2026-08-01", "2026-08-15"]


# ---------------------------------------------------------------------------
# Últimas consultas de animales (panel de botones "consultas recientes")
# ---------------------------------------------------------------------------
def test_ultimas_consultas_animal_orden_mas_reciente_primero(db):
    db.registrar_animal("A048", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("A088", sexo="Hembra", estado="ACTIVO")
    db.registrar_consulta_animal("A048", hoy="2026-08-01")
    db.registrar_consulta_animal("A088", hoy="2026-08-02")
    recientes = db.ultimas_consultas_animal(limite=4)
    assert [r["tag"] for r in recientes] == ["A088", "A048"]


def test_registrar_consulta_animal_re_consultado_sube_al_frente(db):
    db.registrar_animal("A048", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("A088", sexo="Hembra", estado="ACTIVO")
    db.registrar_consulta_animal("A048", hoy="2026-08-01")
    db.registrar_consulta_animal("A088", hoy="2026-08-02")
    # Se vuelve a consultar A048 más tarde: debe pasar al frente sin duplicarse.
    db.registrar_consulta_animal("A048", hoy="2026-08-03")
    recientes = db.ultimas_consultas_animal(limite=4)
    assert [r["tag"] for r in recientes] == ["A048", "A088"]
    assert db.count("consultas_animal") == 2


def test_ultimas_consultas_animal_respeta_limite(db):
    for i in range(6):
        tag = f"A{i:03d}"
        db.registrar_animal(tag, sexo="Hembra", estado="ACTIVO")
        db.registrar_consulta_animal(tag, hoy=f"2026-08-{i + 1:02d}")
    recientes = db.ultimas_consultas_animal(limite=4)
    assert [r["tag"] for r in recientes] == ["A005", "A004", "A003", "A002"]


def test_ultimas_consultas_animal_excluye_historico(db):
    db.registrar_animal("A048", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("A088", sexo="Hembra", estado="HISTORICO")
    db.registrar_consulta_animal("A048", hoy="2026-08-01")
    db.registrar_consulta_animal("A088", hoy="2026-08-02")
    recientes = db.ultimas_consultas_animal(limite=4)
    assert [r["tag"] for r in recientes] == ["A048"]


def test_registrar_consulta_animal_tag_inexistente_no_deja_rastro(db):
    db.registrar_consulta_animal("NOEXISTE9999")
    assert db.count("consultas_animal") == 0


# ---------------------------------------------------------------------------
# Renombrado de crías: código temporal de SG (madre-N) -> chapeta definitiva
# ---------------------------------------------------------------------------
def test_renombrar_animal_conserva_id(db):
    id_original = db.registrar_animal(tag="A090-6", fecha_nacimiento="2026-08-01")
    aid = db.renombrar_animal("A090-6", "B234")
    assert aid == id_original
    assert db.animal_id("A090-6") is None
    assert db.animal_id("B234") == id_original


def test_renombrar_animal_tag_viejo_inexistente(db):
    assert db.renombrar_animal("NOEXISTE", "B234") is None


def test_renombrar_animal_tag_nuevo_ya_ocupado_no_lo_hace(db):
    db.registrar_animal(tag="A090-6")
    db.registrar_animal(tag="B234")
    assert db.renombrar_animal("A090-6", "B234") is None
    assert db.animal_id("A090-6") is not None


# ---------------------------------------------------------------------------
# Registro de importaciones de Software Ganadero (¿está usando el backup de
# hoy?)
# ---------------------------------------------------------------------------
def test_registrar_import_sg_y_consultar_ultimo(db):
    assert db.ultimo_import_sg() is None
    db.registrar_import_sg("Datos20260830.Zip", {
        "animales": {"nuevos": 5, "duplicados": 2},
        "partos": {"nuevos": 3, "duplicados": 0},
    })
    ultimo = db.ultimo_import_sg()
    assert ultimo["archivo"] == "Datos20260830.Zip"
    assert ultimo["nuevos"] == 8
    assert ultimo["duplicados"] == 2
    assert ultimo["fecha_iso"] is not None


def test_registrar_import_sg_usa_solo_el_nombre_del_archivo(db):
    # El vigilante local pasa una ruta absoluta de Windows; solo el nombre
    # del archivo importa para el registro (no la ruta completa del disco
    # del usuario).
    db.registrar_import_sg(r"C:\Usati\Copias\Datos20260830.Zip", {})
    assert db.ultimo_import_sg()["archivo"] == "Datos20260830.Zip"


def test_ultimo_import_sg_devuelve_el_mas_reciente(db):
    db.registrar_import_sg("Datos20260828.Zip", {"animales": {"nuevos": 1, "duplicados": 0}})
    db.registrar_import_sg("Datos20260830.Zip", {"animales": {"nuevos": 2, "duplicados": 0}})
    assert db.ultimo_import_sg()["archivo"] == "Datos20260830.Zip"


