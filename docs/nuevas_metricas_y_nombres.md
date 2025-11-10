# Nuevas Métricas y Cambios en Nombres de Columnas

## Cambios en Nombres de Columnas

Para hacer más intuitivo el análisis de datos, se renombraron las siguientes columnas:

### Cambios Principales:

| Nombre Anterior | Nombre Nuevo | Descripción |
|----------------|--------------|-------------|
| `Residuo_ID` | `Identificador_Residuo` | ID único del residuo/átomo (ej: H:GLU:16 o H:GLU:16:CA) |
| `Residuo_Nombre` | `Aminoacido` | Tipo de aminoácido (GLY, ASP, GLU, CYS, etc.) |
| `Residuo_Numero` | `Posicion_Secuencia` | Posición en la secuencia primaria (número del PDB) |
| `Atomo` | `Tipo_Atomo` | Tipo de átomo (CA, CB, CG, N, C, O, etc.) - solo en granularidad atom |
| `Grado_Nodo` | `Numero_Conexiones` | Cantidad de residuos/átomos conectados |
| `Vecinos_Conectados` | `Residuos_Vecinos` | Lista de residuos conectados |

### Justificación:

- **`Aminoacido`**: Más claro que "Residuo_Nombre" - indica directamente el tipo de aminoácido
- **`Posicion_Secuencia`**: Indica que es la posición en la secuencia primaria del PDB
- **`Numero_Conexiones`**: Más descriptivo que "Grado_Nodo" para usuarios no familiarizados con teoría de grafos
- **`Tipo_Atomo`**: Clarifica que es el tipo específico de átomo (cuando aplica)

---

## Nuevas Métricas Agregadas

### 1. **Distancia_Secuencial_Promedio**

#### ¿Qué mide?
Promedio de la separación en la secuencia entre el residuo actual y todos sus vecinos conectados espacialmente.

**Fórmula**: 
```
Distancia_Secuencial_Promedio = Σ |Posicion_Vecino - Posicion_Actual| / N_vecinos
```

#### ¿Por qué es útil?

**Para investigación de toxinas Nav1.7:**

1. **Identificación de residuos estructuralmente críticos**:
   - Valores **altos** (>10) → El residuo conecta partes **lejanas en secuencia** pero cercanas en el espacio 3D
   - Estos residuos son puntos clave de **plegamiento** y estabilización estructural
   - Ejemplo: Un residuo en posición 15 que conecta con residuos 5, 8, 35, 38 tiene alta distancia secuencial promedio

2. **Detección de farmacóforos**:
   - Los residuos del farmacóforo (región de unión al canal Nav1.7) suelen tener alta distancia secuencial
   - Conectan loops, giros β, y regiones de superficie expuesta
   - Crítico para identificar el "sitio activo" de la toxina

3. **Diferenciación entre mutantes**:
   - Comparar wild-type vs mutantes: cambios en esta métrica indican alteraciones en el plegamiento
   - Si un mutante tiene menor distancia secuencial promedio → plegamiento más compacto o pérdida de estructura terciaria
   - Correlaciona con cambios en IC50 (actividad biológica)

4. **Análisis de estabilidad**:
   - Residuos con alta distancia secuencial promedio son **anclas** que mantienen la arquitectura 3D
   - Mutaciones en estos residuos son más propensas a desestabilizar la proteína
   - Útil para predecir efectos de alanine scanning

#### Ejemplos de Interpretación:

**Escenario 1: Residuo de farmacóforo**
```
Identificador: H:ARG:28
Numero_Conexiones: 12
Distancia_Secuencial_Promedio: 15.3
Residuos_Vecinos: GLY:2, CYS:3, TYR:12, CYS:18, TRP:25, ARG:29, PHE:45, CYS:47, ...
```
**Interpretación**: ARG:28 conecta residuos distantes (2, 3, 12 con 45, 47). Es un residuo **clave en el plegamiento** y probablemente parte del **farmacóforo** (región de unión).

**Escenario 2: Residuo de hélice/hebra**
```
Identificador: H:VAL:10
Numero_Conexiones: 6
Distancia_Secuencial_Promedio: 2.1
Residuos_Vecinos: GLY:8, ALA:9, LEU:11, ILE:12, ...
```
**Interpretación**: VAL:10 conecta principalmente con vecinos secuenciales (8, 9, 11, 12). Es parte de una **estructura secundaria regular** (hélice α o hebra β).

---

### 2. **Proporcion_Contactos_Largos**

#### ¿Qué mide?
Proporción (0.0 - 1.0) de vecinos que están separados **más de 5 posiciones** en la secuencia.

**Fórmula**:
```
Proporcion_Contactos_Largos = N_vecinos_largos / N_vecinos_totales

donde:
  N_vecinos_largos = vecinos con |Posicion_Vecino - Posicion_Actual| > 5
```

#### ¿Por qué es útil?

**Para investigación de toxinas Nav1.7:**

1. **Clasificación funcional de residuos**:
   - **Proporción alta (>0.6)**: Residuos en **superficie/interfaces**
     - Expuestos al solvente o formando interfaces de unión
     - Candidatos principales para interacción con Nav1.7
     - Típicos de loops flexibles y regiones de reconocimiento
   
   - **Proporción baja (<0.3)**: Residuos en **core hidrofóbico**
     - Enterrados en el interior de la proteína
     - Contactos principalmente secuenciales (estructuras secundarias)
     - Importantes para estabilidad, no para función directa

2. **Predicción de sitios de unión**:
   - Residuos con **alta proporción de contactos largos** son candidatos para:
     - Unión a canal Nav1.7
     - Formación de anillos de carga (Arg/Lys clusters)
     - Parches hidrofóbicos de reconocimiento
   - Puedes filtrar: `df[df['Proporcion_Contactos_Largos'] > 0.6]` para obtener candidatos

3. **Análisis comparativo WT vs mutantes**:
   - **Aumento** en proporción de contactos largos → Mayor exposición (pérdida de compactación)
   - **Disminución** → Colapso estructural o mayor enterramiento
   - Correlaciona con cambios en dinámica y flexibilidad

4. **Identificación de puentes disulfuro funcionales**:
   - CYS con alta proporción de contactos largos → Puentes disulfuro que estabilizan estructura terciaria
   - CYS con baja proporción → Puentes disulfuro locales (estructura secundaria)

#### Ejemplos de Interpretación:

**Escenario 1: Residuo de interface (candidato farmacóforo)**
```
Identificador: H:TRP:38
Numero_Conexiones: 10
Proporcion_Contactos_Largos: 0.80
Distancia_Secuencial_Promedio: 18.5
```
**Interpretación**: TRP:38 tiene 80% de contactos no-locales. Está **altamente expuesto** y conecta regiones distantes. **Candidato principal** para interacción con Nav1.7 (probablemente parte del parche hidrofóbico de unión).

**Escenario 2: Residuo de core (estabilizador estructural)**
```
Identificador: H:LEU:22
Numero_Conexiones: 8
Proporcion_Contactos_Largos: 0.12
Distancia_Secuencial_Promedio: 2.8
```
**Interpretación**: LEU:22 tiene 88% de contactos locales. Está **enterrado** en el core hidrofóbico, parte de una hélice α. Importante para **estabilidad**, no para función directa de unión.

**Escenario 3: CYS formando puente disulfuro no-local**
```
Identificador: H:CYS:15
Numero_Conexiones: 7
Proporcion_Contactos_Largos: 0.71
Residuos_Vecinos: CYS:3, GLY:14, TRP:16, CYS:42, PHE:43, ...
```
**Interpretación**: CYS:15 tiene alta proporción de contactos largos y está conectado a CYS:42 (distancia secuencial = 27). Forma un **puente disulfuro no-local** que estabiliza el plegamiento global.

---

## Uso Combinado de Ambas Métricas

### Clasificación de Residuos por Cuadrantes:

| Distancia_Secuencial_Promedio | Proporcion_Contactos_Largos | Tipo de Residuo | Función |
|------------------------------|----------------------------|-----------------|---------|
| **Alta (>10)** | **Alta (>0.6)** | **Farmacóforo / Interface** | Unión al target, reconocimiento molecular |
| **Alta (>10)** | **Baja (<0.3)** | **Ancla estructural** | Plegamiento, estabilización de estructura terciaria |
| **Baja (<5)** | **Alta (>0.6)** | **Loop expuesto** | Flexibilidad, accesibilidad al solvente |
| **Baja (<5)** | **Baja (<0.3)** | **Core / Estructura secundaria** | Estabilidad, empaquetamiento hidrofóbico |

### Ejemplos de Análisis:

#### 1. Identificar farmacóforo completo:
```python
# Filtrar residuos con alta distancia secuencial Y alta proporción de contactos largos
pharmacophore_candidates = df[
    (df['Distancia_Secuencial_Promedio'] > 10) & 
    (df['Proporcion_Contactos_Largos'] > 0.6)
]

print("Candidatos para farmacóforo:")
print(pharmacophore_candidates[['Identificador_Residuo', 'Aminoacido', 'Posicion_Secuencia', 
                                 'Numero_Conexiones', 'Distancia_Secuencial_Promedio', 
                                 'Proporcion_Contactos_Largos']].sort_values('Proporcion_Contactos_Largos', ascending=False))
```

#### 2. Comparar mutante vs wild-type:
```python
# Calcular diferencias en métricas
df_wt['Delta_Dist_Seq'] = df_mutant['Distancia_Secuencial_Promedio'] - df_wt['Distancia_Secuencial_Promedio']
df_wt['Delta_Prop_Largos'] = df_mutant['Proporcion_Contactos_Largos'] - df_wt['Proporcion_Contactos_Largos']

# Identificar residuos más afectados
most_affected = df_wt.nlargest(10, 'Delta_Dist_Seq')
print("Residuos con mayor cambio estructural:")
print(most_affected[['Identificador_Residuo', 'Delta_Dist_Seq', 'Delta_Prop_Largos']])
```

#### 3. Correlación con IC50:
```python
import matplotlib.pyplot as plt
import seaborn as sns

# Scatter plot: Proporcion_Contactos_Largos vs IC50
plt.figure(figsize=(12, 5))

plt.subplot(1, 2, 1)
plt.scatter(df['Proporcion_Contactos_Largos'], df['IC50_nM'], alpha=0.6)
plt.xlabel('Proporción de Contactos Largos')
plt.ylabel('IC50 (nM)')
plt.title('Exposición vs Actividad')

plt.subplot(1, 2, 2)
plt.scatter(df['Distancia_Secuencial_Promedio'], df['IC50_nM'], alpha=0.6)
plt.xlabel('Distancia Secuencial Promedio')
plt.ylabel('IC50 (nM)')
plt.title('Plegamiento vs Actividad')

plt.tight_layout()
plt.show()
```

#### 4. Heatmap de familia:
```python
# Crear matriz de proporción de contactos largos por posición y toxina
pivot = df_family.pivot_table(
    values='Proporcion_Contactos_Largos', 
    index='Posicion_Secuencia', 
    columns='Toxina'
)

sns.heatmap(pivot, cmap='RdYlBu_r', center=0.5)
plt.title('Proporción de Contactos Largos - Familia μ-TRTX-Hh')
plt.ylabel('Posición en Secuencia')
plt.xlabel('Toxina')
plt.show()
```

---

## Interpretación Biológica

### Caso de Uso: Análisis de μ-TRTX-Hh2a

**Hipótesis**: Los residuos del farmacóforo (Y33, W30) deberían tener:
- Alta `Distancia_Secuencial_Promedio` (conectan regiones distantes)
- Alta `Proporcion_Contactos_Largos` (expuestos en superficie)

**Resultados esperados**:
```
Identificador_Residuo: H:TYR:33
Numero_Conexiones: 11
Distancia_Secuencial_Promedio: 16.8
Proporcion_Contactos_Largos: 0.82
→ Confirmado como farmacóforo

Identificador_Residuo: H:TRP:30
Numero_Conexiones: 9
Distancia_Secuencial_Promedio: 14.3
Proporcion_Contactos_Largos: 0.78
→ Confirmado como farmacóforo
```

**Comparación con mutante Y33W**:
```
WT Y33:  Dist.Seq.Prom = 16.8, Prop.Largos = 0.82
Mutante W33: Dist.Seq.Prom = 15.1, Prop.Largos = 0.75

Interpretación: El mutante Y33W muestra:
- Menor distancia secuencial → Plegamiento ligeramente más compacto
- Menor proporción de contactos largos → Residuo menos expuesto
- Resultado: IC50 aumenta (menor actividad) → Correlación estructura-actividad confirmada
```

---

## Resumen

### Beneficios de las Nuevas Métricas:

1. **Identificación automática de farmacóforos** sin análisis manual
2. **Predicción de efectos de mutaciones** antes de experimentos costosos
3. **Clasificación funcional de residuos** (farmacóforo, estabilizador, core)
4. **Análisis comparativo cuantitativo** entre familias/mutantes
5. **Correlación directa con IC50** para análisis SAR (Structure-Activity Relationship)

### Flujo de Trabajo Recomendado:

1. **Exportar datos** con nuevas métricas
2. **Filtrar candidatos** de farmacóforo: `Proporcion_Contactos_Largos > 0.6`
3. **Identificar anclas estructurales**: `Distancia_Secuencial_Promedio > 10`
4. **Comparar WT vs mutantes**: calcular deltas en métricas
5. **Correlacionar con IC50**: buscar tendencias estadísticas
6. **Validar experimentalmente**: alanine scanning en candidatos top

---

**Fecha**: 2025-11-10  
**Implementado en**: `src/infrastructure/exporters/export_service_v2.py`  
**Compatible con**: Granularidades CA y atom
