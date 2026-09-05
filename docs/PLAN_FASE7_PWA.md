# 📱 Plan Fase 7 — PWA Oficina + Corral Offline

> **Proyecto:** Bot Bitácora de Campo Ganadero — Fase 7 (ROADMAP_FASES_4-8.md)
> **Fecha:** 2026-09-03 | **Actualizado:** 2026-09-05 | **Estado:** A y D ✅ implementadas + B-lite (offline lectura) ✅; B completa y C pendientes
> **Principio:** No romper Telegram. La PWA es solo una vista nueva sobre el mismo SQLite.

---

## 1. Punto de partida: qué se reutiliza (sin reinventar)

| Ya existe en el repo | Cómo se reutiliza en Fase 7 |
|---|---|
| `src/db/database.py` + `models.py` (SQLite en WAL, `busy_timeout=10000`) | La PWA lee el mismo `data/bitacora.db`. Solo lectura para dashboard; escritura solo vía cola validada. Regla de oro: todo inventario filtra `estado='ACTIVO'`. |
| `src/server/auth.py` (RBAC OWNER/ADMIN/TRABAJADOR + `users.json`) | Mismo login para PWA: OWNER/ADMIN ven todo, TRABAJADOR solo captura y fichas. Se reutiliza el candado + escritura atómica. |
| `src/server/telegram_bot.py` + `formatters.py` + `keyboards.py` | El bot sigue siendo el canal de captura principal. La PWA corre en otro puerto/proceso y nunca bloquea el polling. Lógica de fichas y tableros se importa, no se copia. |
| `src/reports/pdf_report.py` (reportlab + logo `GANADERÍA JA`, colores marca) | Base para `qr_fichas.py`: misma paleta, cabecera y helpers `_resumen_*`. Solo se agrega capa QR + layout tarjeta. |
| `src/vision/arete_detector.py` (CLAHE, bilateral, paleta vs botón, corrección `O→0, I→1, G→6, S→5, B→8`) + `src/ocr/` | Endpoint `/api/identificar` reusa este detector tal cual + `pytesseract`. Sin modelo nuevo en esta fase. |
| `media/` + tabla `fotos` (con `ocr_text`) | Dashboard y fichas muestran la foto ya vinculada. Sin migración nueva salvo columna `qr_payload` opcional. |
| `src/engine/consultas.py`, pasturas Voisin, NDVI (`/ndvi`, `/ocupacion`) | Endpoints `/api/*` son envoltorios finos sobre estas funciones. |

---

## 2. Arquitectura elegida (liviana y segura)

```text
Telegram (polling, sin cambios) ─┐
                                 ├─→ SQLite WAL data/bitacora.db ←─ PWA backend (Flask, puerto 8080, solo lectura + /sync validado)
PWA Oficina (PC, online) ────────┤
PWA Corral (móvil, offline) ─────┘  Service-Worker + IndexedDB(outbox) → sync al volver señal → SOS si emergencia
```

- **Backend:** `Flask` (una sola dependencia nueva: `Flask` + `qrcode[pil]`). Alternativa válida `FastAPI`, pero Flask es más liviano para el VPS actual. Un solo archivo `src/pwa/app.py` con rutas `/` , `/api/*`, `/manifest.json`, `/sw.js`.
- **Frontend:** HTML + JS vainilla + CSS simple (sin React). App-shell cacheable: `index.html`, `ficha.html`, `cola.html`. Funciona instalada ("Agregar a inicio").
- **Por qué no rompe Telegram:** proceso aparte (`scripts/iniciar_pwa.sh`), puerto distinto (Telegram bot + Flask conviven por WAL), dashboard en modo lectura (`query`, sin `execute` directo), toda escritura entra por `/api/sync` que valida rol + llaves naturales idempotentes (igual que `dbf_importer`).
- **Seguridad:** login con `user_id` + token simple firmado (reusa `users.json`); TRABAJADOR no ve costos ni `/api/export`.

---

## 3. Etapas de implementación (orden recomendado)

> Se empieza por lo de mayor valor/campo fácil (QR + offline) y se deja el dashboard completo al final, según matriz del roadmap (7.3 y 7.1 antes que 7.2).

### Etapa A — Fichas QR en PDF por lote (base de corral) ✅ IMPLEMENTADA
> ✅ **Estado 2026-09-05:** Implementada (ruta QR `/ficha/<tag>`, fichas QR por lote; ver README Fase 7).
- Nuevo `src/reports/qr_fichas.py`: `generar_fichas_lote(db, potrero/lote) → PDF`.
- Cada tarjeta: foto mini, tag grande, QR (payload `JA://animal/<tag>` + URL `/ficha/<tag>`), potrero, edad zootécnica, estado repro/retiro. Hoja A4 de 6 tarjetas plastificables.
- Comandos Telegram que la disparan: `/qr <potrero>` y `/qr <lote>` (reusan `/exportar` y `/reporte`). Botón `[ 🖨️ Fichas QR ]`.
- Detalle técnico: librería `qrcode` + `reportlab` (ya instalado); QR en nivel `M`, 300 dpi; cache en `data/qr_cache/`.

### Etapa B — Modo Offline Lite (cola + sync + SOS) 🟡 PARCIAL (solo lectura)
> 🟡 **Estado 2026-09-05:** B-lite implementada — Service Worker solo lectura (`src/pwa/static/sw.js`: cache-first estáticos, network-first `/api` y `/media` con respaldo, fallback a `/offline.html`), `src/pwa/static/offline.html`, registro SW en `index.html`/`ficha.html`, rutas públicas `/sw.js` y `/offline.html` en `src/pwa/app.py`, `manifest.json` ampliado (id, scope, lang, maskable). Pendiente B completa: cola de escritura + sync + SOS (`src/offline/sync_queue.py`, IndexedDB outbox, `/api/sync`).
- Nuevo `src/offline/sync_queue.py`: valida, deduplica (llaves `animal+fecha+tipo`) y aplica la cola. Tablas NO nuevas: reusa `TABLAS_EVENTOS` + columnas `creado_en/registrado_por`.
- Frontend: `IndexedDB` tabla `outbox` (`id_local, tipo_evento, payload, foto_blob, creado_en, estado`). Botón `Guardar local` siempre disponible; `Sincronizar` manual + `Background Sync` auto.
- Formulario mínimo offline: 8 eventos como selects + foto opcional (comprimida a ≤800px). Sin NLU offline: se guarda texto crudo y el servidor lo parsea al sincronizar.
- **Botón SOS:** siempre visible, funciona sin señal: guarda evento `SOS` con GPS + hora local y al recuperar 1 barra lo envía primero con prioridad (Telegram al OWNER + marca roja en dashboard). Si hay señal nula total, muestra instrucciones (llamar / punto alto).

### Etapa C — Identificación rápida en corral (foto arete + RFID barro) ⏳ PENDIENTE
> ⏳ **Estado 2026-09-05:** Pendiente — falta `POST /api/identificar` + `src/rfid/reader.py`.
- Endpoint `POST /api/identificar` (online) y modo foto-local (offline: guarda foto y la identifica al sincronizar).
- Flujo: foto → `arete_detector.py` (preproceso CLAHE + clasificación paleta/botón) → `pytesseract` → `corregir_caracteres_confusos()` → propone 3 candidatos + ficha. Si barro total, campo manual + lectura RFID.
- Nuevo `src/rfid/reader.py`: lector tipo "teclado" (wedge USB/BLE): el bastón escribe el tag como si fuera teclado; el JS lo captura en un `<input>` sin driver especial. Soporta pegado manual `N069 / JA26 / 47`.
- En barro: botón `[ 📷 Foto arete ]` grande, linterna, ráfaga de 3 fotos (se envía la más nítida).

### Etapa D — Dashboard web ejecutivo PWA (oficina) ✅ IMPLEMENTADA (enriquecida, 10 vistas)
> ✅ **Estado 2026-09-05:** Implementada y enriquecida (5 workstreams). Backend adelgazado `src/pwa/app.py` (envoltorios finos + `@app.errorhandler(500)` JSON) sobre fuente única `src/engine/dashboard_data.py` (conteos_tablero, datos_reproduccion/sanidad/pasturas/leche/ficha + datos_inventario/poblacion/genetica/agenda; errores por sección, nunca falso 0). Endpoints `/api/inventario`, `/api/poblacion`, `/api/genetica`, `/api/agenda?dias=N` + 6 base (tablero/repro/sanidad/pasturas/leche/ficha). Frontend: 10 vistas (Tablero, Agenda, Inventario SG, Población, Genética, Reproducción, Sanidad, Pasturas, Leche, Ficha QR), dark mode, KPIs/chips semáforo, ficha 4 pestañas, polling 60 s, skeleton, `style.css`/`app.js`. Verificación: 545 pytest en verde, ruff E9/F limpio, smoke PWA OK.
- Vistas (cada una = 1 tarjeta + 1 endpoint `/api/*` que envuelve `engine/consultas.py`):
  1. `Tablero finca`: activos por categoría, partos/celos/servicios 7d, retiros activos.
  2. `Reproducción`: FEP ≤30d, eco d35, palpación d60, celos AM-PM pendientes.
  3. `Sanidad`: retiros leche/carne con cuenta regresiva + últimos tratamientos.
  4. `Pasturas`: ocupación Voisin (semáforo 1-3/4-6/≥7d), reposo ≥30d, NDVI último.
  5. `Leche`: serie tanque (`produccion_leche`) + DEL/alertas secado.
  6. `Ficha animal /ficha/<tag>`: header + foto + 5 pestañas (igual que Telegram) + QR imprimible.
- Filtros: por potrero, categoría, rango fechas. Todo read-only para TRABAJADOR salvo captura.

### Etapa E — Chat en la PWA (idea futura, sin empezar) 💡 ANOTADA 2026-09-04

Pedido del usuario, a modo de nota para retomar más adelante — no se ha
diseñado en detalle ni implementado nada todavía. Dos ideas, **ambas
deseadas**:

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
