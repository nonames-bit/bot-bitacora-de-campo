"""Pruebas de concurrencia SQLite WAL.

Valida que la base en archivo (NO ``:memory:``, que no comparte estado entre
conexiones) configurada con ``PRAGMA journal_mode=WAL`` + ``busy_timeout``
(ver ``src/db/database.py``) soporta escrituras simultáneas desde varios
hilos (bot de Telegram, vigilante de copias y backup diario) sin lanzar
"database is locked" ni perder/duplicar filas.
"""
import threading

from src.db.database import Database


def _escribir_recordatorios(conn: Database, tid: int, n: int, errores: list) -> None:
    """Inserta ``n`` recordatorios únicos desde el hilo ``tid``."""
    try:
        for i in range(n):
            conn.registrar_recordatorio(
                mensaje=f"hilo-{tid}-recordatorio-{i:04d}",
            )
    except Exception as e:  # noqa: BLE001 - cualquier fallo debe hacer fallar el test
        errores.append(f"hilo {tid}: {type(e).__name__}: {e}")


def test_concurrencia_wal_escrituras_paralelas_no_pierden_filas(tmp_path):
    """4 hilos insertando 30 filas cada uno: 120 filas exactas, sin locks."""
    ruta_db = str(tmp_path / "concurrencia_wal.db")

    # Crear el esquema una sola vez (evita carreras de CREATE TABLE).
    db = Database(ruta_db)
    db.create_tables()
    db.close()

    # Una conexión por hilo, como en producción: bot + vigilante + respaldo
    # abren cada uno su propia conexión al mismo archivo WAL.
    num_hilos = 4
    registros_por_hilo = 30
    conexiones = [Database(ruta_db) for _ in range(num_hilos)]

    errores: list = []
    hilos = [
        threading.Thread(target=_escribir_recordatorios, args=(conn, tid, registros_por_hilo, errores))
        for tid, conn in enumerate(conexiones)
    ]

    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    for conn in conexiones:
        conn.close()

    # Ningún hilo debe haber tropezado con "database is locked" ni otra excepción.
    assert not errores, f"Errores de escritura concurrente detectados: {errores}"

    # Conteo final exacto: sin pérdidas ni duplicados.
    verificacion = Database(ruta_db)
    try:
        total = verificacion.query_one("SELECT COUNT(*) AS n FROM recordatorios_programados")["n"]
        distintos = verificacion.query_one(
            "SELECT COUNT(DISTINCT mensaje) AS n FROM recordatorios_programados"
        )["n"]
    finally:
        verificacion.close()

    esperado = num_hilos * registros_por_hilo
    assert total == esperado
    assert distintos == esperado


def test_concurrencia_wal_dos_hilos_eventos_por_animal(tmp_path):
    """2 hilos registrando pesajes sobre animales pre-creados: sin duplicados."""
    ruta_db = str(tmp_path / "concurrencia_wal_eventos.db")

    db = Database(ruta_db)
    db.create_tables()
    # Pre-sembrar animales para no depender de la creación concurrente de tags.
    for tag in ("47", "48", "49"):
        db.registrar_animal(tag=tag, sexo="Hembra")
    db.close()

    num_hilos = 2
    registros_por_hilo = 20
    conexiones = [Database(ruta_db) for _ in range(num_hilos)]
    errores: list = []

    def _escribir_pesajes(conn: Database, tid: int, n: int) -> None:
        try:
            for i in range(n):
                # Peso distinto por (hilo, iteración) para que la llave
                # natural animal_id+fecha+peso_kg sea única y no deduplique.
                conn.registrar_pesaje(
                    animal_tag=f"4{7 + tid}",
                    fecha=f"2026-09-{i % 28 + 1:02d}",
                    peso_kg=300.0 + tid * 10.0 + i * 0.5,
                )
        except Exception as e:  # noqa: BLE001
            errores.append(f"hilo {tid}: {type(e).__name__}: {e}")

    hilos = [
        threading.Thread(target=_escribir_pesajes, args=(conn, tid, registros_por_hilo))
        for tid, conn in enumerate(conexiones)
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    for conn in conexiones:
        conn.close()

    assert not errores, f"Errores de escritura concurrente detectados: {errores}"

    verificacion = Database(ruta_db)
    try:
        total = verificacion.query_one("SELECT COUNT(*) AS n FROM pesajes")["n"]
    finally:
        verificacion.close()

    assert total == num_hilos * registros_por_hilo
