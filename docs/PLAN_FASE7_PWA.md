# 📱 Plan Fase 7 — PWA Oficina + Corral Offline

> **Proyecto:** Bot Bitácora de Campo Ganadero — Fase 7 (ROADMAP_FASES_4-8.md)
> **Fecha:** 2026-09-03 | **Actualizado:** 2026-09-05 | **Estado:** ✅ Completamente implementada (Etapas A, B, C, D, E y RBAC)
> **Principio:** No romper Telegram. La PWA es solo una vista nueva sobre el mismo SQLite.

---

## 1. Punto de partida: qué se reutiliza (sin reinventar)

| Ya existe en el repo | Cómo se reutiliza en Fase 7 |
|---|---|
| `src/db/database.py` + `models.py` (SQLite en WAL, `busy_timeout=10000`) | La PWA lee y escribe sobre el mismo `data/bitacora.db`. Tabla `rondas_campo` para auditoría de rondas y potreros GPS. Regla de oro: todo inventario filtra `estado='ACTIVO'`. |
| `src/server/auth.py` (RBAC OWNER/ADMIN/TRABAJADOR + `users.json`) | Autenticación con PIN individual de 4 dígitos. OWNER ve métricas del sistema VPS/logs; ADMIN ve tableros zootécnicos y reportes PDF/Excel; TRABAJADOR solo captura de campo, manga, GPS y fichas. |
| `src/server/telegram_bot.py` + `formatters.py` + `keyboards.py` | El bot sigue siendo el canal de captura principal. La PWA corre en puerto 8080. Lógica de fichas y tableros compartida. |
| `src/reports/pdf_report.py` (reportlab + logo `GANADERÍA JA`) | Generación y descarga directa de Informes Ejecutivos PDF (`/api/reporte.pdf`) y fichas QR por animal o lote. |
| `src/vision/arete_detector.py` + `src/ocr/` | Detección de aretes OCR y lectura de códigos. |
| `src/engine/query_engine.py` | Motor de lenguaje natural para el Asistente IA (Chat) en la PWA (`/api/preguntar`). |
| `src/parsers/media_handler.py` (Whisper) | Dictado por voz directo en la PWA vía `MediaRecorder` (`/api/voz`). |

---

## 2. Arquitectura implementada (liviana y segura)

```text
Telegram (polling, sin cambios) ─┐
                                 ├─→ SQLite WAL data/bitacora.db ←─ PWA backend (Flask, puerto 8080, endpoints REST)
PWA Oficina (PC, online) ────────┤
PWA Corral (móvil, offline) ─────┘  Service-Worker v20 + IndexedDB(outbox) → sync al volver señal → Manga con GMD y BLE
```

- **Backend:** `Flask` en `src/pwa/app.py` con rutas `/`, `/login`, `/api/*`, `/manifest.json`, `/sw.js`.
- **Frontend:** HTML + JS vainilla + CSS moderno con 4 temas (Verde Campestre, ☀️ Sol de Campo para luz solar directa, Claro Editorial, Modo Oscuro).
- **Offline Real:** Base de datos local `IndexedDB` (`ja_bitacora_offline`, almacén `outbox`) que encola eventos cuando se pierde la señal en el potrero y los sincroniza por lote (`POST /api/sync`) al recuperar conectividad.

---

## 3. Etapas de implementación

### Etapa A — Fichas QR en PDF por lote ✅ IMPLEMENTADA
- Generación de tarjetas QR en PDF plastificables para corral (`src/reports/qr_fichas.py`).
- Descarga individual y por lote (`/api/ficha/<tag>/qr.pdf`). Escaneo por cámara en la PWA.

### Etapa B — Modo Offline Real (Cola IndexedDB + Sync) ✅ IMPLEMENTADA
- Almacén local en navegador `IndexedDB` con cola de salida (`outbox`).
- Sincronización diferida automática al detectar evento `online` o manual mediante el botón de nube en el encabezado.
- Soporte para 8 eventos de campo: Parto, Pesaje, Tratamiento, Traslado, Celo, Servicio/IA, Leche y Muerte.

### Etapa C — Modo Manga de Corral & Conectividad BLE ✅ IMPLEMENTADA
- Pestaña **Manga Corral** optimizada para trabajo continuo de pesaje en corral.
- Cálculo instantáneo en pantalla de la Ganancia Media Diaria (**GMD g/día**) comparando con el pesaje anterior y días transcurridos.
- Historial en vivo de la sesión de manga actual.
- Formulario de tratamiento masivo por potrero o lote de aretes (`POST /api/manga/tratamiento_lote`).
- Integración Web Bluetooth (`navigator.bluetooth`) para recepción inalámbrica desde básculas electrónicas y lectores RFID BLE.

### Etapa D — Dashboard Web Ejecutivo PWA & GPS Potrero ✅ IMPLEMENTADA
- Vistas completas: Tablero general, Agenda de avisos y retiros, Inventario SG + Población unificada, Genética y termo de $N_2$, Reproducción, Sanidad, Pasturas (Voisin + NDVI) y Leche.
- **Geolocalización GPS**: Identificación automática de potrero cruzando lat/lon contra polígonos WGS84 (`potreros.geom_wkt_4326`).
- **Auditoría de Rondas**: Registro de paradas en saladeros, bebederos, cercas y conteo con hora exacta, notas y exportación a CSV.
- **Panel de Servidor VPS (Solo OWNER)**: KPIs en vivo de RAM, disco, tamaño SQLite WAL, estado del termo de $N_2$ y visor de logs recientes (`/api/logs`).

### Etapa E — Inteligencia Zootécnica & Dictado por Voz ✅ IMPLEMENTADA
- **Asistente IA (Chat Natural)**: Modal integrado con respuestas zootécnicas desde `QueryEngine` (`POST /api/preguntar`).
- **Dictado por Voz Directo**: Grabación de notas de voz en campo vía `MediaRecorder` y transcripción automática con Whisper (`POST /api/voz`).
- **Exportación CSV & PDF**: Descargas directas en formato Excel-compatible con BOM UTF-8 y reporte institucional en PDF.

1. **Chat tipo asistente (lenguaje natural)**: un cuadro de texto en el
   dashboard donde se escriben preguntas igual que se le escribe al bot
   de Telegram (ej. "¿cuántas vacas hay en Guayabal?") y responde con los
   mismos datos — reutilizaría el motor de consultas en lenguaje natural
   que ya existe para Telegram (`src/engine/query_engine.py`,
   `src/parsers/nlp_engine.py`) en vez de reinventar el parser. Sería un
   nuevo endpoint de solo lectura tipo `POST /api/preguntar` que delegue
   en ese mismo motor.
2. **Chat/mensajes del equipo**: una sección de notas o avisos donde los
   trabajadores de la finca puedan dejarse mensajes entre sí, visible en
   el dashboard. A diferencia de todo lo demás en la PWA (que es de solo
   lectura), esto **sí implica escritura** — habría que decidir el
   almacenamiento (¿tabla nueva en SQLite? ¿reusar `notas`/`alertas`
   existentes?) y quién puede ver/borrar qué (RBAC), ya que rompe el
   principio "solo lectura" que ha guiado el diseño de seguridad de la
   PWA hasta ahora.

Al retomar: decidir alcance y diseño concreto antes de implementar
(especialmente la Etapa E.2, que necesita repensar el modelo de
autenticación/escritura).

### Etapa F — Usuarios y roles reales en la PWA (idea futura, sin empezar) 💡 ANOTADA 2026-09-05

Pedido del usuario tras preguntar cómo se crean los usuarios de la PWA —
hoy **no se crean**: hay una sola `PWA_PASSWORD` compartida en el `.env`
(quien la tenga, entra) y un campo opcional de "ID de Telegram" en el
login que solo *identifica* la sesión contra `src/server/users.json` (el
mismo archivo que usa el bot) — el rol que devuelve (`OWNER`/`TRABAJADOR`)
se guarda y se puede leer en las respuestas de la API, pero **hoy no
restringe nada**: cualquiera con la contraseña ve exactamente lo mismo,
sin importar su rol.

Para que esto sea real haría falta:
1. **Contraseña por persona** en vez de una compartida (ej. agregar un
   campo `pwa_pin`/hash de contraseña a cada entrada de `users.json`, o
   una tabla nueva) — así se sabe quién entró realmente, no solo "alguien
   con la clave".
2. **Aplicar el rol a lo que se muestra/permite**, no solo guardarlo —
   ej. si algún día la Etapa E.2 (chat de equipo) o cualquier endpoint de
   escritura se implementa, decidir explícitamente qué puede hacer
   TRABAJADOR vs OWNER.

Está directamente relacionado con la Etapa E de arriba: cualquier feature
de escritura (chat de equipo, etc.) casi seguro necesita resolver esto
primero. Nada de esto está diseñado en detalle ni implementado, es solo
la nota para no perder la idea.

---

## 4. Tabla de tareas y estimación relativa (S <1d, M 2-4d, L 1-2 sem)

| # | Tarea | Archivos | Talla | Rol |
|---|---|---|:---:|---|
| A1 | `qr_fichas.py` + comando `/qr <potrero/lote>` + test PDF con QR legible | `src/reports/qr_fichas.py`, `src/server/telegram_bot.py`, `tests/test_qr_fichas.py` | S | OWNER/ADMIN |
| A2 | Cache QR + botón `[ 🖨️ Fichas QR ]` | `data/qr_cache/`, `src/server/keyboards.py` | S | — |
| B1 | `sync_queue.py` (validar + deduplicar + aplicar + `/api/sync`) | `src/offline/sync_queue.py`, `src/pwa/app.py` | M | ADMIN+ |
| B2 | Service-Worker + `manifest.json` + app-shell cache + `IndexedDB outbox` + formulario 8 eventos | `src/pwa/static/*`, `src/pwa/sw.js` | L | TRABAJADOR |
| B3 | Botón SOS (local + envío prioritario + alerta Telegram OWNER) | `src/pwa/static/sos.js`, `src/offline/sync_queue.py` | S | Todos |
| C1 | `POST /api/identificar` reusando `arete_detector.py` + 3 candidatos | `src/pwa/app.py`, `src/vision/arete_detector.py` | M | TRABAJADOR |
| C2 | `src/rfid/reader.py` modo wedge + input universal en PWA | `src/rfid/reader.py`, `src/pwa/static/identificar.js` | S | TRABAJADOR |
| D1 | Backend Flask `/api/tablero|repro|sanidad|pasturas|leche|ficha` (envoltorios lectura) | `src/pwa/app.py` | M | OWNER/ADMIN |
| D2 | Frontend dashboard + ficha animal + filtros | `src/pwa/templates/*`, `src/pwa/static/app.js` | L | OWNER/ADMIN |
| D3 | `scripts/iniciar_pwa.sh` + Nginx/systemd + `tests/test_pwa_api.py` | `scripts/iniciar_pwa.sh`, `tests/` | S | OWNER |

**Estructura final a crear (respetando `src/ docs/ tests/ scripts/`):**
```text
src/pwa/app.py, templates/, static/ (index, ficha, cola, sos.js, sw.js, manifest)
src/reports/qr_fichas.py
src/offline/sync_queue.py
src/rfid/reader.py
scripts/iniciar_pwa.sh
tests/test_qr_fichas.py, tests/test_pwa_api.py, tests/test_sync_queue.py
```

---

## 5. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Doble escritura Telegram + PWA corrompe SQLite | Alto | WAL + `busy_timeout` ya activos; PWA dashboard solo `query`; escritura solo por `/api/sync` con reintento + backoff. |
| Cola offline duplica eventos al reintentar | Alto | Idempotencia por llaves naturales (`animal+fecha+tipo/peso`) igual que importador DBF; `id_local` del móvil como clave anti-replay. |
| Fotos offline llenan el móvil | Medio | Comprimir a ≤800px JPEG 70% antes de guardar; límite 50 fotos en outbox con aviso. |
| OCR arete falla con barro total | Medio | Siempre ofrecer manual + RFID; ráfaga 3 fotos; no bloquear captura por fallo de OCR. |
| PWA se vuelve pesada (React/build) | Medio | Prohibido framework: solo HTML/JS vainilla + 1 dependencia Flask. App-shell <500 KB. |
| Exponer datos fuera de Telegram | Alto | Mismo `users.json`/RBAC; HTTPS vía Nginx + token; TRABAJADOR sin costos/export; log de accesos. |

---

## 6. Criterios de aceptación (qué significa "Fase 7 lista")

1. **QR:** `/qr <potrero>` genera en <30 s un PDF A4 con 6 tarjetas por hoja; 3 celulares distintos leen el QR y abren `/ficha/<tag>`.
2. **Offline:** con modo avión se guardan 5 eventos + 2 fotos en outbox; al volver la señal se sincronizan sin duplicados (verificado en `tests/test_sync_queue.py`) y aparecen en Telegram/reporte.
3. **SOS:** en modo avión el botón SOS guarda punto con GPS/hora; al recuperar señal el OWNER recibe la alerta en <2 min.
4. **ID corral:** 10 fotos reales de aretes con barro identifican ≥7 al primer intento o proponen el tag correcto entre 3 candidatos; bastón RFID escribe el tag en el input sin driver.
5. **Dashboard:** oficina abre PWA instalada, filtra por potrero y ve las 6 vistas con datos iguales a `/status` y `/reporte` (sin diferencia de inventario; solo `ACTIVO`).
6. **No regresión:** `pytest` en verde (incluye 3 archivos nuevos de test), Telegram sigue funcionando con el bot + PWA corriendo a la vez, y `graphify update .` ejecutado.
