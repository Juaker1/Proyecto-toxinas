# Métricas, fórmulas y criterios de filtrado del proyecto

> Documento técnico para memoria de título – Proyecto toxinas / Nav1.7

Este documento resume las fórmulas, métricas y criterios de filtrado utilizados en el proyecto, indicando su significado biológico/computacional y dónde están implementados en el código.

## 1. Filtro de toxinas por motivo (buscador de candidatos)

**Archivo principal:** `extractors/toxins_filter.py`

### 1.1. Motivo estructural NaSpTx‑like (Cys‑knottin)

1. **Número mínimo de cisteínas**  
   - Condición: la secuencia debe tener al menos 6 cisteínas:  
     $$\#C(\text{secuencia}) \ge 6$$
   - Implementación: `has_at_least_six_c(seq)`.

2. **Posición de la quinta cisteína y serina siguiente**  
   - Se localiza la 5ª cisteína (índice $i_{C5}$) y se exige una serina inmediatamente después:  
     $$s[i_{C5}] = C,\quad s[i_{C5}+1] = S$$
   - Implementación: `link_c5_S_to_WCK_gap` calcula `iC5` e `iS`.

3. **Motivo WCKX en una ventana de separación**  
   - Se exige un motivo `WCKX` (W‑C‑K seguido de un aminoácido hidrofóbico X) a una distancia entre `gap_min` y `gap_max` residuos desde la S:  
     $$i_W \in [i_S + \text{gap_min},\ i_S + \text{gap_max}]$$  
     $$s[i_W:i_W+3] = \text{"WCK"},\quad X = s[i_{X3}] \in \{F,W,Y,L,I,V,M,A\}$$
   - Implementación: bucle en `link_c5_S_to_WCK_gap`, con `HYDRO_SET`.

4. **Patrones regulares (screening inicial)**  
   - Se usan expresiones regulares sobre la secuencia en mayúsculas:  
     - Núcleo: `PAT_WCKX3 = "WCK[FWYLIVMA]"`  
     - Serina previa: `PAT_S_BEFORE_WCKX3 = "S[A-Z]*WCK[FWYLIVMA]"`
   - Implementación: `rx_core`, `rx_s_before` en `search_toxins`.

### 1.2. Par hidrofóbico antes de la serina

Para refinar candidatos, se busca el mejor par consecutivo de aminoácidos hidrofóbicos antes de la S.

- Para cada par $(a_1,a_2)$ hidrofóbico con índices $(i,i+1)$ antes de $i_S$ se calcula un **score de hidrofobicidad**:
  $$\text{score}_{\text{pair}} = \text{KD}(a_1) + \text{KD}(a_2)$$
  donde $\text{KD}(\cdot)$ es el valor en la **escala de Kyte–Doolittle** `KYTE_DOOLITTLE`.
- Se selecciona el par con mayor `score_pair` (si hay empate, el primero).
- Implementación: `best_hydrophobic_pair_before_S(seq, iS)`.

### 1.3. Puntaje total de candidato (`score`)

Cada toxina candidata recibe un score heurístico entero:

- Contribuciones (hard‑coded en `search_toxins`):
  - `+2` presencia de motivo WCKX3 (implícito al pasar los filtros regex).
  - `+2` gap dentro del rango $[\text{gap_min}, \text{gap_max}]$.
  - `+2` al menos 6 C.
  - `+2` S inmediatamente después de la 5ª C.
  - `+1` si existe par hidrofóbico válido antes de S.

En pseudofórmula:
$$
\text{score} = 2 + 2 + 2 + 2 + \begin{cases}
1 & \text{si existe par hidrofóbico válido}\\
0 & \text{en otro caso}
\end{cases}
$$

Este `score` se usa para **ordenar candidatos** (ranking descendente) y seleccionar los mejores hits.

## 2. Distancias y geometría estructural

### 2.1. Distancias euclidianas en grafos

**Archivos:**
- `src/infrastructure/graphein/graphein_graph_adapter.py`
- `src/infrastructure/graph/graph_metrics.py`
- `src/infrastructure/exporters/export_service_v2.py`
- `src/domain/services/segmentation_service.py`

1. **Distancia entre átomos/CA**  
   Se usa la norma euclídea en 3D:
   $$d(\mathbf{x}, \mathbf{y}) = \lVert \mathbf{x} - \mathbf{y} \rVert_2 = \sqrt{(x_1-y_1)^2 + (x_2-y_2)^2 + (x_3-y_3)^2}$$
   - Implementación: `np.linalg.norm(coords_arr[i] - coords_arr[j])`, `np.linalg.norm(atom.coord - neighbor.coord)`.

2. **Promedio de distancia secuencial entre contactos**  
   Para cada residuo, se promedia la separación en número de residuo de sus vecinos en el grafo:
   $$\overline{\Delta\text{seq}}(i) = \frac{1}{N_i}\sum_{j\in N(i)} |\text{resnum}_j - \text{resnum}_i|$$
   - Implementación: `seq_distance_avg` en `graph_metrics.py` y exportadores.

3. **Proporción de contactos de largo alcance**  
   Dado un umbral de secuencia (p.ej. $>5$ residuos):
   $$\text{long\_contacts\_prop}(i) = \frac{\#\{j\in N(i): |\text{resnum}_j - \text{resnum}_i| > 5\}}{N_i}$$
   - Implementación: `long_contacts_prop` en `graph_metrics.py` y `segmentation_service.py`.

### 2.2. Análisis de hélices y orientación VSD

**Archivo:** `extractors/cortar_pdb.py`

1. **Selección de segmento PDB por residuo**  
   - Se recorta el PDB a un rango de residuos $[r_{\min}, r_{\max}]$ usando MDAnalysis:  
     $$\{\text{átomos} \mid \text{resid} \in [r_{\min}, r_{\max}]\}$$
   - Implementación: `PDBHandler.cut_pdb_by_residue_indices`.

2. **Clasificación de residuos orientados hacia el interior respecto a un eje Z artificial**  
   - Centro de masa global $\mathbf{c}$ de la proteína.  
   - Eje $z$ definido como:
     $$\mathbf{z}_{\text{axis}} = (c_x, c_y, 10^3), \quad \mathbf{z}_{\text{dir}} = \frac{\mathbf{z}_{\text{axis}} - \mathbf{c}}{\lVert \mathbf{z}_{\text{axis}} - \mathbf{c} \rVert}$$
   - Para cada residuo con centro de masa $\mathbf{r}$:
     - Vector al centro: $\mathbf{v} = \mathbf{c} - \mathbf{r}$.  
     - Proyección sobre el eje: $p = \mathbf{v} \cdot \mathbf{z}_{\text{dir}}$.  
     - Componente normal: $\mathbf{n} = \mathbf{v} - p\,\mathbf{z}_{\text{dir}}$.  
     - Distancia normal: $d_{\perp} = \lVert \mathbf{n} \rVert$.
   - Clasificación: residuo "orientado hacia el interior" si  
     $$d_{\perp} < \text{cutoff} \quad (\text{por defecto } 5\,\text{Å})$$
   - Implementación: `VSDAnalyzer.analyze_helices_orientation`.

## 3. Momento dipolar de la toxina

**Archivos:**
- `graphs/graph_analysis2D.py` (versión legacy, Nav17ToxinGraphAnalyzer)
- `src/interfaces/http/flask/controllers/v2/motif_dipoles_controller.py` (cálculo de ángulos y comparaciones)
- `src/infrastructure/graphein/dipole_adapter.py` (no se detalla aquí, usa la misma base conceptual)

### 3.1. Cálculo del momento dipolar (versión simplificada)

En `Nav17ToxinGraphAnalyzer.calculate_dipole_moment(structure)` se aproxima el momento dipolar a partir de cargas efectivas en el átomo CA de cada residuo.

1. **Centro de masa geométrico**  
   - Se calcula un centro de masa simplificado promediando las posiciones de CA:
     $$\mathbf{r}_{\text{CM}} = \frac{1}{N}\sum_{i=1}^N \mathbf{r}_i$$

2. **Asignación de cargas efectivas por residuo**  
   - Tabla `CHARGES` define una carga $q_i$ para cada aminoácido (ejemplo: Lys/Arg $+1$, Asp/Glu $-1$, etc.).

3. **Vector de momento dipolar**  
   - Se suma, sobre los residuos con CA conocido:
     $$\boldsymbol{\mu} = \sum_i q_i \big(\mathbf{r}_i - \mathbf{r}_{\text{CM}}\big)$$

4. **Magnitud y vector normalizado**  
   - Magnitud:
     $$\lVert \boldsymbol{\mu} \rVert = \sqrt{\mu_x^2 + \mu_y^2 + \mu_z^2}$$
   - Vector normalizado:
     $$\hat{\boldsymbol{\mu}} = \begin{cases}
        \boldsymbol{\mu} / \lVert \boldsymbol{\mu} \rVert & \text{si } \lVert \boldsymbol{\mu} \rVert > 0\\
        (0,0,0) & \text{en otro caso}
     \end{cases}$$

5. **Ángulo con el eje Z**  
   - Con $\mathbf{z} = (0,0,1)$:
     $$\cos \theta = \hat{\boldsymbol{\mu}} \cdot \mathbf{z} = \hat{\mu}_z$$
     $$\theta = \arccos(\cos\theta) \quad \text{(en radianes)}$$
   - Conversión a grados:  
     $$\theta_{\text{deg}} = \theta \cdot \frac{180}{\pi}$$

6. **Punto final para visualización**  
   - Se representa el vector en el espacio desde el centro de masa:  
     $$\mathbf{r}_{\text{end}} = \mathbf{r}_{\text{CM}} + 20\,\hat{\boldsymbol{\mu}}$$

### 3.2. Cálculo mejorado con PSF

En `Nav17ToxinGraphAnalyzer.calculate_dipole_moment_with_psf` se usa, si está disponible, el fichero PSF para obtener las cargas atómicas reales:

1. **Usando MDAnalysis**  
   - Se tiene un conjunto de átomos con posiciones $\mathbf{r}_i$ y cargas $q_i$.  
   - Centro de masa geométrico $\mathbf{r}_{\text{CM}}$ (de `protein.center_of_mass()`).  
   - Momento dipolar:
     $$\boldsymbol{\mu} = \sum_i q_i (\mathbf{r}_i - \mathbf{r}_{\text{CM}})$$

2. **Si no hay PSF**, se reusa la versión BioPython (`_extract_charges_positions_from_file`).

La normalización, ángulo con Z y punto final se calculan igual que en la sección 3.1.

### 3.3. Comparación de orientaciones (motif_dipoles)

En `motif_dipoles_controller.py` se comparan vectores de dipolo entre toxinas.

1. **Normalización de un vector**  
   Dado un vector $\mathbf{v} = (x,y,z)$:
   $$\lVert \mathbf{v} \rVert = \sqrt{x^2 + y^2 + z^2}$$
   $$\hat{\mathbf{v}} = \frac{1}{\lVert \mathbf{v} \rVert}(x,y,z)$$
   - Implementación: `_normalize_vector`.

2. **Ángulos con ejes X, Y, Z**  
   - Para cada eje unitario $\mathbf{e}_k$ con componente $v_k$ (X, Y, Z):
     $$\cos \alpha_k = \hat{\mathbf{v}} \cdot \mathbf{e}_k = v_k$$
     $$\alpha_k = \arccos(\cos \alpha_k)$$
   - Implementación: `_compute_axis_angles`.

3. **Ángulo entre vector de referencia y vector de toxina**  
   - Datos: $\hat{\mathbf{v}}_{\text{ref}}$ y $\hat{\mathbf{v}}_{\text{item}}$.  
   - Producto punto:
     $$\cos \theta = \hat{\mathbf{v}}_{\text{ref}} \cdot \hat{\mathbf{v}}_{\text{item}}$$
     $$\theta = \arccos(\cos \theta)$$

4. **Diferencias de ángulos por eje y norma L2**  
   - Sea $\alpha_k^{\text{ref}}$ y $\alpha_k^{\text{item}}$ el ángulo con el eje $k \in \{X,Y,Z\}$.  
   - Diferencias: $\Delta_k = \alpha_k^{\text{item}} - \alpha_k^{\text{ref}}$.  
   - Norma L2 sobre las diferencias:  
     $$\lVert \boldsymbol{\Delta} \rVert_2 = \sqrt{\Delta_X^2 + \Delta_Y^2 + \Delta_Z^2}$$
   - Implementación: suma de cuadrados en `_compute_orientation_metrics`.

5. **"Orientation score" en grados**  
   - En algunos puntos se usa la diferencia absoluta de ángulo con Z como score:  
     $$\text{orientation\_score\_deg} = |\theta_{Z}^{\text{item}} - \theta_{Z}^{\text{ref}}|$$
   - Se utiliza para ordenar toxinas por similitud de orientación respecto a la referencia.

## 4. Métricas de grafo (centralidades y propiedades globales)

**Archivo central:** `src/infrastructure/graph/graph_metrics.py`  
(Otros: `graphs/graph_analysis2D.py`, `src/domain/services/segmentation_service.py`, `src/interfaces/http/flask/presenters/graph_presenter.py`)

### 4.1. Centralidades clásicas (NetworkX)

Dado un grafo no dirigido $G=(V,E)$:

1. **Centralidad de grado**  
   $$C_D(v) = \frac{\deg(v)}{|V|-1}$$
   - Implementación: `nx.degree_centrality(G)`.

2. **Centralidad de intermediación (betweenness)**  
   $$C_B(v) = \sum_{s\ne v\ne t} \frac{\sigma_{st}(v)}{\sigma_{st}}$$
   donde $\sigma_{st}$ es el número de caminos geodésicos entre $s$ y $t$, y $\sigma_{st}(v)$ los que pasan por $v$.
   - Implementación: `nx.betweenness_centrality(G)`.

3. **Centralidad de cercanía (closeness)**  
   $$C_C(v) = \frac{|V|-1}{\sum_{u\in V\setminus\{v\}} d(v,u)}$$
   donde $d(v,u)$ es la longitud del camino más corto.
   - Implementación: `nx.closeness_centrality(G)`.

4. **Coeficiente de clustering local**  
   Para cada nodo $v$ con grado $k_v \ge 2$:
   $$C(v) = \frac{2\,T(v)}{k_v (k_v - 1)}$$
   donde $T(v)$ es el número de aristas entre los vecinos de $v$.
   - Implementación: `nx.clustering(G)`.

### 4.2. Propiedades globales del grafo

1. **Número de nodos y aristas**  
   $$N = |V|, \quad M = |E|$$

2. **Densidad del grafo**  
   $$\text{density} = \frac{2M}{N(N-1)}$$
   - Implementación: `nx.density(G)`.

3. **Coeficiente de clustering promedio**  
   $$\overline{C} = \frac{1}{N}\sum_{v\in V} C(v)$$  
   - Implementación: `nx.average_clustering(G)`.

4. **Métricas derivadas**  
   Se calculan resúmenes estadísticos (mínimo, máximo, media y top‑N residuos) para cada centralidad y para `seq_distance_avg` y `long_contacts_prop`.

## 5. Propiedades fisicoquímicas y farmacóforos

### 5.1. Hidrofobicidad y carga

**Archivos:** `graphs/graph_analysis2D.py`, `src/infrastructure/graph/graph_metrics.py`

Se usan diccionarios de propiedades:

- Hidrofobicidad $H(aa)$ basada en la escala de Kyte–Doolittle.
- Carga efectiva $Q(aa)$ (p.ej. Arg/Lys $+1$, Asp/Glu $-1$, His $+0.5$).

Para cada nodo (residuo) se guardan como atributos:

- `hydrophobicity = H(aa)`
- `charge = Q(aa)`

Estas propiedades participan en:

- Detección de parches positivos/hidrofóbicos (clustering espacial vía `pdist`).
- Identificación de farmacóforos específicos (`identify_pharmacophore_residues`).

### 5.2. Parches y motivos estructurales

**Archivo:** `graphs/graph_analysis2D.py`

1. **Parches positivos**  
   - Conjunto de nodos superficiales con carga positiva:  
     $$S_{+} = \{v : \text{charge}(v) > 0,\ \text{is\_surface}(v)=\text{True}\}$$
   - Si $|S_{+}| \ge 3$ y la mínima distancia euclídea entre ellos es $< 10$ Å, se marca `positive_patch = True`.

2. **Parches hidrofóbicos**  
   - Análogo con `hydrophobicity(v) > 1.0` y `is_surface(v) = True`.

3. **Nudo de cistina**  
   - Si el número de puentes disulfuro $\ge 3$ y hay al menos 6 residuos en puentes, se marca `cystine_knot = True`.

4. **Horquilla beta**  
   - Se verifica si hay al menos 4 residuos con `secondary_structure == "beta"`; se marca `beta_hairpin = True`.

## 6. UniProt y extracción de péptidos

### 6.1. Búsqueda en UniProt

**Archivo:** `extractors/uniprot.py`

- La función `fetch_accessions(query)` no introduce fórmulas numéricas complejas; realiza peticiones REST, pagina resultados y guarda la lista de accession numbers.
- El parseo XML (`parse_protein`) extrae campos textuales y features (peptides/chains) con posiciones `begin`, `end`, `position`.

### 6.2. Definición de péptidos a partir de UniProt

**Archivo:** `extractors/peptide_extractor.py`

1. **Rangos de péptido desde PDB (chains)**  
   - Se interpretan anotaciones tipo `"A=46-72"` como rango $[46,72]$ en la secuencia.
   - Si hay varios rangos PDB, se ordenan por longitud $(end-start)$ y se escoge el más largo.

2. **Rangos de péptido desde features UniProt (peptide/chain)**  
   - Cada feature tiene `begin`, `end`.  
   - Longitud del péptido:  
     $$L = \text{end} - \text{begin} + 1$$
   - Secuencia del péptido: `sequence[begin-1:end]`.

3. **Resolución de solapamientos**  
   - Si hay varios péptidos `protein_peptides`:
     - Se ordenan por `start_position`.  
     - Se testea si hay solapamiento ($\text{start}_i \le \text{end}_{i-1}$).  
     - Si hay solapamiento, se selecciona el péptido de mayor longitud $L$.
     - Si no hay solapamiento, se mantienen todos como cortes independientes, renombrados `(CUT i/N)`.

No hay fórmulas matemáticas nuevas más allá de diferencias y comparaciones de índices.

## 7. Normalización de IC50 y otros valores

**Archivos:**
- `src/domain/models/value_objects.py`
- `src/infrastructure/exporters/export_service_v2.py`
- `src/interfaces/http/flask/controllers/v2/motif_dipoles_controller.py`

### 7.1. Conversión de IC50 a nM

Sea un valor $v$ en una unidad $u \in \{\text{nM}, \mu\text{M}, \text{mM}\}$.  
Se normaliza a nM usando factores:

- $f(\text{nM}) = 1$
- $f(\mu\text{M}) = 10^3$
- $f(\text{mM}) = 10^6$

Entonces:
$$IC50_{\text{nM}} = v \cdot f(u)$$

### 7.2. Normalización lineal [0,1] de IC50

En `motif_dipoles_controller.py` se define una normalización min–max sobre los IC50 (en nM) de las toxinas con datos válidos:

- Dados $IC50_{\text{nM}}^{(i)}$ para $i=1..N$, se calcula:  
  $$\text{min} = \min_i IC50_{\text{nM}}^{(i)}, \quad \text{max} = \max_i IC50_{\text{nM}}^{(i)}$$
- Para cada valor:  
  $$\text{normalized\_ic50}^{(i)} = \frac{IC50_{\text{nM}}^{(i)} - \text{min}}{\text{max} - \text{min}}$$

Esta magnitud es la que se utiliza para:

- Ordenar toxinas por potencia relativa (menor IC50 normalizado = más potente).
- Alimentar paneles de visualización y comparaciones con predicciones de IA.

---
