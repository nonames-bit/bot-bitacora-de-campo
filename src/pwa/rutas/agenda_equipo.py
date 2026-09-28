"""Agenda, eventos, búsqueda, toros, badges, usuarios, presencia y mensajes del equipo.

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

import os
import re
from datetime import date
import logging
from flask import jsonify, request, session
from ...utils import to_date
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _EXTENSIONES_IMAGEN_PERMITIDAS,
    _db,
    _error_interno,
    _es_imagen_valida,
    datos_agenda,
    datos_badges,
    datos_buscar,
    datos_identificar,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def registrar(app, ctx, h):
    _guardar_foto_evento = h._guardar_foto_evento
    _bloqueo_gestion_usuario = h._bloqueo_gestion_usuario
    _cliente_ip = h._cliente_ip
    _limite_api = h._limite_api
    _rol_actual = h._rol_actual
    _usuario_actual = h._usuario_actual
    db_path = ctx.db_path
    users_file = ctx.users_file

    @app.get("/api/agenda")
    def api_agenda():
        try:
            dias = int(request.args.get("dias") or 7)
        except (TypeError, ValueError):
            dias = 7
        dias = max(1, min(dias, 60))
        out = datos_agenda(db_path, dias=dias)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.post("/api/agenda/recordatorio")
    def api_agenda_crear_recordatorio():
        """Crea un evento/recordatorio o tarea asignada de campo (misma tabla de /programar)."""
        datos = request.get_json(silent=True) or request.form or {}
        mensaje = str(datos.get("mensaje") or "").strip()
        fecha = str(datos.get("fecha") or "").strip()
        hora = str(datos.get("hora") or "").strip() or None
        asignado_a = str(datos.get("asignado_a") or "").strip() or None
        tipo_objetivo = str(datos.get("tipo_objetivo") or "").strip().upper() or None
        animal_tag = str(datos.get("animal_tag") or datos.get("tag") or "").strip().upper() or None
        potrero_nombre = str(datos.get("potrero_nombre") or datos.get("potrero") or "").strip() or None
        tipo_tarea = str(datos.get("tipo_tarea") or "").strip().upper() or None
        prioridad = str(datos.get("prioridad") or "NORMAL").strip().upper()
        if not mensaje:
            return jsonify({"ok": False, "error": "El mensaje o descripción de la tarea es obligatorio."}), 400
        if len(mensaje) > 500:
            return jsonify({"ok": False, "error": "El mensaje no puede superar 500 caracteres."}), 400
        if not fecha:
            return jsonify({"ok": False, "error": "Fecha inválida. Use YYYY-MM-DD."}), 400
        try:
            if to_date(fecha) is None:
                return jsonify({"ok": False, "error": "Fecha inválida. Use YYYY-MM-DD."}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Fecha inválida. Use YYYY-MM-DD."}), 400
        if hora and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", hora):
            return jsonify({"ok": False, "error": "Hora inválida. Use HH:MM (24h)."}), 400
        db_r = _db(db_path)
        try:
            uid = session.get("user_id") if session is not None else None
            rid = db_r.registrar_recordatorio(
                mensaje=mensaje,
                fecha_programada=fecha,
                hora=hora,
                creado_por=uid,
                asignado_a=asignado_a,
                tipo_objetivo=tipo_objetivo,
                animal_tag=animal_tag,
                potrero_nombre=potrero_nombre,
                tipo_tarea=tipo_tarea,
                prioridad=prioridad,
            )
            # Notificar al canal del equipo
            try:
                dest = f" a {asignado_a}" if asignado_a else ""
                obj = f" ({animal_tag or potrero_nombre})" if (animal_tag or potrero_nombre) else ""
                texto_aviso = f"📋 Tarea asignada{dest}{obj}: {mensaje}"
                nombre_creador = session.get("nombre") or (_rol_actual() or "Usuario")
                db_r.conn.execute(
                    "INSERT INTO mensajes_equipo (user_id, nombre, rol, texto, creado_en) VALUES (?, ?, ?, ?, ?)",
                    (uid, nombre_creador, _rol_actual() or "USUARIO", texto_aviso, db_r._ahora()),
                )
                db_r.conn.commit()
            except Exception:
                pass
            return jsonify({"ok": True, "id": rid, "fecha": fecha, "hora": hora, "asignado_a": asignado_a})
        except Exception:
            logger.exception("Error creando recordatorio de agenda")
            return jsonify({"ok": False, "error": "No se pudo crear el recordatorio."}), 500
        finally:
            try:
                db_r.close()
            except Exception:
                pass

    @app.post("/api/agenda/recordatorio/<int:rid>/completar")
    def api_agenda_completar_recordatorio(rid: int):
        """Marca un recordatorio PENDIENTE como REALIZADO (acknowledge con notas y foto opcional)."""
        datos = request.get_json(silent=True) or request.form or {}
        notas = str(datos.get("notas") or datos.get("notas_completado") or "").strip() or None
        foto_b64 = datos.get("foto_base64")
        completado_por = str(datos.get("completado_por") or session.get("nombre") or (_rol_actual() or "Usuario")).strip()
        db_r = _db(db_path)
        try:
            fila = db_r.query_one(
                "SELECT * FROM recordatorios_programados WHERE id = ?", (rid,),
            )
            if not fila:
                return jsonify({"ok": False, "error": "El recordatorio no existe."}), 404
            uid = session.get("user_id") if session is not None else None
            foto_ruta = None
            if foto_b64 and isinstance(foto_b64, str):
                tag_ref = fila.get("animal_tag") or "tarea"
                fid_foto = _guardar_foto_evento(db_r, {"foto_base64": foto_b64, "animal_tag": tag_ref}, "tarea", date.today().isoformat(), uid)
                if fid_foto:
                    foto_row = db_r.query_one("SELECT ruta FROM fotos WHERE id = ?", (fid_foto,))
                    if foto_row and foto_row.get("ruta"):
                        foto_ruta = foto_row["ruta"]

            db_r.completar_recordatorio(
                rid,
                completado_por=completado_por,
                completado_por_id=uid,
                notas_completado=notas,
                foto_completado=foto_ruta,
            )
            # Notificar al canal del equipo
            try:
                obj = f" ({fila.get('animal_tag') or fila.get('potrero_nombre')})" if (fila.get('animal_tag') or fila.get('potrero_nombre')) else ""
                detalle = f" · {notas}" if notas else ""
                texto_aviso = f"✅ Tarea realizada por {completado_por}{obj}: {fila.get('mensaje')}{detalle}"
                db_r.conn.execute(
                    "INSERT INTO mensajes_equipo (user_id, nombre, rol, texto, creado_en) VALUES (?, ?, ?, ?, ?)",
                    (uid, completado_por, _rol_actual() or "USUARIO", texto_aviso, db_r._ahora()),
                )
                db_r.conn.commit()
            except Exception:
                pass

            return jsonify({
                "ok": True,
                "id": rid,
                "estado": "REALIZADO",
                "completado_por": completado_por,
                "notas": notas,
                "foto_ruta": foto_ruta,
            })
        except Exception:
            logger.exception("Error completando recordatorio de agenda")
            return jsonify({"ok": False, "error": "No se pudo completar el recordatorio."}), 500
        finally:
            try:
                db_r.close()
            except Exception:
                pass

    @app.post("/api/eventos/eliminar")
    def api_eliminar_evento():
        """Elimina un evento registrado en la base de datos con reversión inteligente de estados.
        Restringido a roles OWNER y ADMIN.
        """
        rol = _rol_actual()
        if rol != "OWNER":
            return jsonify({
                "ok": False,
                "error": "Acceso restringido: solo el propietario (OWNER) puede eliminar eventos del sistema.",
            }), 403

        datos = request.get_json(silent=True) or request.form or {}
        tipo = str(datos.get("tipo") or "").strip()
        try:
            eid = int(datos.get("id"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "ID de evento inválido o faltante."}), 400

        if not tipo:
            return jsonify({"ok": False, "error": "Tipo de evento no especificado."}), 400

        db_r = _db(db_path)
        try:
            uid = session.get("user_id") if session is not None else None
            res = db_r.eliminar_evento(tipo=tipo, eid=eid, user_id=uid)
            if not res.get("ok"):
                return jsonify(res), 404

            # Notificar al canal de auditoría / equipo
            try:
                nombre_autor = session.get("nombre") or session.get("username") or "Administrador"
                texto_aviso = f"🗑️ Evento de {tipo.upper()} #{eid} eliminado del sistema por {nombre_autor} ({rol})."
                db_r.conn.execute(
                    "INSERT INTO mensajes_equipo (user_id, nombre, rol, texto, creado_en) VALUES (?, ?, ?, ?, ?)",
                    (uid, nombre_autor, rol, texto_aviso, db_r._ahora()),
                )
                db_r.conn.commit()
            except Exception:
                pass

            return jsonify(res)
        except Exception as e:
            logger.exception("Error al eliminar evento %s #%s: %s", tipo, eid, e)
            return _error_interno(500)
        finally:
            try:
                db_r.close()
            except Exception:
                pass

    @app.get("/api/eventos/recientes")
    def api_eventos_recientes():
        """Lista los últimos eventos de campo registrados con datos para deshacer."""
        rol = _rol_actual()
        limite = request.args.get("limite", 30, type=int)
        limite = max(5, min(100, limite))
        db_r = _db(db_path)
        try:
            filas = db_r.ultimos_registros(limite=limite)
            eventos = []
            for f in filas:
                eventos.append({
                    "id": f["id"],
                    "tabla": f["tabla"],
                    "tag": f["tag"],
                    "fecha": f["fecha"],
                    "resumen": f["resumen"],
                    "creado_en": f["creado_en"],
                    "registrado_por": f["registrado_por"],
                })
            return jsonify({
                "ok": True,
                "eventos": eventos,
                "puede_deshacer": rol == "OWNER",
                "rol": rol,
            })
        except Exception as e:
            logger.exception("Error al listar eventos recientes: %s", e)
            return _error_interno(500)
        finally:
            try:
                db_r.close()
            except Exception:
                pass

    @app.get("/api/equipo/integrantes")
    def api_equipo_integrantes():
        """Lista roles estándar y usuarios activos para asignación de tareas de campo."""
        roles_base = ["Encargado", "Administrador", "Veterinario", "Trabajador"]
        integrantes = [{"nombre": r, "tipo": "ROL"} for r in roles_base]
        try:
            try:
                from ...server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth
            auth_inst = Auth(users_file)
            for u in auth_inst.listar_usuarios():
                nom = (u.get("nombre") or u.get("username") or "").strip()
                if nom and not any(it["nombre"].lower() == nom.lower() for it in integrantes):
                    integrantes.append({"nombre": nom, "rol": u.get("rol"), "tipo": "USUARIO"})
        except Exception:
            pass
        return jsonify({"ok": True, "integrantes": integrantes})

    @app.get("/api/buscar")
    def api_buscar():
        q = (request.args.get("q") or "").strip()
        out = datos_buscar(db_path, q=q)
        return jsonify(out)

    @app.get("/api/toros")
    def api_toros():
        """Lista de toros reproductores activos oficiales de la finca (T01..T05, prefijo T+número o marca [REPRODUCTOR])."""
        db_t = _db(db_path)
        try:
            filas = db_t.query("""
                SELECT tag, nombre, raza, fecha_nacimiento, notas FROM animales
                WHERE estado = 'ACTIVO' AND (
                    tag GLOB 'T[0-9]*'
                    OR UPPER(COALESCE(notas, '')) LIKE '%[REPRODUCTOR]%'
                    OR UPPER(COALESCE(notas, '')) LIKE '%TORO%'
                )
                ORDER BY CASE WHEN tag GLOB 'T[0-9]*' THEN 0 ELSE 1 END, tag ASC
            """)
            toros = []
            for r in filas:
                nom = " ".join((r["nombre"] or "").split())
                raza_raw = (r["raza"] or "").strip()
                raza_corta = raza_raw
                if "+" in raza_raw:
                    raza_corta = raza_raw.split("+")[0].strip()
                import re as _re
                raza_corta = _re.sub(r'^\s*(\d+/\d+|\d+(\.\d+)?%)\s*', '', raza_corta).strip()
                raza_corta = _re.sub(r'\s+Puro$', '', raza_corta).strip()
                toros.append({
                    "tag": r["tag"],
                    "nombre": nom,
                    "raza": raza_corta or raza_raw,
                    "raza_completa": raza_raw,
                    "fecha_nacimiento": r["fecha_nacimiento"] or "",
                    "es_reproductor": True,
                })
            return jsonify({"ok": True, "toros": toros})
        except Exception as e:
            logger.exception("Error al listar toros: %s", e)
            return _error_interno(500, extra={"toros": []})
        finally:
            try:
                db_t.close()
            except Exception:
                pass

    @app.get("/api/parto/sugerir-padre")
    def api_parto_sugerir_padre():
        """Sugiere el padre más probable para un parto según servicios previos o toros en el mismo potrero."""
        vaca = (request.args.get("vaca") or request.args.get("tag") or "").strip()
        fecha = (request.args.get("fecha") or "").strip() or None
        if not vaca:
            return jsonify({"ok": False, "error": "Parámetro 'vaca' requerido."}), 400
        db_s = _db(db_path)
        try:
            res = db_s.sugerir_padre_parto(vaca, fecha)
            return jsonify(res)
        except Exception as e:
            logger.exception("Error al sugerir padre de parto: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500
        finally:
            try:
                db_s.close()
            except Exception:
                pass

    @app.get("/api/simular-cruzamiento")
    def api_simular_cruzamiento():
        """Simulador de cruzamiento en 1 toque (Fase 5.2): vaca + toro ->
        veredicto de consanguinidad 3G ANTES de servir. Solo lectura
        (nunca crea animales) y abierto a todos los roles autenticados,
        porque el trabajador lo necesita en el corral al inseminar."""
        vaca = (request.args.get("vaca") or "").strip()
        toro = (request.args.get("toro") or "").strip()
        if not vaca or not toro:
            return jsonify({"ok": False, "error": "Indique vaca y toro (ej. ?vaca=JA457&toro=T01)."}), 400
        db_s = _db(db_path)
        try:
            sim = db_s.simular_cruzamiento(vaca, toro)
            sim["ok"] = True
            return jsonify(sim)
        except Exception:
            logger.exception("Error al simular cruzamiento %s x %s", vaca, toro)
            return jsonify({"ok": False, "error": "No se pudo evaluar el cruzamiento."}), 500
        finally:
            try:
                db_s.close()
            except Exception:
                pass

    @app.get("/api/badges")
    def api_badges():
        # Contadores ligeros para los badges de la navegación (Agenda/Repro/Sanidad).
        try:
            dias = int(request.args.get("dias") or 7)
        except (TypeError, ValueError):
            dias = 7
        out = datos_badges(db_path, dias=max(1, min(dias, 60)))
        return jsonify(out)

    @app.post("/api/identificar")
    @_limite_api("identificar")
    def api_identificar():
        # Identificación por texto (arete/RFID/lector de corral) o foto del
        # arete. SOLO LECTURA: nunca inserta ni actualiza registros.
        texto = (request.form.get("texto") or "").strip() or None
        foto = request.files.get("foto") if request.files else None
        if not texto and (foto is None or not foto.filename):
            return jsonify({"existe": False, "error": "Envíe 'texto' (arete/RFID) o un archivo 'foto'."}), 400
        if foto is not None and foto.filename:
            ext = (os.path.splitext(foto.filename)[1] or ".jpg").lower()
            if ext not in _EXTENSIONES_IMAGEN_PERMITIDAS:
                ext = ".jpg"
            foto_bytes = foto.read()
            if not _es_imagen_valida(foto_bytes):
                return jsonify({"existe": False, "error": "El archivo enviado no es una imagen válida."}), 400
            out = datos_identificar(db_path, foto_bytes=foto_bytes, foto_ext=ext)
        else:
            out = datos_identificar(db_path, texto=texto)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/usuario")
    def api_usuario():
        return jsonify(_usuario_actual())

    def _resolver_presencia_usuario(u: dict, presencias: dict[str, dict]) -> dict:
        uid = str(u.get("user_id"))
        tg_id = str(u.get("telegram_id")) if u.get("telegram_id") else None
        rol_u = str(u.get("rol", "")).upper()

        candidatos = []
        if uid in presencias:
            candidatos.append(presencias[uid])
        if tg_id and tg_id in presencias:
            candidatos.append(presencias[tg_id])
        if rol_u == "OWNER" and "Propietario" in presencias:
            candidatos.append(presencias["Propietario"])

        if not candidatos:
            return {}

        # Priorizar sesión que esté 'en_linea'; en empate, la de menor segundos_desde (más reciente)
        candidatos.sort(key=lambda c: (0 if c.get("en_linea") else 1, c.get("segundos_desde", 999999)))
        return candidatos[0]

    @app.get("/api/usuarios")
    def api_listar_usuarios():
        rol = _rol_actual()
        if rol not in ("OWNER", "ADMIN", "ADMINISTRADOR"):
            return jsonify({"error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403
        try:
            try:
                from ...server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            usuarios = auth_inst.listar_usuarios()
            # El PIN se guarda hasheado (no recuperable) -- nunca se manda el
            # valor crudo al frontend, solo si tiene uno asignado o no.
            for u in usuarios:
                u["pin"] = "····" if u.get("pin") else ""

            # EXCLUSIVO OWNER: adjuntar presencia en vivo
            if rol == "OWNER":
                try:
                    db_u = _db(db_path)
                    presencias = db_u.obtener_usuarios_presencia()
                    db_u.close()
                except Exception:
                    presencias = {}
                for u in usuarios:
                    p = _resolver_presencia_usuario(u, presencias)
                    u["online_info"] = {
                        "en_linea": p.get("en_linea", False),
                        "estado": p.get("estado", "offline"),
                        "canal": p.get("canal", ""),
                        "ip": p.get("ip", ""),
                        "ultima_actividad": p.get("ultima_actividad", ""),
                        "hace_texto": p.get("hace_texto", "Nunca"),
                    }
            return jsonify({"ok": True, "usuarios": usuarios, "mi_rol": rol})
        except Exception:
            logger.exception("Error al listar usuarios")
            return _error_interno(500, con_ok=False)

    @app.get("/api/usuarios/online")
    def api_usuarios_online():
        """Consulta de usuarios conectados en vivo (EXCLUSIVO OWNER)."""
        rol = _rol_actual()
        if rol != "OWNER":
            return jsonify({"error": "Acceso denegado. Solo el rol OWNER puede ver usuarios conectados."}), 403

        db_inst = _db(db_path)
        try:
            presencias = db_inst.obtener_usuarios_presencia()
            try:
                from ...server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            usuarios = auth_inst.listar_usuarios()

            resultado = []
            en_linea_cnt = 0
            for u in usuarios:
                p = _resolver_presencia_usuario(u, presencias)
                en_linea = p.get("en_linea", False)
                if en_linea:
                    en_linea_cnt += 1
                resultado.append({
                    "user_id": u.get("user_id"),
                    "nombre": u.get("nombre"),
                    "rol": u.get("rol"),
                    "telegram_id": u.get("telegram_id"),
                    "avatar": u.get("avatar"),
                    "en_linea": en_linea,
                    "estado": p.get("estado", "offline"),
                    "canal": p.get("canal", ""),
                    "ip": p.get("ip", ""),
                    "ultima_actividad": p.get("ultima_actividad", ""),
                    "hace_texto": p.get("hace_texto", "Nunca"),
                })
            return jsonify({
                "ok": True,
                "total": len(resultado),
                "en_linea_count": en_linea_cnt,
                "usuarios": resultado,
            })
        finally:
            db_inst.close()

    @app.route("/api/heartbeat", methods=["GET", "POST"])
    def api_heartbeat():
        """Latido para mantener activo el estado de conexión en la PWA."""
        if not session.get("autenticado"):
            return jsonify({"error": "No autenticado"}), 401
        try:
            db_inst = _db(db_path)
            uid = session.get("user_id") or session.get("nombre")
            nom = session.get("nombre") or ""
            rol = session.get("rol") or "TRABAJADOR"
            ip = _cliente_ip()
            db_inst.registrar_presencia(user_id=uid, nombre=nom, rol=rol, canal="PWA", ip=ip)
            db_inst.close()
        except Exception:
            pass
        return jsonify({"ok": True})

    @app.get("/api/mensajes-equipo")
    @_limite_api("mensajes")
    def api_mensajes_equipo():
        """Lista el canal único de avisos del equipo (broadcast, cualquier rol autenticado)."""
        try:
            despues_de = int(request.args.get("despues_de") or 0)
        except (TypeError, ValueError):
            despues_de = 0
        try:
            limite = int(request.args.get("limite") or 50)
        except (TypeError, ValueError):
            limite = 50
        db_m = _db(db_path)
        try:
            filas = db_m.listar_mensajes_equipo(despues_de_id=despues_de, limite=limite)
            mensajes = [dict(f) for f in filas]
            ultimo_id = mensajes[-1]["id"] if mensajes else despues_de
            return jsonify({"ok": True, "mensajes": mensajes, "ultimo_id": ultimo_id})
        finally:
            db_m.close()

    @app.post("/api/mensajes-equipo")
    @_limite_api("mensajes")
    def api_mensajes_equipo_crear():
        """Publica un mensaje en el canal de equipo (cualquier rol autenticado)."""
        datos = request.get_json(silent=True) or {}
        texto = str(datos.get("texto") or "").strip()
        if not texto:
            return jsonify({"ok": False, "error": "El mensaje no puede estar vacío."}), 400
        if len(texto) > 500:
            return jsonify({"ok": False, "error": "El mensaje no puede superar 500 caracteres."}), 400

        uid = session.get("user_id")
        nombre = session.get("nombre") or "Usuario"
        rol = session.get("rol") or _rol_actual() or "TRABAJADOR"
        db_m = _db(db_path)
        try:
            mid = db_m.registrar_mensaje_equipo(user_id=uid, nombre=nombre, rol=rol, texto=texto)
            fila = db_m.obtener_mensaje_equipo(mid)
            try:
                from ...server.push_sender import enviar_push
            except (ImportError, ValueError):
                from src.server.push_sender import enviar_push  # type: ignore
            try:
                enviar_push(
                    db_m,
                    titulo=f"👥 {nombre}",
                    cuerpo=texto[:120],
                    url="/",
                    tag="chat-equipo",
                    excluir_user_id=uid,
                )
            except Exception:
                logger.exception("No se pudo enviar push del chat de equipo")
            return jsonify({"ok": True, "mensaje": dict(fila) if fila else None})
        finally:
            db_m.close()

    @app.delete("/api/mensajes-equipo/<int:id_mensaje>")
    def api_mensajes_equipo_eliminar(id_mensaje):
        """Borra un mensaje del canal de equipo (autor propio, u OWNER/ADMIN para moderar)."""
        mi_uid = session.get("user_id")
        mi_rol = _rol_actual()
        db_m = _db(db_path)
        try:
            fila = db_m.obtener_mensaje_equipo(id_mensaje)
            if not fila:
                return jsonify({"ok": False, "error": "El mensaje no existe."}), 404
            es_autor = mi_uid is not None and str(fila["user_id"]) == str(mi_uid)
            es_moderador = mi_rol in ("OWNER", "ADMIN", "ADMINISTRADOR")
            if not (es_autor or es_moderador):
                return jsonify({"ok": False, "error": "Solo el autor o un OWNER/ADMIN pueden borrar este mensaje."}), 403
            db_m.eliminar_mensaje_equipo(id_mensaje)
            return jsonify({"ok": True})
        finally:
            db_m.close()

    @app.post("/api/usuarios")
    def api_guardar_usuario():
        mi_rol = _rol_actual()
        if mi_rol not in ("OWNER", "ADMIN", "ADMINISTRADOR"):
            return jsonify({"error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403

        datos = request.get_json(silent=True) or request.form
        nombre = (datos.get("nombre") or "").strip()
        rol_nuevo = str(datos.get("rol") or "TRABAJADOR").strip().upper()
        pin = str(datos.get("pin") or "").strip()
        uid_raw = datos.get("user_id")
        tg_id_raw = datos.get("telegram_id")
        avatar = str(datos.get("avatar") or "").strip() or None

        tg_id = None
        borrar_tg = False
        if tg_id_raw is not None and str(tg_id_raw).strip() != "":
            try:
                tg_id = int(tg_id_raw)
            except (ValueError, TypeError):
                return jsonify({"error": "El ID de Telegram debe ser un número entero (ej. 6123051140)."}), 400
        elif "telegram_id" in datos and (tg_id_raw is None or str(tg_id_raw).strip() == ""):
            borrar_tg = True

        if not nombre:
            return jsonify({"error": "El nombre del usuario es obligatorio."}), 400
        if rol_nuevo not in ("OWNER", "ADMIN", "TRABAJADOR"):
            return jsonify({"error": f"Rol inválido: {rol_nuevo}. Permitidos: OWNER (Level 1), ADMIN (Level 2), TRABAJADOR (Level 3)."}), 400

        # Un ADMIN no puede crear usuarios OWNER ni auto-promocionarse
        if mi_rol != "OWNER" and rol_nuevo == "OWNER":
            return jsonify({"error": "Solo un OWNER (Level 1) puede crear o asignar el rol OWNER."}), 403

        # Validar PIN: 4 dígitos numéricos
        if not re.match(r"^\d{4}$", pin):
            return jsonify({"error": "El PIN debe tener exactamente 4 dígitos numéricos (ej. 4521)."}), 400

        try:
            try:
                from ...server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            usuarios = auth_inst.listar_usuarios()

            # Resolver o generar ID local secuencial (1, 2, 3...)
            if uid_raw:
                try:
                    uid = int(uid_raw)
                except (ValueError, TypeError):
                    return jsonify({"error": "user_id debe ser un entero numérico."}), 400
            else:
                ids_existentes = [int(u.get("user_id", 0)) for u in usuarios if isinstance(u.get("user_id"), int) and int(u.get("user_id", 0)) < 1000000]
                uid = (max(ids_existentes) + 1) if ids_existentes else 1

            # Jerarquía: un ADMIN no puede editar a un OWNER ni a otro ADMIN.
            bloqueo = _bloqueo_gestion_usuario(mi_rol, auth_inst.obtener_usuario(uid))
            if bloqueo:
                return jsonify({"error": bloqueo}), 403
            # Un telegram_id solo puede pertenecer a un usuario: si no, las
            # búsquedas por telegram_id resolverían al usuario equivocado.
            if tg_id is not None:
                for u in usuarios:
                    if u.get("telegram_id") == tg_id and u.get("user_id") != uid:
                        return jsonify({"error": "Ese ID de Telegram ya está asignado a otro usuario."}), 400

            # Verificar que el PIN no esté en colisión con OTRO usuario. Los
            # PIN se guardan hasheados, así que no se puede comparar por
            # igualdad de string -- usuario_con_pin verifica contra cada hash.
            # Mensaje genérico a propósito: no revela el PIN ni a quién
            # pertenece, para que un ADMIN no pueda cosechar PINs ajenos.
            u_dup = auth_inst.usuario_con_pin(pin, excluir_user_id=uid)
            if u_dup is not None:
                return jsonify({"error": "Ese PIN ya está asignado a otro usuario. Elija un PIN de 4 dígitos diferente."}), 400

            auth_inst.agregar_usuario(
                user_id=uid,
                nombre=nombre,
                rol=rol_nuevo,
                pin=pin,
                telegram_id=tg_id,
                avatar=avatar,
                borrar_telegram_id=borrar_tg,
            )
            usr_guardado = auth_inst.obtener_usuario(uid) or {}
            # El PIN nunca vuelve al cliente: ya quedó hasheado en
            # users.json y el frontend solo muestra "····". Quien creó el
            # usuario debe dictar el PIN en persona, no por la red.
            return jsonify({
                "ok": True,
                "mensaje": f"Usuario '{nombre}' (Level {1 if rol_nuevo=='OWNER' else 2 if rol_nuevo=='ADMIN' else 3}) guardado exitosamente.",
                "usuario": {
                    "user_id": uid,
                    "telegram_id": usr_guardado.get("telegram_id"),
                    "nombre": nombre,
                    "rol": rol_nuevo,
                    "avatar": usr_guardado.get("avatar") or ("patron" if rol_nuevo=="OWNER" else "admin" if rol_nuevo=="ADMIN" else "vaquero"),
                }
            })
        except Exception:
            logger.exception("Error al guardar usuario")
            return _error_interno(400, con_ok=False)

    @app.post("/api/usuarios/<int:target_uid>/pin")
    def api_cambiar_pin_usuario(target_uid: int):
        mi_rol = _rol_actual()
        if mi_rol not in ("OWNER", "ADMIN", "ADMINISTRADOR"):
            return jsonify({"error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403

        datos = request.get_json(silent=True) or request.form
        nuevo_pin = str(datos.get("pin") or "").strip()
        if not re.match(r"^\d{4}$", nuevo_pin):
            return jsonify({"error": "El nuevo PIN debe tener exactamente 4 dígitos numéricos."}), 400

        try:
            try:
                from ...server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)

            # Jerarquía: resolver por user_id o telegram_id, igual que asignar_pin.
            objetivo = auth_inst.obtener_usuario(target_uid)
            if objetivo is None:
                return _error_interno(400, con_ok=False)
            bloqueo = _bloqueo_gestion_usuario(mi_rol, objetivo)
            if bloqueo:
                return jsonify({"error": bloqueo}), 403
            target_uid = int(objetivo.get("user_id"))

            # Verificar colisión de PIN (contra cada hash, ver usuario_con_pin).
            # Genérico a propósito: no revela el PIN ni a quién pertenece.
            u_dup = auth_inst.usuario_con_pin(nuevo_pin, excluir_user_id=target_uid)
            if u_dup is not None:
                return jsonify({"error": "Ese PIN ya está asignado a otro usuario. Ingrese un PIN diferente."}), 400

            auth_inst.asignar_pin(target_uid, nuevo_pin)
            return jsonify({"ok": True, "mensaje": "PIN actualizado exitosamente."})
        except Exception:
            logger.exception("Error al cambiar PIN")
            return _error_interno(400, con_ok=False)

    @app.post("/api/usuarios/<int:target_uid>/eliminar")
    def api_eliminar_usuario(target_uid: int):
        mi_rol = _rol_actual()
        if mi_rol not in ("OWNER", "ADMIN", "ADMINISTRADOR"):
            return jsonify({"error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403

        try:
            try:
                from ...server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            usuarios = auth_inst.listar_usuarios()

            target_user = next((u for u in usuarios if u.get("user_id") == target_uid), None)
            if not target_user:
                return jsonify({"error": f"Usuario con ID {target_uid} no encontrado."}), 404

            target_rol = str(target_user.get("rol", "")).strip().upper()

            # Si es ADMIN, no puede eliminar OWNER ni otro ADMIN
            if mi_rol != "OWNER" and target_rol in ("OWNER", "ADMIN"):
                return jsonify({"error": "Un ADMIN solo puede eliminar usuarios de rol TRABAJADOR."}), 403

            auth_inst.quitar_usuario(target_uid)
            return jsonify({"ok": True, "mensaje": f"Usuario '{target_user.get('nombre')}' eliminado exitosamente."})
        except Exception:
            logger.exception("Error al eliminar usuario")
            return _error_interno(400, con_ok=False)
