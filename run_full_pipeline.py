#!/usr/bin/env python3
"""
Pipeline maestro (modo simplificado e interactivo) UniProt → DB:

Flujo automatizado:
    1. Crear/verificar base de datos.
    2. Pedir query al usuario.
    3. Buscar accessions en UniProt.
    4. Descargar XML individuales en paralelo y consolidar + guardar Proteins.
    5. Extraer/descargar/cortar péptidos (PDB / AlphaFold) y guardar en tabla Peptides.
    6. Insertar péptidos Nav1.7 (dataset curado) en tabla Nav1_7_InhibitorPeptides.
    7. Vincular archivos PDB/PSF locales (si existen) como blobs para esos Nav1.7.
    8. Reportar tiempos parciales y totales.

Uso:
    python run_full_pipeline.py
    (El script solicitará la query por consola.)

Requisitos: requests, aiohttp, biopython, mdanalysis, certifi.
"""

import os
import sys
import time
import asyncio
from typing import Dict, Any

try:
    from database.create_db import create_database, DB_PATH as DEFAULT_DB_PATH
    from extractors.uniprot import UniProtPipeline
    from extractors.peptide_extractor import PeptideExtractor
    from loaders.instert_Nav1_7 import insert_peptides as insert_nav1_7_peptides
    from loaders.instert_Nav1_7_pdb_psf import PDBAndPSFInserter
except ModuleNotFoundError as e:
    print(f"Error importando módulos del proyecto: {e}")
    sys.exit(1)


def human_time(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds*1000:.1f} ms"
    if seconds < 60:
        return f"{seconds:.2f} s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{int(m)}m {s:.1f}s"
    h, m = divmod(m, 60)
    return f"{int(h)}h {int(m)}m {s:.1f}s"


def ensure_database(db_path: str):
    """Crea la base de datos si no existe (idempotente)."""
    first_time = not os.path.exists(db_path)
    create_database()
    if first_time:
        print(f"[DB] Creada base de datos en {db_path}")


async def run_peptide_stage(xml_path: str, db_path: str, concurrency: int = 5) -> Dict[str, Any]:
    """Ejecuta extracción/corte de péptidos y devuelve métricas."""
    peptide_extractor = PeptideExtractor(db_path=db_path)
    t0 = time.perf_counter()
    peptide_ids = await peptide_extractor.process_xml_file(xml_path, max_concurrent=concurrency)
    return {
        "peptides_inserted": len(peptide_ids),
        "peptide_ids": peptide_ids,
        "time_seconds": time.perf_counter() - t0
    }


def main():
    print("[PIPELINE] Inicio del proceso completo")
    query = input("🔍 Ingresa una query para buscar proteínas en UniProt: ").strip()
    if not query:
        print("No se ingresó una query. Saliendo.")
        return

    timings = {}
    t_global_start = time.perf_counter()

    # 1. Base de datos
    t0 = time.perf_counter()
    ensure_database(DEFAULT_DB_PATH)
    timings['create_database'] = time.perf_counter() - t0

    # 2. Accessions
    pipeline = UniProtPipeline(db_path=DEFAULT_DB_PATH)
    t1 = time.perf_counter()
    accessions, name_prefix = pipeline.fetch_accessions(query)
    timings['fetch_accessions'] = time.perf_counter() - t1
    if not accessions:
        print("No se obtuvieron accessions. Saliendo.")
        return

    # 3. Descarga XML + inserción Proteins
    xml_path = f"data/processed/{name_prefix}_data.xml"
    t2 = time.perf_counter()
    asyncio.run(pipeline.fetch_all_async(accessions, xml_path))
    timings['download_and_insert_proteins'] = time.perf_counter() - t2

    # 4. Péptidos (extracción + descarga + corte)
    print(f"[PEPTIDES] Procesando péptidos desde {xml_path}")
    t3 = time.perf_counter()
    peptide_stage = asyncio.run(run_peptide_stage(xml_path, DEFAULT_DB_PATH, concurrency=5))
    timings['extract_and_insert_peptides'] = peptide_stage['time_seconds']
    timings['peptides_inserted'] = peptide_stage['peptides_inserted']

    # 5. Insertar dataset Nav1.7
    t4 = time.perf_counter()
    try:
        insert_nav1_7_peptides()
        timings['insert_nav1_7'] = time.perf_counter() - t4
    except Exception as e:
        print(f"[Nav1.7][ERROR] Falló inserción de péptidos Nav1.7: {e}")
        timings['insert_nav1_7'] = time.perf_counter() - t4

    # 6. Actualizar blobs PDB/PSF para Nav1.7
    t5 = time.perf_counter()
    try:
        inserter = PDBAndPSFInserter(db_path=DEFAULT_DB_PATH, pdb_folder="pdbs/", psf_folder="psfs/")
        inserter.process_all_peptides()
        timings['update_nav1_7_blobs'] = time.perf_counter() - t5
    except Exception as e:
        print(f"[Nav1.7][ERROR] Falló actualización de blobs PDB/PSF: {e}")
        timings['update_nav1_7_blobs'] = time.perf_counter() - t5

    # 7. Métricas finales
    timings['total_time_seconds'] = time.perf_counter() - t_global_start

    # 8. Resumen
    print("\n===== RESUMEN DEL PIPELINE =====")
    print(f"Query: {query}")
    print(f"Accession numbers recuperados: {len(accessions)}")
    print(f"Tiempo crear/verificar BD: {human_time(timings['create_database'])}")
    print(f"Tiempo fetch accessions: {human_time(timings['fetch_accessions'])}")
    print(f"Tiempo XML + insert Proteins: {human_time(timings['download_and_insert_proteins'])}")
    print(f"Tiempo péptidos UniProt: {human_time(timings['extract_and_insert_peptides'])} (n={timings.get('peptides_inserted', 0)})")
    if 'insert_nav1_7' in timings:
        print(f"Tiempo insertar Nav1.7: {human_time(timings['insert_nav1_7'])}")
    if 'update_nav1_7_blobs' in timings:
        print(f"Tiempo blobs PDB/PSF Nav1.7: {human_time(timings['update_nav1_7_blobs'])}")
    print(f"Tiempo TOTAL: {human_time(timings['total_time_seconds'])}")
    print("================================\n")

if __name__ == '__main__':
    main()
