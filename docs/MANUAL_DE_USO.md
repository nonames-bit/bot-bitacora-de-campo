# 📖 Manual Integral de Uso — Bot de Bitácora de Campo Ganadera

> **Sistema Inteligente de Gestión Ganadera, Bitácora Móvil y Sincronización con Software Ganadero (SG)**  
> **Ganadería JA** · *Finca Versalles, Santa Martha y Olegario*

---

## 📑 Tabla de Contenidos
1. [Introducción & Visión General](#1-introducción--visión-general)
2. [Estructura de Roles y Accesos (RBAC)](#2-estructura-de-roles-y-accesos-rbac)
3. [Guía Rápida de Inicio y Menú Principal Compacto](#3-guía-rápida-de-inicio-y-menú-principal-compacto)
4. [Operación en Campo para Trabajadores & Mayordomo](#4-operación-en-campo-para-trabajadores--mayordomo)
   - [4.1 Registro por Mensajes de Texto](#41-registro-por-mensajes-de-texto)
   - [4.2 Control de Leche (Total del Hato e Individual)](#42-control-de-leche-total-del-hato-e-individual)
   - [4.3 Programación de Recordatorios de Campo](#43-programación-de-recordatorios-de-campo)
   - [4.4 Dictado por Notas de Voz (Whisper + IA)](#44-dictado-por-notas-de-voz-whisper--ia)
   - [4.5 Fotografías con OCR (Aretes y Medicamentos)](#45-fotografías-con-ocr-aretes-y-medicamentos)
5. [Fichas Zootécnicas Interactivas con Pestañas Táctiles](#5-fichas-zootécnicas-interactivas-con-pestañas-táctiles)
6. [Cómo Preguntarle al Bot (Lenguaje Natural)](#6-cómo-preguntarle-al-bot-lenguaje-natural)
7. [Despacho Matutino (05:30 AM) y Centro de Alertas](#7-despacho-matutino-0530-am-y-centro-de-alertas)
   - [7.1 El Despacho Matutino (Morning Briefing)](#71-el-despacho-matutino-morning-briefing)
   - [7.2 Centro de Alertas Semafórico de Campo](#72-centro-de-alertas-semafórico-de-campo)
8. [Tableros Ejecutivos, KPIs, Gráficos e Informes SG](#8-tableros-ejecutivos-kpis-gráficos-e-informes-sg)
   - [8.1 Tablero Zootécnico de la Finca (/status)](#81-tablero-zootécnico-de-la-finca-status)
   - [8.2 Población y Pirámide de Edades (/poblacion)](#82-población-y-pirámide-de-edades-poblacion)
   - [8.3 Composición Genética y Razas (/genetica)](#83-composición-genética-y-razas-genetica)
   - [8.4 Matriz de Potreros y Rotación Voisin (/potreros, /ocupacion)](#84-matriz-de-potreros-y-rotación-voisin-potreros-ocupacion)
   - [8.5 Gráficos Zootécnicos de la Finca en 4 Categorías (/graficos)](#85-gráficos-zootécnicos-de-la-finca-en-4-categorías-graficos)
   - [8.6 Reportes Profesionales en PDF (/reporte)](#86-reportes-profesionales-en-pdf-reporte)
9. [Submenús Unificados de Sistema y Ayuda](#9-submenús-unificados-de-sistema-y-ayuda)
10. [Sincronización con Software Ganadero (SG)](#10-sincronización-con-software-ganadero-sg)
    - [10.1 Importación de Backups ZIP por Telegram](#101-importación-de-backups-zip-por-telegram)
    - [10.2 Sincronización Automática por Carpeta COPIAS (70+ MB)](#102-sincronización-automática-por-carpeta-copias-70-mb)
    - [10.3 Exportación de Datos para SG (/exportar)](#103-exportación-de-datos-para-sg-exportar)
11. [Administración de Usuarios y Servidor](#11-administración-de-usuarios-y-servidor)
12. [Tabla Resumen de Comandos](#12-tabla-resumen-de-comandos)

---

## 1. Introducción & Visión General

El **Bot de Bitácora de Campo** es un asistente zootécnico inteligente diseñado para conectar las labores cotidianas de la finca ganadera con el sistema central **Software Ganadero (SG)** sin trámites engorrosos ni pérdidas de información.

```
┌─────────────────────────────────────────────────────────────┐
│                    PERSONAL EN EL CORRAL                    │
│    (Notas de voz, fotos de aretes, textos por Telegram)     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   BOT DE TELEGRAM & IA                      │
│   • NLU Zootécnico (Partos, Celos, Servicios, Retiros)     │
│   • Transcripción Whisper & OCR de frascos/medicamentos     │
│   • Fichas Interactivas y Semáforos de Alertas              │
│   • Base de Datos SQLite Normalizada                        │
└──────────────────────────────┬──────────────────────────────┘
                               │ Sincronización Bi-Direccional
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              SOFTWARE GANADERO SG (PC / OFICINA)            │
│   • Importación / Exportación DBF Deduplicada               │
│   • Vigilante Automático de Backups (.Zip de 70+ MB)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Estructura de Roles y Accesos (RBAC)

El acceso al bot está estrictamente protegido. Cada usuario de Telegram tiene un rol asignado:

| Rol | Destinatario | Permisos Principales |
| :--- | :--- | :--- |
| **`TRABAJADOR`** | Mayordomo, vaqueros, ordeñadores | Enviar notas de campo (voz, foto, texto), consultar fichas de animales, ver potreros ocupados y alertas sanitarias del día. |
| **`ADMIN`** | Administrador de finca, veterinario | Todo lo de `TRABAJADOR` + Tableros zootécnicos (`/status`, `/poblacion`, `/genetica`), generación de reportes PDF, importación y exportación de backups ZIP. |
| **`OWNER`** | Dueño de la Ganadería | Control total + Gestión de usuarios (`/agregar_usuario`, `/quitar_usuario`), monitoreo del VPS (`/sistema`, `/logs`) y configuración global. |

---

## 3. Guía Rápida de Inicio y Menú Principal Compacto

1. Abre la aplicación **Telegram** en tu teléfono o computador.
2. Busca el bot de la ganadería (ej. `@GanaderiaJABot`).
3. Presiona el botón **Iniciar** o envía el comando `/start` (o `/menu`).
4. El bot desplegará automáticamente tu **Menú Principal Compacto e Interactivo**:
   - **Para Trabajadores:** Vista directa de campo con acceso a `[ 🌅 Despacho Matutino ]`, `[ 🚨 Alertas del Día ]`, `[ 🔍 Buscar Animal / Ficha ]`, `[ 🌿 Potreros & Pasturas ]`, `[ 💊 Medicamentos & Retiro ]`, `[ 📷 Galería de Fotos ]` y submenú `[ ❓ Ayuda & Guías ]`.
   - **Para Administradores y Dueño (ADMIN/OWNER):** Panel ejecutivo con accesos zootécnicos directos y dos submenús agrupados para evitar desorden visual:
     - `[ 📦 Sistema & Reportes ]`: Agrupa Reporte PDF, Backup ZIP, Servidor, Logs y Usuarios.
     - `[ ❓ Ayuda & Guías ]`: Agrupa Manual de Comandos, Cómo Preguntar, Ejemplos de Notas y Guía de Campo.

---

## 4. Operación en Campo para Trabajadores & Mayordomo

### 4.1 Registro por Mensajes de Texto
No necesitas llenar formularios ni recordar formatos rígidos. Escribe la novedad en español cotidiano mencionando el **número de arete**:

* **🍼 Parto:** `pario la 47 ternero macho vivo 38 kilos`
* **🔥 Celo (Regla AM-PM):** `celo en la tarde la vaca 33` o `celo en la mañana la novilla 15`
* **🐂 Inseminación / Servicio:** `insemine la 12 con pajuela toro brahman 502`
* **💉 Medicamentos & Tratamiento:** `le puse 20ml de oxitetraciclina via IM a la 8 por mastitis`
* **🚚 Traslado de Potrero:** `pase el lote 2 de santa martha a versalles`
* **⚖️ Pesaje:** `pesaje de la 47 dio 460 kilos`
* **💀 Muerte:** `se murio el ternero A060 por timpanismo`
* **📥 Entradas / Salidas:** `entraron 10 novillas compradas en subasta`

---

### 4.2 Control de Leche (Total del Hato e Individual)
El bot permite registrar tanto la producción general del día como el pesaje lechero individual de cada vaca:

* **🥛 Registro Total del Hato (Tanque del Día):**
  - Escribe el comando `/leche <litros>` (ej. `/leche 475` o `/leche 482.5`).
  - O pulsa el botón **`[ 🥛 Registrar Leche Hoy ]`** desde el Despacho Matutino y el bot te pedirá el valor.
  - Guarda automáticamente el registro en la base de datos vinculado a la fecha de hoy sin requerir ID de animal (`animal_id = NULL`).
* **🐮 Control Lechero Individual por Vaca:**
  - Escribe el mensaje natural: `la 47 dio 12 litros de leche` o `pesaje de leche de la 12 fue 14.5 litros`.
  - El bot calcula los Días en Lactancia (**DEL**), actualiza la curva y registra el historial productivo.

---

### 4.3 Programación de Recordatorios de Campo
Para que el equipo nunca olvide una labor, rotación o vacuna:

* **Comando:** `/programar YYYY-MM-DD HH:MM mensaje`
  - Ejemplo: `/programar 2026-09-01 08:00 Rotar potrero Bajo a Guayabal`
  - Ejemplo: `/programar 2026-09-05 06:30 Vacunación aftosa lote de ordeño`
* **Desde Botón:** Toca **`[ ⏰ Programar Recordatorio ]`** en el Despacho Matutino y envía la fecha, hora y texto.
* Los recordatorios quedan guardados en la base de datos (`recordatorios_programados`) y se presentan automáticamente en el **Despacho Matutino de las 05:30 AM** del día correspondiente.

---

### 4.4 Dictado por Notas de Voz (Whisper + IA)
1. En el corral o potrero, mantén presionado el botón del **micrófono** en Telegram.
2. Habla con calma y claridad contando la novedad:
   * *«Don Julio, le aviso que parió la 47 un ternero macho vivo de 38 kilos en santa martha»*
   * *«Inseminé la novilla 15 con el toro 502 en la mañana»*
   * *«Pasé el lote de ordeño para el potrero olegario»*
3. Suelta el botón para enviar.
4. El bot transcribe el audio en tiempo real, extrae los datos zootécnicos y registra la novedad en la base de datos de inmediato.

---

### 4.5 Fotografías con OCR (Aretes y Medicamentos)
* 🏷️ **Fotos de Aretes / Ganado:**
  Toma una foto de frente al arete del animal. El sistema leerá automáticamente el número (ej. `N069`, `JA26`, `47`) y te abrirá su ficha técnica completa al instante.
* 💊 **Fotos de Frascos de Medicamentos:**
  Fotografía la etiqueta del frasco. El OCR detectará el principio activo (ej. *Oxitetraciclina*, *Ivermectina*), la dosis recomendada (`ml/kg`), la vía de aplicación y los **días de retiro en leche y carne**.

---

## 5. Fichas Zootécnicas Interactivas con Pestañas Táctiles

Al consultar un animal (escribiendo su número ej. `47`, `/consulta N069` o enviando su foto), el bot responde con su ficha zootécnica estructurada, su edad exacta, potrero actual y una **botonera de navegación táctil completa**:

```
[ ⚖️ Pesajes & GMD ]    [ 🍼 Partos & Crías ]
[ 🥛 Control Leche ]    [ 💉 Sanidad & Retiro ]
[ 🌳 Genealogía (3G) ]   [ 📷 Ver Foto ]
[ 📈 Gráfico de Peso ]  [ 📉 Curva de Lactancia ]
[ 📋 Ficha Resumen ]    [ 🔍 Buscar Otro ]
[ 🏠 Menú Principal ]
```

* **⚖️ Pesajes & GMD:** Muestra el peso actual, Ganancia Media Diaria (**GMD** en gramos/día) entre pesajes, Ganancia de Vida (**g/d/vida**) y la tabla histórica ponderal.
* **🍼 Partos & Crías:** Muestra partos registrados, crías nacidas (sexo, peso, estado), celos AM/PM, servicios/IA, Días Abiertos (**DEL**), Intervalo Entre Partos (**IEP**) y Fecha Estimada de Parto (**FEP**).
* **🥛 Control Leche:** Estado (en ordeño vs seca), Días en Lactancia (**DEL**), fecha programada de secado ($FEP - 60d$) y alerta si supera los 200 DEL.
* **💉 Sanidad & Retiro:** **Semáforo de retiro** con cuenta regresiva de días para ordeño y sacrificio, junto con el historial clínico de aplicaciones.
* **🌳 Genealogía (3G):** Árbol genealógico en 3 generaciones (Padre, Abuelos paternos, Madre, Abuelos maternos) y lista de crías descendientes.
* **📷 Ver Foto:** Despliega la fotografía del animal guardada en el sistema.
* **📈 Gráfico de Peso / 📉 Curva de Lactancia:** Genera al instante la gráfica ponderal o de producción láctea individual del animal.

> 💡 **Navegación Limpia de Detalle:** Al entrar a cualquiera de estas pestañas o gráficos, la botonera se reduce automáticamente a solo dos botones: `[ ◀ Volver a Ficha (TAG) ]` y `[ 🏠 Menú Principal ]`, manteniendo la pantalla despejada y fácil de leer en el teléfono.

---

## 6. Cómo Preguntarle al Bot (Lenguaje Natural)

Puedes hacerle preguntas abiertas al bot como a un asistente humano (accede también con `/guia` o el botón `[ 💬 Guía: Cómo Preguntar al Chat ]`):

### 🐮 Preguntas sobre un Animal:
* *«¿En qué potrero está la 47?»* → Informa potrero actual, lote y días de estadía.
* *«¿Cuándo parió la vaca 12?»* → Muestra fecha, sexo de la cría y peso.
* *«¿Con qué toro se sirvió la A029?»* → Muestra toro/pajuela, fecha de servicio y FEP.
* *«¿Cuánto pesó la N069?»* → Muestra último peso y GMD.
* *«¿Quién es la madre de patricia?»* → Muestra madre y padre.

### 🌿 Preguntas de Potreros & Rotación Voisin:
* *«¿Qué potreros tienen más de 30 días de descanso?»* → Lista potreros listos para pastorear.
* *«¿Cuántos días de ocupación llevan en santa martha?»* → Muestra días de pastoreo activo.
* *«¿Qué potreros están ocupados hoy?»* → Resumen de ocupación actual.

### 🥛 Preguntas de Leche & Reproducción:
* *«¿Qué vacas tienen más de 90 días abiertas?»* → Lista vacas vacías para revisión reproductiva.
* *«¿Qué partos hubo este mes?»* → Resumen de nacimientos del mes.
* *«¿Qué vacas están próximas a parir?»* → Vacas con FEP en los próximos 30 días.
* *«¿A qué vacas les toca secado?»* → Vacas con $\ge 200$ DEL o a 60 días del parto.

### 💉 Preguntas de Sanidad & Retiro:
* *«¿Qué vacas están en retiro de leche hoy?»* → Bloqueo preventivo de ordeño.
* *«¿Quién está en retiro de carne?»* → Bloqueo preventivo de despacho.
* *«¿Qué medicamento le pusieron a la 105?»* → Fármaco, fecha, dosis y vía.

---

## 7. Despacho Matutino (05:30 AM) y Centro de Alertas

### 7.1 El Despacho Matutino (Morning Briefing)
Todos los días a las **05:30 AM** (o en cualquier momento escribiendo `/despacho`, `/matutino`, `/hoy`, `/briefing` o pulsando `[ 🌅 Despacho Matutino ]`), el bot genera un resumen ejecutivo y operativo enfocado exclusivamente en las tareas prioritarias del día:

```
🌅 DESPACHO MATUTINO — GANADERÍA JA
📅 Lunes, 31 de Agosto de 2026 · 05:30 AM
────────────────────────────────────────
⛔ ¡ALERTA DE ORDEÑO! VACAS EN RETIRO (1):
⚠️ NO echar esta leche al tanque bajo ninguna circunstancia:
• 🔴 8 (Margarita) — Oxitetraciclina (⛔ Quedan 3d, hasta 2026-09-03)

🔥 INSEMINACIONES DE ESTA MAÑANA (1):
• 💉 33 (Lucero) — Celo observado ayer PM (Inseminar antes de las 10:00 AM)

📌 RECORDATORIOS PROGRAMADOS (1):
• ⏰ [08:00] Rotar potrero Bajo a Guayabal

🤰 CALENDARIO REPRODUCTIVO & VETERINARIO (2):
• 🔬 Ecografía (Día 35): Vaca 15 (Servicio del 2026-07-27)
• 🍼 Parto próximo: Vaca 47 — FEP: 2026-09-02 (en 2 días)
────────────────────────────────────────
💡 ¡Excelente y productiva jornada para todo el equipo de campo!
```

**Estructura del Despacho Matutino:**
1. **🥛 Control de Ordeño & Retiro:** Solo se muestra si hay vacas en periodo de carencia activo con alerta roja y fecha límite. Si no hay retiros, no satura el mensaje.
2. **🧬 Inseminaciones AM (Regla AM-PM):** Lista vacas con celo visto la tarde anterior para inseminar antes de las 10:00 AM, más servicios programados para la fecha.
3. **📌 Recordatorios Programados:** Tareas, rotaciones y compromisos agendados para la fecha con su hora asignada.
4. **🤰 Calendario Reproductivo & Veterinario:** Ecografías del día 35, confirmaciones por palpación del día 60 y partos esperados dentro de los próximos 7 días.

**Botonera de Acción Rápida del Despacho:**
```
[ 🥛 Registrar Leche Hoy ]   [ ⏰ Programar Recordatorio ]
[ 🚨 Alertas del Día ]       [ 💊 Medicamentos & Retiro ]
[ 🌿 Potreros & Pasturas ]   [ 🐮 Tablero de la Finca ]
[ 🔍 Buscar Animal ]         [ 🏠 Menú Principal ]
```

---

### 7.2 Centro de Alertas Semafórico de Campo

El comando `/alertas` (o botón `[ 🚨 Alertas del Día ]`) analiza el hato activo y presenta un semáforo interactivo:

```
🚨 CENTRO DE ALERTAS ZOOTÉCNICAS
────────────────────────────────────────
🔴 Partos Próximos (≤30 días): 3 vaca(s)
🟡 Candidatas a Secado (≥200 DEL): 5 vaca(s)
🟢 Crías para Destete (≥200 días): 4 ternero(s)
⚠️ Pérdidas de Peso (GMD < 0): 2 animal(es)
⛔ Retiros Sanitarios Activos: 1 animal(es)
```

Al tocar cualquiera de los botones de alerta, el bot lista los animales involucrados con accesos directos a sus fichas técnicas.

---

## 8. Tableros Ejecutivos, KPIs, Gráficos e Informes SG

### 8.1 Tablero Zootécnico de la Finca (`/status`, `/finca`, `/tablero`)
Resumen ejecutivo con:
* **Hato Activo Total:** Conteo estricto de animales en producción (`estado = 'ACTIVO'`).
* **Novedades de la Semana (últimos 7 días):** Partos (machos/hembras), celos, inseminaciones, pesajes con GMD promedio, tratamientos y traslados.
* **Alertas Próximas:** Ecografías (día 35), palpaciones (día 60) y secados.
* **Potreros Voisin:** Potreros en pastoreo, alertas de sobreocupación ($>3$ días) y potreros listos ($\ge 30$ días de reposo).

### 8.2 Población y Pirámide de Edades (`/poblacion`, `/piramide`)
Réplica de los reportes demográficos de Software Ganadero:
* **Hembras:** `< 1 año`, `1 a 2 años`, `2 a 4 años`, `4 a 8 años`, `8 a 10 años`, `> 10 años`.
* **Machos:** `< 1 año`, `1 a 2 años`, `> 2 años`, `Reproductores`.
* **Totales y Porcentajes de Distribución.**

### 8.3 Composición Genética y Razas (`/genetica`, `/razas`)
Gráfico de distribución racial del hato (Holstein, Gyr, Cebú, Pardo Suizo, Ayrshire y cruces).

### 8.4 Matriz de Potreros y Rotación Voisin (`/potreros`, `/ocupacion`)
* **Matriz Zootécnica SG:** Tabla de 9 columnas (`CH`, `HL`, `NV`, `VP`, `VS`, `CM`, `ML`, `MC`, `RP`, `Total`) idéntica a Software Ganadero.
* **Semáforo Voisin:** Días de ocupación en verde (1-3d), amarillo (4-6d) y rojo ($\ge 7$d sobreocupación).

### 8.5 Gráficos Zootécnicos de la Finca en 4 Categorías (`/graficos`)
Al pulsar el botón `[ 📊 Gráficos de la Finca ]` o enviar `/graficos`, el bot abre un panel estructurado en 4 grandes dominios zootécnicos:

1. 🐄 **HATO:**
   - **📈 Evolución:** Crecimiento y variación temporal de la población total activa.
   - **🌊 Waterfall:** Gráfico de cascada de entradas, nacimientos, ventas y bajas.
   - **🥧 Categorías del Hato:** Distribución porcentual por categorías zootécnicas.
2. 🧬 **REPRODUCCIÓN & GENÉTICA:**
   - **⚖️ GMD del Hato:** Curva de Ganancia Media Diaria ponderal del ganado.
   - **📦 IEP (2 años):** Intervalo Entre Partos reciente con distribución estadística.
   - **📦 IEP Histórico:** Historial multianual de intervalos reproductivos.
   - **🐄 Destete por Raza:** Peso al destete según la genética y cruzamientos.
   - **🐂 Rendimiento Padre:** Evaluación de toros por peso y ganancia de crías.
   - **🤰 Preñadas vs Vacías:** Estado de preñez general del hato reproductor.
   - **📉 Días Abiertos KM:** Curva Kaplan-Meier de vacías y probabilidad de preñez.
   - **🧬 Estado Reproductivo:** Distribución integral de estados ginecológicos.
3. 🌱 **PASTURAS & ROTACIÓN:**
   - **🌱 Aforo Potreros:** Biomasa disponible (kg MV/m² y kg MS/ha).
   - **🔄 Ocupación Voisin:** Semáforo de días de pastoreo y periodos de reposo.
   - **🐄 Carga Animal:** Carga instantánea en Unidades Gran Ganado por hectárea (UGG/ha).
4. 🥛 **PRODUCCIÓN LECHERA:**
   - **🥛 Producción Total:** Historial de litros diarios entregados al tanque.
   - **⚡ Eficiencia Lechera:** Litros promedio por vaca en ordeño vs vacas totales.
   - **🏆 Ranking de Vacas:** Top de mejores productoras por volumen de leche.

> 🖼️ **Vista Detalle de Gráficos:** Cada imagen generada incluye un teclado limpio con solo dos opciones: `[ ◀ Volver a Gráficos ]` y `[ 🏠 Menú Principal ]`.

### 8.6 Reportes Profesionales en PDF (`/reporte`)
Genera y envía un archivo PDF institucional con la identidad visual verde de **Ganadería JA**:
* `/reporte`: Reporte semanal consolidado con tablas de novedades, pesajes y alertas.
* `/reporte diario`: Reporte de las últimas 24 horas.
* `/reporte 15`: Reporte personalizado de los últimos 15 días.

---

## 9. Submenús Unificados de Sistema y Ayuda

Para mantener la pantalla del celular limpia y libre de botones repetidos, el bot organiza las opciones secundarias en dos submenús agrupados:

### 📦 A. Submenú «Sistema & Reportes» (`cmd:sistema_menu`)
Accesible desde el menú principal de administradores y dueños:
* `[ 📋 Reporte Semanal PDF ]`: Descarga inmediata del informe zootécnico.
* `[ 📦 Descargar Backup ZIP ]`: Genera y exporta el paquete DBF para Software Ganadero.
* `[ ⚙️ Servidor & Sistema ]`: Diagnóstico de hardware VPS, memoria RAM, SSD y estado SQLite.
* `[ 📜 Ver Últimos Logs ]`: Muestra los últimos eventos técnicos del sistema.
* `[ 👥 Usuarios / Permisos ]` *(Solo OWNER)*: Gestión de altas y bajas de personal.
* `[ 🏠 Menú Principal ]`: Retorno directo.

### ❓ B. Submenú «Ayuda & Guías» (`cmd:ayuda_menu`)
Accesible para todos los roles:
* `[ 📖 Manual / Comandos ]`: Despliegue completo de comandos y sintaxis.
* `[ 💬 Cómo Preguntar al Chat ]`: Centro de ejemplos de preguntas cotidianas en lenguaje natural.
* `[ 📝 Ejemplos de Notas ]`: Guía didáctica de cómo redactar partos, celos, traslados y remedios.
* `[ 💡 Guía de Campo ]`: Vista de campo guiada para el personal de corral.
* `[ 🏠 Menú Principal ]`: Retorno directo.

---

## 10. Sincronización con Software Ganadero (SG)

### 10.1 Importación de Backups ZIP por Telegram
1. Exporta la copia de seguridad `.Zip` en Software Ganadero.
2. Si pesa menos de 20 MB, envíala como **Documento** al chat del bot en Telegram.
3. El bot te responderá confirmando el tamaño recibido.
4. Escribe `/confirmar_importar` para procesarlo.
5. El importador deduplica automáticamente por llaves zootécnicas y emite el reporte de nuevos y duplicados.

### 10.2 Sincronización Automática por Carpeta COPIAS (70+ MB)
Para backups pesados (con fotos históricas):
* El vigilante de segundo plano (`copias_watcher` en VPS o `schtasks` en Windows) monitorea la carpeta `C:\Usati\Copias` o `data/copias/`.
* Al detectar un nuevo `.Zip`, lo procesa e importa automáticamente.
* Envía una notificación instantánea al `OWNER` por Telegram sin intervención manual.

### 10.3 Exportación de Datos para SG (`/exportar`, solo OWNER)
* `/exportar`: Genera y envía un paquete `.Zip` con las 8 tablas DBF listas para Software Ganadero.
* `/exportar csv`: Exporta toda la base de datos en archivos CSV tabulares.
* `/exportar json`: Exporta la base en formato JSON.
* Solo el OWNER puede exportar (entrega la base completa) y cada exportación avisa a los demás OWNER por Telegram.

---

## 11. Administración de Usuarios y Servidor

*(Comandos exclusivos para el rol `OWNER`)*

* **Ver usuarios autorizados:** `/usuarios`
* **Dar de alta a un trabajador:**
  ```text
  /agregar_usuario 712345678 TRABAJADOR Carlos
  ```
  *(El alta es instantánea; no requiere reiniciar el bot).*
* **Dar de alta a un administrador:**
  ```text
  /agregar_usuario 987654321 ADMIN Juan
  ```
* **Revocar acceso:** `/quitar_usuario 712345678`
* **Ver logs del sistema en vivo:** `/logs`
* **Estado de recursos del servidor:** `/sistema` (CPU, memoria RAM, SSD, SQLite).

---

## 12. Tabla Resumen de Comandos

| Comando | Nivel de Acceso | Descripción |
| :--- | :--- | :--- |
| `/start`, `/menu` | Todos | Abre el menú interactivo compacto con botones táctiles. |
| `/despacho`, `/matutino`, `/hoy` | Todos | Genera el briefing matutino de ordeño, inseminaciones AM, recordatorios y repro. |
| `/leche <litros>` | Todos | Registra la producción total de leche del hato del día. |
| `/programar <fecha> <hora> <msg>` | Todos | Agenda un recordatorio de campo (ej. `/programar 2026-09-01 08:00 Rotar potrero`). |
| `/graficos` | Admin / Owner | Panel de gráficos interactivos organizados en 4 categorías zootécnicas. |
| `/grafico_leche [tag]` | Todos | Genera la curva de lactancia individual de una vaca. |
| `/guia`, `/preguntar` | Todos | Centro de guía con ejemplos de cómo hacer preguntas al chat. |
| `/buscar [tag]` | Todos | Buscador de fichas de animales con filtros por categoría. |
| `/historial <tag>` | Todos | Ficha técnica interactiva del animal con pestañas y gráficos. |
| `/fotos [tag]` | Todos | Galería fotográfica general o fotos de un animal. |
| `/alertas` | Todos | Semáforo inteligente de partos, secados, destetes y retiros. |
| `/medicamentos` | Todos | Panel de control sanitario, fármacos y retiros activos. |
| `/preguntas`, `/faq` | Todos | Preguntas rápidas frecuentes de campo en 1 toque. |
| `/potreros` | Todos | Matriz SG de potreros y animales por pradera. |
| `/ocupacion` | Todos | Días de ocupación y descanso según Leyes de Voisin. |
| `/clima`, `/lluvias` | Todos | Reporte Pluviométrico & Clima IDEAM con acumulados y ajuste forrajero. |
| `/lluvia <mm> [sec]` | Todos | Registro rápido de milímetros de precipitación (ej. `/lluvia 35 sector bajo`). |
| `/balance_forrajero` | Todos | Balance forrajero de Materia Seca (MS): oferta diaria vs demanda hato (2.8% PV). |
| `/ndvi`, `/satelite` | Todos | Monitoreo satelital Sentinel-2 (NDVI), aforo satelital y vigor de potreros. |
| `/status`, `/tablero` | Admin / Owner | Tablero zootécnico general de la finca y novedades semanales. |
| `/poblacion` | Admin / Owner | Pirámide de edades y brackets demográficos de SG. |
| `/genetica` | Admin / Owner | Composición racial y cruces del hato. |
| `/reporte [días]` | Admin / Owner | Genera y envía el informe zootécnico en PDF institucional. |
| `/exportar [dbf\|csv\|json]` | Owner | Exporta paquetes de datos para Software Ganadero o análisis (solo OWNER: entrega la base completa y avisa a los demás OWNER). |
| `/importar` | Admin / Owner | Instrucciones para importar backups ZIP de SG. |
| `/confirmar_importar` | Admin / Owner | Ejecuta la importación del backup subido. |
| `/descartar_backup` | Admin / Owner | Elimina el backup pendiente sin procesar. |
| `/usuarios` | Owner | Lista los usuarios con acceso al bot. |
| `/agregar_usuario` | Owner | Registra un nuevo usuario (`TRABAJADOR`, `ADMIN`, `OWNER`). |
| `/quitar_usuario` | Owner | Elimina el acceso a un usuario. |
| `/sistema`, `/servidor` | Owner | Métricas del servidor VPS, SQLite y servicios de IA. |
| `/logs` | Owner | Consulta las últimas líneas del registro del sistema. |
| `/ayuda`, `/help` | Todos | Muestra el listado de comandos y manual de referencia. |

---

*Ganadería JA — Tecnología y Zootecnia de Precisión en el Campo.* 🌱🐄
