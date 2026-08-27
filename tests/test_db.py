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

