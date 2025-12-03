<div align="center">

# Proyecto Toxinas – Análisis de Toxinas Nav1.7

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Backend-Flask-green.svg)](https://flask.palletsprojects.com/)
[![Graphein](https://img.shields.io/badge/Graphs-Graphein-red.svg)](https://github.com/a-r-j/graphein)
[![Mol*](https://img.shields.io/badge/Viewer-Mol*-%23ff8800.svg)](https://molstar.org/)

Análisis estructural de toxinas que modulan Nav1.7 mediante grafos moleculares, métricas de centralidad avanzadas y visualización 3D interactiva.

</div>

---

## 🧾 Resumen

La creciente necesidad de analgésicos selectivos no opioides ha consolidado a NaV1.7 como un blanco terapéutico clave en el tratamiento del dolor. No obstante, los flujos computacionales para la identificación y priorización de inhibidores peptídicos derivados de venenos se encuentran fragmentados y carecen de estandarización. Este trabajo presenta una plataforma bioinformática modular que automatiza el proceso completo de adquisición, normalización y análisis estructural de toxinas tipo *knottin*. El sistema integra filtrado farmacofórico basado en secuencia, descriptores topológicos obtenidos desde grafos moleculares y propiedades electrostáticas globales como la orientación del momento dipolar. Se procesaron 1308 péptidos maduros provenientes de UniProt, obteniéndose 44 candidatos compatibles con el modelo inhibitorio de NaV1.7. Los resultados evidencian que la plataforma permite analizar de forma consistente la arquitectura interna de estas toxinas y priorizar variantes con potencial bioactividad. Así, se entrega un marco escalable y reproducible para apoyar el descubrimiento racional de inhibidores peptídicos del canal NaV1.7.

---

## 🧬 Descripción General

Este proyecto (desarrollado en el repositorio [`Juaker1/Proyecto-toxinas`](https://github.com/Juaker1/Proyecto-toxinas)) implementa una **plataforma de análisis computacional** para péptidos tóxicos que interactúan con el canal de sodio **Nav1.7**. Combina:

- Construcción de **grafos moleculares** a partir de estructuras PDB (nivel residuo o atómico).
- Cálculo de **métricas de centralidad** y propiedades topológicas.
- **Visualización 3D** con Mol* + grafo interactivo en paralelo.
- Una **base de datos SQLite** con péptidos, familias, PDB/PSF y datos de actividad (IC50).
- Herramientas para **búsqueda de motivos NaSpTx**, análisis de dipolos y exportación avanzada por familias.

El backend sigue una arquitectura en capas (Clean Architecture / Ports & Adapters) documentada en `src/README.md`.

---

## ✨ Características Principales

- **Análisis de Grafos Moleculares**:
  - Construcción de grafos con `graphein` y `networkx` a partir de PDB.
  - Soporte para granularidad por **residuo (CA)** o **átomo**.
  - Distancia umbral y separación secuencial configurables.

- **Métricas de Centralidad y Propiedades**:
  - Degree, betweenness, closeness, eigenvector, clustering, etc.
  - Identificación de residuos clave y motivos estructurales.

- **Interfaz Web Interactiva (Flask + Mol*)**:
  - Visualización 3D con Mol* y panel de métricas.
  - Modos de visualización de **dipolos**, **puentes disulfuro** y combinados.
  - Filtro de toxinas NaSpTx basado en motivo **X1X2-S-WCKX3**.

- **Base de Datos Integrada (SQLite)**:
  - Tablas para proteínas, péptidos, familias y `Nav1_7_InhibitorPeptides`.
  - Almacenamiento de PDB/PSF, secuencias y metadatos.
  - Normalización automática de **IC50 a nM**.

- **Análisis de Relación Estructura-Actividad (SAR)**:
  - Unión entre métricas de grafo y actividad inhibidora.
  - Exportación por familias (μ-TRTX-H, μ-TRTX-C, κ-TRTX, etc.).

- **Pipeline Completo UniProt → DB → Artefactos**:
  - Búsqueda en UniProt, descarga XML, extracción de péptidos y recorte de PDB.
  - Inserción de dataset Nav1.7 curado y asociación con PDB/PSF locales.
  - Exportación de PDB filtrados, generación de PSF/PDB para análisis de dipolos.
  - Generación opcional de un JSON con anotaciones IA sobre los accesiones filtrados.

---

## 🏗 Arquitectura (Resumen)

El código de aplicación se encuentra bajo `src/` y sigue una arquitectura en capas:

- `src/domain/` – **Dominio**: entidades (toxina, familia, grafo, métricas), value objects, servicios puros.
- `src/application/` – **Casos de uso**: orquestan repositorios, adaptadores de grafos, exportadores y cálculo de dipolos.
- `src/infrastructure/` – **Infraestructura**: adaptadores SQLite, Graphein/NetworkX, export a Excel, preprocesado PDB, cálculo de dipolos.
- `src/interfaces/` – **Interfaces HTTP + Web**: aplicación Flask, controladores REST `/v2/*`, templates Jinja y JS/CSS (Mol*, viewer, paneles de métricas, filtros de toxinas, etc.).
- `src/utils/` – Utilidades genéricas (por ejemplo, generación de Excel).

Para más detalle, ver `src/README.md` y los README específicos de cada subcarpeta.

---

## 🧱 Requisitos y Entornos

El proyecto está pensado para ejecutarse en **Python 3.9** con un entorno de **conda** que incluye VMD y dependencias de análisis estructural.

### Opciones de entorno

#### 1. Entorno conda (recomendado)

Hay dos ficheros de entorno principales:

- `vmd.yml` → entorno completo para **Linux** (incluye VMD, PyMOL, MDAnalysis, etc.).
- `vmd_windows.yml` → entorno equivalente ajustado para **Windows**.

Creación del entorno en Linux:

```bash
conda env create -f vmd.yml
conda activate vmd
```

En Windows, usar `vmd_windows.yml` (nombre del entorno análogo) desde Anaconda Prompt/PowerShell.

#### 2. Instalación vía `requirements.txt`

Si ya tienes un entorno conda base configurado, puedes instalar las dependencias Python con:

```bash
pip install -r requirements.txt
```

Algunas características (como generación de PSF con VMD/psfgen) requieren que **VMD** esté instalado y accesible en el `PATH` del sistema.

---

## 🚀 Puesta en Marcha Rápida

### 1. Clonado del repositorio

```bash
git clone https://github.com/Juaker1/Proyecto-toxinas.git
cd Proyecto-toxinas
```

### 2. Crear y activar entorno (ejemplo Linux)

```bash
conda env create -f vmd.yml
conda activate vmd
```

### 3. Inicializar la base de datos

```bash
python database/create_db.py
```

Esto crea (o actualiza de forma idempotente) la base SQLite principal en `database/toxins.db`.

### 4. Ejecutar la API / interfaz web v2

La versión actual utiliza el entrypoint `run_v2.py`, que levanta la aplicación Flask con los endpoints `/v2/*` y la interfaz web actualizada:

```bash
python run_v2.py
```

Por defecto se expone en `http://localhost:5001` (configurable vía variables de entorno `HOST` y `PORT`).

---

## 🔁 Pipeline Completo UniProt → DB → Artefactos (`run_full_pipeline.py`)

El script `run_full_pipeline.py` ejecuta de forma orquestada todo el flujo de ingestión y preparación de datos:

1. **Crear/verificar base de datos**:
   - Llama a `database.create_db.create_database()` y garantiza que `toxins.db` exista.

2. **Buscar accesiones en UniProt**:
   - Usa `extractors.uniprot.UniProtPipeline.fetch_accessions(query)` para obtener accessions y un prefijo de nombre.

3. **Descarga XML + inserción de proteínas**:
   - `UniProtPipeline.fetch_all_async(...)` descarga datos UniProt (XML) y los inserta en la tabla `Proteins`.

4. **Extracción y corte de péptidos**:
   - `extractors.peptide_extractor.PeptideExtractor.process_xml_file(...)`:
     - Identifica péptidos/motivos relevantes, descarga PDB/AlphaFold si es necesario.
     - Recorta las estructuras a los rangos de residuos de interés.
     - Inserta entradas en la tabla `Peptides`.

5. **Insertar dataset Nav1.7 curado**:
   - `loaders.instert_Nav1_7.insert_peptides()` añade un conjunto curado de péptidos inhibidores Nav1.7 a `Nav1_7_InhibitorPeptides` (y tablas asociadas).

6. **Asociar blobs PDB/PSF a Nav1.7**:
   - `loaders.instert_Nav1_7_pdb_psf.PDBAndPSFInserter.process_all_peptides()` lee PDB/PSF desde `pdbs/` y `psfs/` y los vincula en la BD.

7. **Exportar PDBs de péptidos filtrados**:
   - `extractors.export_filtered_pdbs.export_filtered_pdbs(...)` escribe PDB recortados en `pdbs/filtered/` usando un filtro de motivo NaSpTx:
     - Parámetros principales: `gap_min`, `gap_max`, `require_pair`.

8. **Generar PSF/PDB para filtrados** (para análisis de dipolos):
   - `extractors.generate_filtered_psfs.FilteredPSFGenerator` recorre los péptidos filtrados y genera PSF/PDB en `pdbs/filtered_psfs/` mediante VMD/psfgen.
   - Respeta `--no-psf` para omitir esta etapa.

9. **Construir JSON de análisis IA** (opcional):
   - `tools.export_filtered_accessions_nav1_7.process_filtered_hits(...)` produce un JSON (`exports/filtered_accessions_nav1_7_analysis.json`) con anotaciones IA sobre los accessions filtrados.
   - Respeta `--no-ai` y `--overwrite`.

10. **Resumen de tiempos y contadores**:
    - Al final imprime un resumen con tiempos por etapa, número de accesiones recuperadas, péptidos insertados, PDB/PSF generados, etc.

### Uso desde la línea de comandos

Desde la raíz del proyecto:

```bash
conda activate vmd  # o tu entorno equivalente
python run_full_pipeline.py \
  --query "Nav1.7 toxin" \
  --gap-min 3 \
  --gap-max 6 \
  --require-pair \
  --overwrite
```

Parámetros soportados:

- `--query` (str): cadena de búsqueda para UniProt. Si se omite, se pedirá por consola.
- `--gap-min` (int): separación mínima entre los residuos del motivo (por defecto 3).
- `--gap-max` (int): separación máxima (por defecto 6).
- `--require-pair` (flag): exige la presencia de un par hidrofóbico en el motivo.
- `--no-psf` (flag): omite la generación de PSF/PDB para péptidos filtrados.
- `--no-ai` (flag): omite la generación del JSON de análisis IA.
- `--overwrite` (flag): fuerza la reescritura de artefactos ya existentes (PDB filtrados, PSF/PDB, JSON IA).

Este comando puede tardar varios minutos dependiendo de la conexión a UniProt, el número de péptidos y la disponibilidad de VMD/psfgen.

---

## 🌐 Interfaz Web y API

La aplicación Flask v2 se define en `src/interfaces/http/flask/app.py` y se ejecuta con `run_v2.py`.

### Inicio de la aplicación web

```bash
conda activate vmd
python run_v2.py
```

Accede en el navegador a:

- `http://localhost:5001` → Página principal (selección de péptido, parámetros de grafo, visualización 3D, panel de métricas).

### Controles principales en la UI

- **Fuente / péptido**: selección de toxinas o péptidos Nav1.7.
- **Granularidad**: `CA` (nivel residuo) o `Atom` (nivel atómico).
- **Distancia umbral**: típica entre 6–12 Å (recomendado 8–10 Å).
- **Separación de secuencia**: p.ej. 5 residuos (evita contactos triviales adyacentes).
- **Modos de visualización**: vectores dipolares, puentes disulfuro, ambos (en la vista de dipolos/familias).

La UI integra Mol* para el PDB y un visor de grafo 2D/3D basado en Plotly/JS.

### Endpoints principales (v2)

Los controladores Flask v2 exponen endpoints documentados en `src/interfaces/README.md`. Algunos ejemplos típicos:

- `/v2/proteins/<source>/<peptide_id>/graph` → cálculo del grafo y métricas.
- `/v2/export/residues/<source>/<peptide_id>` → exportación Excel/CSV de métricas de un péptido.
- `/v2/export/family/<family_name>` → exportación masiva por familia con IC50 normalizado.
- `/v2/dipole/<source>/<peptide_id>` → cálculo de dipolo y propiedades asociadas.
- `/v2/peptides` → listado de péptidos.
- `/v2/families` → listado de familias y péptidos por familia.
- `/v2/health` → endpoint de salud (usado en despliegues Docker/Nginx).

Consulta `tools/print_routes.py` para inspeccionar todas las rutas expuestas.

---

## 📊 Esquema de Base de Datos (Resumen)

La base de datos SQLite (típicamente `database/toxins.db`) incluye, entre otras, las tablas:

- `Proteins` – metadatos de proteínas UniProt.
- `Peptides` – péptidos individuales, secuencias y PDB recortados.
- `Nav1_7_InhibitorPeptides` – información de péptidos inhibidores Nav1.7:
  - `peptide_name`, `ic50_value`, `ic50_unit`, `classification`, etc.
- Tablas auxiliares para familias, alias, relaciones entre péptidos y estructuras, etc.

La normalización de IC50 a nM se realiza en consultas y/o vistas, p.ej.:

```sql
CASE 
    WHEN ic50_unit = 'μM' THEN ic50_value * 1000
    WHEN ic50_unit = 'mM' THEN ic50_value * 1000000
    ELSE ic50_value 
END AS normalized_ic50_nm
```

Los detalles del esquema y las relaciones se documentan en `database/README.md` y `docs/` (diagramas MER y de casos de uso).

---

## 🧪 Tests

El repositorio incluye tests unitarios y de integración bajo `tests/`.

Para ejecutar el conjunto de tests (requiere entorno configurado):

```bash
pytest
```

Hay también scripts en `tools/` que actúan como pruebas manuales/semi-automatizadas de componentes específicos (nuevas métricas, exportaciones, etc.).

---

## 🐛 Solución de Problemas Comunes

- **`ModuleNotFoundError: graphein`** → instalar dependencias:

  ```bash
  pip install -r requirements.txt
  ```

- **`SQLite database is locked`** → cerrar procesos que usen `toxins.db` y, si es necesario:

  ```bash
  python -c "import sqlite3; conn = sqlite3.connect('database/toxins.db'); conn.close()"
  ```

- **Problemas con VMD/psfgen (generación de PSF)** → verificar que VMD esté instalado y accesible en el `PATH`, y revisar mensajes de error de `run_full_pipeline.py` en la sección PSF.

- **La interfaz web no carga**:
  - Confirmar que `python run_v2.py` está en ejecución.
  - Verificar que no haya conflictos de puertos.
  - Revisar la consola del navegador (F12) y los logs de Flask.

- **Errores Unicode en nombres de archivo (μ, κ, etc.)**:
  - El sistema convierte automáticamente estos caracteres a `mu`, `kappa`, etc., pero si ves errores, revisa rutas y nombres de familia utilizados.

---

## 📚 Referencias Científicas (Selección)

- Graphein – *"Graphein: a Python library for geometric deep learning and network analysis on biomolecular structures"*.
- Mol* Viewer – *"Mol* Viewer: modern web app for 3D visualization and analysis of large biomolecular structures"*.
- NetworkX – *"Exploring network structure, dynamics, and function using NetworkX"*.
- Nav1.7 – *"Voltage-gated sodium channel Nav1.7 and pain: from gene to pharmacology"*.
- Farmacóforo NaSpTx – motivo **X1X2-S-WCKX3**, basado en Sharma et al., 2025 (FEBS Letters): patrón de residuos críticos que definen la actividad inhibidora sobre Nav1.7.

---


