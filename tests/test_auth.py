"""Pruebas unitarias de autenticación y control de acceso RBAC (Auth)."""
import json
import logging
import pytest

from src.server.auth import Auth


def test_auth_crea_archivo_vacio_si_no_existe(tmp_path):
    archivo = tmp_path / "subdir" / "users.json"
    assert not archivo.exists()

    auth = Auth(users_file=str(archivo))
    assert auth.usuarios == []
    assert archivo.exists()
    assert json.loads(archivo.read_text(encoding="utf-8")) == []


def test_auth_carga_usuarios_existentes(tmp_path):
    archivo = tmp_path / "users.json"
    datos_iniciales = [
        {"user_id": 111, "nombre": "Admin Vaca", "rol": "OWNER"},
        {"user_id": 222, "nombre": "Peon Campo", "rol": "TRABAJADOR"},
    ]
    archivo.write_text(json.dumps(datos_iniciales), encoding="utf-8")

    auth = Auth(users_file=str(archivo))
    assert len(auth.usuarios) == 2
    assert auth.es_autorizado(111) is True
    assert auth.es_autorizado(222) is True
    assert auth.es_autorizado(999) is False
    assert auth.rol_de(111) == "OWNER"
    assert auth.rol_de(222) == "TRABAJADOR"
    assert auth.rol_de(999) is None


def test_auth_json_corrupto_o_invalido_levanta_error(tmp_path):
    archivo_corrupto = tmp_path / "corrupto.json"
    archivo_corrupto.write_text("{ esto no es json válido }", encoding="utf-8")

    with pytest.raises(ValueError, match="corrupto o inválido"):
        Auth(users_file=str(archivo_corrupto))

    archivo_no_lista = tmp_path / "no_lista.json"
    archivo_no_lista.write_text(json.dumps({"user_id": 1}), encoding="utf-8")

    with pytest.raises(ValueError, match="se esperaba una lista"):
        Auth(users_file=str(archivo_no_lista))

    archivo_malformado = tmp_path / "malformado.json"
    archivo_malformado.write_text(json.dumps([{"invalido": True}]), encoding="utf-8")

    with pytest.raises(ValueError, match="Usuario inválido"):
        Auth(users_file=str(archivo_malformado))


def test_permisos_por_rol(tmp_path):
    archivo = tmp_path / "users.json"
    auth = Auth(users_file=str(archivo))
    auth.agregar_usuario(10, "Duenio", "OWNER")
    auth.agregar_usuario(20, "Veterinario", "ADMIN")
    auth.agregar_usuario(30, "Mayordomo", "TRABAJADOR")

    # OWNER: puede todo
    assert auth.puede_consultar(10) is True
    assert auth.puede_administrar(10) is True
    assert auth.puede_gestionar_usuarios(10) is True
    assert auth.es_owner(10) is True
    assert auth.es_admin(10) is False

    # ADMIN: consultar y administrar, pero no gestionar usuarios
    assert auth.puede_consultar(20) is True
    assert auth.puede_administrar(20) is True
    assert auth.puede_gestionar_usuarios(20) is False
    assert auth.es_owner(20) is False
    assert auth.es_admin(20) is True

    # TRABAJADOR: solo consultar
    assert auth.puede_consultar(30) is True
    assert auth.puede_administrar(30) is False
    assert auth.puede_gestionar_usuarios(30) is False

    # Usuario desconocido / no registrado
    assert auth.puede_consultar(999) is False
    assert auth.puede_administrar(999) is False
    assert auth.puede_gestionar_usuarios(999) is False


def test_agregar_y_actualizar_usuario(tmp_path):
    archivo = tmp_path / "users.json"
    auth = Auth(users_file=str(archivo))

    # Agregar nuevo
    auth.agregar_usuario(101, "Pedro", "trabajador")
    assert auth.es_autorizado(101) is True
    assert auth.rol_de(101) == "TRABAJADOR"

    # Verificar persistencia en disco
    auth2 = Auth(users_file=str(archivo))
    assert auth2.es_autorizado(101) is True
    assert auth2.rol_de(101) == "TRABAJADOR"

    # Actualizar existente
    auth.agregar_usuario(101, "Pedro Sanchez", "ADMIN")
    assert auth.rol_de(101) == "ADMIN"
    lista = auth.listar_usuarios()
    assert len(lista) == 1
    assert lista[0]["nombre"] == "Pedro Sanchez"
    assert lista[0]["rol"] == "ADMIN"


def test_agregar_usuario_rol_invalido_o_id_invalido(tmp_path):
    archivo = tmp_path / "users.json"
    auth = Auth(users_file=str(archivo))

    with pytest.raises(ValueError, match="Rol inválido"):
        auth.agregar_usuario(101, "Pedro", "SUPERUSER")

    with pytest.raises(ValueError, match="user_id inválido"):
        auth.agregar_usuario("no-un-numero", "Pedro", "OWNER")


def test_quitar_usuario_y_proteccion_ultimo_owner(tmp_path):
    archivo = tmp_path / "users.json"
    auth = Auth(users_file=str(archivo))

    auth.agregar_usuario(1, "Owner 1", "OWNER")
    auth.agregar_usuario(2, "Trabajador 1", "TRABAJADOR")

    # Eliminar trabajador
    auth.quitar_usuario(2)
    assert auth.es_autorizado(2) is False
    assert len(auth.listar_usuarios()) == 1

    # Intentar eliminar usuario que no existe
    with pytest.raises(ValueError, match="no existe"):
        auth.quitar_usuario(999)

    # Intentar eliminar al único OWNER
    with pytest.raises(ValueError, match="único OWNER"):
        auth.quitar_usuario(1)

    # Agregar un segundo OWNER y eliminar uno de ellos
    auth.agregar_usuario(3, "Owner 2", "OWNER")
    auth.quitar_usuario(1)
    assert auth.es_autorizado(1) is False
    assert auth.es_autorizado(3) is True

    # Ahora el 3 es el único OWNER y no debe poder ser eliminado
    with pytest.raises(ValueError, match="único OWNER"):
        auth.quitar_usuario(3)


def test_auth_logging_intentos_denegados(tmp_path, caplog):
    archivo = tmp_path / "users.json"
    auth = Auth(users_file=str(archivo))
    auth.agregar_usuario(1, "Owner 1", "OWNER")

    with caplog.at_level(logging.WARNING, logger="bitacora.auth"):
        auth.es_autorizado(999)
        auth.puede_administrar(999)
        auth.puede_gestionar_usuarios(999)

    mensajes = [record.message for record in caplog.records if record.name == "bitacora.auth"]
    assert any("no autorizado" in m.lower() for m in mensajes)
    assert any("denegado" in m.lower() for m in mensajes)


def test_auth_telegram_id_y_avatar(tmp_path):
    archivo = tmp_path / "users.json"
    auth = Auth(users_file=str(archivo))
    auth.agregar_usuario(
        user_id=1,
        nombre="Don José",
        rol="OWNER",
        pin="1234",
        telegram_id=6123051140,
        avatar="patron"
    )

    # Verificar autorización por ID local y por telegram_id
    assert auth.es_autorizado(1) is True
    assert auth.es_autorizado(6123051140) is True
    assert auth.rol_de(1) == "OWNER"
    assert auth.rol_de(6123051140) == "OWNER"

    # Autenticación PIN
    u = auth.autenticar_pin("1234")
    assert u is not None
    assert u["user_id"] == 1
    assert u["telegram_id"] == 6123051140
    assert u["avatar"] == "patron"
    assert u["nombre"] == "Don José"

    # PIN incorrecto (mismo largo y distinto largo) no autentica -- regresión
    # del cambio de == a hmac.compare_digest, que no debe alterar el
    # resultado, solo hacerlo en tiempo constante.
    assert auth.autenticar_pin("4321") is None
    assert auth.autenticar_pin("12345") is None
    assert auth.autenticar_pin("123") is None
    assert auth.autenticar_pin("") is None


def test_auth_actualizar_usuario_preserva_telegram_id(tmp_path):
    archivo = tmp_path / "users.json"
    auth = Auth(users_file=str(archivo))
    auth.agregar_usuario(
        user_id=1,
        nombre="Jaime",
        rol="OWNER",
        pin="1144",
        telegram_id=6123051140,
        avatar="patron"
    )

    # Actualizar solo nombre y rol sin pasar telegram_id
    auth.agregar_usuario(
        user_id=1,
        nombre="Jaime Actualizado",
        rol="OWNER",
        pin="1144",
    )
    u = auth.obtener_usuario(1)
    assert u is not None
    assert u["nombre"] == "Jaime Actualizado"
    # Debe preservar el telegram_id
    assert u["telegram_id"] == 6123051140
    assert auth.es_autorizado(6123051140) is True

    # Si se pide explícitamente borrar_telegram_id=True
    auth.agregar_usuario(
        user_id=1,
        nombre="Jaime Actualizado",
        rol="OWNER",
        pin="1144",
        borrar_telegram_id=True,
    )
    u2 = auth.obtener_usuario(1)
    assert u2["telegram_id"] is None
    assert auth.es_autorizado(6123051140) is False


