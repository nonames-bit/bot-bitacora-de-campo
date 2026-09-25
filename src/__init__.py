"""Bot de bitácora de campo zootécnico."""
import os as _os
import time as _time

# Zona horaria de la finca para todo el proceso (bot, PWA, watchers, scripts).
# El código usa date.today()/datetime.now() en muchos sitios; en un VPS en UTC,
# después de las 19:00 de Colombia "hoy" ya era mañana (alertas, retiros y
# FEP corridos un día). TZ_FINCA permite cambiarla; un TZ explícito del
# entorno se respeta.
if not _os.environ.get("TZ"):
    _os.environ["TZ"] = _os.environ.get("TZ_FINCA", "America/Bogota")
    if hasattr(_time, "tzset"):  # POSIX; en Windows manda la hora del equipo
        _time.tzset()
