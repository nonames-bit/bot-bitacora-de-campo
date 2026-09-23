# 📊 Análisis y Plan de Migración de Reportes: Software Ganadero (SG) -> PWA Bitácora JA

Documento de referencia técnica elaborado a partir de las 11 capturas de pantalla de Software Ganadero (SG) suministradas en `C:\Users\Owner\Desktop\fotos`.

---

## 📸 1. Análisis Individual de Capturas y Métricas Clave

### 1. `indicefertilidad.jpg` — Índice de Fertilidad Oficial (SG)
- **Fórmula Oficial SG**:
  $$\text{I.F.} = \left( \frac{\text{Hembras Preñadas} + \text{Vacas } \le 120 \text{ días postparto}}{\text{Vacas y novillas vientre con edad } \ge 3.0 \text{ años}} \right) \times 100$$
- **Criterio Zootécnico**: Evalúa el porcentaje del hato apto que está gestando o en período de descanso fisiológico óptimo.
- **Implementación PWA**:
  - Incorporado en la tarjeta principal de la pestaña **Reproducción**.
  - Semáforo zootécnico: 🟢 $\ge 75\%$, 🟡 $60\% - 74\%$, 🔴 $< 60\%$.
  - Muestra desglose: Preñadas, En descanso ($\le 120$ d) y Total vientres aptos.

---

### 2. `diasabiertosanalisis.jpg` — Distribución de Días Abiertos
- **Estructura en SG**: 9 intervalos zootécnicos de días abiertos desde el último parto hasta la concepción o fecha actual:
  1. `0 - 90` días (Meta óptima)
  2. `91 - 120` días (Aceptable)
  3. `121 - 150` días (En observación)
  4. `151 - 180` días (Retraso)
  5. `181 - 210` días (Crítico)
  6. `211 - 240` días
  7. `241 - 270` días
  8. `271 - 300` días
  9. `> 300` días (Problema reproductivo grave / Candidata a descarte)
- **Implementación PWA**:
  - Gráfico de barras de frecuencia y conteo de vacas por tramo en el panel de Reproducción.

---

### 3. `fetilidadparidas.jpg` — Distribución de Frecuencias de IEP (Intervalo Entre Partos)
- **Estructura en SG**: 6 tramos de Intervalo Entre Partos real e histórico:
  1. `< 365` días (Excelente)
  2. `365 - 395` días (Óptimo)
  3. `396 - 425` días (Normal)
  4. `426 - 455` días (Alerta)
  5. `456 - 485` días (Desfavorable)
  6. `> 485` días (Deficiente)
- **Implementación PWA**:
  - Resumen visual con conteo de vacas y porcentajes por rango de IEP.

---

### 4. `leche2.jpg` — Análisis de DEL (Días En Leche) y Etapas de Lactancia
- **Métricas SG**:
  - Días En Leche (DEL) promedio del lote de ordeño.
  - Distribución por etapas fisiológicas de la curva de lactancia:
    - **Pico de lactancia**: $0 - 100$ días.
    - **Meseta / Media lactancia**: $101 - 200$ días.
    - **Descenso / Lactancia tardía**: $201 - 340$ días.
    - **Lactancia prolongada**: $> 340$ días (requieren secado inminente).
- **Implementación PWA**:
  - Tarjeta de DEL promedio en la pestaña **Leche** con desglose de vacas por etapa.

---

### 5. `lechehoy.jpg` — Control Diario de Ordeño
- Total litros entregados vs autoconsumo.
- Promedio litros/vaca/día en ordeño.
- Comparativa vs semana anterior.
- Ya implementado en PWA y Bot Telegram (`/leche`).

---

### 6. `poblacionhoy.jpg` — Dinámica Poblacional del Hato Activo
- Desglose por sexo y grupos de edad:
  - Terneros/as ($< 1$ año).
  - Levantes/Mañecos ($1 - 2$ años).
  - Novillas de vientre y toretes ($2 - 3$ años).
  - Vacas adultas y toros reproductores ($> 3$ años).
- Regla: Siempre filtrar estrictamente por `estado = 'ACTIVO'` para no contabilizar descartes ni ventas históricas.
- Ya disponible en PWA en **Inventario / Población**.

---

### 7. `reproduccion1.jpg` — Eficiencia Reproductiva Global
- Resumen consolidado: Tasa de preñez global, IEP promedio general, servicios por concepción.
- Presente en PWA consolidando datos zootécnicos.

---

### 8. `vacasparidas.jpg` — Ficha de Vacas Paridas Recientes
- Lista detallada de vacas con fecha de parto, días transcurridos, cría asociada y estado reproductivo actual.
- Disponible en PWA en la tabla detallada de vientres.

---

### 9. `carnehoy.jpg` — Ganancia Media Diaria y Rendimiento en Carne
- GMD general por lote de ceba y levante.
- Pesajes ajustados y proyección de salida a matadero.
- Disponible en PWA bajo **Pesajes / Carne**.

---

### 10. `indicadoresnovillos.jpg` — Indicadores de Levante y Ceba Masculina
- Edad promedio de salida a ceba, curva de ganancia de peso y conversión forrajera.
- Integrado en el módulo de Pesajes y GMD.

---

### 11. `indicadoresnovillas.jpg` — Indicadores de Hembras de Reemplazo
- Edad a primer servicio (meta: $< 24 - 27$ meses).
- Peso a primera monta (meta: $\ge 320 - 350$ kg según raza/cruce).
- Monitoreo en PWA en la pestaña de Reproducción / Hembras Jóvenes.

---

## 🔄 2. Módulo de Reversión Inteligente ("Deshacer Último Registro")

Para responder a la necesidad de subsanar equivocaciones de campo sin recurrir a backups:
1. **PWA**: Botón y modal interactivo **"Últimos eventos registrados (Deshacer)"** accesible desde:
   - Menú de usuario (Avatar en el header).
   - Menú "Más Módulos" (Hoja de accesos rápidos).
   - En cada evento individual de la Ficha del Animal.
2. **Reversión en Cascada**:
   - **Muerte / Venta / Descarte borrado**: Restaura automáticamente el animal al estado `ACTIVO`.
   - **Traslado borrado**: Restaura al animal al `potrero_origen` previo.
   - **Parto borrado**: Elimina alertas derivadas de secado/palpación y limpia la cría si era un registro automático sin otros eventos.
   - **Servicio/IA borrado**: Limpia las alertas automáticas de ecografía, palpación y FEP.
