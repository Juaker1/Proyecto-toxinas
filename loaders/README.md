# loaders — Carga e inserción de datos estructurales/experimentales en la base de datos

Scripts de ETL ligero para consolidar toxinas peptídicas en SQLite. Integran información de UniProt (metadatos/secuencias), PDB/AlphaFold (estructuras) y archivos locales (PDB/PSF), y adjuntan binarios para habilitar análisis topológicos y electrostáticos posteriores.

## Qué resuelve
- Inserción de paneles de péptidos con metadatos clave (códigos, secuencias, farmacóforo, IC50, enlaces PDB/AlphaFold).
- Poblado de blobs binarios PDB/PSF en la tabla `Nav1_7_InhibitorPeptides` a partir de archivos locales en `pdbs/` y `psfs/`.
- Trazabilidad: imprime progreso y faltantes, ayudando a identificar huecos (p. ej., PSF no disponible).

## Tecnologías y dependencias clave
- SQLite3 (módulo estándar de Python) — conexión e inserciones/updates.
- Sistema de archivos — lectura de PDB/PSF locales.
- Compatibilidad con Windows PowerShell para ejecución directa.

## Arquitectura y lógica

### 1) `instert_Nav1_7.py` (inserción de registros base)
- Contiene `peptides_data`: una lista curada con:
  - `accession_number`, `peptide_code`, `sequence`, `pharmacophore_match`, `pharmacophore_residue_count` (campo `residue_count` en el script), `ic50_value` + `ic50_unit`, y `pdb_download_link`.
- Función: `insert_peptides()`
  - Abre la BD `database/toxins.db`.
  - Recorre `peptides_data` e inserta filas en `Nav1_7_InhibitorPeptides` con parámetros enlazados.
  - Confirma y cierra.

Requisitos de esquema mínimos (campos esperados):
- `Nav1_7_InhibitorPeptides(accession_number, peptide_code, sequence, pharmacophore_match, pharmacophore_residue_count, ic50_value, ic50_unit, pdb_download_link, pdb_blob, psf_blob, ...)`.

Consideraciones:
- Usa INSERT “ciego”. Si el esquema impone UNIQUE en `peptide_code`, podría requerir UPSERT (`INSERT OR REPLACE`).
- Las URLs de PDB pueden usarse en etapas posteriores para descargar faltantes; este script no descarga.

### 2) `instert_Nav1_7_pdb_psf.py` (adjuntar PDB/PSF como BLOB)
- Clase: `PDBAndPSFInserter(db_path="database/toxins.db", pdb_folder="pdbs/", psf_folder="psfs/")`
- Flujo `process_all_peptides()`:
  1. `fetch_peptides()` consulta todos los `peptide_code` en la tabla.
  2. `read_file_as_blob(folder, filename, extension)` abre `<folder>/<peptide_code>.<ext>` y devuelve bytes o `None` si falta.
  3. `update_blobs_in_database(peptide_code, pdb_blob, psf_blob)` hace `UPDATE` de los campos `pdb_blob` y `psf_blob`.
  4. Log de progreso por péptido: encontrado/ausente/errores.

Consideraciones:
- Nombres de archivo deben coincidir exactamente con `peptide_code` (incluyendo caracteres especiales como `β`, `μ`, `ω`). En Windows, los nombres Unicode son soportados, pero evita inconsistencias de normalización.
- Si ambos archivos faltan, el script deja el registro sin cambios (mensaje “no se actualizó”).

## Uso rápido (Windows PowerShell)

1) Insertar los péptidos base y metadatos:
```powershell
python loaders/instert_Nav1_7.py
```

2) Adjuntar PDB/PSF desde carpetas locales a la base:
```powershell
python loaders/instert_Nav1_7_pdb_psf.py
```

Salida esperada:
- Mensajes de progreso por péptido y ✓ cuando se actualiza la fila con al menos un blob.

## Buenas prácticas y edge cases
- Asegurar que la BD existe y el esquema contiene los campos destino. Puedes crear/validar el esquema con los scripts de `database/`.
- Cohesión de nombres: los archivos deben estar en `pdbs/` y `psfs/` y llamarse exactamente como `peptide_code` + extensión. Ej.: `β-TRTX-Cd1a.pdb` y `β-TRTX-Cd1a.psf`.
- Control de versiones de datos: ejecutar primero la inserción base (`instert_Nav1_7.py`) y luego los blobs para evitar updates a filas inexistentes.
- Manejo de NULLs: si `pdb_blob` o `psf_blob` ya contiene datos y no deseas sobrescribir, extiende el método con condición `WHERE (pdb_blob IS NULL OR psf_blob IS NULL)` o comparaciones por tamaño/fecha.
- Caracteres especiales/espacios: evita renombrar a variantes ASCII si ya se usaron códigos griegos; homogeniza fuentes.


---
Estos scripts son el puente entre la capa de adquisición/curación y los análisis topológicos/visuales; mantenerlos simples y deterministas ayuda a la reproducibilidad del pipeline.