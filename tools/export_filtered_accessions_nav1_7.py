import argparse
import json
import sqlite3
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure project root is on sys.path so 'extractors' and 'tools' package imports work
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from extractors.toxins_filter import search_toxins
    from tools.few_shot2 import analyze_text_for_nav17
except Exception as e:
    raise ImportError(
        "No se pudieron importar módulos del proyecto. Ejecuta el script desde la raíz del repositorio "
        "o añade el directorio raíz a PYTHONPATH. Detalle: " + str(e)
    )

DB_PATH_DEFAULT = "database/toxins.db"


def process_filtered_hits(
    db_path: str = DB_PATH_DEFAULT,
    gap_min: int = 3,
    gap_max: int = 6,
    require_pair: bool = False,
    log_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    hits = search_toxins(gap_min=gap_min, gap_max=gap_max, require_pair=require_pair, db_path=db_path)
    results: List[Dict[str, Any]] = []
    seen_accessions = set()

    total = len(hits)
    def log(msg: str):
        print(msg)
        if log_path:
            try:
                with open(log_path, "a", encoding="utf-8") as lf:
                    lf.write(msg + "\n")
            except Exception:
                pass

    for idx, h in enumerate(hits, start=1):
        peptide_id = h.get("peptide_id")
        # Obtener accession/sequence desde Peptides
        cur.execute("SELECT accession_number, peptide_name, sequence FROM Peptides WHERE peptide_id = ?", (peptide_id,))
        prow = cur.fetchone()
        accession = None
        peptide_name = None
        sequence = None
        if prow:
            accession = prow["accession_number"]
            peptide_name = prow["peptide_name"]
            sequence = prow["sequence"]
        else:
            # fallback a campos del hit
            peptide_name = h.get("name")
            sequence = h.get("sequence")

        # Normalize key for grouping (use peptide_code / accession)
        key = accession or peptide_name or f"peptide_{peptide_id}"
        if key in seen_accessions:
            log(f"[{idx}/{total}] Saltando duplicado: {key}")
            continue
        seen_accessions.add(key)

        # Log inicio de procesamiento
        id_display = accession if accession else (peptide_name or f"peptide_{peptide_id}")
        # Excluded accessions list
        EXCLUDED_ACCESSIONS = {"P83303","P84507","P0DL84","P84508","D2Y1X8","P0DL72","P0CH54"}
        if accession and accession in EXCLUDED_ACCESSIONS:
            log(f"[{idx}/{total}] Omitido (accession excluido): {accession}")
            continue
        log(f"[{idx}/{total}] Procesando: {id_display}")

        # Recuperar descripción desde Proteins
        description = None
        description_present = False
        if accession:
            cur.execute("SELECT description FROM Proteins WHERE accession_number = ?", (accession,))
            drow = cur.fetchone()
            if drow and drow["description"]:
                description = drow["description"]
                description_present = True

        log(f"  Descripción presente: {description_present}")

        # Buscar si ya hay IC50 en tabla Nav1_7_InhibitorPeptides (metadata existente en BD)
        nav_ic50_db: Optional[Dict[str, Any]] = None
        try:
            cur.execute(
                "SELECT ic50_value, ic50_unit, peptide_code FROM Nav1_7_InhibitorPeptides WHERE accession_number = ? OR peptide_code = ? LIMIT 1",
                (accession, peptide_name),
            )
            navrow = cur.fetchone()
            if navrow:
                nav_ic50_db = {"value": navrow["ic50_value"], "unit": navrow["ic50_unit"], "peptide_code": navrow["peptide_code"]}
        except Exception as e:
            log(f"  Warning: error consultando Nav1_7_InhibitorPeptides: {e}")

        # Analizar description con IA (solo si existe)
        ai_result = None
        if description_present and description:
            try:
                ai_result = analyze_text_for_nav17(description, verbose=False)
                # Imprimir respuesta IA (si es dict, formatear como JSON)
                if isinstance(ai_result, dict):
                    try:
                        pretty = json.dumps(ai_result, ensure_ascii=False, indent=2)
                        log("  AI response (JSON):")
                        for line in pretty.splitlines():
                            log("    " + line)
                    except Exception:
                        log(f"  AI response (raw dict): {ai_result}")
                else:
                    log(f"  AI response (raw): {ai_result}")
            except Exception as e:
                ai_result = {"error": str(e)}
                log(f"  AI error: {e}")
        else:
            log("  No se envió descripción a IA (no disponible).")

        results.append({
            "peptide_id": peptide_id,
            "accession": accession,
            "peptide_name": peptide_name,
            "sequence": sequence,
            "description_present": description_present,
            "description": description if description_present else None,
            "nav1_7_ic50_db": nav_ic50_db,
            "ai_analysis": ai_result,
            "hit_meta": {
                "score": h.get("score"),
                "iC5": h.get("iC5"),
                "gap": h.get("gap"),
            }
        })

    conn.close()
    return results


def main():
    p = argparse.ArgumentParser(description="Export filtered accessions + Nav1.7 AI analysis")
    p.add_argument("--db", default=DB_PATH_DEFAULT, help="Path to SQLite DB")
    p.add_argument("--gap-min", type=int, default=3)
    p.add_argument("--gap-max", type=int, default=6)
    p.add_argument("--require-pair", action="store_true")
    p.add_argument("--out", default="exports/filtered_accessions_nav1_7_analysis.json")
    args = p.parse_args()

    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "process_log.txt")

    # Remove previous log if present (start fresh)
    try:
        if os.path.exists(log_path):
            os.remove(log_path)
    except Exception:
        pass

    data = process_filtered_hits(db_path=args.db, gap_min=args.gap_min, gap_max=args.gap_max, require_pair=args.require_pair, log_path=log_path)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(data)} records to {args.out}")
    print(f"Log written to {log_path}")


if __name__ == "__main__":
    main()