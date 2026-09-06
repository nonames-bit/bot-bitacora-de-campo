"""Pruebas unitarias de la lógica pura del bot de Telegram (sin red ni dependencias externas)."""
from datetime import date
import os
import pytest

from src.db.database import Database
from src.server.auth import Auth
from src.server.telegram_bot import (
    construir_application,
    descartar_backup_pendiente,
    formatear_alertas,
    formatear_animales,
    formatear_ayuda,
    formatear_fotos,
    formatear_historial,
    formatear_instrucciones_importar,
    formatear_potreros,
    formatear_reporte_importacion,
    formatear_status,
    formatear_usuarios,
    guardar_backup_pendiente,
    obtener_backup_pendiente,
    obtener_ultimos_logs,
)


def test_formatear_alertas_vacio(db):
    resp = formatear_alertas(db)
    assert "No hay alertas pendientes" in resp


def test_formatear_alertas_con_datos(db):
    db.registrar_animal(tag="47")
    db.registrar_alerta("47", "ECOGRAFIA", "2026-09-15", descripcion="Ecografía día 35")
    db.registrar_alerta("47", "PALPACION", "2026-10-15", descripcion="Palpación rectal")

    resp = formatear_alertas(db)
    assert "Alertas pendientes (2)" in resp
    assert "Tag 47" in resp
    assert "ECOGRAFIA" in resp
    assert "PALPACION" in resp
    assert "2026-09-15" in resp


def test_formatear_animales_vacio(db):
    resp = formatear_animales(db)
    assert "0 registrados" in resp


def test_formatear_animales_con_datos(db):
    db.registrar_animal(tag="101", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal(tag="102", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal(tag="201", sexo="Macho", estado="DESCARTADO")

    resp = formatear_animales(db)
    assert "Activos: 2" in resp
    assert "♀ 2" in resp
    assert "♂ 0" in resp
    assert "Histórico total" not in resp


def test_formatear_animales_cuenta_solo_activos(db):
    db.registrar_animal(tag="101", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal(tag="102", sexo="Macho", estado="ACTIVO")
    db.registrar_animal(tag="103", sexo="Hembra", estado="MUERTO")
    db.registrar_animal(tag="104", sexo="Macho", estado="VENDIDO")

    resp = formatear_animales(db)
    assert "Activos: 2" in resp
    assert "♀ 1" in resp
    assert "♂ 1" in resp
    assert "Histórico total" not in resp


def test_formatear_status_memoria_y_archivo(db, tmp_path):
    # En memoria
    db.registrar_animal(tag="47", estado="ACTIVO")
    db.registrar_potrero(nombre="Norte", dias_reposo=35)
    db.registrar_parto("47", "2026-08-15", sexo_cria="Macho")
    db.registrar_pesaje("47", "2026-08-20", peso_kg=120, evento="DESTETE")
    db.registrar_alerta("47", "SECADO", "2026-11-01")

    resp_mem = formatear_status(db, ":memory:", hoy=date(2026, 9, 1))
    assert "Activos" in resp_mem and "GANADERIA-JA" in resp_mem
    assert "Histórico:" not in resp_mem
    assert "Partos últimos 30d:" in resp_mem
    assert "Destetes últimos 30d:" in resp_mem
    assert "Norte (35d)" in resp_mem
    assert "Alertas pendientes:" in resp_mem
    assert "en memoria" in resp_mem
    assert "<pre>" not in resp_mem
    assert "<b>Activos:</b>" in resp_mem
    assert "<i>Actualizado:" in resp_mem

    # Con archivo físico
    db_file = tmp_path / "test.db"
    db_fisica = Database(str(db_file))
    db_fisica.create_tables()
    db_fisica.registrar_animal(tag="99")
    resp_file = formatear_status(db_fisica, str(db_file))
    assert "MB" in resp_file
    db_fisica.close()


def test_formatear_status_filtrado_finca_y_sin_historico(db):
    # Base con animales activos, históricos y potrero abandonado con reposo absurdo (>365d)
    db.registrar_animal(tag="A1", estado="ACTIVO", potrero="01")
    db.registrar_animal(tag="A2", estado="ACTIVO", potrero="01")
    db.registrar_animal(tag="H1", estado="MUERTO", potrero="01")
    db.registrar_animal(tag="H2", estado="VENDIDO", potrero="02")

    # Potrero activo con reposo real de 45 días
    db.registrar_potrero(nombre="POTRERO CASA", codigo="01", dias_reposo=45)
    # Potrero histórico/abandonado con 3.232 días de reposo (no debe mostrarse)
    db.registrar_potrero(nombre="JARA", codigo="99", dias_reposo=3232)

    resp = formatear_status(db, hoy=date(2026, 9, 1))

    # 1. Muestra Activos con nombre/código de finca
    assert "Activos" in resp and "GANADERIA-JA" in resp and "2" in resp
    # 2. No muestra Histórico
    assert "Histórico:" not in resp
    # 3. Potrero con más reposo no debe ser JARA sino POTRERO CASA
    assert "POTRERO CASA (45d)" in resp
    assert "JARA" not in resp


def test_formatear_usuarios(tmp_path):
    archivo = tmp_path / "users.json"
    auth = Auth(users_file=str(archivo))

    # Vacío
    resp_vacio = formatear_usuarios(auth)
    assert "No hay usuarios registrados" in resp_vacio

    # Con usuarios
    auth.agregar_usuario(111, "Juan", "OWNER")
    auth.agregar_usuario(222, "Carlos", "TRABAJADOR")
    resp = formatear_usuarios(auth)
    assert "Usuarios registrados (2)" in resp
    assert "111" in resp
    assert "Juan" in resp
    assert "OWNER" in resp
    assert "222" in resp
    assert "Carlos" in resp


def test_formatear_historial(db):
    db.registrar_animal(tag="47")
    db.registrar_parto("47", fecha="2026-05-01")
    resp = formatear_historial(db, "47")
    assert "FICHA ZOOTÉCNICA" in resp or "47" in resp
    assert "partos: 1" in resp

    resp_vacio = formatear_historial(db, "")
    assert "De cuál animal desea" in resp_vacio


def test_formatear_potreros(db):
    db.registrar_potrero(nombre="Potrero Norte", dias_reposo=30, aforo_kg_m2=0.6)
    resp = formatear_potreros(db)
    assert "Potrero Norte" in resp


def test_formatear_potreros_con_argumento(db):
    db.registrar_potrero(nombre="Olegario 1", codigo="01")
    db.registrar_animal("JA400", potrero="01", estado="ACTIVO")
    resp = formatear_potreros(db, potrero="olegario 1")
    assert "Olegario 1" in resp
    assert "1 animal" in resp
    assert "JA400" in resp


def test_formatear_ayuda():
    ayuda_owner = formatear_ayuda("OWNER")
    assert "Propietario / OWNER" in ayuda_owner
    assert "/agregar_usuario" in ayuda_owner
    assert "/logs" in ayuda_owner
    assert "🆘 ¿Agregar un trabajador nuevo?" in ayuda_owner
    assert "@userinfobot" in ayuda_owner
    assert "/alertas" in ayuda_owner
    assert "/importar" in ayuda_owner
    assert "/confirmar_importar" in ayuda_owner
    assert "/descartar_backup" in ayuda_owner
    assert "/deshacer" in ayuda_owner
    assert "/confirmar_deshacer" in ayuda_owner
    assert "/ultimos" in ayuda_owner
    assert "restaurar_backup.sh" in ayuda_owner
    assert "/grafico" in ayuda_owner
    assert "/renombrar_animal" in ayuda_owner

    ayuda_admin = formatear_ayuda("ADMIN")
    assert "Administrador" in ayuda_admin
    assert "/alertas" in ayuda_admin
    assert "/importar" in ayuda_admin
    assert "/confirmar_importar" in ayuda_admin
    assert "/descartar_backup" in ayuda_admin
    assert "/agregar_usuario" not in ayuda_admin
    assert "¿Agregar un trabajador nuevo?" not in ayuda_admin
    assert "/renombrar_animal" in ayuda_admin

    ayuda_trabajador = formatear_ayuda("TRABAJADOR")
    assert "Trabajador / Campo" in ayuda_trabajador
    assert "/alertas" not in ayuda_trabajador
    assert "Envía notas de texto" in ayuda_trabajador

    ayuda_anon = formatear_ayuda(None)
    assert "No autorizado" in ayuda_anon


def test_obtener_ultimos_logs(tmp_path):
    log_file = tmp_path / "bot.log"

    # Archivo no existe
    resp_inexistente = obtener_ultimos_logs(str(log_file))
    assert "no existe" in resp_inexistente

    # Archivo vacío
    log_file.write_text("", encoding="utf-8")
    assert "está vacío" in obtener_ultimos_logs(str(log_file))

    # Archivo con 30 líneas
    lineas = [f"Log linea {i}\n" for i in range(1, 31)]
    log_file.write_text("".join(lineas), encoding="utf-8")

    resp = obtener_ultimos_logs(str(log_file), lineas=20)
    assert "Log linea 30" in resp
    assert "Log linea 11" in resp
    assert "Log linea 10" not in resp  # Solo las últimas 20 (de 11 a 30)


# ---------------------------------------------------------------------------
# Pruebas de las funciones puras de importación de backup
# ---------------------------------------------------------------------------
def test_formatear_reporte_importacion():
    # Caso con registros nuevos y duplicados
    conteos = {
        "potreros": {"nuevos": 5, "duplicados": 0},
        "animales": {"nuevos": 120, "duplicados": 10},
        "partos": {"nuevos": 40, "duplicados": 5},
        "celos": {"nuevos": 15, "duplicados": 2},
        "servicios": {"nuevos": 30, "duplicados": 0},
        "pesajes": {"nuevos": 80, "duplicados": 10},
        "traslados": {"nuevos": 25, "duplicados": 0},
        "muertes": {"nuevos": 2, "duplicados": 1},
    }
    reporte = formatear_reporte_importacion(conteos)
    assert "Reporte de Importación de Backup" in reporte
    assert "Total consolidado: 317 nuevos, 28 duplicados" in reporte
    assert "• partos: 40 nuevos, 5 duplicados" in reporte
    assert "• animales: 120 nuevos, 10 duplicados" in reporte

    # Caso todo duplicados
    conteos_dup = {
        "animales": {"nuevos": 0, "duplicados": 50},
        "partos": {"nuevos": 0, "duplicados": 20},
    }
    reporte_dup = formatear_reporte_importacion(conteos_dup)
    assert "Total consolidado: 0 nuevos, 70 duplicados" in reporte_dup

    # Caso vacío
    assert "No se procesaron registros" in formatear_reporte_importacion({})


def test_formatear_instrucciones_importar():
    instrucciones = formatear_instrucciones_importar()
    assert ".zip" in instrucciones
    assert "/confirmar_importar" in instrucciones
    assert "/descartar_backup" in instrucciones
    assert "20MB" in instrucciones
    assert "importar_backup.sh" in instrucciones


def test_gestion_backup_pendiente(tmp_path):
    uploads = tmp_path / "uploads"
    uploads_dir = str(uploads)

    # Inicialmente no hay pendiente
    assert obtener_backup_pendiente(uploads_dir) is None
    assert descartar_backup_pendiente(uploads_dir) is False

    # Crear un archivo de backup simulado
    uploads.mkdir(parents=True, exist_ok=True)
    zip_fake = uploads / "backup_123.zip"
    import zipfile
    with zipfile.ZipFile(str(zip_fake), "w") as zf:
        zf.writestr("test.txt", "contenido")

    # Guardar pendiente
    guardar_backup_pendiente(str(zip_fake), uploads_dir=uploads_dir)

    # Verificar que se obtiene correctamente
    pendiente = obtener_backup_pendiente(uploads_dir=uploads_dir)
    assert pendiente is not None
    assert os.path.exists(pendiente)
    assert os.path.samefile(pendiente, str(zip_fake))

    # Descartar pendiente
    eliminado = descartar_backup_pendiente(uploads_dir=uploads_dir)
    assert eliminado is True
    assert not zip_fake.exists()
    assert obtener_backup_pendiente(uploads_dir=uploads_dir) is None


def test_formatear_fotos_vacio_y_con_datos(db):
    assert "No hay fotos registradas" in formatear_fotos(db)
    assert "No hay fotos registradas para el animal 47" in formatear_fotos(db, "47")

    db.registrar_animal("47")
    db.registrar_foto("media/f1.jpg", animal_tag="47", caption="Foto lateral")

    resp_vaca = formatear_fotos(db, "47")
    assert "Fotos de la 47 (1)" in resp_vaca
    assert "f1.jpg" in resp_vaca
    assert "Foto lateral" in resp_vaca

    resp_ultimas = formatear_fotos(db)
    assert "Últimas fotos registradas (1)" in resp_ultimas
    assert "Tag 47" in resp_ultimas


def test_ayuda_trabajador_incluye_consulta_y_fotos():
    ayuda = formatear_ayuda("TRABAJADOR")
    assert "/consulta" in ayuda
    assert "/fotos" in ayuda
    assert "transcripción automática" in ayuda


def test_formatear_historial_con_tag_alfanumerico(db):
    db.registrar_animal(tag="N069", nombre="Negra", raza="Gyr")
    db.registrar_parto(vaca_tag="N069", fecha="2026-08-23", sexo_cria="Macho")

    resp = formatear_historial(db, "N069")
    assert "FICHA ZOOTÉCNICA" in resp
    assert "N069" in resp
    assert "Negra" in resp
    assert "partos: 1" in resp


def test_construir_application_registra_callback_handler():
    import pathlib
    content = pathlib.Path("src/server/telegram_bot.py").read_text(encoding="utf-8")
    assert "CallbackQueryHandler" in content
    assert "callback" in content.lower()
    assert "InlineKeyboard" in content


def test_formatear_animales_sg_brackets_y_filtro_activos(db):
    hoy = date(2026, 9, 1)

    # Sembrar animales con edades conocidas
    db.registrar_animal(tag="H01", sexo="Hembra", fecha_nacimiento="2026-01-01", estado="ACTIVO")  # <1
    db.registrar_animal(tag="H02", sexo="Hembra", fecha_nacimiento="2024-01-01", estado="ACTIVO")  # 2-4
    db.registrar_animal(tag="M01", sexo="Macho", fecha_nacimiento="2026-02-01", estado="ACTIVO")   # <1
    db.registrar_animal(tag="M02", sexo="Macho", nombre="TORO PADRON", fecha_nacimiento="2022-01-01", estado="ACTIVO")  # Reproductor
    db.registrar_animal(tag="H_DESC", sexo="Hembra", estado="DESCARTADO")

    resp = formatear_animales(db, hoy=hoy)

    assert "Resumen General de Inventario" in resp
    assert "<pre>" in resp
    assert "</pre>" in resp
    assert "Hembras &lt;1 año" in resp or "Hembras <1 año" in resp
    assert "Hembras 2-4 años" in resp
    assert "Machos &lt;1 año" in resp or "Machos <1 año" in resp
    assert "Reproductor" in resp
    assert "Hembras 2 | Machos 2 | Total 4" in resp
    assert "Activos: 4" in resp
    assert "♀ 2" in resp
    assert "♂ 2" in resp
    assert "Histórico total" not in resp
    assert "H_DESC" not in resp


def test_texto_ejemplo_evento():
    from src.server.telegram_bot import texto_ejemplo_evento
    ej_parto = texto_ejemplo_evento("parto")
    assert "pario la 47" in ej_parto

    ej_celo = texto_ejemplo_evento("celo")
    assert "AM-PM" in ej_celo

    ej_serv = texto_ejemplo_evento("servicio")
    assert "pajuela" in ej_serv

    ej_trat = texto_ejemplo_evento("tratamiento")
    assert "retiro" in ej_trat


def test_guias_didacticas_trabajador():
    from src.server.telegram_bot import (
        texto_guia_animal,
        texto_guia_audios,
        texto_guia_chat_hub,
        texto_guia_consultas,
        texto_guia_fotos,
        texto_guia_preguntas_animal,
        texto_guia_preguntas_potreros,
        texto_guia_preguntas_reproduccion,
        texto_guia_preguntas_sanidad,
        texto_guia_voz_fotos,
    )
    g_cons = texto_guia_consultas()
    assert "patricia" in g_cons
    assert "potrero" in g_cons
    assert "parto" in g_cons

    g_hub = texto_guia_chat_hub()
    assert "PREGUNTAR" in g_hub
    assert "campo" in g_hub

    g_anim = texto_guia_preguntas_animal()
    assert "Ubicación" in g_anim
    assert "Partos" in g_anim
    assert "47" in g_anim

    g_potr = texto_guia_preguntas_potreros()
    assert "Potreros" in g_potr
    assert "santa martha" in g_potr

    g_rep = texto_guia_preguntas_reproduccion()
    assert "abiertas" in g_rep
    assert "Partos" in g_rep

    g_san = texto_guia_preguntas_sanidad()
    assert "retiro" in g_san
    assert "leche" in g_san

    g_vf = texto_guia_voz_fotos()
    assert "Whisper" in g_vf
    assert "OCR" in g_vf

    g_fotos = texto_guia_fotos()
    assert "Aretes" in g_fotos
    assert "Remedios" in g_fotos or "Medicamentos" in g_fotos
    assert "retiro" in g_fotos

    g_audios = texto_guia_audios()
    assert "micrófono" in g_audios
    assert "transcribe" in g_audios

    g_animal = texto_guia_animal()
    assert "/consulta" in g_animal
    assert "fotografía" in g_animal


def test_texto_menu_principal():
    from src.server.telegram_bot import texto_menu_principal
    menu_owner = texto_menu_principal("OWNER")
    assert "Dueño" in menu_owner
    assert "Panel de Control" in menu_owner

    menu_admin = texto_menu_principal("ADMIN")
    assert "Administrador" in menu_admin

    menu_trabajador = texto_menu_principal("TRABAJADOR")
    assert "Trabajador de Campo" in menu_trabajador
    assert "cuaderno digital" in menu_trabajador

    menu_anon = texto_menu_principal(None)
    assert "No autorizado" in menu_anon


def test_formatear_tablero_finca(db):
    from src.server.telegram_bot import formatear_tablero_finca
    hoy = date(2026, 9, 1)
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("26", sexo="Macho", estado="ACTIVO")
    db.registrar_parto("47", "2026-08-28", sexo_cria="Hembra")
    db.registrar_celo("47", "2026-08-29")
    db.registrar_servicio("47", "2026-08-30", tipo_servicio="IA", toro_pajilla="TORO1")
    db.registrar_tratamiento("47", "2026-08-29", producto="Oxitetraciclina", dias_retiro_carne=10)
    db.registrar_pesaje("47", "2026-08-27", peso_kg=450, gmd_calculada=500.0)
    db.registrar_alerta("47", "ECOGRAFIA", "2026-09-04")
    db.registrar_potrero(nombre="Potrero 1", dias_reposo=40)

    resp = formatear_tablero_finca(db, hoy=hoy)
    assert "Tablero de Control Zootécnico" in resp
    assert "HATO ACTIVO" in resp
    assert "NOVEDADES DE LA SEMANA" in resp
    assert "Partos:" in resp
    assert "Celos observados:" in resp
    assert "Inseminaciones / Servicios:" in resp
    assert "Tratamientos médicos:" in resp
    assert "ALERTAS & TAREAS" in resp
    assert "PASTURAS & ROTACIÓN VOISIN" in resp


def test_formatear_estado_servidor(db, tmp_path):
    from src.server.telegram_bot import formatear_estado_servidor
    from src.server.auth import Auth

    users_file = tmp_path / "users.json"
    auth = Auth(str(users_file))
    auth.agregar_usuario(111, "Carlos", "OWNER")
    auth.agregar_usuario(222, "Juan", "TRABAJADOR")

    resp = formatear_estado_servidor(db, auth, ":memory:")
    assert "Tablero Técnico del Servidor & Sistema" in resp
    assert "SERVIDOR VPS" in resp
    assert "BASE DE DATOS" in resp
    assert "USUARIOS AUTORIZADOS (2)" in resp
    assert "OWNER" in resp
    assert "TRABAJADOR" in resp
    assert "INTEGRACIÓN DE MODELOS & APIS" in resp
    assert "Whisper" in resp
    assert "Pytesseract" in resp
    # Regresión real: sin registro explícito de importaciones de Software
    # Ganadero, no había forma de confirmar "¿ya está usando el backup de
    # hoy?" salvo adivinar por la fecha de modificación del .db.
    assert "Último backup importado" in resp
    assert "Nunca" in resp

    db.registrar_import_sg("Datos20260830.Zip", {"animales": {"nuevos": 5, "duplicados": 1}})
    resp2 = formatear_estado_servidor(db, auth, ":memory:")
    assert "Datos20260830.Zip" in resp2
    assert "5 nuevos" in resp2


def test_formatear_panel_medicamentos(db):
    from src.server.telegram_bot import formatear_panel_medicamentos
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_tratamiento(
        "47",
        date.today().isoformat(),
        producto="Oxitetraciclina",
        dosis="20ml",
        dias_retiro_leche=5,
        dias_retiro_carne=28,
        diagnostico="Mastitis",
    )
    resp = formatear_panel_medicamentos(db)
    assert "Control Sanitario, Medicamentos & Retiros" in resp
    assert "ANIMALES EN RETIRO ACTIVO" in resp
    assert "47" in resp
    assert "Oxitetraciclina" in resp
    assert "Fin leche:" in resp


def test_paneles_textos_guia():
    from src.server.telegram_bot import (
        formatear_panel_buscar_animal_texto,
        formatear_panel_preguntas_rapidas_texto,
    )
    t_buscar = formatear_panel_buscar_animal_texto()
    assert "Buscador de Animales & Fichas Zootécnicas" in t_buscar
    assert "patricia" in t_buscar

    t_faq = formatear_panel_preguntas_rapidas_texto()
    assert "Consultas Rápidas de Campo (1-Toque)" in t_faq


def test_construir_application_y_teclado_buscar(db, tmp_path):
    pytest.importorskip("telegram")
    from src.server.auth import Auth

    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("N069", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("47", date.today().isoformat(), sexo_cria="Macho")

    users_file = tmp_path / "users.json"
    auth = Auth(str(users_file))
    auth.agregar_usuario(111, "Dueño", "OWNER")

    app = construir_application(
        token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        db=db,
        auth=auth,
    )
    assert app is not None


def test_filtros_busqueda_sql_queries(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2020-01-01")
    db.registrar_animal("TORO1", sexo="Macho", estado="ACTIVO")
    db.registrar_animal("CRIA1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2026-08-01")
    db.registrar_parto("47", "2026-08-20", sexo_cria="Hembra")
    db.registrar_servicio("47", "2026-08-25", tipo_servicio="IA", toro_pajilla="TORO1")
    db.registrar_pesaje("47", "2026-08-27", peso_kg=450)

    # 1. Paridas
    q_paridas = db.query(
        """
        SELECT DISTINCT a.tag, a.nombre, p.fecha FROM partos p
        JOIN animales a ON a.id_animal = p.vaca_id
        WHERE a.estado = 'ACTIVO' AND a.sexo LIKE 'H%'
        ORDER BY p.fecha DESC LIMIT 9
        """
    )
    assert len(q_paridas) > 0
    assert q_paridas[0]["tag"] == "47"

    # 2. Inseminadas
    q_insem = db.query(
        """
        SELECT DISTINCT a.tag, a.nombre, s.fecha FROM servicios s
        JOIN animales a ON a.id_animal = s.vaca_id
        WHERE a.estado = 'ACTIVO'
        ORDER BY s.fecha DESC LIMIT 9
        """
    )
    assert len(q_insem) > 0
    assert q_insem[0]["tag"] == "47"

    # 3. Toros
    q_toros = db.query(
        """
        SELECT DISTINCT a.tag, a.nombre FROM animales a
        WHERE a.estado = 'ACTIVO' AND (a.sexo LIKE 'M%' OR a.sexo = 'Macho')
        ORDER BY a.tag ASC LIMIT 9
        """
    )
    assert len(q_toros) > 0
    assert q_toros[0]["tag"] == "TORO1"

    # 4. Crías
    q_crias = db.query(
        """
        SELECT DISTINCT a.tag, a.nombre, a.fecha_nacimiento AS fecha FROM animales a
        WHERE a.estado = 'ACTIVO' AND a.fecha_nacimiento IS NOT NULL
        ORDER BY a.fecha_nacimiento DESC LIMIT 9
        """
    )
    assert len(q_crias) > 0

    # 5. Pesajes
    q_pesajes = db.query(
        """
        SELECT DISTINCT a.tag, a.nombre, pe.peso_kg, pe.fecha FROM pesajes pe
        JOIN animales a ON a.id_animal = pe.animal_id
        WHERE a.estado = 'ACTIVO'
        ORDER BY pe.fecha DESC LIMIT 9
        """
    )
    assert len(q_pesajes) > 0
    assert q_pesajes[0]["peso_kg"] == 450


def test_formatear_pesajes_animal_tab_no_falla_por_potrero(db):
    """Regresión: la vista de pesajes unía contra pe.potrero_id, columna que no
    existe en la tabla pesajes (el potrero vive en animales)."""
    from src.server.telegram_bot import formatear_pesajes_animal_tab
    p1 = db.registrar_potrero("Norte")
    db.registrar_animal("47", potrero=p1, estado="ACTIVO")
    db.registrar_pesaje("47", fecha="2026-08-01", peso_kg=200)
    resp = formatear_pesajes_animal_tab(db, "47", hoy=date(2026, 9, 1))
    assert "Error" not in resp
    assert "Norte" in resp


def test_formatear_sanidad_animal_tab_no_falla_por_potrero(db):
    """Regresión: misma columna inexistente (t.potrero_id) en la vista de sanidad,
    más un segundo bug encadenado (r['via_administracion'] cuando la columna real
    es 'via')."""
    from src.server.telegram_bot import formatear_sanidad_animal_tab
    p1 = db.registrar_potrero("Norte")
    db.registrar_animal("47", potrero=p1, estado="ACTIVO")
    db.registrar_tratamiento(animal_tag="47", fecha="2026-08-01", producto="Ivermectina", via="SC")
    resp = formatear_sanidad_animal_tab(db, "47", hoy=date(2026, 9, 1))
    assert "Error" not in resp
    assert "Ivermectina" in resp
    assert "[SC]" in resp


def test_formatear_poblacion_panel_usa_datos_reales(db):
    """Regresión: el panel accedía a datos['hembras']/datos['machos'] (KeyError,
    esas claves no existen) y mostraba cifras de ejemplo fijas sin importar la DB."""
    from src.server.telegram_bot import formatear_poblacion_panel
    p1 = db.registrar_potrero("Norte")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2020-01-01")
    db.registrar_parto("47", fecha="2026-01-01")
    db.registrar_animal("T1", sexo="Macho", estado="ACTIVO", potrero=p1, nombre="TORO PADRON", fecha_nacimiento="2020-01-01")

    resp = formatear_poblacion_panel(db, hoy=date(2026, 9, 1))
    assert "Error" not in resp
    # Ya no debe mostrar los valores de ejemplo hardcodeados del bug original.
    assert "88 días" not in resp
    assert "372 días" not in resp
    assert "Vacas Totales:</b> 1" in resp
    assert "Toros / Reproductores:</b> 1" in resp
    assert "243 días" in resp  # días abiertos reales: parto 2026-01-01 -> hoy 2026-09-01


def test_total_animales_finca_no_se_confunde_con_ficha(db):
    """Regresión: 'animales' en plural no matcheaba \\banimal\\b, así que "Total
    animales finca" caía en el fallback de ficha con tag='total'."""
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    for pregunta in ["Total animales finca", "total animales", "cuantos animales hay"]:
        resp = qe.responder(pregunta)
        assert "No hay registros para la total" not in resp
        assert "No entendí" not in resp


def test_formatear_duplicados_geneticos(db):
    from src.server.telegram_bot import formatear_duplicados_geneticos

    assert "No se detectaron" in formatear_duplicados_geneticos([])

    grupos = [{
        "madre_id": 1, "madre_tag": "MADRE1", "fecha_nacimiento": "2024-11-01",
        "ids": [10, 11], "tags": ["N065", "NO65"], "n": 2,
    }]
    resp = formatear_duplicados_geneticos(grupos)
    assert "MADRE1" in resp
    assert "N065" in resp and "NO65" in resp
    assert "2024-11-01" in resp


def test_formatear_ultimos_registros_vacio_y_con_datos(db):
    from src.server.formatters import formatear_ultimos_registros

    assert "No hay eventos" in formatear_ultimos_registros([])

    db.registrar_muerte("47", fecha="2026-08-20", causa_presunta="culebra", registrado_por=999)
    filas = db.ultimos_registros(5)
    resp = formatear_ultimos_registros(filas)
    assert "/deshacer muertes" in resp
    assert "47" in resp
    assert "Muerte" in resp


def test_comandos_deshacer_registrados():
    import pathlib
    content = pathlib.Path("src/server/telegram_bot.py").read_text(encoding="utf-8")
    assert 'CommandHandler(["ultimos", "ultimos_registros"], cmd_ultimos)' in content
    assert 'CommandHandler("deshacer", cmd_deshacer)' in content
    assert 'CommandHandler("confirmar_deshacer", cmd_confirmar_deshacer)' in content
    assert 'CommandHandler("cancelar_deshacer", cmd_cancelar_deshacer)' in content


def test_comando_renombrar_animal_registrado():
    import pathlib
    content = pathlib.Path("src/server/telegram_bot.py").read_text(encoding="utf-8")
    assert 'CommandHandler("renombrar_animal", cmd_renombrar_animal)' in content


def test_comando_sos_registrado_y_avisa_owner_admin():
    import pathlib
    content = pathlib.Path("src/server/telegram_bot.py").read_text(encoding="utf-8")
    assert 'CommandHandler("sos", cmd_sos)' in content
    assert 'u_rol in ("OWNER", "ADMIN")' in content


def test_ayuda_trabajador_menciona_sos_y_resiliencia_sin_senal():
    ayuda_trabajador = formatear_ayuda("TRABAJADOR")
    assert "/sos" in ayuda_trabajador
    assert "Sin señal" in ayuda_trabajador


def test_tablero_finca_enlaza_graficos_no_servidor():
    # El Tablero de la Finca (zootécnico) ya no atajo directo a Servidor &
    # Sistema (mezclaba salud del hato con salud del servidor); en su lugar
    # enlaza a Gráficos de la Finca, su contraparte visual.
    import pathlib
    content = pathlib.Path("src/server/telegram_bot.py").read_text(encoding="utf-8")
    assert '"⚙️ Servidor & Sistema", callback_data="cmd:sistema"' not in content
    assert content.count('"📊 Gráficos de la Finca", callback_data="cmd:graficos"') >= 2


def test_comando_grafico_registrado():
    import pathlib
    content = pathlib.Path("src/server/telegram_bot.py").read_text(encoding="utf-8")
    assert 'CommandHandler(["grafico", "grafica", "curva"], cmd_grafico)' in content
    assert 'animal:grafico:' in content


def test_comando_grafico_leche_registrado():
    import pathlib
    content = pathlib.Path("src/server/telegram_bot.py").read_text(encoding="utf-8")
    assert 'CommandHandler(["grafico_leche", "curva_lactancia"], cmd_grafico_leche)' in content
    assert 'animal:grafico_leche:' in content


def test_formatear_leche_animal_tab_muestra_controles(db):
    from src.server.telegram_bot import formatear_leche_animal_tab
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01")
    db.registrar_leche("47", fecha="2026-06-08", litros=10.0)
    resp = formatear_leche_animal_tab(db, "47", hoy=date(2026, 8, 30))
    assert "10.0" in resp
    assert "2026-06-08" in resp


def test_formatear_leche_animal_tab_sin_controles_da_tip(db):
    from src.server.telegram_bot import formatear_leche_animal_tab
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01")
    resp = formatear_leche_animal_tab(db, "47", hoy=date(2026, 8, 30))
    assert "Sin controles de leche" in resp


def test_comando_graficos_panel_registrado():
    import pathlib
    content = pathlib.Path("src/server/telegram_bot.py").read_text(encoding="utf-8")
    assert 'CommandHandler(["graficos", "graficas", "panel_graficos"], cmd_graficos)' in content
    assert 'panel_grafico:' in content
    from src.server.telegram_bot import GRAFICOS_PANEL
    for tipo in (
        "evolucion", "waterfall", "categorias", "gmd", "iep", "iep_completo",
        "destete_raza", "padre", "aforo", "ocupacion", "prenadas", "dias_abiertos_km",
        "leche_total", "eficiencia_lechera", "ranking_leche", "reproductivo_hato", "carga_animal",
    ):
        assert tipo in GRAFICOS_PANEL


def test_existencias_potreros_nota_animales_sin_potrero(db):
    """Un animal ACTIVO sin potrero resoluble debe explicarse en la tabla, no
    desaparecer en silencio haciendo que el total no cuadre con el general."""
    from src.engine.query_engine import QueryEngine
    p1 = db.registrar_potrero("Norte")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1)
    db.registrar_animal("SINPOT", sexo="Hembra", estado="ACTIVO")  # sin potrero
    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("existencias por potrero")
    assert "1 animal activo" in resp
    assert "sin potrero asignado" in resp


def test_formatear_deteccion_potrero_gps_dentro():
    from src.server.formatters import formatear_deteccion_potrero_gps
    det = {"id": 1, "nombre": "Potrero Norte", "codigo": "N-01", "area_has": 5.2, "distancia_m": 0.0, "dentro": True}
    resp = formatear_deteccion_potrero_gps(det, usuario_nombre="Juan", fecha="2026-09-06", hora="10:30")
    assert "Potrero Norte" in resp
    assert "DENTRO" in resp
    assert "/ocupacion" in resp


def test_formatear_deteccion_potrero_gps_fuera():
    from src.server.formatters import formatear_deteccion_potrero_gps
    resp = formatear_deteccion_potrero_gps(None, usuario_nombre="Juan", fecha="2026-09-06", hora="10:30")
    assert "fuera" in resp.lower()
    assert "No se registr" in resp


def test_comando_arbol_genealogico_registrado():
    import pathlib
    content = pathlib.Path("src/server/telegram_bot.py").read_text(encoding="utf-8")
    assert 'CommandHandler(["arbol", "genealogia", "pedigree", "trazabilidad"], cmd_arbol_genealogico)' in content


def test_formatear_genealogia_3g_con_crias_y_consanguinidad(db):
    from src.server.formatters import formatear_genealogia_animal_tab
    db.registrar_animal("MAMA", sexo="Hembra")
    db.registrar_animal("PAPA", sexo="Macho")
    db.registrar_animal("VACA", sexo="Hembra", madre_tag="MAMA", padre_tag="PAPA")
    db.registrar_animal("HIJO", sexo="Macho", madre_tag="VACA")
    db.registrar_parto("VACA", "2026-03-22", id_cria_tag="HIJO", sexo_cria="Macho")

    txt = formatear_genealogia_animal_tab(db, "VACA")
    assert "ÁRBOL GENEALÓGICO & TRAZABILIDAD (3G)" in txt
    assert "PAPA" in txt
    assert "MAMA" in txt
    assert "Consanguinidad Parental:" in txt
    assert "HIJO" in txt




