"""Persistencia en disco del rate-limit de intentos fallidos de login.

Se guarda en JSON aparte (no en la DB principal de animales) porque es
estado efímero y pequeño. Antes vivía solo en un dict en memoria del
proceso Flask: un `systemctl restart` (frecuente en este proyecto, cada
deploy) lo vaciaba por completo y reabría la ventana de fuerza bruta sobre
el PIN de 4 dígitos justo después de cada despliegue. Persistiendo a disco
el bloqueo sobrevive al reinicio del servicio.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from typing import Dict, List

_LOCK = threading.Lock()


class RateLimitStore:
    """Cuenta intentos por clave (típicamente una IP) dentro de una ventana deslizante."""

    def __init__(self, path: str):
        self.path = path
        self._datos: Dict[str, List[float]] = {}
        self._cargar()

    def _cargar(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                bruto = json.load(f)
            if isinstance(bruto, dict):
                self._datos = {
                    str(k): [float(t) for t in v if isinstance(t, (int, float))]
                    for k, v in bruto.items() if isinstance(v, list)
                }
        except Exception:
            self._datos = {}

    def _guardar_sin_lock(self) -> None:
        dir_padre = os.path.dirname(os.path.abspath(self.path))
        if dir_padre and not os.path.exists(dir_padre):
            os.makedirs(dir_padre, exist_ok=True)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=dir_padre or ".", delete=False, mode="w", encoding="utf-8"
            ) as f:
                json.dump(self._datos, f)
                tmp_path = f.name
            os.replace(tmp_path, self.path)
            tmp_path = None
        except Exception:
            pass
        finally:
            if tmp_path is not None and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def bloqueado(self, clave: str, max_intentos: int, ventana_seg: float) -> bool:
        """True si `clave` ya alcanzó `max_intentos` dentro de la ventana."""
        ahora = time.time()
        with _LOCK:
            vivos = [t for t in self._datos.get(clave, ()) if ahora - t < ventana_seg]
            self._datos[clave] = vivos
            return len(vivos) >= max_intentos

    def registrar(self, clave: str) -> None:
        """Registra un intento fallido para `clave` en el instante actual."""
        with _LOCK:
            self._datos.setdefault(clave, []).append(time.time())
            if len(self._datos) > 500:
                ahora = time.time()
                self._datos = {
                    k: v for k, v in self._datos.items() if v and (ahora - max(v)) < 3600
                }
            self._guardar_sin_lock()
