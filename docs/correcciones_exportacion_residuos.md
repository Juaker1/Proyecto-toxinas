# Correcciones en la Exportación de Datos de Residuos

## Problema Identificado

Se detectaron dos problemas críticos en la exportación de datos:

### 1. **Números de Residuo Incorrectos**
- **Antes**: Se usaba un contador secuencial o valores parseados incorrectamente
- **Problema**: Varios residuos GLU aparecían con el mismo número (ej: 17 GLU con número 1)
- **Causa**: No se extraía correctamente el `residue_number` de los atributos del nodo del grafo

### 2. **Falta de Información de Conectividad**
- **Antes**: Solo se mostraba el grado del nodo (número de conexiones)
- **Problema**: No se sabía QUÉ residuos estaban conectados
- **Necesidad**: Ver explícitamente la lista de vecinos conectados

---

## Soluciones Implementadas

### ✅ Cambio 1: Extracción Correcta de Números de Residuo

**Archivo**: `src/infrastructure/exporters/export_service_v2.py`

**Modificación en `extract_residue_data()`**:

```python
# NUEVO CÓDIGO
for node in G.nodes():
    node_attrs = G.nodes[node]
    
    # Extraer atributos del nodo (Graphein guarda estos datos)
    chain = node_attrs.get('chain_id', 'A')
    residue_name = node_attrs.get('residue_name', 'UNK')
    residue_number = node_attrs.get('residue_number', None)  # <-- NÚMERO ORIGINAL DEL PDB
```

**Resultado**:
- Los números de residuo ahora corresponden a los números ORIGINALES del archivo PDB
- No hay duplicados artificiales (cada GLU tiene su número correcto: GLU:1, GLU:16, GLU:23, etc.)

---

### ✅ Cambio 2: Columna "Vecinos_Conectados"

**Nueva columna agregada**: `Vecinos_Conectados`

**Código agregado**:
```python
# Obtener vecinos del nodo (residuos conectados)
neighbors = list(G.neighbors(node))
neighbor_list = []
for neighbor in neighbors:
    neighbor_attrs = G.nodes[neighbor]
    neighbor_res_name = neighbor_attrs.get('residue_name', 'UNK')
    neighbor_res_num = neighbor_attrs.get('residue_number', str(neighbor))
    neighbor_list.append(f"{neighbor_res_name}:{neighbor_res_num}")

# En el diccionario de datos:
'Vecinos_Conectados': ', '.join(neighbor_list) if neighbor_list else 'Ninguno'
```

**Qué significa**:
- Si un residuo tiene `Grado_Nodo = 13`, la columna `Vecinos_Conectados` mostrará exactamente cuáles son esos 13 residuos
- Formato: `GLY:14, CYS:33, VAL:45, ...`

---

### ✅ Cambio 3: Columna "Residuo_ID" Única con Átomo

**Nueva columna**: `Residuo_ID`

**Formato según granularidad**:
- **CA**: `{Cadena}:{Nombre_Residuo}:{Numero_Residuo}`  
  Ejemplo: `H:GLU:16`
  
- **atom**: `{Cadena}:{Nombre_Residuo}:{Numero_Residuo}:{Atomo}`  
  Ejemplo: `H:GLU:16:CA`

**Nueva columna adicional para granularidad atom**: `Atomo`

Esta columna separada facilita el filtrado y análisis:
- Ejemplo: `CA`, `CB`, `CG`, `CD`, `OE1`, `OE2`, etc.

**Propósito**:
- Identificador único e inequívoco para cada residuo/átomo
- Para granularidad `atom`: diferencia cada átomo del mismo residuo
- Facilita joins/merges en análisis posteriores
- Evita ambigüedad cuando hay múltiples cadenas

---

### ✅ Cambio 4: Actualización de Segmentación Atómica

**Archivo**: `src/domain/services/segmentation_service.py`

**Para análisis con `granularity=atom`**:

Se agregó la columna `Residuos_Vecinos_Conectados` que muestra:
- Residuos EXTERNOS conectados al segmento atómico
- Solo cuenta residuos diferentes (no átomos del mismo residuo)

Ejemplo:
```
Segmento: RES_016 (GLU:16)
  ├─ Átomos internos: CA, CB, CG, CD, OE1, OE2, etc.
  ├─ Residuos vecinos: GLY:14, CYS:15, VAL:17, LYS:18
  └─ Grado_Nodo promedio del segmento: 4.5
```

---

## Formato de Exportación Actualizado

### **Granularidad: CA** (un registro por residuo)

| Residuo_ID | Cadena | Residuo_Nombre | Residuo_Numero | Grado_Nodo | Centralidad_Grado | Vecinos_Conectados |
|------------|--------|----------------|----------------|------------|-------------------|--------------------|
| H:GLU:1    | H      | GLU            | 1              | 3          | 0.045             | GLY:2, CYS:3       |
| H:GLY:2    | H      | GLY            | 2              | 4          | 0.067             | GLU:1, CYS:3, VAL:4|
| H:CYS:3    | H      | CYS            | 3              | 6          | 0.089             | GLU:1, GLY:2, VAL:4, CYS:23, ...|
| H:VAL:4    | H      | VAL            | 4              | 5          | 0.078             | GLY:2, CYS:3, LEU:5, ...|
| ...        | ...    | ...            | ...            | ...        | ...               | ...                |
| H:GLU:16   | H      | GLU            | 16             | 13         | 0.156             | GLY:14, CYS:15, VAL:17, LYS:18, ...|
| ...        | ...    | ...            | ...            | ...        | ...               | ...                |

**Nota**: Ahora hay UN SOLO GLU:1, UN SOLO GLU:16, etc. (sin duplicados)

---

### **Granularidad: atom** (múltiples registros por residuo)

**NUEVA COLUMNA**: `Atomo` - indica el tipo de átomo (CA, CB, CG, etc.)

Si usas `granularity=atom`, el formato incluye una columna adicional para el átomo:

| Residuo_ID     | Cadena | Residuo_Nombre | Residuo_Numero | Atomo | Grado_Nodo | Vecinos_Conectados |
|----------------|--------|----------------|----------------|-------|------------|--------------------|
| H:GLU:16:CA    | H      | GLU            | 16             | CA    | 5          | GLY:14:CA, CYS:15:CA, VAL:17:CA, GLU:16:CB, GLU:16:N|
| H:GLU:16:CB    | H      | GLU            | 16             | CB    | 3          | GLU:16:CA, GLU:16:CG, VAL:17:CB|
| H:GLU:16:CG    | H      | GLU            | 16             | CG    | 4          | GLU:16:CB, GLU:16:CD, VAL:17:CG|
| H:GLU:16:CD    | H      | GLU            | 16             | CD    | 3          | GLU:16:CG, GLU:16:OE1, GLU:16:OE2|
| H:GLU:16:OE1   | H      | GLU            | 16             | OE1   | 1          | GLU:16:CD|
| H:GLU:16:OE2   | H      | GLU            | 16             | OE2   | 1          | GLU:16:CD|
| H:GLU:16:N     | H      | GLU            | 16             | N     | 2          | GLU:16:CA, CYS:15:C|
| H:GLU:16:C     | H      | GLU            | 16             | C     | 2          | GLU:16:CA, VAL:17:N|
| H:GLU:16:O     | H      | GLU            | 16             | O     | 1          | GLU:16:C|
| ...            | ...    | ...            | ...            | ...   | ...        | ...                |

**Ventajas de la columna separada `Atomo`**:
- ✅ Fácil filtrado: `df[df['Atomo'] == 'CA']` para obtener solo Cα
- ✅ Comparación entre tipos de átomo: `df.groupby('Atomo')['Grado_Nodo'].mean()`
- ✅ Análisis backbone vs sidechain: `df[df['Atomo'].isin(['N', 'CA', 'C', 'O'])]`
- ✅ Identificación completa: `Residuo_ID` incluye todo (H:GLU:16:CA)

---

## Interpretación de los Datos

### Ejemplo Práctico

**Registro**:
```
Residuo_ID: H:GLU:16
Grado_Nodo: 13
Centralidad_Intermediacion: 0.156
Vecinos_Conectados: GLY:14, CYS:15, VAL:17, LYS:18, ALA:19, PRO:20, 
                    CYS:33, TYR:34, ARG:35, PHE:36, GLU:37, TRP:38, MET:39
```

**Interpretación**:
1. **Residuo**: Glutamato en posición 16 de la cadena H
2. **Grado**: Tiene 13 conexiones (dentro del umbral de distancia de 10 Å)
3. **Centralidad**: Betweenness de 0.156 indica que es un "hub" importante (muchas rutas pasan por él)
4. **Vecinos**: Está conectado a:
   - Residuos secuencialmente cercanos (14, 15, 17, 18, 19, 20)
   - Residuos lejanos en secuencia pero cercanos espacialmente (33-39)
   - Esto indica que GLU:16 está en una región que conecta dos partes de la estructura

### Verificación de Consistencia

**Grado_Nodo debe coincidir con el número de vecinos**:
- Si `Grado_Nodo = 13` → debe haber exactamente 13 residuos en `Vecinos_Conectados`
- Puedes verificar esto contando las comas + 1

**Los números de residuo deben ser únicos por cadena**:
- No deberías ver dos `H:GLU:16` diferentes
- Si los ves, significa que el problema persiste

---

## Cómo Usar Esta Información

### 1. **Análisis de Hubs Estructurales**
```python
# Identificar residuos con alta conectividad
df_sorted = df.sort_values('Grado_Nodo', ascending=False)
top_hubs = df_sorted.head(10)

# Ver qué conectan estos hubs
for idx, row in top_hubs.iterrows():
    print(f"{row['Residuo_ID']}: conecta {row['Grado_Nodo']} residuos")
    print(f"  → {row['Vecinos_Conectados']}")
```

### 2. **Identificar Puentes Disulfuro**
```python
# Buscar CYS conectados entre sí
cys_residues = df[df['Residuo_Nombre'] == 'CYS']
for idx, row in cys_residues.iterrows():
    vecinos = row['Vecinos_Conectados']
    if 'CYS' in vecinos:
        print(f"Posible puente: {row['Residuo_ID']} ↔ {vecinos}")
```

### 3. **Análisis de Regiones Compactas**
```python
# Identificar residuos que conectan partes distantes
for idx, row in df.iterrows():
    vecinos_nums = [int(v.split(':')[1]) for v in row['Vecinos_Conectados'].split(', ') if ':' in v]
    res_num = row['Residuo_Numero']
    
    # Ver si hay vecinos lejanos en secuencia (gap > 10)
    gaps = [abs(n - res_num) for n in vecinos_nums]
    max_gap = max(gaps) if gaps else 0
    
    if max_gap > 10:
        print(f"{row['Residuo_ID']}: conecta residuos separados por {max_gap} posiciones")
```

### 4. **Correlación Estructura-Actividad**
```python
# Correlacionar conectividad con IC50
import matplotlib.pyplot as plt
import numpy as np

plt.scatter(df['Grado_Nodo'], df['IC50_nM'])
plt.xlabel('Grado del Nodo (Conectividad)')
plt.ylabel('IC50 (nM) - menor = más potente')
plt.title('Relación entre Conectividad Estructural y Actividad')
plt.show()

# Calcular correlación
correlation = np.corrcoef(df['Grado_Nodo'], df['IC50_nM'])[0, 1]
print(f"Correlación Pearson: {correlation:.3f}")
```

---

## Testing

Para verificar que los cambios funcionan correctamente, usa:

```powershell
python tools\test_residue_neighbors.py
```

**Verificaciones automáticas**:
1. ✓ No hay duplicados de `Residuo_ID`
2. ✓ Los números de residuo están en el rango esperado
3. ✓ Cada residuo tiene su lista de vecinos
4. ✓ El `Grado_Nodo` coincide con el número de vecinos

---

## Archivos Modificados

1. **`src/infrastructure/exporters/export_service_v2.py`**
   - Método `extract_residue_data()`: 
     - Extracción correcta de números de residuo originales del PDB
     - Agregada columna `Vecinos_Conectados` con lista de residuos/átomos conectados
     - Agregada columna `Atomo` cuando `granularity=atom`
     - `Residuo_ID` ahora incluye átomo: `H:GLU:16:CA` (para atom)

2. **`src/domain/services/segmentation_service.py`**
   - Método `agrupar_por_segmentos_atomicos()`: Vecinos para segmentos atómicos
   - Método `agrupar_por_segmentos()`: Vecinos para granularidad CA

3. **`tools/test_residue_neighbors.py`** (NUEVO)
   - Script de validación para verificar correcciones
   - Prueba con ambas granularidades (CA y atom)
   - Muestra ejemplos de la nueva columna `Atomo`

---

## Próximos Pasos Recomendados

1. **Ejecutar el script de prueba** para validar con tus PDBs
2. **Exportar un dataset** con los nuevos campos
3. **Verificar en Excel/CSV** que:
   - No hay duplicados de residuos
   - Los vecinos son correctos (puedes validar algunos manualmente con PyMOL/Mol*)
   - Los números de residuo coinciden con tu PDB original
4. **Actualizar tests unitarios** si es necesario (algunos pueden esperar columnas antiguas)

---

## Preguntas Frecuentes

**Q: ¿Por qué antes veía 17 GLU:1?**
A: Porque en granularidad `atom`, cada átomo del GLU se contaba como un nodo separado, pero todos compartían el mismo identificador incompleto.

**Q: ¿Cuándo debo usar `granularity=CA` vs `atom`?**
A: 
- `CA`: Análisis a nivel de residuo (recomendado para SAR, más limpio)
- `atom`: Análisis detallado de interacciones atómicas (útil para dinámica molecular)

**Q: ¿Cómo valido que un vecino está realmente cerca?**
A: Los vecinos listados están dentro del `distance_threshold` (típicamente 8-10 Å). Puedes verificar distancias reales en PyMOL con:
```
distance H:GLU:16 and name CA, H:CYS:33 and name CA
```

**Q: ¿Qué pasa si hay múltiples cadenas?**
A: El formato `Cadena:Residuo:Numero` maneja múltiples cadenas correctamente (ej: `A:GLU:16` vs `B:GLU:16`).

---

**Fecha de actualización**: 2025-11-10  
**Autor**: Sistema de análisis de toxinas Nav1.7
