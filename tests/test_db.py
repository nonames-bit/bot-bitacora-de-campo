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


def test_registrar_animal_chip_y_color(db):
    db.registrar_animal("47", chip="985123456", color="Negro")
    animal = db.get_animal("47")
    assert animal["chip"] == "985123456"
    assert animal["color"] == "Negro"


def test_registrar_animal_existente_actualiza_en_vez_de_duplicar(db):
    aid1 = db.registrar_animal("47", nombre="Original", sexo="Hembra")
    aid2 = db.registrar_animal("47", nombre="Editada")
    assert aid1 == aid2
    animal = db.get_animal("47")
    assert animal["nombre"] == "Editada"
    assert animal["sexo"] == "Hembra"  # campo no enviado en la 2da llamada: se conserva


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


def test_registrar_parto_potrero_cria_explicito_pisa_la_herencia(db):
    pid_madre = db.registrar_potrero(nombre="ORDENO SANTA MARTHA")
    pid_cria = db.registrar_potrero(nombre="LEVANTE")
    db.registrar_animal("JA379", sexo="Hembra", potrero=pid_madre, estado="ACTIVO")
    db.registrar_parto(vaca_tag="JA379", fecha="2026-08-24", sexo_cria="Hembra",
                       id_cria_tag="NO65", potrero_cria="LEVANTE")
    cria = db.get_animal("NO65")
    assert cria["potrero_id"] == pid_cria


def test_registrar_parto_potrero_madre_la_mueve(db):
    pid_origen = db.registrar_potrero(nombre="Potrero Origen")
    pid_maternidad = db.registrar_potrero(nombre="Maternidad")
    db.registrar_animal("JA379", sexo="Hembra", potrero=pid_origen, estado="ACTIVO")
    db.registrar_parto(vaca_tag="JA379", fecha="2026-08-24", potrero_madre="Maternidad")
    madre = db.get_animal("JA379")
    assert madre["potrero_id"] == pid_maternidad


def test_registrar_destete_actualiza_potrero_de_la_cria_y_registra_pesaje(db):
    pid_madre = db.registrar_potrero(nombre="Ordeño")
    pid_levante = db.registrar_potrero(nombre="Levante")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=pid_madre)
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho", id_cria_tag="47-1")

    did = db.registrar_destete("47-1", fecha="2026-09-01", peso_kg=120.0, potrero_cria="Levante")
    assert isinstance(did, int)

    cria = db.get_animal("47-1")
    assert cria["potrero_id"] == pid_levante
    pesajes = db.query("SELECT * FROM pesajes WHERE animal_id = ?", (cria["id_animal"],))
    assert len(pesajes) == 1
    assert pesajes[0]["peso_kg"] == 120.0
    assert pesajes[0]["evento"] == "DESTETE"
    traslados = db.query("SELECT * FROM traslados WHERE animal_id = ?", (cria["id_animal"],))
    assert len(traslados) == 1
    assert traslados[0]["motivo"] == "Destete"


def test_registrar_destete_mueve_tambien_a_la_madre_si_se_indica(db):
    pid_ordeno = db.registrar_potrero(nombre="Ordeño")
    pid_secas = db.registrar_potrero(nombre="Vacas Secas")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=pid_ordeno)
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho", id_cria_tag="47-1")

    db.registrar_destete("47-1", fecha="2026-09-01", potrero_madre="Vacas Secas",
                         peso_madre_kg=410.0, cond_corporal_madre=3.0)

    madre = db.get_animal("47")
    assert madre["potrero_id"] == pid_secas
    traslados_madre = db.query("SELECT * FROM traslados WHERE animal_id = ?", (madre["id_animal"],))
    assert len(traslados_madre) == 1
    assert traslados_madre[0]["motivo"] == "Destete de cría"


def test_registrar_destete_es_idempotente(db):
    db.registrar_animal("47-1", sexo="Macho", estado="ACTIVO")
    id1 = db.registrar_destete("47-1", fecha="2026-09-01", peso_kg=120.0)
    id2 = db.registrar_destete("47-1", fecha="2026-09-01", peso_kg=120.0)
    assert id1 == id2


def test_registrar_destete_sin_potreros_no_falla(db):
    db.registrar_animal("47-1", sexo="Macho", estado="ACTIVO")
    did = db.registrar_destete("47-1", fecha="2026-09-01", notas="Destete simple, sin cambio de lote")
    assert isinstance(did, int)


def test_historial_incluye_destetes_propios_y_de_crias(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho", id_cria_tag="47-1")
    db.registrar_destete("47-1", fecha="2026-09-01", peso_kg=120.0)

    h_cria = db.historial("47-1")
    assert len(h_cria["destetes"]) == 1

    h_madre = db.historial("47")
    assert len(h_madre["destetes_crias"]) == 1


def test_registrar_destete_no_afecta_estado_de_leche_de_la_madre(db):
    """El destete solo separa a la cría -- NO seca a la vaca. Sin un
    registro explícito en `secados`, la madre no debe quedar marcada como
    seca ni generar ninguna fila en esa tabla."""
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho", id_cria_tag="47-1")
    db.registrar_destete("47-1", fecha="2026-09-01", peso_kg=120.0,
                         potrero_madre="Vacas Secas", peso_madre_kg=410.0, cond_corporal_madre=3.0)
    assert db.count("secados") == 0


def test_registrar_secado_actualiza_potrero_y_condicion_corporal(db):
    pid_ordeno = db.registrar_potrero(nombre="Ordeño")
    pid_secas = db.registrar_potrero(nombre="Vacas Secas")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=pid_ordeno)

    sid = db.registrar_secado("47", fecha="2026-09-12", potrero_destino="Vacas Secas",
                              cond_corporal=3.0, motivo="Fin de lactancia")
    assert isinstance(sid, int)

    vaca = db.get_animal("47")
    assert vaca["potrero_id"] == pid_secas
    traslados = db.query("SELECT * FROM traslados WHERE animal_id = ?", (vaca["id_animal"],))
    assert len(traslados) == 1
    assert traslados[0]["motivo"] == "Secado"
    cc = db.query("SELECT * FROM condicion_corporal WHERE animal_id = ?", (vaca["id_animal"],))
    assert len(cc) == 1
    assert cc[0]["valor"] == 3.0


def test_registrar_secado_es_idempotente(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    id1 = db.registrar_secado("47", fecha="2026-09-12", motivo="Fin de lactancia")
    id2 = db.registrar_secado("47", fecha="2026-09-12", motivo="Fin de lactancia")
    assert id1 == id2
    assert db.count("secados") == 1


def test_registrar_secado_sin_potrero_ni_cc_no_falla(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    sid = db.registrar_secado("47", fecha="2026-09-12", notas="Se secó sola")
    assert isinstance(sid, int)
    assert db.count("traslados") == 0
    assert db.count("condicion_corporal") == 0


def test_registrar_parto_autorreferenciado_proteccion(db):
    # Intentar registrar parto donde vaca_tag == id_cria_tag
    res = db.registrar_parto(vaca_tag="V009", fecha="2026-03-02", sexo_cria="Macho", id_cria_tag="V009")
    assert res is None
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


def test_fotos_de_no_mezcla_foto_de_otro_animal_cuyo_tag_es_substring(db):
    """Regresión: la ficha de JA14 mostraba también la foto de su propia
    cría JA14-7, porque el match difuso (caption/ocr/ruta LIKE '%JA14%')
    también calza con 'JA14-7'. Una vez que la foto de JA14-7 tiene su
    propio animal_id, no debe filtrarse en la ficha del padre/madre."""
    db.registrar_animal("JA14", sexo="Hembra")
    db.registrar_animal("JA14-7", sexo="Hembra")

    db.registrar_foto("media/ja14.jpg", animal_tag="JA14", fecha="2026-08-01", caption="JA14 en potrero")
    db.registrar_foto("media/ja14-7.jpg", animal_tag="JA14-7", fecha="2026-08-02", caption="Cria JA14-7 recien nacida")

    fotos_ja14 = db.fotos_de("JA14")
    assert len(fotos_ja14) == 1
    assert fotos_ja14[0]["ruta"] == "media/ja14.jpg"

    fotos_cria = db.fotos_de("JA14-7")
    assert len(fotos_cria) == 1
    assert fotos_cria[0]["ruta"] == "media/ja14-7.jpg"


def test_fotos_de_conserva_match_difuso_solo_para_fotos_huerfanas(db):
    """Una foto sin animal_id (aun no vinculada) sí debe encontrarse por
    coincidencia de caption/ocr/ruta, que es el comportamiento original que
    complementa a vincular_fotos_huerfanas()."""
    db.registrar_animal("47")
    db.insert("fotos", {
        "animal_id": None, "tag": None, "fecha": "2026-08-01",
        "ruta": "media/huerfana_47.jpg", "caption": "Animal 47 en la manga",
    })
    fotos = db.fotos_de("47")
    assert len(fotos) == 1
    assert fotos[0]["ruta"] == "media/huerfana_47.jpg"


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


def test_registrar_traslado_actualiza_el_potrero_actual_del_animal(db):
    """Regresión: el traslado solo quedaba como nota histórica sin mover al
    animal de verdad -- Inventario/Ficha/filtros leen animales.potrero_id
    directo, no el último traslado, así que sin esto el animal seguía
    apareciendo en su potrero viejo después de "moverlo"."""
    origen = db.registrar_potrero("Olegario I")
    destino = db.registrar_potrero("Olegario II")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=origen)
    db.registrar_traslado("47", fecha="2026-08-01", potrero_origen=origen, potrero_destino=destino)
    fila = db.query_one("SELECT potrero_id FROM animales WHERE tag = '47'")
    assert fila["potrero_id"] == destino


def test_registrar_traslado_sin_destino_no_toca_el_potrero_actual(db):
    origen = db.registrar_potrero("Olegario I")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=origen)
    db.registrar_traslado("47", fecha="2026-08-01", potrero_origen=origen)
    fila = db.query_one("SELECT potrero_id FROM animales WHERE tag = '47'")
    assert fila["potrero_id"] == origen


def test_animales_activos_en_potrero(db):
    p1 = db.registrar_potrero("Olegario I")
    p2 = db.registrar_potrero("Olegario II")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1)
    db.registrar_animal("48", sexo="Macho", estado="ACTIVO", potrero=p1)
    db.registrar_animal("49", sexo="Hembra", estado="VENDIDO", potrero=p1)  # inactivo: no cuenta
    db.registrar_animal("50", sexo="Hembra", estado="ACTIVO", potrero=p2)  # otro potrero: no cuenta
    tags = db.animales_activos_en_potrero(p1)
    assert sorted(tags) == ["47", "48"]


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


def test_rectificar_tag_animal_renombrado_libre(db):
    aid = db.registrar_animal(tag="JA83", sexo="Hembra")
    db.registrar_pesaje(animal_tag="JA83", peso_kg=350.0, fecha="2026-09-01")
    res = db.rectificar_tag_animal("JA83", "JA88")
    assert res["ok"] is True
    assert res["accion"] == "renombrado"
    assert db.animal_id("JA83") is None
    assert db.animal_id("JA88") == aid
    ult = db.ultimos_pesajes("JA88", 1)
    assert len(ult) == 1 and ult[0]["peso_kg"] == 350.0


def test_rectificar_tag_animal_destino_existente_fusion(db):
    aid_err = db.registrar_animal(tag="JA83", sexo="Hembra", notas="Leído mal en manga")
    db.registrar_pesaje(animal_tag="JA83", peso_kg=320.0, fecha="2026-09-02")

    aid_real = db.registrar_animal(tag="JA88", sexo="Hembra")
    db.registrar_pesaje(animal_tag="JA88", peso_kg=310.0, fecha="2026-08-01")

    # Sin fusionar: pide confirmación
    res1 = db.rectificar_tag_animal("JA83", "JA88", fusionar_si_existe=False)
    assert res1["ok"] is False
    assert res1["requiere_confirmacion_fusion"] is True
    assert res1["origen"]["id"] == aid_err
    assert res1["destino"]["id"] == aid_real

    # Con fusión confirmada
    res2 = db.rectificar_tag_animal("JA83", "JA88", fusionar_si_existe=True)
    assert res2["ok"] is True
    assert res2["accion"] == "fusionado"
    assert db.animal_id("JA83") is None
    assert db.animal_id("JA88") == aid_real

    pesajes = db.ultimos_pesajes("JA88", 5)
    assert len(pesajes) == 2  # Ambos pesajes ahora pertenecen a JA88
    pesos = {p["peso_kg"] for p in pesajes}
    assert 320.0 in pesos and 310.0 in pesos


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


# ---------------------------------------------------------------------------
# Finanzas: libro de ingresos/egresos + resumen de utilidad.
# ---------------------------------------------------------------------------
def test_registrar_finanza_basico(db):
    fid = db.registrar_finanza(
        fecha="2026-09-07", tipo="egreso", categoria="insumo",
        concepto="Sal mineralizada 40kg", monto=180000, contraparte="Agropecuaria X",
    )
    fila = db.query_one("SELECT * FROM finanzas WHERE id = ?", (fid,))
    assert fila["tipo"] == "EGRESO"
    assert fila["categoria"] == "INSUMO"
    assert fila["monto"] == 180000
    assert fila["creado_en"] is not None


def test_registrar_finanza_vincula_animal_y_potrero_opcionales(db):
    db.registrar_animal("N069", sexo="Hembra", estado="ACTIVO")
    db.registrar_potrero(nombre="Olegario")
    fid = db.registrar_finanza(
        fecha="2026-09-07", tipo="egreso", categoria="veterinario",
        monto=50000, animal_tag="N069", potrero="Olegario",
    )
    fila = db.query_one("SELECT * FROM finanzas WHERE id = ?", (fid,))
    assert fila["animal_id"] == db.animal_id("N069")
    assert fila["potrero_id"] == db.potrero_id("Olegario")


def test_editar_finanza_actualiza_solo_los_campos_provistos(db):
    fid = db.registrar_finanza(
        fecha="2026-09-07", tipo="EGRESO", categoria="INSUMO",
        concepto="Sal mineralizada 40kg", monto=180000, contraparte="Agropecuaria X",
    )
    ok = db.editar_finanza(fid, monto=200000, concepto="Sal mineralizada 50kg")
    assert ok is True
    fila = db.query_one("SELECT * FROM finanzas WHERE id = ?", (fid,))
    assert fila["monto"] == 200000
    assert fila["concepto"] == "Sal mineralizada 50kg"
    # No tocados: siguen igual que al registrar.
    assert fila["tipo"] == "EGRESO"
    assert fila["categoria"] == "INSUMO"
    assert fila["contraparte"] == "Agropecuaria X"


def test_editar_finanza_cambia_tipo_y_categoria(db):
    fid = db.registrar_finanza(fecha="2026-09-07", tipo="EGRESO", categoria="INSUMO", monto=100000)
    db.editar_finanza(fid, tipo="ingreso", categoria="otro_ingreso")
    fila = db.query_one("SELECT * FROM finanzas WHERE id = ?", (fid,))
    assert fila["tipo"] == "INGRESO"
    assert fila["categoria"] == "OTRO_INGRESO"


def test_editar_finanza_vacia_campo_de_texto_con_string_vacio(db):
    fid = db.registrar_finanza(fecha="2026-09-07", tipo="EGRESO", categoria="INSUMO",
                               monto=100000, contraparte="Agropecuaria X")
    db.editar_finanza(fid, contraparte="")
    fila = db.query_one("SELECT * FROM finanzas WHERE id = ?", (fid,))
    assert fila["contraparte"] == ""


def test_editar_finanza_animal_tag_vacio_desvincula_el_animal(db):
    db.registrar_animal("N069", sexo="Hembra", estado="ACTIVO")
    fid = db.registrar_finanza(fecha="2026-09-07", tipo="EGRESO", categoria="VETERINARIO",
                               monto=50000, animal_tag="N069")
    db.editar_finanza(fid, animal_tag="")
    fila = db.query_one("SELECT * FROM finanzas WHERE id = ?", (fid,))
    assert fila["animal_id"] is None


def test_editar_finanza_id_inexistente_devuelve_false(db):
    assert db.editar_finanza(99999, monto=1000) is False


def test_eliminar_finanza_borra_el_registro(db):
    fid = db.registrar_finanza(fecha="2026-09-07", tipo="EGRESO", categoria="INSUMO", monto=100000)
    ok = db.eliminar_finanza(fid)
    assert ok is True
    assert db.query_one("SELECT * FROM finanzas WHERE id = ?", (fid,)) is None


def test_eliminar_finanza_id_inexistente_devuelve_false(db):
    assert db.eliminar_finanza(99999) is False


def test_resumen_finanzas_calcula_utilidad_incluyendo_ventas_de_animales(db):
    # Ingresos: venta de leche (finanzas) + venta de un animal (movimientos).
    db.registrar_finanza(fecha="2026-09-05", tipo="INGRESO", categoria="VENTA_LECHE", monto=2000000, litros=1500)
    db.registrar_movimiento("V089", fecha="2026-09-06", tipo_movimiento="VENTA", precio=1500000)
    # Egresos: nómina + insumo + compra de un animal.
    db.registrar_finanza(fecha="2026-09-05", tipo="EGRESO", categoria="NOMINA", monto=800000, contraparte="Andrés")
    db.registrar_finanza(fecha="2026-09-06", tipo="EGRESO", categoria="INSUMO", monto=180000)
    db.registrar_movimiento("V090", fecha="2026-09-06", tipo_movimiento="COMPRA", precio=1200000)

    resumen = db.resumen_finanzas("2026-09-01", "2026-09-30")
    assert resumen["total_ingresos"] == 3500000
    assert resumen["total_egresos"] == 2180000
    assert resumen["utilidad"] == 1320000
    categorias = {(c["tipo"], c["categoria"]): c["total"] for c in resumen["categorias"]}
    assert categorias[("INGRESO", "VENTA_LECHE")] == 2000000
    assert categorias[("INGRESO", "VENTA_ANIMAL")] == 1500000
    assert categorias[("EGRESO", "COMPRA_ANIMAL")] == 1200000


def test_resumen_finanzas_ignora_fuera_de_rango(db):
    db.registrar_finanza(fecha="2026-08-15", tipo="INGRESO", categoria="VENTA_LECHE", monto=100000)
    db.registrar_finanza(fecha="2026-09-15", tipo="INGRESO", categoria="VENTA_LECHE", monto=200000)
    resumen = db.resumen_finanzas("2026-09-01", "2026-09-30")
    assert resumen["total_ingresos"] == 200000


def test_flujo_caja_mensual(db):
    db.registrar_finanza(fecha="2026-08-05", tipo="INGRESO", categoria="VENTA_LECHE", monto=1000000)
    db.registrar_finanza(fecha="2026-08-10", tipo="EGRESO", categoria="INSUMO", monto=300000)
    db.registrar_finanza(fecha="2026-09-05", tipo="EGRESO", categoria="NOMINA", monto=500000)
    db.registrar_movimiento("V1", fecha="2026-09-10", tipo_movimiento="VENTA", precio=2000000)

    filas = db.flujo_caja_mensual("2026-08-01", "2026-09-30")
    por_mes = {f["mes"]: f for f in filas}
    assert por_mes["2026-08"]["ingresos"] == 1000000
    assert por_mes["2026-08"]["egresos"] == 300000
    assert por_mes["2026-08"]["utilidad"] == 700000
    assert por_mes["2026-09"]["ingresos"] == 2000000
    assert por_mes["2026-09"]["egresos"] == 500000


def test_kpis_financieros_costo_litro_y_margen(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_produccion_leche(fecha="2026-09-01", litros=100.0, animal_tag="47")
    db.registrar_produccion_leche(fecha="2026-09-02", litros=100.0, animal_tag="47")
    db.registrar_finanza(fecha="2026-09-01", tipo="INGRESO", categoria="VENTA_LECHE", monto=400000)
    db.registrar_finanza(fecha="2026-09-02", tipo="EGRESO", categoria="INSUMO", monto=100000)

    k = db.kpis_financieros("2026-09-01", "2026-09-30")
    assert k["litros_producidos"] == 200.0
    assert k["costo_por_litro_leche"] == 500.0  # 100000 egresos / 200 L
    assert k["margen_utilidad_pct"] == 75.0  # (400000-100000)/400000
    assert k["total_activos"] == 1
    assert k["costo_por_cabeza"] == 100000.0
    assert "flujo_mensual" in k


def test_kpis_financieros_costo_por_kg_carne_usa_ultimo_pesaje(db):
    db.registrar_animal("V1", sexo="Macho", estado="VENDIDO")
    db.registrar_pesaje(animal_tag="V1", fecha="2026-08-01", peso_kg=380)
    db.registrar_pesaje(animal_tag="V1", fecha="2026-08-20", peso_kg=420)  # el más reciente antes de vender
    db.registrar_movimiento("V1", fecha="2026-09-01", tipo_movimiento="VENTA", precio=3000000)
    db.registrar_finanza(fecha="2026-09-01", tipo="EGRESO", categoria="INSUMO", monto=420000)

    k = db.kpis_financieros("2026-09-01", "2026-09-30")
    assert k["kg_carne_estimados"] == 420.0
    assert k["ventas_con_peso"] == 1
    assert k["ventas_sin_peso"] == 0
    assert k["costo_por_kg_carne"] == 1000.0  # 420000 / 420 kg


def test_kpis_financieros_venta_sin_pesaje_queda_excluida(db):
    db.registrar_animal("V2", sexo="Macho", estado="VENDIDO")
    db.registrar_movimiento("V2", fecha="2026-09-01", tipo_movimiento="VENTA", precio=1000000)
    k = db.kpis_financieros("2026-09-01", "2026-09-30")
    assert k["ventas_sin_peso"] == 1
    assert k["ventas_con_peso"] == 0
    assert k["kg_carne_estimados"] == 0.0
    assert k["costo_por_kg_carne"] is None


def test_iep_promedio_hato(db):
    """Auditoría de SG mostró un IEP de 2,063 días (imposible) por huecos de
    registro -- el cálculo del bot debe excluir intervalos >730d por defecto
    para no repetir ese mismo problema."""
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2018-01-01")
    db.registrar_parto("V1", fecha="2023-01-01")
    db.registrar_parto("V1", fecha="2024-02-01")  # intervalo real: 396 días
    db.registrar_animal("V2", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2015-01-01")
    db.registrar_parto("V2", fecha="2020-01-01")
    db.registrar_parto("V2", fecha="2026-01-01")  # intervalo de 2192 días: hueco de registro

    res = db.iep_promedio_hato()
    assert res["n_intervalos"] == 1  # el intervalo de V2 se excluye por >730d
    assert res["iep_promedio_dias"] == 396

    res_completo = db.iep_promedio_hato(umbral_max_dias=None)
    assert res_completo["n_intervalos"] == 2


def test_iep_promedio_hato_sin_datos(db):
    assert db.iep_promedio_hato() is None


def test_dias_abiertos_promedio_hato(db):
    from datetime import date
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("V1", fecha="2026-01-01")  # sin servicio posterior: sigue "abierta"
    db.registrar_animal("V2", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("V2", fecha="2026-01-01")
    db.registrar_servicio("V2", fecha="2026-03-01")  # ya tiene servicio posterior: no cuenta

    res = db.dias_abiertos_promedio_hato(hoy=date(2026, 9, 1))
    assert res["n"] == 1
    assert res["dias_abiertos_promedio"] == 243  # 2026-01-01 -> 2026-09-01


def test_edad_primer_parto_promedio_meses(db):
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2024-01-01")
    db.registrar_parto("V1", fecha="2026-01-01")  # 24 meses exactos
    db.registrar_parto("V1", fecha="2027-06-01")  # 2do parto: no debe contar de nuevo

    res = db.edad_primer_parto_promedio_meses()
    assert res["n"] == 1
    assert 23.5 <= res["edad_primer_parto_meses"] <= 24.5


# --- Climatología CHIRPS y SPI (Alerta Temprana de Sequía) ---------------
def test_guardar_y_obtener_climatologia_lluvia(db):
    muestra = [45.0, 60.5, 30.2, 80.0]
    db.guardar_climatologia_lluvia(30, muestra, lat=3.4, lon=-74.1)
    obtenida = db.obtener_climatologia_lluvia(30)
    assert obtenida == muestra


def test_guardar_climatologia_lluvia_reemplaza_la_anterior(db):
    db.guardar_climatologia_lluvia(30, [1.0, 2.0])
    db.guardar_climatologia_lluvia(30, [3.0, 4.0, 5.0])
    obtenida = db.obtener_climatologia_lluvia(30)
    assert obtenida == [3.0, 4.0, 5.0]
    n = db.query_one("SELECT COUNT(*) n FROM climatologia_lluvia_chirps WHERE dias_ventana = 30")
    assert n["n"] == 1  # no se acumulan filas viejas


def test_obtener_climatologia_lluvia_ventanas_distintas_no_se_mezclan(db):
    db.guardar_climatologia_lluvia(30, [1.0, 2.0])
    db.guardar_climatologia_lluvia(60, [10.0, 20.0])
    assert db.obtener_climatologia_lluvia(30) == [1.0, 2.0]
    assert db.obtener_climatologia_lluvia(60) == [10.0, 20.0]


def test_obtener_climatologia_lluvia_inexistente_devuelve_none(db):
    assert db.obtener_climatologia_lluvia(90) is None


def test_obtener_climatologia_lluvia_vieja_devuelve_none(db):
    """Climatología calculada hace más de max_edad_dias se considera vencida
    (recomendación: refrescar ~1 vez al año para sumar el año recién cerrado)."""
    from datetime import date, timedelta
    fid = db.guardar_climatologia_lluvia(30, [1.0, 2.0])
    vieja = (date.today() - timedelta(days=400)).isoformat()
    db.execute("UPDATE climatologia_lluvia_chirps SET calculado_en = ? WHERE id = ?", (vieja, fid))
    assert db.obtener_climatologia_lluvia(30, max_edad_dias=365) is None


def test_registrar_y_obtener_ultimos_spi_sequia(db):
    db.registrar_spi_sequia(dias_ventana=30, mm_actual=10.0, spi_valor=-1.8, clasificacion="Sequía severa", fecha="2026-09-01")
    db.registrar_spi_sequia(dias_ventana=60, mm_actual=80.0, spi_valor=0.2, clasificacion="Normal", fecha="2026-09-01")
    # Segunda corrida del SPI-30: debe reemplazar cuál es "la última", no duplicarla.
    db.registrar_spi_sequia(dias_ventana=30, mm_actual=12.0, spi_valor=-1.5, clasificacion="Sequía severa", fecha="2026-09-08")

    filas = db.ultimos_spi_sequia()
    por_ventana = {f["dias_ventana"]: f for f in filas}
    assert len(filas) == 2  # una por ventana, no 3
    assert por_ventana[30]["fecha"] == "2026-09-08"  # la más reciente
    assert por_ventana[30]["mm_actual"] == 12.0
    assert por_ventana[60]["spi_valor"] == 0.2


def test_kpis_financieros_margenes_unitarios_dinamicos(db):
    # Registrar lechería
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_produccion_leche(fecha="2026-09-01", litros=200.0, animal_tag="47")
    db.registrar_finanza(fecha="2026-09-01", tipo="INGRESO", categoria="VENTA_LECHE", monto=400000, litros=200.0)
    db.registrar_finanza(fecha="2026-09-02", tipo="EGRESO", categoria="INSUMO", monto=100000)

    # Registrar venta de carne
    db.registrar_animal("T1", sexo="Macho", estado="VENDIDO")
    db.registrar_pesaje(animal_tag="T1", fecha="2026-08-25", peso_kg=400.0)
    db.registrar_movimiento("T1", fecha="2026-09-03", tipo_movimiento="VENTA", precio=3200000)

    k = db.kpis_financieros("2026-09-01", "2026-09-30")

    # Verificaciones de leche
    assert k["litros_producidos"] == 200.0
    assert k["ingresos_leche"] == 400000.0
    assert k["precio_promedio_litro_leche"] == 2000.0
    assert k["costo_por_litro_leche"] == 500.0
    assert k["margen_por_litro_leche"] == 1500.0
    assert k["margen_leche_pct"] == 75.0

    # Verificaciones de carne
    assert k["ingresos_carne"] == 3200000.0
    assert k["animales_vendidos"] == 1
    assert k["kg_carne_estimados"] == 400.0
    assert k["precio_promedio_kg_carne"] == 8000.0  # 3200000 / 400
    assert k["costo_por_kg_carne"] == 250.0  # 100000 / 400
    assert k["margen_por_kg_carne"] == 7750.0  # 8000 - 250
    assert k["margen_carne_pct"] == 96.9


def test_registrar_parto_idempotente_no_duplica(db):
    id1 = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho", id_cria_tag="47-1")
    id2 = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho", id_cria_tag="47-1")
    assert id1 == id2
    assert db.count("partos") == 1


def test_registrar_parto_gemelos_distinta_cria_crea_dos_filas(db):
    primer_id = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho",
                                   id_cria_tag="47-1", tipo_evento="GEMELAR")
    segundo_id = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Hembra",
                                    id_cria_tag="47-2", tipo_evento="GEMELAR",
                                    grupo_parto_id=primer_id)
    assert segundo_id != primer_id
    filas = db.query("SELECT * FROM partos ORDER BY id")
    assert len(filas) == 2
    assert filas[1]["grupo_parto_id"] == primer_id
    # Reintento offline del mismo batch no duplica ninguno de los dos.
    otra_vez_1 = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho",
                                    id_cria_tag="47-1", tipo_evento="GEMELAR")
    otra_vez_2 = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Hembra",
                                    id_cria_tag="47-2", tipo_evento="GEMELAR",
                                    grupo_parto_id=primer_id)
    assert otra_vez_1 == primer_id
    assert otra_vez_2 == segundo_id
    assert db.count("partos") == 2


def test_resiembra_forzada_preserva_precio_manual(db):
    db.sembrar_precios_mercado_iniciales()
    db.registrar_precio_mercado(plaza="GRANADA", producto="MACHO_GORDO", precio_promedio=9999.0,
                                fuente="MANUAL", fecha="2026-09-09", notas="precio del productor")
    db.sembrar_precios_mercado_iniciales(forzar=True)
    fila = db.query_one("SELECT * FROM precios_mercado WHERE fuente = 'MANUAL' AND precio_promedio = 9999.0")
    assert fila is not None


def test_registrar_parto_gemelos_reintento_preserva_grupo_parto_id(db):
    primer_id = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho",
                                   id_cria_tag="47-1", tipo_evento="GEMELAR")
    segundo_id = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Hembra",
                                    id_cria_tag="47-2", tipo_evento="GEMELAR",
                                    grupo_parto_id=primer_id)
    # Reintento offline del 2º gemelo con el mismo grupo: no duplica y el
    # grupo se conserva (antes quedaba en NULL por el retorno temprano).
    reintento_id = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Hembra",
                                      id_cria_tag="47-2", tipo_evento="GEMELAR",
                                      grupo_parto_id=primer_id)
    assert reintento_id == segundo_id
    assert db.count("partos") == 2
    fila = db.query_one("SELECT * FROM partos WHERE id = ?", (segundo_id,))
    assert fila["grupo_parto_id"] == primer_id


def test_registrar_parto_misma_cria_distinto_tipo_no_duplica(db):
    id1 = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho",
                             id_cria_tag="47-1", tipo_evento="PARTO")
    id2 = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho",
                             id_cria_tag="47-1", tipo_evento="GEMELAR",
                             grupo_parto_id=id1)
    assert id2 == id1
    assert db.count("partos") == 1


def test_registrar_parto_sin_cria_distinto_tipo_no_colisiona(db):
    id_aborto = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", tipo_evento="ABORTO")
    id_reabs = db.registrar_parto(vaca_tag="47", fecha="2026-06-01", tipo_evento="REABSORCION")
    assert id_aborto != id_reabs
    assert db.count("partos") == 2


# ---------------------------------------------------------------------------
# Chat de equipo: canal único de avisos (broadcast) entre usuarios de la PWA.
# ---------------------------------------------------------------------------
def test_registrar_mensaje_equipo_y_obtenerlo(db):
    mid = db.registrar_mensaje_equipo(user_id=1, nombre="Jaime", rol="owner", texto="  Revisar la cerca del potrero  ")
    assert isinstance(mid, int)
    fila = db.obtener_mensaje_equipo(mid)
    assert fila["nombre"] == "Jaime"
    assert fila["rol"] == "OWNER"  # normalizado a mayúsculas
    assert fila["texto"] == "Revisar la cerca del potrero"  # trim aplicado
    assert fila["creado_en"] is not None


def test_obtener_mensaje_equipo_inexistente_devuelve_none(db):
    assert db.obtener_mensaje_equipo(99999) is None


def test_listar_mensajes_equipo_carga_inicial_orden_cronologico(db):
    db.registrar_mensaje_equipo(user_id=1, nombre="Jaime", rol="OWNER", texto="Uno")
    db.registrar_mensaje_equipo(user_id=2, nombre="Carlos", rol="TRABAJADOR", texto="Dos")
    filas = db.listar_mensajes_equipo()
    assert [f["texto"] for f in filas] == ["Uno", "Dos"]


def test_listar_mensajes_equipo_polling_incremental(db):
    id1 = db.registrar_mensaje_equipo(user_id=1, nombre="Jaime", rol="OWNER", texto="Uno")
    db.registrar_mensaje_equipo(user_id=2, nombre="Carlos", rol="TRABAJADOR", texto="Dos")
    filas = db.listar_mensajes_equipo(despues_de_id=id1)
    assert len(filas) == 1
    assert filas[0]["texto"] == "Dos"


def test_listar_mensajes_equipo_respeta_limite_y_tope_maximo(db):
    for i in range(5):
        db.registrar_mensaje_equipo(user_id=1, nombre="Jaime", rol="OWNER", texto=f"Msg {i}")
    filas = db.listar_mensajes_equipo(limite=2)
    assert len(filas) == 2
    assert [f["texto"] for f in filas] == ["Msg 3", "Msg 4"]  # los últimos 2, en orden ascendente


def test_eliminar_mensaje_equipo_borra_solo_ese(db):
    id1 = db.registrar_mensaje_equipo(user_id=1, nombre="Jaime", rol="OWNER", texto="Uno")
    id2 = db.registrar_mensaje_equipo(user_id=2, nombre="Carlos", rol="TRABAJADOR", texto="Dos")
    assert db.eliminar_mensaje_equipo(id1) is True
    assert db.obtener_mensaje_equipo(id1) is None
    assert db.obtener_mensaje_equipo(id2) is not None


def test_eliminar_mensaje_equipo_inexistente_devuelve_false(db):
    assert db.eliminar_mensaje_equipo(99999) is False


# ---------------------------------------------------------------------------
# transaccion(): agrupa varias escrituras en un solo COMMIT (usado por el
# import de Software Ganadero para no exponer conteos parciales a lectores
# concurrentes, ej. el Tablero de la PWA, mientras procesa ~1500+ registros).
# ---------------------------------------------------------------------------
def test_transaccion_agrupa_escrituras_invisibles_hasta_el_commit(tmp_path):
    from src.db.database import Database

    ruta = str(tmp_path / "transaccion.db")
    d = Database(ruta)
    d.create_tables()
    lector = Database(ruta)
    try:
        with d.transaccion():
            d.registrar_animal("A1", sexo="Hembra", estado="ACTIVO")
            d.registrar_animal("A2", sexo="Macho", estado="ACTIVO")
            # Un lector en otra conexión no debe ver nada mientras el
            # bloque `with` sigue abierto (todavía no hubo COMMIT).
            assert lector.count("animales") == 0
        # Al salir del bloque ya se commiteó todo de una sola vez.
        assert lector.count("animales") == 2
        assert d.count("animales") == 2
    finally:
        d.close()
        lector.close()


def test_transaccion_hace_rollback_completo_si_algo_falla(tmp_path):
    import pytest
    from src.db.database import Database

    ruta = str(tmp_path / "transaccion_rollback.db")
    d = Database(ruta)
    d.create_tables()
    try:
        with pytest.raises(ValueError):
            with d.transaccion():
                d.registrar_animal("B1", sexo="Hembra", estado="ACTIVO")
                raise ValueError("fallo simulado a mitad del import")
        # Ni B1 quedó a medias: el rollback deshizo todo el bloque.
        assert d.count("animales") == 0
    finally:
        d.close()


def test_transaccion_anidada_no_abre_una_segunda(db):
    # Si el código que ya está dentro de una transaccion() llama a otra
    # función que también usa `with db.transaccion():`, no debe intentar
    # abrir un segundo BEGIN (SQLite no permite transacciones anidadas).
    with db.transaccion():
        with db.transaccion():
            db.registrar_animal("C1", sexo="Hembra", estado="ACTIVO")
        # La transacción interna no cerró la externa.
        assert db._en_transaccion is True
    assert db.count("animales") == 1




