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

---

## 4. Teclado Táctil Interactivo y Menús Diferenciados 🔘📱

El bot adapta su pantalla y botones de acuerdo a quién lo está usando:

### 🤠 A. Menú de Campo para Trabajadores / Mayordomo
Diseñado para ser **100% didáctico y visual**. El personal de campo no ve comandos complejos ni reportes administrativos; solo ve botones que le enseñan y facilitan su labor:
- `[ 📝 Cómo Anotar Reportes ]`: Abre ejemplos listos para copiar de partos, celos, servicios, remedios, pesajes y traslados.
- `[ 🔍 Cómo Hacer Preguntas ]`: Guía didáctica con ejemplos de preguntas cotidianas (*«¿en qué potrero está patricia?»*, *«¿cuándo parió la 47?»*, etc.).
- `[ 📷 Fotos Aretes y Remedios ]`: Guía paso a paso de cómo fotografiar aretes y etiquetas de frascos de remedios para que el bot los lea solo.
- `[ 🐮 Consultar un Animal ]`: Muestra cómo ver la ficha y foto de cualquier vaca escribiendo su número o nombre.
- `[ 🎤 Cómo Mandar Audios ]`: Consejos para enviar notas de voz claras desde el potrero.
- `[ 📷 Galería de Fotos ]`: Muestra las últimas fotos registradas en la finca.

### 👑 B. Panel de Control para Dueño (OWNER) y Administradores (ADMIN)
Tablero de mando integral con acceso inmediato a los reportes y gestión zootécnica:
- `[ 📊 Inventario Hato ]`: Resumen zootécnico del ganado activo por categorías.
- `[ ⚠️ Alertas Pendientes ]`: Ecografías, palpaciones y secados programados.
- `[ 🌿 Potreros Voisin ]`: Estado de rotación y potreros que cumplieron su descanso.
- `[ 📋 Reporte Semanal PDF ]`: Genera y descarga el informe PDF completo de la semana.
- `[ 📦 Descargar Backup ZIP ]`: Exporta el paquete ZIP listo para Software Ganadero (SG).
- `[ 📷 Galería de Fotos ]`: Galería fotográfica general.
- `[ 👥 Usuarios / Permisos ]` *(Solo OWNER)*: Administra altas y bajas de trabajadores.
- `[ ⚙️ Estado Servidor ]`: Salud de la base de datos, memoria y registros del sistema.
- `[ 💡 Modo Guía de Campo ]`: Permite al dueño ver el menú didáctico de los trabajadores.

### 📷 Fotos Automáticas de Animales
Cuando cualquier usuario consulte la ficha de un animal (ej. `/consulta a009`, `/historial patricia` o escribiendo `patricia` o `47`), el bot **busca automáticamente su foto en la galería del backup** y se la envía adjunta a la ficha técnica, junto con botones interactivos:
- `[ ⚖️ Pesajes ]` `[ 🧬 Reproducción ]`
- `[ 🌱 Potrero ]` `[ 💊 Retiro ]`
- `[ 📷 Ver Foto ]` `[ 📋 Ficha Completa ]`

---

## 5. También puede mandar notas de voz y fotos 🎤📷

- **Nota de voz:** mantenga presionado el micrófono y cuente la novedad hablando. El bot la transcribe y procesa automáticamente con inteligencia artificial.
- **Foto:** saque una foto del arete, del frasco del remedio o del animal y mándela con o sin texto. El OCR del bot detecta automáticamente el arete o medicamento y lo registra.
- **Ver fotos:** escriba `/fotos 47` o `/fotos` para ver las imágenes guardadas.

---

## 6. Comandos de Consulta y Administración (Dueño y Administrador)

| Comando | Para qué sirve | Ejemplo de uso |
|---|---|---|
| `/menu` o `/start` | Abre el **Menú Táctil de Botones** interactivo y visual. | `/menu`, `/start` |
| `/guia` o `/preguntar` | **Centro de Guía de Consultas**: Ejemplos de cómo preguntar al chat sobre animales, potreros, leche y sanidad. | `/guia`, `/preguntar` |
| `/ayuda` o `/help` | Muestra la **Lista Completa de Comandos** y sintaxis. | `/ayuda`, `/comandos` |
| `/reporte` | Genera y envía el **Reporte en PDF** (semanal por defecto). | `/reporte`, `/reporte diario`, `/reporte 15` |
| `/exportar` | Descarga el **Backup ZIP** para Software Ganadero. | `/exportar`, `/exportar csv`, `/exportar json` |
| `/fotos <tag>` | Consulta las fotos guardadas de un animal o las recientes. | `/fotos 47`, `/fotos` |
| `/alertas` | Muestra el **semáforo inteligente de alertas** (partos $\le 30$d, secados $\ge 200$ DEL, destetes, pérdidas de peso y retiros). | `/alertas` |
| `/poblacion`, `/piramide` | **Tablero Poblacional**: Pirámide de edades y brackets demográficos de Software Ganadero. | `/poblacion`, `/piramide` |
| `/genetica`, `/razas` | **Composición Genética**: Distribución racial y cruces del hato. | `/genetica`, `/razas` |
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

## 4. ¿El bot le dijo "No autorizado"? ⛔

Si al mandarle `/start` o cualquier nota el bot le responde **"No autorizado"**,
significa que su número **todavía no está dado de alta** en el sistema.

👉 **Avísele al dueño.** Solo él puede agregarlo para que pueda usar el bot.

### 4.1 Cómo agregar un nuevo trabajador (solo dueño) 👥

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

## 5. Consejos para que el bot entienda bien

- Mencione siempre el **número del animal** (el tag o arete), por ejemplo "la 47".
- Para traslados, diga **de dónde a dónde**.
- Para celo, diga si fue **en la mañana o en la tarde**.
- Para tratamientos, diga **qué le puso y cuánto**.
- Si algo no quedó registrado, vuelva a mandarlo un poquito más claro y con el
  número del animal.

---

## 6. ¿Y el dueño qué puede ver?

El dueño (y el administrador) pueden consultar desde su celular las alertas, el
historial de cada animal, los potreros listos, el inventario y el estado del
sistema. Usted solo se encarga de **mandar las novedades**; el bot hace el resto.

---

## 7. Sincronización automática por carpeta COPIAS (Backups grandes de 70 MB) 📦⚡

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
