"""Login por PIN/contraseña, logout y WebAuthn (huella / Face ID).

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

import hmac
import json
import time
import logging
from typing import Optional
from flask import jsonify, redirect, render_template, request, session
# WebAuthn (login con huella/Face ID). El módulo degrada solo si falta
# py_webauthn (webauthn.disponible() == False); este import nunca falla.
from .. import webauthn as _webauthn
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _db,
    _rol_de,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def registrar(app, ctx, h):
    _castigo_store = ctx._castigo_store
    _login_store = ctx._login_store
    _cliente_ip = h._cliente_ip
    _login_bloqueado = h._login_bloqueado
    _login_registrar_intento = h._login_registrar_intento
    _texto_espera = h._texto_espera
    clave_esperada = ctx.clave_esperada
    db_path = ctx.db_path
    pwa_version = ctx.pwa_version
    users_file = ctx.users_file

    @app.get("/login")
    def login_form():
        if not clave_esperada:
            return (
                "⚠️ PWA_PASSWORD no está configurada en el entorno (.env). "
                "El dashboard permanece bloqueado hasta que se configure una "
                "contraseña — no se sirve sin autenticación.",
                503,
            )
        return render_template("login.html", error=request.args.get("error"), pwa_v=pwa_version)

    @app.post("/login")
    def login_submit():
        if not clave_esperada:
            return (
                "⚠️ PWA_PASSWORD no está configurada en el entorno (.env).",
                503,
            )
        ip = _cliente_ip()
        # Backoff progresivo: cada ventana agotada duplica el bloqueo
        # (60s, 120s, 240s… tope 1h). Sin esto, el PIN de 4 dígitos se
        # barre en días rotando pocos IPs.
        castigo = _castigo_store.segundos_restantes(ip)
        if castigo > 0:
            return (
                f"⚠️ Demasiados intentos fallidos. Espere {_texto_espera(castigo)} e intente de nuevo.",
                429,
            )
        if _login_bloqueado(ip):
            espera = _castigo_store.castigar(ip)
            return (
                f"⚠️ Demasiados intentos fallidos. Espere {_texto_espera(espera)} e intente de nuevo.",
                429,
            )
        intento = (request.form.get("password") or request.form.get("pin") or "").strip()
        uid_form = (request.form.get("user_id") or "").strip() or None

        # 1. Intentar autenticar por PIN individual de users.json
        try:
            try:
                from ...server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            user_auth = auth_inst.autenticar_pin(intento)
        except Exception as e:
            logger.warning("Fallo autenticando PIN: %s", e)
            user_auth = None

        if user_auth:
            # Éxito: se levantan ventana y castigo de esta IP y se rota la
            # sesión (no arrastrar claves previas en equipos compartidos).
            _login_store.olvidar(ip)
            _castigo_store.perdonar(ip)
            # Rotación de sesión: no arrastrar claves de una sesión previa
            # (ej. telegram_id de otro usuario en un equipo compartido).
            session.clear()
            session["autenticado"] = True
            session["user_id"] = user_auth.get("user_id")
            session["telegram_id"] = user_auth.get("telegram_id")
            session["nombre"] = user_auth.get("nombre") or "Usuario"
            session["rol"] = user_auth.get("rol") or "TRABAJADOR"
            session["avatar"] = user_auth.get("avatar") or "vaquero"
            return redirect("/")

        # 2. Intentar autenticar por contraseña maestra (PWA_PASSWORD)
        if clave_esperada and intento and hmac.compare_digest(intento, clave_esperada):
            # El user_id del formulario no es confiable (el login.html ni
            # siquiera lo pide): solo se adopta si existe en users.json.
            # Un ID inexistente o revocado se descarta en vez de firmar
            # eventos y presencia a nombre de otro usuario.
            uid_verificado = None
            if uid_form is not None:
                try:
                    _uid_candidato = int(uid_form)
                except (ValueError, TypeError):
                    _uid_candidato = None
                if _uid_candidato is not None and _rol_de(_uid_candidato, users_file):
                    uid_verificado = _uid_candidato
            _login_store.olvidar(ip)
            _castigo_store.perdonar(ip)
            session.clear()
            session["autenticado"] = True
            session["user_id"] = uid_verificado
            session["rol"] = _rol_de(uid_verificado, users_file) or "OWNER"
            session["nombre"] = "Propietario" if session["rol"] == "OWNER" else "Usuario"
            session["avatar"] = "patron" if session["rol"] == "OWNER" else "admin"
            return redirect("/")

        _login_registrar_intento(ip)
        return redirect("/login?error=1")

    @app.get("/logout")
    def logout():
        # Logout-CSRF: un enlace desde otro sitio no debe cerrar la sesión.
        # Los navegadores modernos marcan esa navegación con Sec-Fetch-Site.
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            return redirect("/")
        session.clear()
        resp = redirect("/login")
        # Respaldo del lado del servidor al borrado de caché en JS (app.js):
        # si el navegador soporta Clear-Site-Data, esto limpia la caché del
        # Service Worker aunque JS esté deshabilitado o el logout se dispare
        # por navegación directa (sin pasar por el listener de app.js). En
        # un equipo compartido, sin esto alguien podría ver offline los
        # datos de la finca cacheados por la sesión anterior tras cerrarla.
        resp.headers["Clear-Site-Data"] = '"cache", "storage"'
        return resp

    # ------------------------------------------------------------------ #
    # WebAuthn: login con huella / Face ID
    # ------------------------------------------------------------------ #
    def _wa_rp() -> tuple:
        return _webauthn.rp_config(request.host or "", request.scheme or "https")

    def _wa_guardar_challenge(tipo: str) -> bytes:
        challenge = _webauthn.nuevo_challenge()
        session["wa_challenge"] = _webauthn.b64url_encode(challenge)
        session["wa_tipo"] = tipo
        session["wa_exp"] = time.time() + _webauthn.CHALLENGE_MAX_EDAD_SEG
        return challenge

    def _wa_consumir_challenge(tipo: str) -> Optional[bytes]:
        # One-shot: se borra siempre (acierte o no) para que no se reutilice.
        chall_b64 = session.pop("wa_challenge", None)
        tipo_guardado = session.pop("wa_tipo", None)
        exp = session.pop("wa_exp", 0) or 0
        if tipo_guardado != tipo or not chall_b64:
            return None
        try:
            if time.time() > float(exp):
                return None
            return _webauthn.b64url_decode(chall_b64)
        except Exception:
            return None

    def _wa_usuario_por_uid(uid: int) -> Optional[dict]:
        """Usuario de users.json por user_id (NO por telegram_id)."""
        try:
            try:
                from ...server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            for u in Auth(users_file).listar_usuarios():
                if u.get("user_id") == uid:
                    return u
        except Exception as e:
            logger.warning("WebAuthn: no se pudo leer users.json: %s", e)
        return None

    def _wa_roles_gestion() -> bool:
        return (session.get("rol") or "").upper() in ("OWNER", "ADMIN")

    def _wa_error(msg: str, code: int = 400):
        return jsonify({"ok": False, "error": msg}), code

    def _wa_uid_sesion() -> Optional[int]:
        uid = session.get("user_id")
        try:
            return int(uid) if uid is not None else None
        except (TypeError, ValueError):
            return None

    @app.get("/api/webauthn/disponible")
    def webauthn_disponible():
        """Público: ¿hay biometría disponible y ya usada en esta finca?"""
        if not _webauthn.disponible():
            return jsonify({"ok": True, "disponible": False, "motivo": "no_soportado"})
        dbi = _db(db_path)
        try:
            hay = dbi.hay_credenciales_webauthn()
        except Exception:
            hay = False
        finally:
            try:
                dbi.close()
            except Exception:
                pass
        rp_id, _rp_name, _origin = _wa_rp()
        return jsonify({"ok": True, "disponible": bool(hay), "rp_id": rp_id})

    @app.post("/api/webauthn/registro/opciones")
    def webauthn_registro_opciones():
        if not _webauthn.disponible():
            return _wa_error("Biometría no disponible en el servidor.", 503)
        rp_id, rp_name, _origin = _wa_rp()
        uid_int = _wa_uid_sesion()
        dbi = _db(db_path)
        try:
            existentes = dbi.listar_credenciales_de_usuario(uid_int)
        finally:
            try:
                dbi.close()
            except Exception:
                pass
        if len(existentes) >= _webauthn.MAX_CREDENCIALES_POR_USUARIO:
            return _wa_error(
                f"Máximo {_webauthn.MAX_CREDENCIALES_POR_USUARIO} dispositivos con huella por usuario.",
                409,
            )
        challenge = _wa_guardar_challenge("registro")
        nombre = session.get("nombre") or ("Propietario" if session.get("rol") == "OWNER" else "Usuario")
        user_id_wa = str(uid_int) if uid_int is not None else "maestro"
        try:
            opciones = _webauthn.opciones_registro(
                rp_id=rp_id, rp_name=rp_name,
                user_id=user_id_wa, user_name=nombre, user_display_name=nombre,
                challenge=challenge,
                excluir_ids=[c["credencial_id"] for c in existentes],
            )
        except Exception as e:
            logger.warning("WebAuthn: no se pudieron generar opciones de registro: %s", e)
            return _wa_error("No se pudo iniciar el registro de huella.", 500)
        return jsonify({"ok": True, "opciones": opciones})

    @app.post("/api/webauthn/registro/verificar")
    def webauthn_registro_verificar():
        if not _webauthn.disponible():
            return _wa_error("Biometría no disponible en el servidor.", 503)
        datos = request.get_json(silent=True) or {}
        credencial = datos.get("credencial")
        if not isinstance(credencial, dict):
            return _wa_error("Credencial inválida.")
        rp_id, _rp_name, origin = _wa_rp()
        challenge = _wa_consumir_challenge("registro")
        if not challenge:
            return _wa_error("Registro expirado. Intente de nuevo.", 409)
        try:
            verificado = _webauthn.verificar_registro(
                credencial=credencial, challenge=challenge, rp_id=rp_id, origin=origin
            )
        except Exception as e:
            logger.warning("WebAuthn registro falló: %s", e)
            return _wa_error("No se pudo verificar la huella.", 400)
        cred_id = _webauthn.b64url_encode(verificado.credential_id)
        uid_int = _wa_uid_sesion()
        nombre_disp = str(datos.get("nombre_dispositivo") or "").strip()[:60] or None
        dbi = _db(db_path)
        try:
            dbi.guardar_credencial_webauthn(
                credencial_id=cred_id,
                clave_publica=_webauthn.b64url_encode(verificado.credential_public_key),
                user_id=uid_int,
                nombre_usuario=session.get("nombre"),
                sign_count=int(verificado.sign_count or 0),
                aaguid=str(verificado.aaguid) if verificado.aaguid else None,
                transportes=json.dumps(credencial.get("transports") or [], ensure_ascii=False),
                nombre_dispositivo=nombre_disp,
            )
        finally:
            try:
                dbi.close()
            except Exception:
                pass
        logger.info("WebAuthn: credencial registrada user_id=%s cred=%s", uid_int, cred_id[:12])
        return jsonify({"ok": True, "credencial_id": cred_id})

    @app.post("/api/webauthn/login/opciones")
    def webauthn_login_opciones():
        if not _webauthn.disponible():
            return _wa_error("Biometría no disponible en el servidor.", 503)
        rp_id, _rp_name, _origin = _wa_rp()
        challenge = _wa_guardar_challenge("login")
        try:
            opciones = _webauthn.opciones_login(rp_id=rp_id, challenge=challenge)
        except Exception as e:
            logger.warning("WebAuthn: no se pudieron generar opciones de login: %s", e)
            return _wa_error("No se pudo iniciar el login con huella.", 500)
        return jsonify({"ok": True, "opciones": opciones})

    @app.post("/api/webauthn/login/verificar")
    def webauthn_login_verificar():
        if not _webauthn.disponible():
            return _wa_error("Biometría no disponible en el servidor.", 503)
        ip = _cliente_ip()
        castigo = _castigo_store.segundos_restantes(ip)
        if castigo > 0:
            return _wa_error(f"Demasiados intentos fallidos. Espere {_texto_espera(castigo)}.", 429)
        if _login_bloqueado(ip):
            espera = _castigo_store.castigar(ip)
            return _wa_error(f"Demasiados intentos fallidos. Espere {_texto_espera(espera)}.", 429)
        datos = request.get_json(silent=True) or {}
        credencial = datos.get("credencial")
        raw_id = credencial.get("rawId") or credencial.get("id") if isinstance(credencial, dict) else None
        if not isinstance(credencial, dict) or not raw_id:
            _login_registrar_intento(ip)
            return _wa_error("Credencial inválida.", 400)
        rp_id, _rp_name, origin = _wa_rp()
        challenge = _wa_consumir_challenge("login")
        if not challenge:
            return _wa_error("Login expirado. Intente de nuevo.", 409)

        uid_cred = None
        telegram_id = None
        dbi = _db(db_path)
        try:
            fila = dbi.obtener_credencial_webauthn(str(raw_id))
            if not fila:
                _login_registrar_intento(ip)
                return _wa_error("Esta huella no está registrada.", 401)
            # Revalidar usuario/rol contra users.json (honra revocaciones).
            uid_cred = fila.get("user_id")
            if uid_cred is not None:
                usuario = _wa_usuario_por_uid(int(uid_cred))
                if not usuario:
                    dbi.borrar_credencial_webauthn(str(raw_id))
                    _login_registrar_intento(ip)
                    logger.warning("WebAuthn: usuario %s revocado; credencial borrada", uid_cred)
                    return _wa_error("Su acceso fue revocado.", 401)
                rol = str(usuario.get("rol", "")).strip().upper() or "TRABAJADOR"
                nombre = usuario.get("nombre") or "Usuario"
                avatar = usuario.get("avatar") or (
                    "patron" if rol == "OWNER" else "admin" if rol == "ADMIN" else "vaquero"
                )
                telegram_id = usuario.get("telegram_id")
            else:
                rol, nombre, avatar = "OWNER", "Propietario", "patron"
            try:
                verificado = _webauthn.verificar_login(
                    credencial=credencial, challenge=challenge, rp_id=rp_id, origin=origin,
                    clave_publica=_webauthn.b64url_decode(fila["clave_publica"]),
                    sign_count=int(fila.get("sign_count") or 0),
                )
            except Exception as e:
                _login_registrar_intento(ip)
                logger.warning("WebAuthn login falló cred=%s: %s", str(raw_id)[:12], e)
                return _wa_error("No se pudo verificar la huella.", 401)
            # Anti-clon: el contador de firmas no debe retroceder.
            nuevo_sign = int(getattr(verificado, "new_sign_count", 0) or 0)
            actual_sign = int(fila.get("sign_count") or 0)
            if actual_sign > 0 and nuevo_sign <= actual_sign:
                _login_registrar_intento(ip)
                logger.warning(
                    "WebAuthn: sign_count retrocedió cred=%s (%s -> %s)",
                    str(raw_id)[:12], actual_sign, nuevo_sign,
                )
                return _wa_error("No se pudo verificar la huella.", 401)
            dbi.actualizar_uso_credencial_webauthn(str(raw_id), nuevo_sign)
        finally:
            try:
                dbi.close()
            except Exception:
                pass

        _login_store.olvidar(ip)
        _castigo_store.perdonar(ip)
        session.clear()
        session["autenticado"] = True
        session["user_id"] = uid_cred
        session["telegram_id"] = telegram_id
        session["nombre"] = nombre
        session["rol"] = rol
        session["avatar"] = avatar
        logger.info("WebAuthn: sesión iniciada con huella user_id=%s", uid_cred)
        return jsonify({"ok": True, "redirect": "/"})

    @app.get("/api/webauthn/estado")
    def webauthn_estado():
        if not _webauthn.disponible():
            return jsonify({"ok": True, "soportado": False, "credenciales": []})
        dbi = _db(db_path)
        try:
            filas = dbi.listar_credenciales_de_usuario(_wa_uid_sesion())
        finally:
            try:
                dbi.close()
            except Exception:
                pass
        return jsonify({"ok": True, "soportado": True, "credenciales": [
            {"credencial_id": f["credencial_id"],
             "nombre_dispositivo": f.get("nombre_dispositivo"),
             "creado_en": f.get("creado_en"), "ultimo_uso": f.get("ultimo_uso")}
            for f in filas
        ]})

    @app.get("/api/webauthn/credenciales/todas")
    def webauthn_credenciales_todas():
        if not _wa_roles_gestion():
            return jsonify({"ok": False, "error": "Permiso denegado."}), 403
        dbi = _db(db_path)
        try:
            filas = dbi.listar_credenciales_webauthn()
        finally:
            try:
                dbi.close()
            except Exception:
                pass
        return jsonify({"ok": True, "credenciales": [
            {"credencial_id": f["credencial_id"], "user_id": f.get("user_id"),
             "nombre_usuario": f.get("nombre_usuario"),
             "nombre_dispositivo": f.get("nombre_dispositivo"),
             "creado_en": f.get("creado_en"), "ultimo_uso": f.get("ultimo_uso")}
            for f in filas
        ]})

    @app.delete("/api/webauthn/credenciales/<path:cred_id>")
    def webauthn_credencial_borrar(cred_id):
        if not _webauthn.disponible():
            return _wa_error("Biometría no disponible en el servidor.", 503)
        dbi = _db(db_path)
        try:
            fila = dbi.obtener_credencial_webauthn(str(cred_id))
            if not fila:
                return _wa_error("Credencial no encontrada.", 404)
            uid_int = _wa_uid_sesion()
            es_propia = (fila.get("user_id") is None and uid_int is None) or (
                fila.get("user_id") is not None and fila.get("user_id") == uid_int
            )
            if not es_propia and not _wa_roles_gestion():
                return jsonify({"ok": False, "error": "Permiso denegado."}), 403
            borrada = dbi.borrar_credencial_webauthn(str(cred_id))
        finally:
            try:
                dbi.close()
            except Exception:
                pass
        if borrada:
            logger.info("WebAuthn: credencial revocada %s", str(cred_id)[:12])
        return jsonify({"ok": True})
