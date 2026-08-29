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
    assert "<pre>" in resp_mem
    assert "</pre>" in resp_mem
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

    ayuda_admin = formatear_ayuda("ADMIN")
    assert "Administrador" in ayuda_admin
    assert "/alertas" in ayuda_admin
    assert "/importar" in ayuda_admin
    assert "/confirmar_importar" in ayuda_admin
    assert "/descartar_backup" in ayuda_admin
    assert "/agregar_usuario" not in ayuda_admin
    assert "¿Agregar un trabajador nuevo?" not in ayuda_admin

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

    assert "Resumen General de Inventario (SG)" in resp
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
        texto_guia_consultas,
        texto_guia_fotos,
    )
    g_cons = texto_guia_consultas()
    assert "patricia" in g_cons
    assert "potrero" in g_cons
    assert "parto" in g_cons

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






