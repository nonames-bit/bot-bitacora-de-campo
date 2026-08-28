# 🤖 Directrices del Asistente de IA (AGENTS.md)

Este archivo define las reglas de comportamiento, estándares y herramientas para este proyecto.

---

## 📌 Protocolo de Inicio
1. **Revisión de Estado**: Antes de iniciar cualquier tarea, lee [README.md](./README.md) para comprender el objetivo, el hardware/stack en uso y el estado actual de los pendientes.
2. **Knowledge Graph (Graphify)**:
   - Si existe la carpeta `graphify-out/`, ejecuta `graphify query "<tu-pregunta>"` para consultar la arquitectura del código.
   - Para relaciones entre componentes: `graphify path "<ComponenteA>" "<ComponenteB>"`.
   - Después de crear o modificar código, ejecuta `graphify update .` para mantener el grafo al día.

---

## 🎯 Reglas Generales de Calidad
- **Preservación**: No elimines comentarios existentes ni documentación técnica al editar código.
- **Control de Versiones**:
  - Commits descriptivos en presente indicativo (ej: `add sensor calibration routine`, `fix tag binding`).
  - Cada cambio significativo debe documentarse en la sección de progreso de [README.md](./README.md).
- **Estructura Limpia**:
  - `src/`: Código fuente principal.
  - `docs/`: Documentación técnica, diagramas y especificaciones.
  - `tests/`: Pruebas unitarias, scripts de simulación o validaciones.
  - `scripts/`: Utilidades y scripts de automatización.
- **Regla Fundamental de Inventario (Hato Activo vs Histórico)**:
  - En Software Ganadero (SG), la base contiene todo el histórico (animales muertos, vendidos, descartados o con estado NULL).
  - **Toda consulta de inventario presente, conteos de hato, animales por potrero, ocupación o estado actual DEBE filtrar estrictamente por `estado = 'ACTIVO'`** (NUNCA usar `COALESCE(estado, 'ACTIVO')` ni omitir el filtro de estado, para no inflar el inventario sumando registros históricos).
  - Las consultas históricas puntuales (genealogía, partos pasados, fichas por tag) sí pueden consultar cualquier animal independientemente de su estado.

---

## 🧬 Dominio: Finca > Reproducción & Inseminación Artificial

### Metodología Zootécnica
- **Detección de Celos**: Regla AM-PM (celo en la mañana -> se insemina en la tarde; celo en la tarde -> se insemina en la mañana siguiente).
- **Control de Gestación**: Programación estricta de ecografías (día 35) y confirmación por palpación (día 60).
- **Inventario de Pajuelas**: Registro riguroso de tanque de nitrógeno líquido, código de toro, raza, pajuelas disponibles y procedencia genética.

### Herramientas & Skills
- **Skill Especializada**: `@inseminacion-calc`


---\n
## 📋 Dominio: Finca > Genética, Trazabilidad & Registros

### Metodología
- **Identificación Única**: Asignación de identificador inviolable (RFID / Arete visual / Tatuaje).
- **Control de Consanguinidad**: Verificación automática de parentesco en 3 generaciones antes de autorizar un cruzamiento.
- **Curvas de Crecimiento**: Registro de peso al nacer, al destete, a los 18 meses y al sacrificio.

### Herramientas & Skills
- **Skill Especializada**: `@trazabilidad-ganadera`


---\n
## 🌿 Dominio: Finca > Nutrición, Pasturas & Rotación

### Metodología
- **Leyes de André Voisin**: Ley del reposo, ley de la ocupación (máx 1-3 días), ley de los rendimientos máximos y ley del rendimiento regular.
- **Aforo**: Método del doble muestreo o marco de 1 m² (mínimo 10-15 puntos aleatorios por potrero).
- **Balance Forrajero**: Planificación estacional (época de lluvias vs época seca).

### Herramientas & Skills
- **Skill Especializada**: `@aforo-pasturas`


---\n
## 💉 Dominio: Finca > Sanidad Animal & Control Veterinario

### Metodología
- **Control de Fármacos**: Registro de principio activo, lote, dosis (ml/kg), vía de administración (SC, IM, IV, Oral) y fecha de vencimiento.
- **Alertas de Retiro**: Bloqueo automático de leche o carne para animales tratados durante su periodo de carencia/retiro.
- **Protocolos de Bioseguridad**: Cuarentena de animales recién ingresados y desinfección de instalaciones.

### Herramientas & Skills
- **Skill Especializada**: `@plan-sanitario`

