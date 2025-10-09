# Changelog
Todas las modificaciones significativas del proyecto se documentan aquí.  
El historial se organiza en "versiones" retrospectivas según hitos de desarrollo.

## [1.9.0] – 2025-10-09
### Added
- Rediseño completo del frontend con sistema de diseño profesional unificado:
  - Sistema de variables CSS centralizadas (design-system.css) con escalas de color, espaciado, tipografía, sombras y transiciones.
  - Componentes reutilizables (buttons, cards, forms, tables, alerts, badges) con diseño consistente.
  - Navbar unificada responsive con toggle móvil y navegación coherente entre páginas.
  - Iconografía con Font Awesome 6.4.0 en lugar de emojis para apariencia profesional.
- Separación de contenedores en vista del visualizador:
  - "Análisis Detallado del Grafo" y "Exportar Datos Completos" como secciones independientes con toggles individuales.
  - Botones de toggle lado a lado para acceso directo sin necesidad de scroll extenso.
  - Sistema de exclusión mutua: solo una sección visible a la vez para UI limpia.
- Auto-scroll en visualización de familias:
  - Scroll automático y suave hacia la sección de visualización al seleccionar "Visualizar los dipolos de las familias".
  - Offset configurable (100px) para mejor posicionamiento visual.
- Mejoras en página de filtros de toxinas:
  - Checkbox personalizado funcional con animaciones checkPop y hover effects.
  - Click unificado: funciona tanto en el cuadrado del checkbox como en el texto del label.
  - Estados visuales claros con transiciones suaves y feedback inmediato.
  - Mejoras en botones de exportación y toggle de tabla con gradientes y micro-interacciones.

### Changed
- Animaciones de botones mejoradas:
  - Reemplazo de expansión circular por sliding horizontal para llenar botones completamente.
  - Hover effects consistentes en todos los botones con translateY y box-shadow.
  - Estados disabled con opacidad apropiada y cursor not-allowed.
- Estructura HTML del apartado "Exportar Datos Completos":
  - Uso de componentes card con card-header y card-body para consistencia visual.
  - Selectores y controles con clases control-group y control-label estandarizadas.
  - Tooltips con iconos Font Awesome y posicionamiento absoluto mejorado.
  - Secciones de familia y comparación WT con diseño profesional y spacing uniforme.
- Sistema de paginación de tabla en filtros:
  - Paginación client-side (10 filas por página) sin cambios en backend.
  - Controles de navegación con estados disabled apropiados.

### Fixed
- Funcionalidad del checkbox de pareja hidrofóbica en página de filtros:
  - Eliminación de atributo for conflictivo en label HTML.
  - Event listeners unificados para evitar doble-triggering.
  - Sincronización correcta entre estado visual (CSS) y estado lógico (JavaScript).
  - Inicialización adecuada del estado visual en page load.
  - Restauración de estructura HTML requerida por JavaScript (.button-text span).
  - Preservación de IDs y clases necesarias para event listeners.
  - Compatibilidad mantenida con export_feedback.js y graph_viewer.js.
- Problemas de UI/UX y redundancias:
  - Eliminación de botones duplicados en análisis del visualizador.
  - Remoción de símbolos extraños (?) en labels de toggle.
  - Corrección de posicionamiento de botones (dipolo aparecía sobre navbar).
  - Limpieza de console.log innecesarios en producción.

### Removed
- Emojis en interfaz de usuario reemplazados por Font Awesome icons.
- Código duplicado de manejo de checkbox en toxin_filter.js.

---

## [1.8.0] – 2025-10-03
Todas las modificaciones significativas del proyecto se documentan aquí.  
El historial se organiza en “versiones” retrospectivas según hitos de desarrollo.

## [1.8.0] – 2025-10-03
### Added
- Generación masiva de PSF/PDB para péptidos filtrados:
  - Nuevo script tools/generate_filtered_psfs.py que crea outputs en tools/filtered/ nombrados por accession_number.
  - Ejecución de VMD por subproceso, captura de logs por péptido en tools/filtered/logs y reintento automático con tail del log.
- Mejoras en psfgen (resources/psf_gen.tcl):
  - Detección de DISU robusta (medida de distancias SG-SG con función propia), y patch DISU forzado al segmento único.
  - Sanitización previa del PDB (elimina NH2, PCA, ACE, NME), renumeración de resid y segid uniforme, alias de residuos frecuentes (HIS→HSE/HSD, MSE→MET, SEC/CYX→CYS).
  - Carga única de topologías por sesión (evita duplicados).
- Integración Flask para comparación de dipolos:
  - Nuevo blueprint v2 con endpoints:
    - GET /v2/motif_dipoles/reference: retorna PDB y dipolo de la referencia μ-TRTX-Cg4a.
    - GET /v2/motif_dipoles/page: pagina toxinas filtradas y calcula/retorna su dipolo desde tools/filtered.
- UI de comparación integrada en la página de filtrado:
  - Sección superior fija con el dipolo de la referencia μ-TRTX-Cg4a.
  - Grid paginado de toxinas filtradas (6 por página, 3 por fila) con visualizador 3D.
  - Visualización con ejes XYZ, flecha de dipolo y leyenda (magnitud en Debye y ángulo respecto a Z).
  - Nuevo JS estático motif_dipoles.js y estilos de grid/alturas para py3Dmol.

### Changed
- Panel de filtros movido debajo de la nueva sección de visualización.


---

## [1.7.2] – 2025-10-02
### Added
- Cálculo y exposición del par hidrofóbico óptimo previo a la S posterior al 5.º C (campos: hydrophobic_pair, hydrophobic_pair_score, hydrophobic_pair_start, iHP1, iHP2).
- Nuevas columnas en la tabla de filtrado: Par Hidrofóbico y Score Par (incluye resaltado visual en la secuencia).
- Botón para colapsar/expandir la lista de resultados (mejorando la usabilidad en listas largas).

---
 
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
