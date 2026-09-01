# 🐄 Guía del Bot de Telegram — Manual para el Personal de Campo

> Manual sencillo para el **mayordomo y los trabajadores**. Aquí no hay palabras
> raras: el bot es como un cuaderno de campo, pero en el celular. Usted manda el
> dato, el bot lo anota solo.

---

## 1. Cómo empezar

1. Abra **Telegram** en su celular.
2. Busque el bot de la finca por su nombre (se lo pasa el dueño).
3. Ábrale el chat y mándele: `/start`
4. Si está autorizado, el bot le muestra qué puede hacer. ¡Listo, ya puede
   mandarle notas!

> 👉 Cada vez que quiera recordar qué puede hacer, mándele `/start` o `/help`.

---

## 2. Cómo anotar cada cosa (solo escríbale al bot, como si hablara)

No hay formularios ni botones. Usted **le escribe la novedad con sus palabras** y
el bot la entiende y la guarda. Vea los ejemplos:

### 🍼 Parto
> `pario la 47, ternero macho`

Dígale la vaca que parió y si fue ternero o ternera.

### 💀 Muerte
> `se murio el 105 mordedura de culebra`

Dígale qué animal se murió y, si sabe, la causa.

### 🐂 Servicio / Inseminación
> `insemine la 12 con toro brahman 502`

Dígale la vaca que sirvió o inseminó, y el toro o pajuela que usó.

### 🔥 Celo (mañana o tarde)
> `celo en la mañana la 33`

Importa si fue **en la mañana o en la tarde**, porque eso define cuándo se
insemina. Dígalo claro: "celo en la mañana la 33" o "celo en la tarde la 33".

### 💉 Tratamiento / remedio
> `le puse ivermectina 5ml via sc a la 8, 30 dias de retiro`

Dígale el animal, el producto, cuánto le puso, por dónde (subcutánea,
intramuscular, etc.) y los días de retiro si los sabe.

### 🚚 Traslado de potrero
> `pase el lote 2 del potrero 3 al potrero 5`

Dígale qué lote o animal movió, de qué potrero y a cuál.

### ⚖️ Pesaje
> `peso 420 kg la 47`

Dígale el animal y cuántos kilos pesó.

### 🥛 Control de Leche (Individual y Total)
> `la 47 dio 12 litros de leche`  *(Vaca individual)*  
> `/leche 475`  *(Total del hato recogido hoy en el tanque)*

Dígale los litros de una vaca o use `/leche <litros>` para anotar todo el tanque del día de una sola vez.

### ⏰ Recordatorios de Campo
> `/programar 2026-09-01 08:00 Rotar potrero Bajo a Guayabal`  
> `/programar 2026-09-05 06:30 Vacunación aftosa en el corral`

Dígale la fecha (`AAAA-MM-DD`), la hora (`HH:MM`) y la tarea. El bot se lo recordará en el **Despacho Matutino** de ese día.

### 📥 Entrada / Salida (compra o venta)
> `entraron 15 novillas compradas en subasta`

Dígale qué animales entraron o salieron de la finca.

---

## 3. Pregúntele al Bot con sus Propias Palabras 🗣️🔍

Usted no necesita memorizar comandos difíciles. Puede hacerle preguntas directamente en español cotidiano usando el número de arete (`47`, `JA26`, `A009`) o el **nombre propio** de la vaca (`patricia`):

- **Ubicación actual y potrero:**
  - *«¿en qué potrero está patricia?»*
  - *«¿dónde está la vaca 47?»*
  - *«¿dónde anda el toro 502?»*
  - ➡️ El bot responde el potrero actual, lote, fecha de entrada y si está activa.

- **Parto puntual y maternidad:**
  - *«¿cuándo parió patricia?»*
  - *«¿cuándo fue el parto de la 47?»*
  - ➡️ El bot responde la fecha exacta, sexo de la cría, estado (vivo/muerto) y peso al nacer.

- **Inseminación y Servicio:**
  - *«¿cuándo se inseminó patricia?»*
  - *«¿con qué toro se sirvió la 47?»*
  - ➡️ El bot responde la fecha, pajuela/toro, días de gestación transcurridos y Fecha Estimada de Parto (FEP).

- **Retiro y Medicamentos:**
  - *«¿patricia está en retiro?»*
  - *«¿qué remedio le pusieron a la 105?»*
  - ➡️ El bot le avisa si tiene retiro activo en leche o carne y cuántos días faltan.

- **Genealogía y Familia:**
  - *«¿quién es la madre de patricia?»*
  - *«¿qué crías tiene la 47?»*
  - ➡️ El bot le muestra la madre, el padre y sus partos registrados.

- **Pesajes y Ganancia:**
  - *«¿cuánto pesó patricia?»*
  - *«¿cuál fue la ganancia diaria de la 12?»*
  - ➡️ El bot le muestra el último peso y los gramos ganados por día (GMD).

- **Notas y Observaciones de Campo:**
  - *«¿qué notas hay de la vaca 47?»*
  - *«¿cuáles son las observaciones de patricia?»*
  - *«¿últimas notas de campo de la finca?»*
  - ➡️ El bot le muestra todos los apuntes, comentarios de partos, celos, compras, tratamientos y fotos del animal o de la finca.

---

## 4. El Despacho Matutino de las 05:30 AM (`/despacho`) 🌅

Todos los días a las **05:30 AM**, el bot envía automáticamente a su chat el resumen operativo de la mañana. También puede pedirlo en cualquier momento escribiendo `/despacho`, `/matutino`, `/hoy` o pulsando el botón `[ 🌅 Despacho Matutino ]`.

### ¿Qué incluye el Despacho?
1. ⛔ **Control de Ordeño & Retiros Sanitarios:** Le muestra de inmediato qué vacas tienen retiro activo y cuándo vence, para **no echar esa leche al tanque**. Si ninguna vaca tiene retiro, no satura el mensaje.
2. 🔥 **Inseminaciones de la Mañana (Regla AM-PM):** Lista las vacas que mostraron celo ayer por la tarde para inseminar antes de las 10:00 AM, más servicios programados.
3. 📌 **Recordatorios Programados:** Compromisos del día anotados previamente (rotar potreros, vacunar lotes, desparasitar).
4. 🤰 **Calendario Reproductivo & Veterinario:** Ecografías del día 35, palpaciones del día 60 y partos programados para los próximos 7 días.

### Botones de Acción Rápida en el Despacho:
- `[ 🥛 Registrar Leche Hoy ]`: Le pide los litros del tanque para guardarlos al instante.
- `[ ⏰ Programar Recordatorio ]`: Le guía para agendar una labor futura con fecha y hora.
- `[ 🚨 Alertas del Día ]` · `[ 💊 Medicamentos & Retiro ]` · `[ 🌿 Potreros & Pasturas ]` · `[ 🐮 Tablero de la Finca ]` · `[ 🔍 Buscar Animal ]` · `[ 🏠 Menú Principal ]`.

---

## 5. Teclado Táctil Interactivo y Menús Compactos 🔘📱

El bot adapta su pantalla y botones de acuerdo a quién lo está usando para mantener la vista limpia y sin desorden:

### 🤠 A. Menú de Campo para Trabajadores / Mayordomo
Diseñado para ser **100% didáctico y visual**:
- `[ 🌅 Despacho Matutino ]`: Tareas del día, retiros de ordeño y celos a inseminar.
- `[ 🚨 Alertas del Día ]`: Semáforo de partos próximos, secados y retiros.
- `[ 🔍 Buscar Animal / Ficha ]`: Buscador por aretes recientes o por categorías (paridas, inseminadas, toros, crías).
- `[ 🌿 Potreros & Pasturas ]`: Matriz de potreros ocupados y días de pastoreo.
- `[ 💊 Medicamentos & Retiro ]`: Fármacos aplicados y días de carencia.
- `[ 📷 Galería de Fotos ]`: Fotos de animales y novedades de campo.
- `[ ❓ Ayuda & Guías ]`: Submenú con ejemplos de notas, guía de cómo preguntar y manual de campo.

### 👑 B. Panel de Control para Dueño (OWNER) y Administradores (ADMIN)
Tablero ejecutivo que organiza las herramientas en accesos directos y submenús limpios:
- Accesos zootécnicos directos: `[ 🌅 Despacho Matutino ]`, `[ 🚨 Alertas del Día ]`, `[ 🔍 Buscar Animal ]`, `[ 🌿 Potreros ]`, `[ 💊 Medicamentos ]`, `[ 📊 Población & KPIs ]`, `[ 🧬 Composición Genética ]`, `[ 🐮 Tablero Finca ]`.
- `[ 📊 Gráficos de la Finca ]`: Panel interactivo organizado en 4 categorías:
  - 🐄 **Hato:** Evolución, Waterfall (cascada de movimientos) y Categorías del Hato.
  - 🧬 **Reproducción:** GMD del Hato, IEP 2 años, IEP histórico, Destete por Raza, Rendimiento del Padre, Preñadas vs Vacías, Días Abiertos Kaplan-Meier y Estado Reproductivo.
  - 🌱 **Pasturas:** Aforo de Potreros, Ocupación Voisin y Carga Animal (UGG/ha).
  - 🥛 **Leche:** Producción Total del Hato, Eficiencia Lechera y Ranking de Vacas.
- `[ 📦 Sistema & Reportes ]`: Submenú que reúne:
  - `[ 📋 Reporte Semanal PDF ]`
  - `[ 📦 Descargar Backup ZIP ]`
  - `[ ⚙️ Servidor & Sistema ]`
  - `[ 📜 Ver Últimos Logs ]`
  - `[ 👥 Usuarios / Permisos ]` *(Solo OWNER)*
- `[ ❓ Ayuda & Guías ]`: Submenú unificado de manuales, cómo preguntar y ejemplos.

### 📷 Fichas Zootécnicas y Curvas Individuales
Al consultar cualquier animal (escribiendo su número ej. `47`, `/consulta N069` o enviando foto), el bot envía su ficha con foto y botones interactivos:
- `[ ⚖️ Pesajes & GMD ]` · `[ 🍼 Partos & Crías ]` · `[ 🥛 Control Leche ]` · `[ 💉 Sanidad & Retiro ]` · `[ 🌳 Genealogía (3G) ]` · `[ 📷 Ver Foto ]` · `[ 📈 Gráfico de Peso ]` · `[ 📉 Curva de Lactancia ]`.
- **Navegación limpia de 2 botones:** Al ver cualquier detalle o gráfico, la botonera se reduce a `[ ◀ Volver a Ficha (TAG) / Gráficos | 🏠 Menú Principal ]` para evitar llenar la pantalla de botones innecesarios.

---

## 6. También puede mandar notas de voz y fotos 🎤📷

- **Nota de voz:** mantenga presionado el micrófono y cuente la novedad hablando. El bot la transcribe y procesa automáticamente con inteligencia artificial.
- **Foto:** saque una foto del arete, del frasco del remedio o del animal y mándela con o sin texto. El OCR del bot detecta automáticamente el arete o medicamento y lo registra.
- **Ver fotos:** escriba `/fotos 47` o `/fotos` para ver las imágenes guardadas.

---

## 7. Comandos de Consulta y Administración

| Comando | Para qué sirve | Ejemplo de uso |
|---|---|---|
| `/menu` o `/start` | Abre el **Menú Táctil de Botones** interactivo y compacto. | `/menu`, `/start` |
| `/despacho`, `/matutino`, `/hoy` | Genera el **Despacho Matutino de las 05:30 AM** con retiros, inseminaciones AM y tareas. | `/despacho`, `/matutino` |
| `/leche <litros>` | Anota la **Producción Total de Leche del Hato** de hoy en el tanque. | `/leche 475`, `/leche 480.5` |
| `/programar <fecha> <hora> <msg>` | Agenda un **Recordatorio de Campo** para el Despacho Matutino. | `/programar 2026-09-01 08:00 Rotar potrero Bajo` |
| `/graficos` | Panel interactivo de **Gráficos Zootécnicos en 4 Categorías** (Hato/Repro/Pasturas/Leche). | `/graficos` |
| `/grafico_leche [tag]` | Genera la **Curva de Lactancia individual** (litros vs días en leche). | `/grafico_leche N069`, `/grafico_leche 47` |
| `/guia` o `/preguntar` | **Centro de Guía de Consultas**: Ejemplos de cómo preguntar al chat sobre animales, potreros, leche y sanidad. | `/guia`, `/preguntar` |
| `/ayuda` o `/help` | Muestra la **Lista Completa de Comandos** y sintaxis. | `/ayuda`, `/comandos` |
| `/reporte` | Genera y envía el **Reporte en PDF** (semanal por defecto). | `/reporte`, `/reporte diario`, `/reporte 15` |
| `/exportar` | Descarga el **Backup ZIP** para Software Ganadero. | `/exportar`, `/exportar csv`, `/exportar json` |
| `/fotos <tag>` | Consulta las fotos guardadas de un animal o las recientes. | `/fotos 47`, `/fotos` |
| `/alertas` | Muestra el **semáforo inteligente de alertas** (partos $\le 30$d, secados $\ge 200$ DEL, destetes, pérdidas de peso y retiros). | `/alertas` |
| `/poblacion`, `/piramide` | **Tablero Poblacional**: Pirámide de edades y brackets demográficos de Software Ganadero. | `/poblacion`, `/piramide` |
| `/genetica`, `/razas` | **Composición Genética**: Distribución racial y cruces del hato. | `/genetica`, `/razas` |
| `/duplicados` | **Auditoría de Duplicados**: animales activos con la misma madre, padre y fecha de nacimiento. | `/duplicados` |
| `/historial <tag>` | Ficha interactiva con pestañas táctiles (Pesajes, Partos, Leche, Retiro, Genealogía). | `/historial 47`, `/consulta N069` |
| `/buscar [tag]` | **Buscador & Fichas de Animales**: Filtros por vacas paridas, inseminadas, toros o crías. | `/buscar`, `/buscar 47` |
| `/medicamentos`, `/retiros` | **Control Sanitario & Retiros**: Animales en retiro activo de leche/carne y tratamientos. | `/medicamentos`, `/retiros` |
| `/preguntas`, `/faq` | **Consultas Rápidas de Campo**: Botones táctiles de preguntas frecuentes en 1 toque. | `/preguntas`, `/faq` |
| `/potreros` | Muestra la **matriz de existencias por potrero de Software Ganadero** o potreros listos. | `/potreros`, `/potreros sg` |
| `/ocupacion` o `/rotacion` | Muestra los **días de ocupación y rotación Voisin** de potreros ocupados y en reposo. | `/ocupacion`, `/rotacion` |
| `/animales` | Resumen del inventario actual (hembras, machos, total activos). | `/animales` |
| `/status`, `/tablero`, `/finca` | **Tablero Zootécnico Ejecutivo**: Novedades de la semana, alertas próximas y pasturas. | `/status`, `/tablero`, `/finca` |
| `/sistema`, `/servidor`, `/vps` | **Tablero Técnico del Servidor**: Recursos VPS, RAM, disco SSD, SQLite y estado de APIs. | `/sistema`, `/servidor` |
| `/importar` | Muestra la guía para subir un backup `.zip` de Software Ganadero. | `/importar` |
| `/confirmar_importar` | Procesa el archivo `.zip` subido sin duplicar registros. | `/confirmar_importar` |
| `/descartar_backup` | Elimina el backup pendiente sin procesar. | `/descartar_backup` |
| `/usuarios` | Lista los usuarios autorizados en el bot. | `/usuarios` |
| `/agregar_usuario` *(Solo OWNER)* | Autoriza a un trabajador o administrador. | `/agregar_usuario 123456 TRABAJADOR Carlos` |
| `/quitar_usuario` *(Solo OWNER)* | Revoca el acceso a un usuario. | `/quitar_usuario 123456` |
| `/logs` *(Solo OWNER)* | Ver las últimas líneas del registro del sistema. | `/logs` |

---

## 8. ¿El bot le dijo "No autorizado"? ⛔

Si al mandarle `/start` o cualquier nota el bot le responde **"No autorizado"**,
significa que su número **todavía no está dado de alta** en el sistema.

👉 **Avísele al dueño.** Solo él puede agregarlo para que pueda usar el bot.

### 8.1 Cómo agregar un nuevo trabajador (solo dueño) 👥

Si llega un trabajador nuevo a la finca o cambia de celular, el dueño puede darle acceso en 4 pasos sencillos **directamente desde su Telegram** (sin necesidad de reiniciar el bot ni tocar el servidor):

1. **Pídale que busque el bot y le mande `/start`:**
   Al trabajador le saldrá el mensaje *"⛔ No autorizado"*. Esto es normal.
2. **Consiga su ID de Telegram (`user_id`):**
   - **Opción fácil (desde el celular del trabajador):** Que él busque en Telegram el usuario `@userinfobot`, le dé `/start` y le envíe a usted el número que aparece en **Id** (por ejemplo: `712345678`).
   - **Opción servidor:** Si tiene acceso por SSH, puede ver el intento en los logs ejecutando `grep "no autorizado" /root/bitacora/bot.log`.
3. **Agréguelo enviándole este comando al bot:**
   ```
   /agregar_usuario 712345678 TRABAJADOR Carlos
   ```
   *(Reemplace `712345678` por el ID del trabajador y `Carlos` por su nombre).*
4. **Verifique que quedó registrado:**
   - Envíe `/usuarios` al bot para confirmar que aparece en la lista.
   - Si más adelante la persona se retira de la finca, puede quitarle el acceso con:
     ```
     /quitar_usuario 712345678
     ```

> 💡 **Nota:** El alta es **inmediata**; no requiere reiniciar el bot ni el servidor. Tan pronto mande el comando, el trabajador puede empezar a enviar notas y novedades de campo.
>
> **Roles disponibles:**
> - `TRABAJADOR`: Solo reporta notas de campo y consulta fichas básicas.
> - `ADMIN`: Ve reportes, potreros, alertas, inventario y exporta/importa datos.
> - `OWNER`: Dueño con control total (incluyendo agregar/quitar usuarios y ver logs).

---

## 9. Consejos para que el bot entienda bien

- Mencione siempre el **número del animal** (el tag o arete), por ejemplo "la 47".
- Para traslados, diga **de dónde a dónde**.
- Para celo, diga si fue **en la mañana o en la tarde**.
- Para tratamientos, diga **qué le puso y cuánto**.
- Si algo no quedó registrado, vuelva a mandarlo un poquito más claro y con el
  número del animal.

---

## 10. ¿Y el dueño qué puede ver?

El dueño (y el administrador) pueden consultar desde su celular el despacho matutino, alertas, historial de cada animal, potreros listos, gráficos zootécnicos, inventario y estado del sistema. Usted solo se encarga de **mandar las novedades**; el bot hace el resto.

---

## 11. Sincronización automática por carpeta COPIAS (Backups grandes de 70 MB) 📦⚡

Cuando el backup de Software Ganadero contiene fotos y tablas históricas completas, suele pesar **más de 20 MB** (habitualmente 70 MB o más), por lo que Telegram no permite enviarlo por chat directo.

Para resolver esto, el bot cuenta con un **observador automático (watcher)** que detecta los backups apenas se generan:

### ¿Cómo funciona el flujo automático?
1. **Generación en Software Ganadero:** Al hacer la copia de seguridad periódica en el PC de la finca o la oficina, el SG genera un archivo `.Zip` con la fecha (ej. `Datos20260828.Zip`) en la carpeta de copias (`C:\Usati\Copias` en el PC de la finca, configurable vía `COPIAS_DIR`).
2. **Detección por Fecha / mtime / Hash (cada 60 min):** La Tarea Programada `VigilarCopiasSG` (Windows, `schtasks` cada 60 min) y/o el servicio `copias_watcher` en el VPS revisan la carpeta, validan que el `.Zip` ya esté completo y comprueban por MD5+mtime que no fue importado antes.
3. **Auto-Importación Idempotente:** El sistema procesa internamente las tablas DBF y fotos en SQLite, aplicando deduplicación por llaves zootécnicas sin sobreescribir ni duplicar datos.
4. **Notificación Instantánea al Dueño:** Al terminar, el bot le envía automáticamente un mensaje al OWNER por Telegram con el reporte consolidado:
   ```text
   📦 Software Ganadero — Auto-Import Exitoso
   📁 Archivo: Datos20260828.Zip (1.4s)
   📊 Consolidado: 15 nuevos, 480 duplicados

   📋 Detalle por tabla:
   • animales: 2 nuevos, 310 duplicados
   • celos: 1 nuevos, 40 duplicados
   • partos: 3 nuevos, 55 duplicados
   • pesos: 5 nuevos, 38 duplicados
   • servicios: 4 nuevos, 37 duplicados
   ```
5. **Cero intervención manual:** No necesita escribir comandos ni confirmar por chat; todo queda registrado en `data/copias_import.log`.

---

> 📞 Si algo le parece raro o el bot no le responde, avísele al dueño. Este
> cuaderno de campo es de todos: mientras mejor anotemos, mejor trabaja la
> finca. 🌱
