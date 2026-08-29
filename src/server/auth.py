"""Módulo de autenticación y control de acceso basado en roles (RBAC)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("bitacora.auth")

ROLES_VALIDOS = {"OWNER", "ADMIN", "TRABAJADOR"}


class Auth:
    """Gestiona usuarios autorizados, roles y permisos de la bitácora."""

    def __init__(self, users_file: str = "src/server/users.json"):
        self.users_file = users_file
        self.usuarios: list[dict[str, Any]] = []
        self.cargar()

    def cargar(self) -> None:
        """Carga la lista de usuarios desde el archivo JSON. Si no existe, crea uno vacío."""
        if not os.path.exists(self.users_file):
            self.usuarios = []
            self.guardar()
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

    def guardar(self) -> None:
        """Persiste la lista actual de usuarios en el archivo JSON."""
        dir_padre = os.path.dirname(os.path.abspath(self.users_file))
        if dir_padre and not os.path.exists(dir_padre):
            os.makedirs(dir_padre, exist_ok=True)

        with open(self.users_file, "w", encoding="utf-8") as f:
            json.dump(self.usuarios, f, indent=2, ensure_ascii=False)

    def es_autorizado(self, user_id: int) -> bool:
        """Verifica si el usuario está registrado en el sistema."""
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            logger.warning("Intento de acceso con user_id no numérico: %s", user_id)
            return False

        for u in self.usuarios:
            if u.get("user_id") == uid:
                return True

        logger.warning("Intento de acceso no autorizado: user_id=%s", uid)
        return False

    def rol_de(self, user_id: int) -> Optional[str]:
        """Devuelve el rol normalizado (OWNER, ADMIN, TRABAJADOR) o None si no existe."""
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            return None

        for u in self.usuarios:
            if u.get("user_id") == uid:
                return str(u.get("rol", "")).strip().upper()
        return None

    def puede_consultar(self, user_id: int) -> bool:
        """Verifica permiso de consulta y registro básico (OWNER, ADMIN, TRABAJADOR)."""
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

    def agregar_usuario(self, user_id: int, nombre: str, rol: str) -> None:
        """Agrega o actualiza un usuario y persiste los cambios."""
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

        for u in self.usuarios:
            if u.get("user_id") == uid:
                u["nombre"] = nombre_norm
                u["rol"] = rol_norm
                self.guardar()
                logger.info("Usuario actualizado: user_id=%s, nombre=%s, rol=%s", uid, nombre_norm, rol_norm)
                return

        self.usuarios.append({
            "user_id": uid,
            "nombre": nombre_norm,
            "rol": rol_norm,
        })
        self.guardar()
        logger.info("Usuario agregado: user_id=%s, nombre=%s, rol=%s", uid, nombre_norm, rol_norm)

    def quitar_usuario(self, user_id: int) -> None:
        """Elimina un usuario del sistema si no es el último OWNER."""
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
        self.guardar()
        logger.info("Usuario eliminado: user_id=%s", uid)

    def listar_usuarios(self) -> list[dict[str, Any]]:
        """Devuelve una copia de la lista de usuarios."""
        return [dict(u) for u in self.usuarios]
