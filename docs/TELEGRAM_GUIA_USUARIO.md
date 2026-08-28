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

## 3. También puede mandar notas de voz y fotos 🎤📷

- **Nota de voz:** mantenga presionado el micrófono y cuente la novedad hablando.
  El bot la guarda. *(La transcripción automática llega en la Fase 3 con Whisper).*
- **Foto:** saque una foto del arete, del frasco del remedio o del animal y
  mándela con un texto (ej. `vaca 47` o `pario la 47 ternero macho`). El bot la guarda
  y la vincula a la base de datos.
- **Ver fotos:** escriba `/fotos 47` o `/fotos` para ver las imágenes guardadas.

---

## 4. Comandos de Consulta y Administración (Dueño y Administrador)

| Comando | Para qué sirve | Ejemplo de uso |
|---|---|---|
| `/reporte` | Genera y envía el **Reporte en PDF** (semanal por defecto). | `/reporte`, `/reporte diario`, `/reporte 15` |
| `/exportar` | Descarga el **Backup ZIP** para Software Ganadero. | `/exportar`, `/exportar csv`, `/exportar json` |
| `/fotos <tag>` | Consulta las fotos guardadas de un animal o las recientes. | `/fotos 47`, `/fotos` |
| `/alertas` | Muestra las alertas pendientes (ecografías, palpaciones, secado). | `/alertas` |
| `/historial <tag>` | Ficha completa con todos los eventos de un animal. | `/historial 47` |
| `/potreros` | Muestra qué potreros cumplieron su tiempo de reposo Voisin. | `/potreros` |
| `/animales` | Resumen del inventario actual (hembras, machos, total activos). | `/animales` |
| `/status` | Estado de la base de datos, total de eventos y peso del archivo. | `/status` |
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

> 📞 Si algo le parece raro o el bot no le responde, avísele al dueño. Este
> cuaderno de campo es de todos: mientras mejor anotemos, mejor trabaja la
> finca. 🌱
