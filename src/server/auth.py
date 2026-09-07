"""Módulo de autenticación y control de acceso basado en roles (RBAC)."""
from __future__ import annotations

import hmac
import json
import logging
import os
import tempfile
import threading
from typing import Any, Optional

logger = logging.getLogger("bitacora.auth")

ROLES_VALIDOS = {"OWNER", "ADMIN", "TRABAJADOR"}

# Candado de módulo que serializa toda mutación + persistencia de users.json.
# python-telegram-bot atiende los handlers en hilos (dos /agregar_usuario a la
# vez pueden llegar concurrentes) y sin candado la reescritura del JSON tiene
# una carrera que puede corromper el archivo. No se usa fcntl: no existe en
# Windows (la escritura atómica con os.replace sí es segura en ambos SO).
_LOCK = threading.Lock()


class Auth:
    """Gestiona usuarios autorizados, roles y permisos de la bitácora."""

    def __init__(self, users_file: str = "src/server/users.json"):
        self.users_file = users_file
        self.usuarios: list[dict[str, Any]] = []
        self.cargar()

    def cargar(self) -> None:
        """Carga la lista de usuarios desde el archivo JSON. Si no existe, crea uno vacío."""
        with _LOCK:
            self._cargar_sin_lock()

    def _cargar_sin_lock(self) -> None:
        """Lee users.json asumiendo el candado de módulo ya adquirido.

        Si el archivo no existe lo crea vacío con escritura atómica (el
        ``guardar()`` inicial de la carga queda así también bajo el lock).
        """
        if not os.path.exists(self.users_file):
            self.usuarios = []
            self._guardar_sin_lock()
            return

        try:
            with open(self.users_file, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except Exception as e:
            logger.error("Error al leer archivo de usuarios %s: %s", self.users_file, e)
            raise ValueError(f"Archivo de usuarios corrupto o inválido: {e}") from e

        if not isinstance(datos, list):
            logger.error("Estructura inválida en %s: no es una lista", self.users_file)
            raise ValueError(f"Estructura inválida en {self.users_file}: se esperaba una lista JSON.")

        for u in datos:
            if not isinstance(u, dict) or "user_id" not in u or "rol" not in u:
                logger.error("Usuario malformado en %s: %s", self.users_file, u)
                raise ValueError(f"Usuario inválido en {self.users_file}: {u}")

        self.usuarios = datos
        try:
            self._ultimo_mtime = os.path.getmtime(self.users_file)
        except Exception:
            pass

    def _recargar_si_cambio(self) -> None:
        """Recarga la lista de usuarios si users.json fue modificado en disco por otro proceso (ej. PWA)."""
        try:
            if os.path.exists(self.users_file):
                mtime = os.path.getmtime(self.users_file)
                if getattr(self, "_ultimo_mtime", None) != mtime:
                    with _LOCK:
                        mtime_check = os.path.getmtime(self.users_file)
                        if getattr(self, "_ultimo_mtime", None) != mtime_check:
                            self._cargar_sin_lock()
        except Exception as e:
            logger.debug("Error comprobando mtime de users.json: %s", e)

    def guardar(self) -> None:
        """Persiste la lista actual de usuarios en el archivo JSON (bajo candado)."""
        with _LOCK:
            self._guardar_sin_lock()

    def _guardar_sin_lock(self) -> None:
        """Escritura atómica de users.json asumiendo el candado ya adquirido.

        Escribe primero a un temporal en el MISMO directorio y luego lo
        renombra con ``os.replace`` (atómico en Windows y POSIX): un lector
        concurrente nunca ve un archivo a medio escribir y dos escritores no
        pueden corromper el JSON. Si algo falla, el temporal se borra.
        """
        dir_padre = os.path.dirname(os.path.abspath(self.users_file))
        if dir_padre and not os.path.exists(dir_padre):
            os.makedirs(dir_padre, exist_ok=True)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=dir_padre or ".", delete=False, mode="w", encoding="utf-8"
            ) as f:
                json.dump(self.usuarios, f, indent=2, ensure_ascii=False)
                tmp_path = f.name
            os.replace(tmp_path, self.users_file)
            tmp_path = None
            try:
                self._ultimo_mtime = os.path.getmtime(self.users_file)
            except Exception:
                pass
        finally:
            if tmp_path is not None and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def es_autorizado(self, user_id: int) -> bool:
        """Verifica si el usuario está registrado en el sistema."""
        self._recargar_si_cambio()
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            logger.warning("Intento de acceso con user_id no numérico: %s", user_id)
            return False

        for u in self.usuarios:
            if u.get("user_id") == uid or u.get("telegram_id") == uid:
                return True

        logger.warning("Intento de acceso no autorizado: user_id=%s", uid)
        return False

    def rol_de(self, user_id: int) -> Optional[str]:
        """Devuelve el rol normalizado (OWNER, ADMIN, TRABAJADOR) o None si no existe."""
        self._recargar_si_cambio()
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            return None

        for u in self.usuarios:
            if u.get("user_id") == uid or u.get("telegram_id") == uid:
                return str(u.get("rol", "")).strip().upper()
        return None

    def obtener_usuario(self, user_id: int | str) -> Optional[dict]:
        """Devuelve una copia del diccionario del usuario coincidente por user_id o telegram_id."""
        self._recargar_si_cambio()
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            return None
        for u in self.usuarios:
            if u.get("user_id") == uid or u.get("telegram_id") == uid:
                return dict(u)
        return None

    def puede_consultar(self, user_id: int) -> bool:
        """Verifica permiso de consulta y registro básico (OWNER, ADMIN, TRABAJADOR)."""
        self._recargar_si_cambio()
        rol = self.rol_de(user_id)
        if rol in ("OWNER", "ADMIN", "TRABAJADOR"):
            return True
        logger.warning("Permiso de consulta denegado para user_id=%s (rol=%s)", user_id, rol)
        return False

    def puede_administrar(self, user_id: int) -> bool:
        """Verifica permiso administrativo (OWNER, ADMIN)."""
        rol = self.rol_de(user_id)
        if rol in ("OWNER", "ADMIN"):
            return True
        logger.warning("Permiso de administración denegado para user_id=%s (rol=%s)", user_id, rol)
        return False

    def puede_gestionar_usuarios(self, user_id: int) -> bool:
        """Verifica permiso para gestionar usuarios y sistema (solo OWNER)."""
        rol = self.rol_de(user_id)
        if rol == "OWNER":
            return True
        logger.warning("Permiso de gestión de usuarios denegado para user_id=%s (rol=%s)", user_id, rol)
        return False

    def es_owner(self, user_id: int) -> bool:
        """Verifica si el usuario tiene rol OWNER (propietario)."""
        return self.rol_de(user_id) == "OWNER"

    def es_admin(self, user_id: int) -> bool:
        """Verifica si el usuario tiene rol ADMIN (administrador)."""
        return self.rol_de(user_id) == "ADMIN"

    def autenticar_pin(self, pin: str) -> Optional[dict[str, Any]]:
        """Busca un usuario por su PIN numérico y devuelve sus datos normalizados si coincide."""
        self._recargar_si_cambio()
        if not pin:
            return None
        pin_limpio = str(pin).strip()
        for u in self.usuarios:
            pin_u = str(u.get("pin", "")).strip()
            # compare_digest en vez de == : una comparación normal corta en
            # cuanto encuentra el primer carácter distinto, así que el tiempo
            # de respuesta revela cuántos dígitos del PIN acertó un atacante
            # (ataque de temporización). Con 4 dígitos y el sitio expuesto a
            # internet, vale la pena la comparación en tiempo constante.
            if pin_u and hmac.compare_digest(pin_u, pin_limpio):
                rol_u = str(u.get("rol", "")).strip().upper()
                avatar_u = u.get("avatar") or ("patron" if rol_u == "OWNER" else "admin" if rol_u == "ADMIN" else "vaquero")
                return {
                    "user_id": u.get("user_id"),
                    "telegram_id": u.get("telegram_id"),
                    "nombre": u.get("nombre", ""),
                    "rol": rol_u,
                    "avatar": avatar_u,
                }
        return None

    def asignar_pin(self, user_id: int, pin: str) -> None:
        """Asigna o actualiza el PIN de acceso de un usuario."""
        with _LOCK:
            try:
                uid = int(user_id)
            except (ValueError, TypeError) as e:
                raise ValueError(f"user_id inválido: {user_id}") from e

            pin_limpio = str(pin).strip()
            for u in self.usuarios:
                if u.get("user_id") == uid or u.get("telegram_id") == uid:
                    u["pin"] = pin_limpio
                    self._guardar_sin_lock()
                    logger.info("PIN actualizado para user_id=%s", uid)
                    return
            raise ValueError(f"El usuario con ID {uid} no existe.")

    def agregar_usuario(
        self,
        user_id: int,
        nombre: str,
        rol: str,
        pin: Optional[str] = None,
        telegram_id: Optional[int] = None,
        avatar: Optional[str] = None,
        borrar_telegram_id: bool = False,
    ) -> None:
        """Agrega o actualiza un usuario y persiste los cambios."""
        # Mutación + persistencia como una sola unidad crítica bajo el candado
        # de módulo (ver _LOCK): evita perder actualizaciones entre hilos.
        with _LOCK:
            try:
                uid = int(user_id)
            except (ValueError, TypeError) as e:
                raise ValueError(f"user_id inválido: {user_id}") from e

            rol_norm = str(rol).strip().upper()
            if rol_norm not in ROLES_VALIDOS:
                raise ValueError(
                    f"Rol inválido: '{rol}'. Roles permitidos: {', '.join(sorted(ROLES_VALIDOS))}"
                )

            nombre_norm = str(nombre).strip() if nombre else f"Usuario_{uid}"
            pin_norm = str(pin).strip() if pin else None
            tg_id_norm = int(telegram_id) if telegram_id else None
            avatar_norm = avatar or ("patron" if rol_norm == "OWNER" else "admin" if rol_norm == "ADMIN" else "vaquero")

            for u in self.usuarios:
                if u.get("user_id") == uid:
                    u["nombre"] = nombre_norm
                    u["rol"] = rol_norm
                    if pin_norm is not None:
                        u["pin"] = pin_norm
                    if telegram_id is not None:
                        u["telegram_id"] = tg_id_norm
                    elif borrar_telegram_id:
                        u["telegram_id"] = None
                    if avatar is not None:
                        u["avatar"] = avatar_norm
                    self._guardar_sin_lock()
                    logger.info("Usuario actualizado: user_id=%s, nombre=%s, rol=%s", uid, nombre_norm, rol_norm)
                    return

            nuevo = {
                "user_id": uid,
                "nombre": nombre_norm,
                "rol": rol_norm,
                "telegram_id": tg_id_norm,
                "avatar": avatar_norm,
            }
            if pin_norm:
                nuevo["pin"] = pin_norm
            self.usuarios.append(nuevo)
            self._guardar_sin_lock()
            logger.info("Usuario agregado: user_id=%s, nombre=%s, rol=%s", uid, nombre_norm, rol_norm)

    def quitar_usuario(self, user_id: int) -> None:
        """Elimina un usuario del sistema si no es el último OWNER."""
        # Mutación + persistencia bajo el candado de módulo (ver _LOCK).
        with _LOCK:
            try:
                uid = int(user_id)
            except (ValueError, TypeError) as e:
                raise ValueError(f"user_id inválido: {user_id}") from e

            usuario = None
            for u in self.usuarios:
                if u.get("user_id") == uid:
                    usuario = u
                    break

            if usuario is None:
                logger.warning("Intento de quitar usuario inexistente: user_id=%s", uid)
                raise ValueError(f"El usuario con ID {uid} no existe.")

            if str(usuario.get("rol", "")).strip().upper() == "OWNER":
                owners = [u for u in self.usuarios if str(u.get("rol", "")).strip().upper() == "OWNER"]
                if len(owners) <= 1:
                    logger.warning("Intento de eliminar al último OWNER: user_id=%s", uid)
                    raise ValueError("No se puede eliminar al único OWNER registrado en el sistema.")

            self.usuarios = [u for u in self.usuarios if u.get("user_id") != uid]
            self._guardar_sin_lock()
            logger.info("Usuario eliminado: user_id=%s", uid)

    def listar_usuarios(self) -> list[dict[str, Any]]:
        """Devuelve una copia de la lista de usuarios."""
        self._recargar_si_cambio()
        return [dict(u) for u in self.usuarios]
