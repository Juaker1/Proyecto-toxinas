# Changelog
Todas las modificaciones significativas del proyecto se documentan aquí.  
El historial se organiza en "versiones" retrospectivas según hitos de desarrollo.

## [2.8.0] – 2025-11-13

### Added
- Glosario interactivo de residuos clave del motivo farmacofórico en la página de filtros:
  - 8 residuos con código de color específico: Cisteína ICK estructural (rojo), 5.ª Cisteína (morado), 6.ª Cisteína del motivo WCK (verde), Serina (azul), Triptófano (naranja), Lisina (amarillo), Par Hidrofóbico X₁X₂ (café), X₃ Hidrofóbico (verde lima).
  - Diseño de tarjetas horizontales con badges de colores (48×48px) y formato "Nombre — Descripción".
  - Funcionalidad de colapsar/expandir con botón toggle y animación de chevron.
  - Fondo con color de botón activo (#3B82F6) para consistencia visual con el sistema de diseño.
- Resaltado automático de cisteínas en secuencias de la tabla de resultados:
  - Sistema de conteo inteligente que identifica todas las cisteínas (C) en la secuencia.
  - Coloreado diferenciado: 5.ª cisteína en morado, 6.ª en verde (parte del motivo WCK), resto en rojo (estructura ICK).
  - Overlay de colores de motivo farmacofórico sobre las cisteínas estructurales.
- Visualización mejorada de residuos en secuencias:
  - Badges con fondo de color sólido en lugar de solo texto coloreado.
  - Contraste optimizado con pares de color de fondo/texto para cada tipo de residuo.
  - Estilo consistente con padding, border-radius y box-shadow.

### Changed
- Actualización del apartado "Motivo de Búsqueda" a "Motivo Farmacofórico":
  - Patrón actualizado a X₁X₂–S–WCK–X₃ con explicación científica completa.
  - Referencia a estructura tipo NaSpTx1 del marco ICK con descripción de cada componente del motivo.
- Enlaces a artículo científico actualizados en ambas páginas (Familias y Filtros):
  - Nueva URL: https://febs.onlinelibrary.wiley.com/doi/epdf/10.1002/1873-3468.70036
- Tabla de resultados optimizada:
  - Eliminación de la columna "Score" (no relevante tras cambios en backend).
  - Contenedor de secuencias con scroll horizontal para evitar desbordamiento.
  - Scrollbar personalizado (6px de altura, azul #3B82F6) para mejor UX.
  - Mejora de contraste en celdas de secuencia con fondo degradado sutil.
- Glosario muestra/oculta automáticamente según presencia de resultados en la tabla.
- Título de sección actualizado: "Dipolos de Toxinas Filtradas" → "Dipolos de Toxinas Filtradas de UniProt" para mayor claridad del origen de datos.
- Sistema de referencia de dipolos completamente rediseñado:
  - Eliminación total de la proteína WT (hwt4_Hh2a) como referencia.
  - Selector de referencia ahora usa automáticamente la primera toxina disponible de Nav1_7_InhibitorPeptides (ordenada por IC50 normalizado).
  - Secuencias de referencias obtenidas correctamente desde el campo `sequence` de la tabla Nav1_7_InhibitorPeptides.

### Removed
- Botones de exportación del navbar en las páginas de Filtros y Visualizador para simplificar la interfaz.
- Proteína WT (hwt4_Hh2a) completamente removida del sistema:
  - Eliminada de la lista de opciones de referencia en el selector.
  - Removida la opción hardcodeada en el HTML del selector de referencia.
  - Eliminados todos los fallbacks y lógica especial para WT en el frontend y backend.

### Fixed
- Problema de visibilidad en diseños previos del glosario (texto gris sobre fondo claro).
- Overflow horizontal en secuencias largas de la tabla de resultados.
- Cisteínas sin marcar o con colores incorrectos en la visualización de secuencias.
- Lógica de resaltado de residuos ahora procesa la secuencia completa en dos pasadas:
  - Primera pasada: identifica y cuenta todas las cisteínas, asigna tipos (C5/C6/CICK).
  - Segunda pasada: overlay de residuos del motivo farmacofórico sobre la estructura base.

### Technical Details
- Archivos modificados:
  - `templates/dipole_families.html`: actualización de enlace científico (línea ~80).
  - `templates/toxin_filter.html`: 
    * Sección "Motivo Farmacofórico" reescrita (líneas 66-85).
    * Estructura completa del glosario con collapse (líneas 291-362).
    * Tabla con 9 columnas (Score removido), secuencias en contenedor scrolleable.
    * Selector de referencia sin opción WT hardcodeada (se puebla dinámicamente desde JS).
    * Eliminado bloque navbar_actions con botón de exportar.
  - `templates/viewer.html`:
    * Eliminado bloque navbar_actions con botón de exportar.
  - `static/css/filter-page.css`:
    * Estilos del glosario completo (.residue-glossary-full, .glossary-header-full, .glossary-grid-full).
    * Cards horizontales con badges (.glossary-card, .residue-badge-full, .residue-text).
    * Contenedor de secuencias con scroll personalizado (.sequence-container).
    * Mejoras de contraste en celdas de tabla (.table-cell-mono).
  - `static/js/toxin_filter.js`:
    * Event listener para toggle del glosario (líneas 23-30).
    * Función paintRows() actualizada a 9 columnas.
    * Función highlightSequence() completamente reescrita (líneas 253-305):
      - Algoritmo de doble pasada para cisteínas + motivo.
      - Map de colores con 9 tipos: C5, C6, CICK, iS, iW, iK, iX3, iHP1, iHP2.
      - Retorna spans con estilos inline (background-color, color, padding, border-radius).
    * Lógica para mostrar/ocultar glosario basada en resultados.
  - `static/js/motif_dipoles.js`:
    * Variable selectedReferenceCode inicializada en null en lugar de 'WT'.
    * Eliminado caso especial para WT en formatReferenceOption().
    * Eliminadas todas las condiciones que verificaban si no es 'WT' (6 ocurrencias).
    * Eliminados todos los fallbacks a 'WT' (3 ocurrencias).
    * Función loadReference() actualizada para usar primera opción disponible si no hay código seleccionado.
    * Agregada validación en botón de descarga para verificar existencia de referencia seleccionada.
  - `controllers/v2/motif_dipoles_controller.py`:
    * Función _get_reference_options() ya no incluye opción WT en la lista.
    * Función _get_reference_data() completamente reescrita:
      - Eliminada lógica de carga desde filesystem para WT.
      - Si no se especifica código, usa primera opción disponible de Nav1_7_InhibitorPeptides.
      - Siempre carga referencias desde base de datos.
    * Función _load_reference_from_db() corregida para obtener secuencia desde Nav1_7_InhibitorPeptides.sequence (antes buscaba en Peptides.sequence).

---

## [2.7.2] – 2025-11-10

### Added

- Dos nuevas métricas de centralidad para análisis de grafos moleculares:
  - Distancia Secuencial Promedio: identifica residuos con conexiones locales vs. globales.
  - Proporción de Contactos Largos: clasifica residuos por su rol estructural (núcleo vs. superficie).
- Formato de nombres de residuos extendido para granularidad atómica: `A:TRP:21:N` (cadena:residuo:número:átomo).

### Changed

- Visualizador 3D de grafos: etiquetas de nodos ahora muestran formato completo con átomos cuando aplica.
- Panel de información de nodos: mantiene funcionalidad de selección después de usar reset o doble-click.

### Fixed

- Cálculo de métricas de centralidad: incluye las nuevas métricas en el pipeline completo (cálculo → API → UI).
- Top 5 residuos: ahora muestra correctamente las dos nuevas métricas en la interfaz.

### Technical Details

- Archivos modificados:
  - `src/infrastructure/graph/graph_metrics.py`: cálculo de `seq_distance_avg` y `long_contacts_prop`.
  - `src/infrastructure/graphein/graphein_graph_adapter.py`: inclusión de nuevas métricas en respuesta API.
  - `src/interfaces/http/flask/presenters/graph_presenter.py`: formateo de métricas para frontend.
  - `src/infrastructure/graphein/graph_visualizer_adapter.py`: etiquetas de nodos con formato atómico.
  - `src/interfaces/http/flask/web/static/js/molstar_graph_renderer.js`: reset de panel sin perder estructura.
- Nuevas métricas disponibles en exportaciones Excel y visualización Top 5.
- Compatibilidad mantenida con granularidad de residuos (sin átomos).

## [2.7.1] – 2025-11-04

### Added
- Orquestación completa en `run_full_pipeline.py` de los procesos offline necesarios para la web:
  - Exportación de PDBs filtrados.
  - Generación de PSF/PDB para los PDBs filtrados (vía VMD/Tcl).
  - Producción del JSON de análisis por IA para accesiones filtradas.
- Nuevos flags de CLI para control fino del pipeline:
  - `--no-psf` y `--no-ai` para omitir etapas específicas.
  - `--overwrite` para forzar la regeneración de artefactos existentes.
  - Parámetros de filtros/motivos: `--query`, `--gap-min`, `--gap-max`, `--require-pair`.

### Changed
- Ejecución idempotente por defecto: se omiten etapas si los artefactos finales ya existen; `--overwrite` fuerza su recreación.
- Resumen final con tiempos por etapa, recuentos y rutas de salida para trazabilidad del proceso.

### Technical Details
- Archivos implicados:
  - `run_full_pipeline.py` (orquestador con argparse, timings y control de etapas).
  - Reutiliza: `extractors/export_filtered_pdbs.py`, `extractors/generate_filtered_psfs.py`, `tools/export_filtered_accessions_nav1_7.py`.
- Salidas estandarizadas:
  - JSON IA: `exports/filtered_accessions_nav1_7_analysis.json`.
  - Log/timings: `exports/process_log.txt`.
- Reglas de omisión:
  - `--no-psf` omite la generación de PSF/PDB.
  - `--no-ai` omite la generación del JSON de IA.
  - Exportación de PDBs filtrados respeta `--overwrite` (no reescribe si ya existen, salvo que se indique).
- Retrocompatibilidad: no cambia APIs ni rutas usadas por la aplicación web; es una mejora de tooling offline.

## [2.7.0] – 2025-11-03

### Added
- Navbar como componente reutilizable:
  - Nuevo parcial `templates/partials/navbar.html` con “slot” para acciones por página (`navbar_actions`).
- Página de Familias: aviso guiado que indica cómo visualizar los dipolos; aparece al seleccionar una familia, se oculta al visualizar y reaparece al cambiar la selección.
- Leyenda global de flechas en la visualización de Familias (arriba del grid):
  - Colores: Dipolo=rojo, Eje X=verde, Eje Y=naranja, Eje Z=azul.
- Flechas de ejes X e Y añadidas en cada visualizador (además del eje Z existente).
- Controles “Resaltar” por péptido en las tablas (original y modificados): permiten marcar visualizaciones 3D específicas sin abandonar la tabla.

### Changed
- Orden del menú actualizado en todas las vistas: Inicio → Familias → Visualizador → Filtros.
- Plantillas `home.html`, `viewer.html`, `dipole_families.html` y `toxin_filter.html` ahora incluyen el parcial y, cuando aplica, inyectan sus acciones con `navbar_actions`.
- La marca (logo/título) enlaza a Inicio de forma consistente.
- Página de Familias (UX):
  - Mayor contraste en “Familia de Toxinas” y “Familia seleccionada”.
  - Reposicionamiento del aviso junto al cartel de “Familia seleccionada” con iconos claros.
  - Más espacio vertical entre selector/botón, avisos y la lista de péptidos.
  - Resaltado de cambios en secuencias: ahora se ve claramente (fondo blanco + borde acentuado) sobre el contenedor amarillo y aplica a todas las familias; si no hay tokens en el código del péptido, se usa un fallback por diferencias contra el original.
  - Visualización 3D por familia: el péptido original (código sin "_") aparece primero en la grilla; el resto se ordena alfabéticamente por código.
- En las tarjetas de visualización, se reemplaza “Componentes” por los ángulos respecto a los ejes X/Y/Z (en grados) junto a la Magnitud.
- Estilos más visibles para IC50 (chip) y para el control “Resaltar” (pill con borde/fondo y negrita).
- Color de resaltado de la tarjeta 3D cambiado a azul (borde/halo) para combinar con la paleta existente.
- Al activar “Resaltar” ya no se hace auto‑scroll a la visualización (permite marcar varios a la vez).

### Removed
- Página de Familias: se eliminaron las tarjetas/estadísticas finales (magnitud, orientación, componentes) para simplificar la UI y evitar información redundante.
- Página de Familias: se eliminaron los botones de exportación (acción del navbar y “Exportar Datos” en el header de la visualización).

### Fixed
- Eliminación de marcado duplicado del navbar entre plantillas, evitando desincronizaciones de iconos/orden/estados.
- Estado activo y comportamiento móvil consistentes en todas las páginas al compartir un único marcado.
- Señal de ayuda en Familias: ahora se oculta al iniciar la visualización y solo reaparece al cambiar de familia.

### Technical Details
- Integración vía `{% include 'partials/navbar.html' %}` y bloque inline `{% set navbar_actions %}…{% endset %}` cuando se requieren botones específicos por página.
- Sin cambios en `static/js/navbar.js` ni en `static/css/navbar.css`; el comportamiento existente aplica al nuevo parcial.
- Familias:
  - `templates/dipole_families.html`: se removió la sección de estadísticas; se mantiene solo el área de visualización.
  - `templates/dipole_families.html`: se quitaron las acciones de exportar del navbar y el botón “Exportar Datos” del header; se añadió la leyenda `.dipole-legend` sobre el área de visualización; columnas “Resaltar” agregadas a las tablas.
  - `static/js/dipole_family_analysis.js`: `displayFamilyStats()` no‑op; ocultado de `statisticsArea`; orden "original primero"; resaltado de secuencias (`parseModificationsFromCode()` + `highlightDiffs()`); `computeAxisAngles()` para X/Y/Z; `addDipoleArrowToViewer()` dibuja X (verde), Y (naranja), Z (azul) y dipolo (rojo); nuevo vínculo tabla↔tarjetas con `cardIndexByCode`; controles “Resaltar” activan `.highlighted-card` y se eliminó el auto‑scroll al togglear.
  - `static/css/families-page.css` y `.min.css`: estilos de `.seq-change` (alto contraste), `.dipole-legend`, chips de `IC50`, pills de `Resaltar` (accent azul) y `.highlighted-card` con borde/halo azul.

---

## [2.6.1] – 2025-11-03

### Added
- Overlay de carga con spinner para la tarjeta de Gráficos en la página de filtros:
  - Se muestra al inicializar y actualizar los gráficos; se oculta automáticamente al finalizar.
- Script de seguridad para sincronizar el texto/estado de los botones de toggle (“Mostrar/Ocultar …”) con la visibilidad real de las secciones (fallback si se carga una build minificada antigua).
- Estilo responsive tipo “chip” para los tabs de la tabla de resultados (Todos / Con Nav1.7 / …), con estado activo resaltado y mejor distribución en pantallas pequeñas.

### Changed
- Navbar: unificación de iconos en todas las plantillas para coherencia visual:
  - “Visualizador” → `fas fa-microscope`
  - “Familias” → `fas fa-flask`
- Navbar: se componentiza el marcado en `templates/partials/navbar.html` y se actualiza el orden de los ítems a: Inicio → Familias → Visualizador → Filtros. Las plantillas `home.html`, `viewer.html`, `dipole_families.html` y `toxin_filter.html` ahora incluyen el parcial y, cuando aplica, inyectan sus acciones con `navbar_actions`.
- `toxin_filter.html`: carga del script `motif_dipoles` vía `asset_path(...)` para respetar el modo minificado y mantener consistencia con el resto de assets.
- Paginación de la tabla de resultados: flechas reemplazadas por Font Awesome (`fa-angle-left` / `fa-angle-right`) para uniformidad con el resto de iconografía.

### Fixed
- Botones de mostrar/ocultar: ahora cambian correctamente a “Ocultar visualizaciones 3D” y “Ocultar gráficos” tras la primera carga y mantienen el estado sincronizado (aria-pressed y clase `.active`).
- Actualización de gráficos envuelta en overlay para evitar parpadeos y dar feedback de estado durante cargas pesadas.

## [2.6.0] – 2025-11-02

### Added
- Carga perezosa de gráficos en la página de filtros mediante IntersectionObserver (se renderizan solo al ser visibles).
- Web Worker dedicado (motif_dipoles.worker.js) para construir datasets de gráficos fuera del hilo principal.
- Capa de caché por parámetros (gap_min, gap_max, require_pair, referencia) para el agregado de items.
- Loader on‑demand de 3Dmol (load3DmolOnce) y bootstrap diferido de la vista (requestIdleCallback) para no bloquear el hilo principal.
- Placeholder temprano de la leyenda (.dipole-legend) para adelantar el LCP (texto visible inmediato).
- Minificado de CSS de first‑party: se extendió `tools/minify_assets.py` para generar `.min.css` en `static/css` (p. ej. `viewer.min.css`).

### Changed
- Actualizaciones de gráficos diferidas con scheduleChartsUpdate usando requestIdleCallback (fallback setTimeout).
- Carga on‑demand de Plotly (loadPlotlyOnce) para evitar coste inicial innecesario.
- Render con Plotly.react en lugar de recrear gráficos completos, reutilizando instancias.
- Reemplazo de llamadas directas a updateChartsWithAllItems por scheduleChartsUpdate en cambios de filtros, referencia y paginación.
- `toxin_filter.html`: se eliminan los scripts de 3Dmol y Plotly (ahora se inyectan bajo demanda desde JS).
- `motif_dipoles.js`: los viewers 3D esperan a 3Dmol (await load3DmolOnce) en loadReference/renderPage/reRenderCurrentPage; reRenderCurrentPage pasa a async.
- `toxin_filter.html`: hojas CSS no críticas se cargan como no‑bloqueantes (media="print" + onload + <noscript>) y se reserva altura mínima de contenedores para estabilidad (CLS≈0).
- `toxin_filter.html`: se elimina la carga anticipada de SheetJS; ahora se carga bajo demanda.
- `toxin_filter.js`: se agrega loader on‑demand de `xlsx.core.min.js` y el export se vuelve asíncrono con feedback de UI.
- `toxin_filter.html` y `motif_dipoles.js`: visualizaciones 3D y gráficos quedan detrás de botones (“Mostrar visualizaciones 3D”, “Mostrar gráficos”); se revela la sección bajo demanda (hidden + inert) y se inicializa en el primer clic.
- `motif_dipoles.js`: la carga de la referencia 3D se difiere a idle y a cuando el contenedor es visible (IntersectionObserver) para no competir con el primer paint.
- `toxin_filter.js` y `motif_dipoles.js`: los spinners de “Descargando/Exportando…” se reemplazaron por un indicador de texto (`⏳ ...`) para evitar dependencias de clases FA.
 - `toxin_filter.html`: las hojas de estilo clave de layout (design-system.css, navbar.css, components.css, filter-page.css) pasan a cargarse en modo bloqueante para evitar FOUC y eliminar los últimos saltos de layout (CLS) en `div.filter-container`; el CSS no crítico se mantiene diferido.
### Changed
- Las plantillas ya usan `asset_path('css/…')`, por lo que cuando `USE_MINIFIED_ASSETS=1` el servidor servirá automáticamente las versiones `.min.css` si existen.
### Fixed
- Reducción significativa de “Reduce JavaScript execution time” en Lighthouse:
  - Menos CPU en js/motif_dipoles.js (‑60–80% en pruebas locales).
  - Disminución del Total Blocking Time al mover cómputo a Worker y a momentos ociosos.
- Eliminado reprocesamiento/refetch redundante entre pestañas y páginas.
- “Minimize main‑thread work”: menor Script Evaluation inicial al quitar 3Dmol/Plotly del camino crítico y diferir la primera carga de referencia/grid.
- “Eliminate render‑blocking resources”: CSS no crítico deja de bloquear FCP/LCP; mejora de varios cientos de ms por archivo según Lighthouse.
- “Reduce the impact of third‑party code”: SheetJS deja de evaluarse en cada carga (se demanda al presionar Exportar) y se usa la build mínima (`xlsx.core.min.js`), recortando transferencia y tiempo de evaluación.
- “Avoid large layout shifts (CLS)”: al no crear viewers/plots hasta un clic explícito y reservar espacio con placeholders, los cambios de layout ocurren tras interacción y no computan en CLS; además se reduce TBT del arranque.
- “Largest Contentful Paint”: Render Delay reducido al prerenderizar la leyenda y retrasar la inicialización 3D hasta visibilidad/idle.
 - CLS residual en `div.filter-container`: se estabiliza reservando altura del header y tabs (placeholder `#tabs-placeholder`) y fijando min-height para header/estado/paginación y filas esqueleto; ya no hay saltos al inyectar pestañas ni al pintar resultados.

---

## [2.5.9] – 2025-11-03

### Changed
- Rediseño completo del intro section en la página de filtros de toxinas con layout de grid responsive y referencia al paper FEBS Letters (2025).
- Unificación de paleta de colores a blues sólidos, eliminación de gradientes en toda la página para consistencia con home.html.
- Mejora de controles de visualización con toggle cards interactivas mostrando estado "Oculto"/"Visible".

### Fixed
- Arreglos de Lighthouse audit: corrección de jerarquía de headings (h3→h2), mejora de ratios de contraste en botones, eliminación de CSS no utilizado (~18 KiB), consolidación de reglas duplicadas (#reference-viewer).
- Optimización de critical CSS path para reducir latencia de 695ms.
- Actualización de JavaScript (motif_dipoles.js) para manejo de badges de estado en toggle cards.

---

## [2.5.8] – 2025-11-03

### Fixed
- Sincronización del toggle de granularidad en el visualizador de grafos: implementación de estado visual consistente entre el slider CSS y el checkbox JavaScript.
- Agregado event listener para clics en el wrapper visual del toggle (`#granularity-toggle-wrapper`) que actualiza el estado del checkbox oculto y dispara la actualización del grafo.
- Función `syncGranularityToggleVisual()` para mantener la clase CSS `active` sincronizada con el estado del checkbox, controlando la posición del slider (izquierda para 'Atómico', derecha para 'Carbono Alfa').


---

## [2.5.7] – 2025-11-03

### Added
- Rediseño completo del apartado "Explora métricas y exporta resultado" en la página del visualizador con sistema de navegación moderno basado en cards horizontales.
- Nuevo panel de conexiones del grafo con diseño tipo card grid responsive, mostrando conexiones como cards individuales con iconos, nombres y distancias calculadas.
- Sistema de navegación horizontal con cards interactivas para acceso directo a secciones de análisis y exportación.
- Estados de carga y feedback visual mejorado en botones de exportación con animaciones ripple.

### Changed
- Reestructuración completa del header del analysis hub con badge introductorio, título grande y navegación basada en cards en lugar de botones tradicionales.
- Rediseño de panels de análisis y exportación con headers modernos que incluyen iconos grandes, badges temáticos y descripciones extendidas.
- Transformación de las cards de exportación en un diseño de 3 capas (header, body, footer) con form groups estructurados, selects estilizados y botones con gradientes temáticos.
- Actualización del sistema de grids para usar layouts modernos con mejor jerarquía visual y espaciado consistente.
- Mejora del panel de información del grafo con nuevo diseño card grid para conexiones, reemplazando la lista simple por cards interactivas.

### Fixed
- Alineación y espaciado inconsistente en el apartado de métricas y exportación, ahora completamente uniforme con el sistema de diseño.
- Problemas de UX/UI en las opciones de exportación, ahora con diseño profesional y navegación intuitiva.
- Estados visuales de botones de exportación mejorados con feedback claro de carga y estados disabled apropiados.



--- 

## [2.5.7] – 2025-11-02

# Changelog
Todas las modificaciones significativas del proyecto se documentan aquí.  
El historial se organiza en "versiones" retrospectivas según hitos de desarrollo.

## [2.7.0] – 2025-11-03

### Added
- Navbar como componente reutilizable:
  - Nuevo parcial `templates/partials/navbar.html` con “slot” para acciones por página (`navbar_actions`).
- Página de Familias: aviso guiado que indica cómo visualizar los dipolos; aparece al seleccionar una familia, se oculta al visualizar y reaparece al cambiar la selección.
- Leyenda global de flechas en la visualización de Familias (arriba del grid):
  - Colores: Dipolo=rojo, Eje X=verde, Eje Y=naranja, Eje Z=azul.
- Flechas de ejes X e Y añadidas en cada visualizador (además del eje Z existente).
- Controles “Resaltar” por péptido en las tablas (original y modificados): permiten marcar visualizaciones 3D específicas sin abandonar la tabla.

### Changed
- Orden del menú actualizado en todas las vistas: Inicio → Familias → Visualizador → Filtros.
- Plantillas `home.html`, `viewer.html`, `dipole_families.html` y `toxin_filter.html` ahora incluyen el parcial y, cuando aplica, inyectan sus acciones con `navbar_actions`.
- La marca (logo/título) enlaza a Inicio de forma consistente.
- Página de Familias (UX):
  - Mayor contraste en “Familia de Toxinas” y “Familia seleccionada”.
  - Reposicionamiento del aviso junto al cartel de “Familia seleccionada” con iconos claros.
  - Más espacio vertical entre selector/botón, avisos y la lista de péptidos.
  - Resaltado de cambios en secuencias: ahora se ve claramente (fondo blanco + borde acentuado) sobre el contenedor amarillo y aplica a todas las familias; si no hay tokens en el código del péptido, se usa un fallback por diferencias contra el original.
  - Visualización 3D por familia: el péptido original (código sin "_") aparece primero en la grilla; el resto se ordena alfabéticamente por código.
- En las tarjetas de visualización, se reemplaza “Componentes” por los ángulos respecto a los ejes X/Y/Z (en grados) junto a la Magnitud.
- Estilos más visibles para IC50 (chip) y para el control “Resaltar” (pill con borde/fondo y negrita).
- Color de resaltado de la tarjeta 3D cambiado a azul (borde/halo) para combinar con la paleta existente.
- Al activar “Resaltar” ya no se hace auto‑scroll a la visualización (permite marcar varios a la vez).

### Removed
- Página de Familias: se eliminaron las tarjetas/estadísticas finales (magnitud, orientación, componentes) para simplificar la UI y evitar información redundante.
- Página de Familias: se eliminaron los botones de exportación (acción del navbar y “Exportar Datos” en el header de la visualización).

### Fixed
- Eliminación de marcado duplicado del navbar entre plantillas, evitando desincronizaciones de iconos/orden/estados.
- Estado activo y comportamiento móvil consistentes en todas las páginas al compartir un único marcado.
- Señal de ayuda en Familias: ahora se oculta al iniciar la visualización y solo reaparece al cambiar de familia.

### Technical Details
- Integración vía `{% include 'partials/navbar.html' %}` y bloque inline `{% set navbar_actions %}…{% endset %}` cuando se requieren botones específicos por página.
- Sin cambios en `static/js/navbar.js` ni en `static/css/navbar.css`; el comportamiento existente aplica al nuevo parcial.
- Familias:
  - `templates/dipole_families.html`: se removió la sección de estadísticas; se mantiene solo el área de visualización.
  - `templates/dipole_families.html`: se quitaron las acciones de exportar del navbar y el botón “Exportar Datos” del header; se añadió la leyenda `.dipole-legend` sobre el área de visualización; columnas “Resaltar” agregadas a las tablas.
  - `static/js/dipole_family_analysis.js`: `displayFamilyStats()` no‑op; ocultado de `statisticsArea`; orden "original primero"; resaltado de secuencias (`parseModificationsFromCode()` + `highlightDiffs()`); `computeAxisAngles()` para X/Y/Z; `addDipoleArrowToViewer()` dibuja X (verde), Y (naranja), Z (azul) y dipolo (rojo); nuevo vínculo tabla↔tarjetas con `cardIndexByCode`; controles “Resaltar” activan `.highlighted-card` y se eliminó el auto‑scroll al togglear.
  - `static/css/families-page.css` y `.min.css`: estilos de `.seq-change` (alto contraste), `.dipole-legend`, chips de `IC50`, pills de `Resaltar` (accent azul) y `.highlighted-card` con borde/halo azul.

---

## [2.6.1] – 2025-11-03

### Added
- Overlay de carga con spinner para la tarjeta de Gráficos en la página de filtros:
  - Se muestra al inicializar y actualizar los gráficos; se oculta automáticamente al finalizar.
- Script de seguridad para sincronizar el texto/estado de los botones de toggle (“Mostrar/Ocultar …”) con la visibilidad real de las secciones (fallback si se carga una build minificada antigua).
- Estilo responsive tipo “chip” para los tabs de la tabla de resultados (Todos / Con Nav1.7 / …), con estado activo resaltado y mejor distribución en pantallas pequeñas.

### Changed
- Navbar: unificación de iconos en todas las plantillas para coherencia visual:
  - “Visualizador” → `fas fa-microscope`
  - “Familias” → `fas fa-flask`
- Navbar: se componentiza el marcado en `templates/partials/navbar.html` y se actualiza el orden de los ítems a: Inicio → Familias → Visualizador → Filtros. Las plantillas `home.html`, `viewer.html`, `dipole_families.html` y `toxin_filter.html` ahora incluyen el parcial y, cuando aplica, inyectan sus acciones con `navbar_actions`.
- `toxin_filter.html`: carga del script `motif_dipoles` vía `asset_path(...)` para respetar el modo minificado y mantener consistencia con el resto de assets.
- Paginación de la tabla de resultados: flechas reemplazadas por Font Awesome (`fa-angle-left` / `fa-angle-right`) para uniformidad con el resto de iconografía.

### Fixed
- Botones de mostrar/ocultar: ahora cambian correctamente a “Ocultar visualizaciones 3D” y “Ocultar gráficos” tras la primera carga y mantienen el estado sincronizado (aria-pressed y clase `.active`).
- Actualización de gráficos envuelta en overlay para evitar parpadeos y dar feedback de estado durante cargas pesadas.

## [2.6.0] – 2025-11-02

### Added
- Carga perezosa de gráficos en la página de filtros mediante IntersectionObserver (se renderizan solo al ser visibles).
- Web Worker dedicado (motif_dipoles.worker.js) para construir datasets de gráficos fuera del hilo principal.
- Capa de caché por parámetros (gap_min, gap_max, require_pair, referencia) para el agregado de items.
- Loader on‑demand de 3Dmol (load3DmolOnce) y bootstrap diferido de la vista (requestIdleCallback) para no bloquear el hilo principal.
- Placeholder temprano de la leyenda (.dipole-legend) para adelantar el LCP (texto visible inmediato).
- Minificado de CSS de first‑party: se extendió `tools/minify_assets.py` para generar `.min.css` en `static/css` (p. ej. `viewer.min.css`).

### Changed
- Actualizaciones de gráficos diferidas con scheduleChartsUpdate usando requestIdleCallback (fallback setTimeout).
- Carga on‑demand de Plotly (loadPlotlyOnce) para evitar coste inicial innecesario.
- Render con Plotly.react en lugar de recrear gráficos completos, reutilizando instancias.
- Reemplazo de llamadas directas a updateChartsWithAllItems por scheduleChartsUpdate en cambios de filtros, referencia y paginación.
- `toxin_filter.html`: se eliminan los scripts de 3Dmol y Plotly (ahora se inyectan bajo demanda desde JS).
- `motif_dipoles.js`: los viewers 3D esperan a 3Dmol (await load3DmolOnce) en loadReference/renderPage/reRenderCurrentPage; reRenderCurrentPage pasa a async.
- `toxin_filter.html`: hojas CSS no críticas se cargan como no‑bloqueantes (media="print" + onload + <noscript>) y se reserva altura mínima de contenedores para estabilidad (CLS≈0).
- `toxin_filter.html`: se elimina la carga anticipada de SheetJS; ahora se carga bajo demanda.
- `toxin_filter.js`: se agrega loader on‑demand de `xlsx.core.min.js` y el export se vuelve asíncrono con feedback de UI.
- `toxin_filter.html` y `motif_dipoles.js`: visualizaciones 3D y gráficos quedan detrás de botones (“Mostrar visualizaciones 3D”, “Mostrar gráficos”); se revela la sección bajo demanda (hidden + inert) y se inicializa en el primer clic.
- `motif_dipoles.js`: la carga de la referencia 3D se difiere a idle y a cuando el contenedor es visible (IntersectionObserver) para no competir con el primer paint.
- `toxin_filter.js` y `motif_dipoles.js`: los spinners de “Descargando/Exportando…” se reemplazaron por un indicador de texto (`⏳ ...`) para evitar dependencias de clases FA.
 - `toxin_filter.html`: las hojas de estilo clave de layout (design-system.css, navbar.css, components.css, filter-page.css) pasan a cargarse en modo bloqueante para evitar FOUC y eliminar los últimos saltos de layout (CLS) en `div.filter-container`; el CSS no crítico se mantiene diferido.
### Changed
- Las plantillas ya usan `asset_path('css/…')`, por lo que cuando `USE_MINIFIED_ASSETS=1` el servidor servirá automáticamente las versiones `.min.css` si existen.
### Fixed
- Reducción significativa de “Reduce JavaScript execution time” en Lighthouse:
  - Menos CPU en js/motif_dipoles.js (‑60–80% en pruebas locales).
  - Disminución del Total Blocking Time al mover cómputo a Worker y a momentos ociosos.
- Eliminado reprocesamiento/refetch redundante entre pestañas y páginas.
- “Minimize main‑thread work”: menor Script Evaluation inicial al quitar 3Dmol/Plotly del camino crítico y diferir la primera carga de referencia/grid.
- “Eliminate render‑blocking resources”: CSS no crítico deja de bloquear FCP/LCP; mejora de varios cientos de ms por archivo según Lighthouse.
- “Reduce the impact of third‑party code”: SheetJS deja de evaluarse en cada carga (se demanda al presionar Exportar) y se usa la build mínima (`xlsx.core.min.js`), recortando transferencia y tiempo de evaluación.
- “Avoid large layout shifts (CLS)”: al no crear viewers/plots hasta un clic explícito y reservar espacio con placeholders, los cambios de layout ocurren tras interacción y no computan en CLS; además se reduce TBT del arranque.
- “Largest Contentful Paint”: Render Delay reducido al prerenderizar la leyenda y retrasar la inicialización 3D hasta visibilidad/idle.
 - CLS residual en `div.filter-container`: se estabiliza reservando altura del header y tabs (placeholder `#tabs-placeholder`) y fijando min-height para header/estado/paginación y filas esqueleto; ya no hay saltos al inyectar pestañas ni al pintar resultados.



## [2.5.6] – 2025-11-01

### Added

- Sistema dual de interacción CLICK/HOVER para nodos:
  - **CLICK**: Selecciona el nodo (color rojo/magenta), actualiza panel inferior y resalta sus conexiones en rojo.
  - **MOUSE HOVER**: Resalta nodo en amarillo/naranja y sus conexiones sin cambiar el panel de información.
  - Ambos estados pueden coexistir: permite explorar vecinos mientras se mantiene la información del nodo seleccionado.

### Changed

- Renderizado de nodos mejorado con diferenciación visual clara:
  - Nodos seleccionados (CLICK): Rojo/Magenta brillante + borde blanco grueso (3.5px) + tamaño 60% mayor.
  - Nodos hovados (MOUSE): Amarillo/Naranja brillante + borde blanco (3.0px) + tamaño 40% mayor.

- Comportamiento mejorado del resetView():
  - Limpia tanto la selección como el hover al hacer doble-click.
  - Restaura el panel inferior al estado inicial.

### Technical Details


- Arquitectura:
  - Separación limpia entre lógica de hover (visual) y selección (actualización de datos).
  - Sin dependencias nuevas; solo manipulación de canvas 2D y DOM estándar.

### Fixed

- Problema de z-index: panel flotante ya no se pierde detrás del canvas.
- Hover desaparece al inicio: ahora es estrictamente visual y siempre responde.
- Panel de conexiones limitado a 15: ahora muestra TODAS las conexiones en grid responsive.

---

## [2.5.5] – 2025-10-31

### Added

- Migración completa de Plotly a Mol* WebGL para visualización 3D de grafos, optimizando rendimiento para grafos grandes (600+ nodos, 10-20K aristas).
- Nuevo renderizador WebGL optimizado para grafos con controles interactivos (zoom, rotación, hover tooltips).


### Changed

- Reemplazo del adaptador PlotlyGraphVisualizerAdapter por MolstarGraphVisualizerAdapter para generación de datos ligeros compatibles con WebGL.
- Mejora significativa en rendimiento: reducción del 94% en tiempo de renderizado (de ~5s a <500ms) y del 94% en tamaño de payload.
- Visualización enfocada únicamente en nodos y aristas, manteniendo precisión PDB y cálculos de métricas.
- Fondo mejorado con gradiente y eliminación de ejes para mayor claridad.

### Technical Details

- Backend:
  - `graph_visualizer_adapter.py`: Nuevo adaptador MolstarGraphVisualizerAdapter con métodos para extracción de posiciones 3D y serialización de datos ligeros.
  - `graphs_controller.py`: Actualización de imports y uso del nuevo adaptador.
  - `graph_presenter.py`: Simplificación para formato WebGL, eliminación de datos Plotly.
  - `app.py`: Actualización de import del adaptador.
- Frontend:
  - `molstar_graph_renderer.js`: Nuevo renderizador WebGL con proyección 3D-2D, controles de cámara, tooltips y renderizado optimizado.
  - `graph_viewer.js`: Eliminación de código Plotly, integración del nuevo renderizador.
  - `viewer.html`: Remoción de script Plotly, agregado del nuevo script de renderizador.
- Arquitectura: Patrón adaptador para facilitar cambios tecnológicos; uso de Canvas2D para renderizado eficiente.

---

## [2.5.4] – 2025-10-30


### Added
- Tarjeta fija “Gráficos” siempre visible en la página de filtros con dos visualizaciones:
  - IC50 (puntos, eje Y log(nM)) para todos los péptidos con IC50 (BD y/o IA).
  - Δori (°) únicamente para accesiones sin IC50.
- Actualización automática de ambos gráficos al cambiar filtros, referencia y paginación.

### Changed
- El gráfico IC50 pasa a renderizarse sin botón, siempre presente; las etiquetas del eje X ahora muestran “ACCESSION (ori=…°)”.
- El nuevo gráfico de Δori usa en el eje X solo el ACCESSION (sin “(ori=…)”) y en el eje Y el Δori en grados.

### Removed
- Botón “Gráfico IC50 (puntos)” y su contenedor dinámico.

### Technical Details
- Frontend (motif_dipoles.js):
  - Nuevas funciones: buildLabelWithOri, renderIc50ScatterAllFixed, renderOriNoIc50Chart y updateChartsWithAllItems.
  - Hooks a eventos existentes: onReferenceChanged, applyFiltersAndRender y onPaginationChange para refrescar gráficos.
  - IC50: usa campos normalizados a nM (nav1_7_ic50_value_nm y ai_ic50_*_nm); AI con barras de error (min/max) y punto central (avg o value).
  - Δori: usa orientation_score_deg del backend o cálculo cliente como fallback; eje Y lineal [0, 180].
  - Manejo seguro de instancias (destroy/recreate) para evitar duplicados y fugas.
- HTML (toxin_filter.html):
  - Nueva tarjeta “Gráficos” con contenedores fijos: ic50-scatter-all y ori-no-ic50-chart.

---

## [2.5.3] – 2025-10-30

### Changed

- Optimización integral del código eliminando redundancias en módulos de cálculo de grafos:
  - Creación del módulo común `graph_metrics.py` con funciones centralizadas para cálculo de métricas de grafo, estadísticas de centralidad y top residuos.
  - Refactorización de `graph_analysis2D.py`, `graphein_graph_adapter.py` y `graph_presenter.py` para usar el módulo común y eliminar código duplicado.
  - Implementación de lazy imports en `graph_metrics.py` para evitar dependencias circulares y mejorar rendimiento.

### Fixed

- Eliminación completa de logs innecesarios en producción:
  - Remoción de `print()` statements en archivos Python (`graph_analysis2D.py`, archivos de test en `tools/`) dejando solo logs de tiempo en `run_full_pipeline.py`.
  - Eliminación de `console.log()` en JavaScript (`graph_viewer.js`) para limpiar la consola del navegador.
- Corrección de errores de sintaxis en `test_psf_generation.py` causados por indentación incorrecta de comentarios.

### Technical Details

- Arquitectura: Separación de responsabilidades entre construcción de grafos, cálculo de métricas y presentación; uso de lazy imports para compatibilidad con NetworkX y NumPy.
- Rendimiento: Reducción significativa de código duplicado y mejora en mantenibilidad del sistema de análisis de grafos.
- Calidad: Limpieza de código de producción eliminando outputs de debug que afectaban la experiencia del usuario.

## [2.5.2] – 2025-10-29
### Added
- Overlay de carga con spinner al cambiar de pestaña IC50 (“Todos / Con IC50 / Sin IC50”) y al cambiar de página en el visualizador.
- Bloqueo temporal de navegación “Anterior / Siguiente” mientras se cargan y renderizan los dipolos.

### Changed
- Diseños de los botones “Todos / Con IC50 / Sin IC50” con estilo pill, gradiente, sombras y estado activo; ubicados a la izquierda en el mismo contenedor que “Vectores Dipolares” y “Puentes Disulfuro”.

### Technical Details
- Frontend:
  - motif_dipoles.js: helpers getIc50Overlay/showIc50Loading/hideIc50Loading; deshabilita botones IC50 y paginación durante renderPage(); re‑habilita en finally.
  - toxin_filter.html: estilos para .ic50-filter-btn y clases del overlay (.ic50-loading-overlay, .ic50-loading-box, .ic50-spinner).
- Comportamiento:
  - Cambio de pestaña IC50: muestra overlay, resetea a página 1, aplica filtro (cliente) y re-renderiza; luego oculta overlay.
  - Cambio de página: muestra overlay “Cargando página…”, desactiva Anterior/Siguiente, renderiza y restaura controles.

---

## [2.5.1] – 2025-10-29
### Changed
- Visualizador de dipolos (página de filtros): al cambiar de pestaña IC50 ahora se reinicia la paginación y se muestra el conjunto filtrado desde la primera página.
  - Con IC50: se filtra el conjunto completo, se resetea a página 1 y se mantiene el orden original de los elementos.
  - Sin IC50: igual que arriba, aplicado a los que no tienen IC50.
  - Todos: restaura el orden y la paginación original del backend.

### Technical Details
- Frontend (motif_dipoles.js): se conserva el arreglo en orden original, se aplica filtrado client‑side sobre el agregado y se reinicia currentPage=1 al cambiar de pestaña.

---


## [2.5.0] - 2025-10-29

Added
- Exclusión de accessions en toda la app (backend, visualizadores y front-end) para: P83303, P84507, P0DL84, P84508, D2Y1X8, P0DL72, P0CH54. No aparecen en tablas, visualizadores ni descargas.
- Detección y marcado de IC50 por péptido:
  - Desde BD (Nav1_7_InhibitorPeptides) con conversión a nM.
  - Desde archivo AI exportado exports/filtered_accessions_nav1_7_analysis.json (ai_analysis.ic50_values), soportando valores únicos y rangos (value_min/value_max).
  - Campos añadidos en respuestas del backend y usados por la UI: nav1_7_has_ic50, nav1_7_ic50_value_nm (y derivados AI: min/avg/max cuando existan).
- Nueva UI de filtros IC50 en el visualizador de dipolos de toxinas filtradas:
  - Botones “Todos / Con IC50 / Sin IC50” ubicados a la izquierda dentro del mismo contenedor de “Vectores Dipolares” y “Puentes Disulfuro”.
- Nuevo gráfico IC50:
  - Botón “Gráfico IC50 (puntos)” a la derecha del mismo contenedor.
  - Gráfico de puntos (eje Y log(nM)) con todos los péptidos que tienen IC50 (AI y/o BD), mostrando barras de error cuando hay rangos (min/max) y el promedio como punto central.
  - Respeta exclusiones y filtros activos.
- Script de exportación y análisis IA: tools/export_filtered_accessions_nav1_7.py
  - Toma los accession de los dipolos filtrados, busca Proteins.description por accession y ejecuta el analizador IA.
  - Genera exports/filtered_accessions_nav1_7_analysis.json con los resultados por péptido.
  - Logging a consola y archivo (exports/process_log.txt): “Procesando: <accession>”, presencia de descripción, y respuesta del análisis (JSON o error).

Improved
- Procesamiento IA más robusto (tools/few_shot2.py): instrucciones para forzar salida JSON y extractor tolerante a texto extra (bloques ```json```, recorte por primeras/últimas llaves).
- Normalización a nM en backend para facilitar comparaciones y graficado.

Notes
- El gráfico usa datos AI (value / value_min–value-max) y/o BD. Cuando existe rango AI, se plotea min, max y el promedio; si solo hay un valor (AI o BD), se plotea como punto único.
- El archivo exports/filtered_accessions_nav1_7_analysis.json se carga y cachea en el backend para marcar presencia de IC50; refresca el servidor si regeneras el JSON.

---

## [2.4.1] – 2025-10-25
### Fixed
- Integración completa de graphein_graph_adapter.py con graph_analysis2D.py para cálculo de métricas de grafo.
- Preparación automática de atributos de nodos requeridos (carga, hidrofobicidad, estructura secundaria) para compatibilidad con análisis de toxinas.

---
### Changed
- Rediseño completo del navbar con paleta de colores oscura profesional.
- Eliminación de gradientes y transparencias, reemplazados por colores sólidos.

### Fixed
- Corrección de conflictos de CSS inline en páginas HTML que sobrescribían estilos del navbar.
- Agregado del enlace "Inicio" al navbar en la vista de filtros para navegación consistente.

### Deleted
- Se eliminio graph_analysis3D.py debido a que era simplemente un PLOTLY que reidreccionaba a otra pagina
---

## [2.4.0] – 2025-10-24
### Added
- Botón de descarga para la referencia del dipolo en la vista de filtros (UI + endpoint GET /v2/motif_dipoles/reference/download).
- Botón de descarga por toxina en cada visualizador (UI + endpoint GET /v2/motif_dipoles/item/download?accession=...).
- Panel de búsqueda por accession en la tabla de resultados:
  - Input de búsqueda y botón "Limpiar" en la cabecera de la tabla que permiten filtrar las filas cargadas por accession (búsqueda por substring, case-insensitive).
  - El filtrado es client-side sobre los resultados ya descargados; la paginación y el contador de hits se actualizan según el conjunto filtrado.

### Changed
- Se reemplazaron las métricas en la esquina superior derecha de cada tarjeta por el botón de descarga ubicado en el header (nombre + accession), evitando solapamiento con el canvas 3D.
- Frontend: listeners de descarga ligados tras el renderizado de tarjetas para soportar paginación/refresh y mejorar feedback (spinner/errores).
- Header de los visualizadores de toxinas: el accession pasa a ser un enlace a UniProt (https://www.uniprot.org/uniprotkb/{accession}/entry), la secuencia de la toxina se muestra directamente bajo el nombre, y nombre/accession/secuencia usan un tamaño de fuente uniforme y aumentado; el botón de descarga se ubica en el header reemplazando las métricas previas.
- En el panel de referencia, la secuencia de la referencia se muestra a la derecha del selector.

### Removed
- Eliminado el modo de visualización "Ambos"; solo quedan los modos "Vectores Dipolares" y "Puentes S–S".

### Fixed
- Corrección de la visualización de puentes disulfuro: detección basada en átomos SG de residuos CYS (umbral de distancia) y renderizado adecuado (cilindros) en el viewer.
- Problemas de interacción resueltos (botones clickeables, z-index y registro de handlers).

### Notes
- Las descargas se generan en memoria (ZIP) y requieren acceso a los PDB/PSF correspondientes en disco o en la fuente de datos configurada.
- Si se requiere, se puede restaurar la visualización de métricas en otro lugar (tooltip/leyenda) sin afectar la descarga.

---

## [2.2.1] – 2025-10-20
### Added
- **Dockerización local completa del proyecto**:
  - Se creó un `Dockerfile` de producción que incluye la base de datos, archivos PDB, PSF y carpeta filtered, permitiendo levantar la app Flask y acceder a la UI y API desde el navegador.
  - Se añadió `.dockerignore` para acelerar los builds y reducir el tamaño de la imagen.
  - Se agregó `docker-compose.yml` con dos servicios:
    - `app`: modo producción con gunicorn.
    - `dev`: modo desarrollo con Flask y autoreload, permitiendo edición en caliente y visualización completa de la página.
  - Se configuraron variables de entorno y healthcheck para facilitar el despliegue y diagnóstico.

### Notes
- Por ahora la dockerización es solo local; no se ha publicado la imagen en ningún registro ni automatizado el despliegue en servidores externos.

---

## [2.2.0] – 2025-10-20
### Added
- **Optimización integral de rendimiento Lighthouse**: Sistema completo de carga diferida y cacheado:
  - Font Awesome con `preload + async onload` para evitar render-blocking resources.
  - Mol* CSS con trick `media="print" onload` para carga no-bloqueante.
  - HTTP cache headers: 1 año para assets estáticos, 1 hora para HTML, no-cache para API.
- **Infraestructura de minificación**: Script `tools/minify_assets.py` para minificar automáticamente CSS/JS:
  - Helper `asset_path()` en Flask que prefiere `.min` cuando `USE_MINIFIED_ASSETS=1`.
  - Registered como Jinja global para templates (viewer.html, dipole_families.html, etc).
  - Reporte automático de ahorros de tamaño por archivo.


---

## [2.1.0] – 2025-10-16
### Added
- Selector de referencia en la vista de dipolos: opción fija **WT hwt4_Hh2a** seguida de toxinas de la tabla `Nav1_7_InhibitorPeptides` ordenadas por IC50 normalizado; al cambiar la referencia se recalculan dipolo y orden del listado.
- Visualización multi-modo para los hits filtrados (Vectores, Puentes S–S, Ambos) con overlays que exhiben magnitud, ángulos y ΔX/ΔY/ΔZ frente a la referencia.
- Métricas de orientación completas: cálculo y exposición de Δori, proyecciones vectoriales normalizadas y diferencias por eje tanto en tarjetas como en overlays.
- Extensión de `tools/generate_filtered_psfs.py` con soporte `--pdb-file`, `--output-dir`, `--chain` y `--disulfide-cutoff`; los artefactos del WT se generan en `pdbs/WT/generated/`.

### Changed
- El backend ordena los resultados filtrados por el “orientation_score” (ángulo entre vectores normalizados) y usa ΔZ solo como métrica secundaria; la paginación opera sobre la lista ya ordenada.
- El layout del panel de visualización incluye la lista desplegable junto al título “Dipolo de referencia” y refresca viewers al cambiar la selección sin recargar la página.
- Cacheo de referencia centralizado: la app reutiliza PDB/PSF y vectores normalizados cuando es la WT y solo recalcula al seleccionar otra toxina.

### Technical Details
- Helper `_compute_orientation_metrics` consolida normalización, proyección por eje y diferencias absolutas; la respuesta JSON expone `orientation_score_deg`, `delta_axes` y metadatos de la referencia activa.
- `motif_dipoles.js` incorpora utilidades `normalizeVector`, `computeAngle`, `computeAxisDiffs` y renderizado agnóstico al modo, compartiendo leyendas y tooltips entre viewers.
- `motif_dipoles_controller.py` resuelve la referencia por código, normaliza IC50 a nM (`_convert_ic50_to_nm`) y mantiene caches en memoria para minimizar cálculos repetidos.

---

## [2.0.0] – 2025-10-09
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
