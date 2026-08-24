---
name: trazabilidad-ganadera
description: Gestión de árboles genealógicos, control de consanguinidad, pesajes periódicos y ganancia media diaria (GMD).
---

# 📋 Skill: Trazabilidad y Genética Ganadera

## 🎯 Cálculos de Crecimiento & Rendimiento
1. **Ganancia Media Diaria (GMD)**:
   $$\text{GMD (kg/día)} = \frac{\text{Peso Actual (kg)} - \text{Peso Anterior (kg)}}{\text{Días Transcurridos}}$$
2. **Peso Ajustado al Destete (a los 205 días)**:
   $$\text{Peso 205d} = \left( \frac{\text{Peso Destete} - \text{Peso Nacimiento}}{\text{Edad en Días al Destete}} \times 205 \right) + \text{Peso Nacimiento}$$

## 🌳 Estructura de Pedigree / Genealogía
```json
{
  "id_animal": "TORO-001",
  "raza": "Senepol",
  "fecha_nacimiento": "2024-03-10",
  "peso_nacimiento_kg": 34.5,
  "padre_id": "TORO-P-900",
  "madre_id": "VACA-M-420",
  "pesajes": [
    { "fecha": "2024-09-30", "peso_kg": 210.0, "evento": "DESTETE" },
    { "fecha": "2025-03-30", "peso_kg": 340.0, "evento": "YEARLING" }
  ]
}
```
