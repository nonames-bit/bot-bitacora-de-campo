# 🤖 Claude Code Guidelines

Este proyecto sigue los estándares y reglas definidos en [AGENTS.md](./AGENTS.md).

## Comandos Rápidos
- **Consultar arquitectura**: `graphify query "<pregunta>"`
- **Actualizar grafo**: `graphify update .`
- **Revisar estado del proyecto**: Consulta [README.md](./README.md)


## Reglas Especificas del Dominio

### 📱 Verificación y Navegación Visual de la PWA
- En tareas de interfaz, backend con impacto visual o flujos de usuario, **navegar y revisar activamente la PWA** (local o producción).
- Probar y capturar en viewport móvil (**390×844**) para validar usabilidad táctil, visibilidad de tarjetas, modales y ausencia de desbordes.

### ⚠️ Regla Fundamental de Inventario (Hato Activo vs Histórico)
- Toda consulta de inventario presente, conteos de hato, animales por potrero, ocupación o estado actual **DEBE filtrar estrictamente por `estado = 'ACTIVO'`**.
- **NUNCA usar `COALESCE(estado, 'ACTIVO')`** ni omitir el filtro de estado en consultas presentes, para evitar sumar animales históricos/muertos/vendidos/NULL.
- Las consultas históricas puntuales (genealogía, partos pasados, fichas por arete) sí pueden consultar cualquier animal independientemente de su estado.

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

