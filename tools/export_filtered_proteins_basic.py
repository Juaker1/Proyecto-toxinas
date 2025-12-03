import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

# Reutilizar search_toxins
PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from extractors.toxins_filter import search_toxins

DB_PATH_DEFAULT = "database/toxins.db"

# Conjunto de accessions excluidos (mismo criterio que en otros sitios)
EXCLUDED_ACCESSIONS = {"P83303", "P84507", "P0DL84", "P84508", "D2Y1X8", "P0DL72", "P0CH54"}


def export_filtered_proteins_basic(
    db_path: str = DB_PATH_DEFAULT,
    gap_min: int = 3,
    gap_max: int = 6,
    require_pair: bool = False,
) -> List[Dict[str, Any]]:
    """
    Devuelve una lista de dicts con información básica de péptidos filtrados:
    - accession_number
    - sequence
    - model_source

    Respeta el filtro de motivos (search_toxins) y omite los mismos accession
    excluidos que el resto de la aplicación.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    hits = search_toxins(
        gap_min=gap_min,
        gap_max=gap_max,
        require_pair=require_pair,
        db_path=db_path,
    )

    results: List[Dict[str, Any]] = []
    seen_keys = set()

    for h in hits:
        peptide_id = h.get("peptide_id")
        if peptide_id is None:
            continue

        # Recuperar datos desde Peptides
        cur.execute(
            "SELECT accession_number, sequence, model_source FROM Peptides WHERE peptide_id = ?",
            (peptide_id,),
        )
        row = cur.fetchone()
        if not row:
            continue

        accession = row["accession_number"]
        sequence = row["sequence"]
        model_source = row["model_source"]

        # Omitir accessions excluidos
        if accession and accession in EXCLUDED_ACCESSIONS:
            continue

        # Normalizar clave para evitar duplicados (por accession si existe)
        key = accession or f"peptide_{peptide_id}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        results.append(
            {
                "peptide_id": peptide_id,
                "accession": accession,
                "sequence": sequence,
                "model_source": model_source,
            }
        )

    conn.close()
    return results


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exportar información básica (accession, sequence, model_source) de péptidos filtrados a JSON"
    )
    parser.add_argument("--db", default=DB_PATH_DEFAULT, help="Ruta a la base de datos SQLite")
    parser.add_argument("--gap-min", type=int, default=3)
    parser.add_argument("--gap-max", type=int, default=6)
    parser.add_argument("--require-pair", action="store_true")
    parser.add_argument(
        "--out",
        default="exports/filtered_proteins_basic.json",
        help="Ruta del archivo JSON de salida",
    )

    args = parser.parse_args(argv)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = export_filtered_proteins_basic(
        db_path=args.db,
        gap_min=args.gap_min,
        gap_max=args.gap_max,
        require_pair=args.require_pair,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(data)} records to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())