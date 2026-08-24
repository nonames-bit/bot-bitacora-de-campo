---
name: inseminacion-calc
description: Cálculos reproductivos para ganado bovino (Fecha Estimada de Parto FEP, Días Abiertos, Intervalo Entre Partos IEP).
---

# 🧬 Skill: Cálculos Reproductivos Bovinos & Inseminación Artificial

## 🎯 Constantes y Fórmulas Zootécnicas
1. **Gestación Bovina**:
   - Promedio: **283 días** (Rango estándar: 280 - 285 días según raza).
   - `FEP = Fecha_IA + 283 días`
2. **Programación de Chequeos**:
   - Ecografía: `Fecha_IA + 35 días`
   - Palpación Rectal: `Fecha_IA + 60 días`
   - Secado de la vaca lechera: `FEP - 60 días` (7 meses de gestación)
3. **Indicadores de Eficiencia Reproductiva**:
   - $\text{Días Abiertos} = \text{Fecha Concepción} - \text{Fecha Último Parto}$ (Meta ideal: < 100-110 días).
   - $\text{Intervalo Entre Partos (IEP)} = \text{Días Abiertos} + 283\text{ días}$ (Meta ideal: 12-13 meses / 365-400 días).

## 📊 Estructura de Registro JSON / Base de Datos
```json
{
  "id_animal": "VACA-204",
  "nombre": "Mariposa",
  "fecha_ia": "2026-08-15",
  "hora_ia": "06:30",
  "tipo_servicio": "IA_CONGELADA",
  "id_toro_semen": "TORO-BRAHMAN-502",
  "raza_toro": "Brahman Rojo",
  "inseminador": "Juan Pérez",
  "fep_calculada": "2027-05-25",
  "estado_reproductivo": "SERVIDA_POR_CONFIRMAR"
}
```
