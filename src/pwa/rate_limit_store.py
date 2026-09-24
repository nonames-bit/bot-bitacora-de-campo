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

    def olvidar(self, clave: str) -> None:
        """Borra el historial de `clave` (éxito: se levanta la ventana)."""
        with _LOCK:
            if clave in self._datos:
                del self._datos[clave]
                self._guardar_sin_lock()


class CastigoStore:
    """Bloqueo progresivo (backoff exponencial) por clave, persistido en JSON.

    Complementa a RateLimitStore: cuando una IP agota la ventana de login
    una y otra vez, cada reincidencia duplica el bloqueo (60s, 120s, 240s…
    con tope de 1 hora). Sin esto, un PIN de 4 dígitos (10.000
    combinaciones) cae en días rotando pocos IPs.
    El castigo se perdona con un login exitoso.
    """

    BASE_SEG = 60.0
    TOPE_SEG = 3600.0
    TOPE_NIVEL = 6

    def __init__(self, path: str):
        self.path = path
        self._datos: Dict[str, Dict[str, float]] = {}
        self._cargar()

    def _cargar(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                bruto = json.load(f)
            if isinstance(bruto, dict):
                self._datos = {
                    str(k): {
                        "hasta": float(v.get("hasta", 0)),
                        "nivel": int(v.get("nivel", 0)),
                    }
                    for k, v in bruto.items() if isinstance(v, dict)
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

    def segundos_restantes(self, clave: str, ahora: float | None = None) -> float:
        """Segundos de bloqueo vigentes para `clave` (0 si no hay)."""
        ts = ahora if ahora is not None else time.time()
        with _LOCK:
            reg = self._datos.get(clave)
            if not reg:
                return 0.0
            return max(0.0, float(reg.get("hasta", 0)) - ts)

    def castigar(self, clave: str, ahora: float | None = None) -> float:
        """Sube un nivel el bloqueo de `clave` y devuelve los segundos impuestos."""
        ts = ahora if ahora is not None else time.time()
        with _LOCK:
            reg = self._datos.get(clave) or {"hasta": 0.0, "nivel": -1}
            nivel = min(int(reg.get("nivel", -1)) + 1, self.TOPE_NIVEL)
            duracion = min(self.BASE_SEG * (2 ** nivel), self.TOPE_SEG)
            self._datos[clave] = {"hasta": ts + duracion, "nivel": nivel}
            if len(self._datos) > 500:
                self._datos = {
                    k: v for k, v in self._datos.items() if v.get("hasta", 0) > ts
                }
            self._guardar_sin_lock()
            return duracion

    def perdonar(self, clave: str) -> None:
        """Borra el castigo de `clave` (login exitoso)."""
        with _LOCK:
            if clave in self._datos:
                del self._datos[clave]
                self._guardar_sin_lock()
