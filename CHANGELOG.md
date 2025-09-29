# Changelog
Todas las modificaciones significativas del proyecto se documentan aquí.  
El historial se organiza en “versiones” retrospectivas según hitos de desarrollo.

## [1.7.1] – 2025-09-29
### Added
- Script maestro run_full_pipeline.py que ejecuta de forma interactiva y secuencial todo el pipeline (UniProt → Proteins → Peptides → Nav1.7 curados → blobs PDB/PSF).
- Integración automática de los loaders: inserción de péptidos Nav1.7 y posterior carga de blobs PDB/PSF en la misma ejecución.

### Changed
- Simplificación del flujo: se eliminó el uso de parámetros/flags CLI; ahora el pipeline solicita solo la query por consola.
- Limpieza de salida estándar: se redujeron prints informativos, dejando solo mensajes de error y confirmaciones clave (p.ej. cantidad de péptidos guardados).

---

## [1.7.0] – 2025-09-24 → 2025-09-26
### Added
- Página de filtrado de toxinas almacenadas en la base de datos según criterios del paper de toxinas Nav1.7.
- READMEs en las carpetas y archivos clave del proyecto para facilitar la comprensión y despliegue.

### Changed 
- Nomenclatura y textos de UI unificados(familias, codigos de peptidos) para mejorar consistencia en vistas y exportes.
---

## [1.6.1] – 2025-08-06
### Fixed
- Ajustes en el manejo y generación de archivos XLSX(Nombres de hojas/archivos, normalización de columnas).
- Eliminación de archivos innecesarios del repositorio.

---

## [1.6.0] – 2025-08-04
### Added
- Página para visualizar y comparar dipolos de **familias completas** de toxinas Nav1.7, mostrando cálculos y datos agregados.

---
## [1.5.1] - 2025 - 07 - 26
### Changed
- Sanitización y transliteración de nombres (p. ej., letras griegas β→beta) para archivos y hojas Excel.
- Homogeneización de columnas y oden por número de residuos en todas las exportaciones.

### Fixed
- Corrección de separadores decimales/locale en XLSX y rutas Windows con espacios.
--- 
## [1.5.0] – 2025-07-22 → 2025-07-24
### Added 
- Agrupamiento y segmentación atómica para toxinas individuales y familias.
- Exportación de resultados del agrupamiento en formato XLSX.
- Validaciones y gormateo consistente a 4 decimales en exporatciones nuevas.

### Fixed
- Ajuste menores en etiquetas y orden de columnas para mantener homogeneidad entre hojas.
---


## [1.4.0] – 2025-06-21 → 2025-07-14
### Added
- Inclusión de archivos **.PSF** para las toxinas Nav1.7 en la base de datos.
- Cálculo del ángulo del dipolo respecto al eje Z.
- Visualización mejorada del muestreo de dipolos de toxinas Nav1.7.
- Respuestas JSON de error uniformes en endpoints de exportacion(jsonify) y trazas detalladas.

### Changed
- Actualización del frontend para usar endpoints XLSX y nombres de archivo con extensión .xlsx.
- Actualización del CDN de Plotly a versión explícita 2.x y alineación de trazas/layout para evitar “Unrecognized subplot: xy”.

### Fixed
- Problemas en la visualización de grafos de toxinas individuales.
- Correcciones en el sistema de descarga de archivos XLSX:
- - Content-Type y Content-Disposition correctos para XLSX.
- - Importación faltante de jsonify y functools.partial.
- - Manejo de estructura no cargada en Mol*.

---

## [1.3.1] - 2025-06-21 → 2025-06-23

### Changed
- Estabilidad de centralidades en grafos parcialmente desconectados (enmascarado de NaN y documentación de supuestos).
- Renumeración coherente post-corte en PDBs con inserciones/gaps.
## Fixed
- Tolerancias de distancia en detección de puentes S–S para PDBs con pequeñas desviaciones. 

---
## [1.3.0] – 2025-06-14 → 2025-06-20
### Added
- Comparación de métricas de grafos entre toxinas Nav1.7 y una WT simulada.
- Mejoras en el sistema de descargas e implementación de notificaciones *Toast*.
- Exportacion en XLSX con lógica completa:
- - Toxinas individuales: una hoja por archivo, nombre de hoja limpio, mismas columnas que CSV, IC50_nM en su propia columna.
- - Familias: un libro por dataset con una hoja por toxina (peptide_code/toxina_id normalizado), columnas homogéneas, orden por número de residuo ascendente.
- - Comparación WT: un libro con hojas para WT, referencia y una hoja resumen de diferencias topológicas.

### Changed

- Migración del formato de exportación de CSV a XLSX (pandas + openpyxl).
- Frontend: URLs actualizadas para apuntar a los nuevos endpoints XLSX y nombres de descarga consistentes.

### Removed
- Endpoints y soporte de exportación CSV: /export_residues_csv, /export_family_csv, /export_wt_comparison.

---
## [1.2.1] - 2025-06-11 → 2025-06-12

### Fixed 
- Condiciones de carrera en inicialización de py3Dmol/Mol* al cargar estructuras pesadas.
- Mensajes de error más claro cuando faltan PSF para cálculo de dipolo preciso.  

---
## [1.2.0] – 2025-06-10 
### Added
- Visualización del **dipolo** de la toxina mediante carga de archivo PSF y render en **py3Dmol**.
- Interfaz con vista dual: estructura(izquierda) y grafo(Derecha) de forma simultanea.
- Actualización de la visualización de proteínas y grafos.

---

## [1.1.0] – 2025-06-04 → 2025-06-07
### Added
- Cálculo de métricas de grafos y exportación de residuos en CSV.
- Obtención de datos por familia de toxinas con cálculos y descarga de CSV.
### Fixed
- Problema de carga de proteína en la primera visualización.
- Corrección de rutas en la carga inicial de la página.

---

## [1.0.0] – 2025-05-22 → 2025-05-26
### Added
- **Aplicación Flask** con visualización de:
  - Estructura proteica en **Mol\***.
  - Grafo 3D de la proteína, con selección de átomos y CA.
- Vistas coordinadas para explorar estructura y topologia.

---

## [0.2.0] – 2025-05-05 → 2025-05-21
### Added
- Creación de grafos a partir de archivos PDB de toxinas.
- Extracción de información relevante de grafos.
- Visualización 3D de los grafos para exploración interactiva.

---

## [0.1.1] – 2025-04-26
### Added
- Nueva tabla **Nav1.7InhibitorPeptides** en la base de datos.
- Incorporación de toxinas Nav1.7 con sus respectivos archivos PDB.

---

## [0.1.0] – 2025-04-17 → 2025-04-26
### Added
- **Primera base de datos** del proyecto.
- Pipeline para:
  - Obtención de proteínas/toxinas desde UniProt.
  - Recolección de *accession numbers* y guardado en JSON según la query.
  - Descarga paralela de datos XML y almacenamiento con nombre de query.
  - Filtrado de proteínas incompletas y guardado en la base de datos.
  - Filtrado por flag de péptido y descarga de archivos PDB desde RCSB PDB o AlphaFold, con corte para respetar el *peptide length*.
