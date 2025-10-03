from flask import Blueprint, jsonify, request
import os
import sqlite3
from pathlib import Path

from extractors.toxins_filter import search_toxins
from src.infrastructure.graphein.dipole_adapter import DipoleAdapter


motif_dipoles_v2 = Blueprint("motif_dipoles_v2", __name__)

# Defaults (overridden via configure_motif_dipoles_dependencies)
_DB_PATH: str = "database/toxins.db"
_FILTERED_DIR: Path = Path("tools/filtered").resolve()
_DIP = None  # type: DipoleAdapter


def configure_motif_dipoles_dependencies(*, db_path: str, filtered_dir: str, dipole_adapter: DipoleAdapter):
    global _DB_PATH, _FILTERED_DIR, _DIP
    _DB_PATH = db_path
    _FILTERED_DIR = Path(filtered_dir).resolve()
    _DIP = dipole_adapter


def _compute_dipole_from_files(pdb_path: Path, psf_path: Path):
    if _DIP is None:
        raise RuntimeError("Dipole service not configured")
    dip = _DIP.calculate_dipole_from_files(str(pdb_path), str(psf_path))
    pdb_text = pdb_path.read_text(encoding="utf-8", errors="ignore")
    return {"dipole": dip, "pdb_text": pdb_text}


def _fetch_reference_row(db_path: str, peptide_code: str = "μ-TRTX-Cg4a"):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, peptide_code, pdb_blob, psf_blob
            FROM Nav1_7_InhibitorPeptides
            WHERE peptide_code = ?
            """,
            (peptide_code,),
        )
        return cur.fetchone()
    finally:
        conn.close()


@motif_dipoles_v2.get("/v2/motif_dipoles/reference")
def motif_reference():
    try:
        row = _fetch_reference_row(_DB_PATH)
        if not row:
            return jsonify({"error": "Referencia no encontrada"}), 404
        pid, code, pdb_blob, psf_blob = row
        if not pdb_blob or not psf_blob:
            return jsonify({"error": "PDB/PSF de referencia no disponibles"}), 404
        if _DIP is None:
            return jsonify({"error": "Servicio de dipolo no configurado"}), 500
        # Calcular dipolo usando bytes en memoria
        res = _DIP.process_dipole_calculation(pdb_blob, psf_blob)
        if not res.get("success"):
            return jsonify({"error": "No se pudo calcular dipolo de referencia"}), 500
        pdb_text = (
            pdb_blob.decode("utf-8", errors="replace")
            if isinstance(pdb_blob, (bytes, bytearray))
            else str(pdb_blob)
        )
        return jsonify({
            "peptide_code": code,
            "pid": pid,
            "dipole": res.get("dipole"),
            "pdb_text": pdb_text,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@motif_dipoles_v2.get("/v2/motif_dipoles/page")
def motif_page():
    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = max(1, min(24, int(request.args.get("page_size", 6))))
        gap_min = int(request.args.get("gap_min", 3))
        gap_max = int(request.args.get("gap_max", 6))
        require_pair = request.args.get("require_pair", "0") in ("1", "true", "True")

        hits = search_toxins(gap_min=gap_min, gap_max=gap_max, require_pair=require_pair, db_path=_DB_PATH)
        total = len(hits)
        start = (page - 1) * page_size
        end = min(total, start + page_size)
        if start >= total:
            return jsonify({"count": total, "page": page, "page_size": page_size, "items": []})

        # Enriquecer con accession_number/peptide_name
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        items = []
        for h in hits[start:end]:
            peptide_id = h.get("peptide_id") if isinstance(h, dict) else h
            cur.execute("SELECT accession_number, peptide_name FROM Peptides WHERE peptide_id = ?", (peptide_id,))
            row = cur.fetchone()
            if not row:
                continue
            acc = row["accession_number"]
            name = row["peptide_name"]
            pdb_path = _FILTERED_DIR / f"{acc}.pdb"
            psf_path = _FILTERED_DIR / f"{acc}.psf"
            if not pdb_path.exists() or not psf_path.exists():
                # saltar si no está disponible aún
                continue
            comp = _compute_dipole_from_files(pdb_path, psf_path)
            items.append({
                "peptide_id": peptide_id,
                "accession_number": acc,
                "name": name,
                "dipole": comp["dipole"],
                "pdb_text": comp["pdb_text"],
            })
        conn.close()

        return jsonify({"count": total, "page": page, "page_size": page_size, "items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
