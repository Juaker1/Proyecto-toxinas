from flask import Blueprint, jsonify, request, send_file
import io
import zipfile
import math
import os
import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, Any, Iterable, Tuple, List

from extractors.toxins_filter import search_toxins
from src.infrastructure.graphein.dipole_adapter import DipoleAdapter


motif_dipoles_v2 = Blueprint("motif_dipoles_v2", __name__)

# Defaults (overridden via configure_motif_dipoles_dependencies)
_DB_PATH: str = "database/toxins.db"
_FILTERED_DIR: Path = Path("pdbs/filtered_psfs").resolve()
_DIP = None  # type: DipoleAdapter
_REFERENCE_PDB: Optional[Path] = None
_REFERENCE_PSF: Optional[Path] = None
_REFERENCE_CACHE: Optional[Dict[str, Any]] = None
_REFERENCE_DB_CACHE: Dict[str, Dict[str, Any]] = {}
_REFERENCE_OPTIONS_CACHE: Optional[List[Dict[str, Any]]] = None

_AXES = ("x", "y", "z")
_DEFAULT_DB_REFERENCE_CODE = "μ-TRTX-Cg4a"
_REFERENCE_WT_SEQUENCE = "ECLEIFKACNPSNDQCCKSSKLVCSRKTRWCAYQI"


def configure_motif_dipoles_dependencies(
    *,
    db_path: str,
    filtered_dir: str,
    dipole_adapter: DipoleAdapter,
    reference_pdb: Optional[str] = None,
    reference_psf: Optional[str] = None,
):
    global _DB_PATH, _FILTERED_DIR, _DIP, _REFERENCE_PDB, _REFERENCE_PSF, _REFERENCE_CACHE, _REFERENCE_DB_CACHE, _REFERENCE_OPTIONS_CACHE
    _DB_PATH = db_path
    _FILTERED_DIR = Path(filtered_dir).resolve()
    _DIP = dipole_adapter
    _REFERENCE_CACHE = None
    _REFERENCE_DB_CACHE = {}
    _REFERENCE_OPTIONS_CACHE = None

    if reference_pdb:
        ref_path = Path(reference_pdb)
        _REFERENCE_PDB = ref_path.resolve()
    else:
        _REFERENCE_PDB = None

    if reference_psf:
        _REFERENCE_PSF = Path(reference_psf).resolve()
    elif _REFERENCE_PDB is not None:
        candidate = _REFERENCE_PDB.with_suffix(".psf")
        _REFERENCE_PSF = candidate if candidate.exists() else None
    else:
        _REFERENCE_PSF = None


def _compute_dipole_from_files(pdb_path: Path, psf_path: Path):
    if _DIP is None:
        raise RuntimeError("Dipole service not configured")
    dip = _DIP.calculate_dipole_from_files(str(pdb_path), str(psf_path))
    pdb_text = pdb_path.read_text(encoding="utf-8", errors="ignore")
    return {"dipole": dip, "pdb_text": pdb_text}


def _normalize_vector(seq: Iterable[float]) -> Optional[Tuple[float, float, float]]:
    try:
        values = [float(x) for x in seq]
    except (TypeError, ValueError):
        return None
    if len(values) < 3:
        return None
    x, y, z = values[:3]
    norm = math.sqrt(x * x + y * y + z * z)
    if norm == 0:
        return None
    return (x / norm, y / norm, z / norm)


def _get_normalized_vector(dipole: Dict[str, Any]) -> Optional[Tuple[float, float, float]]:
    if not dipole:
        return None
    vec = dipole.get("normalized") or dipole.get("vector")
    if vec is None:
        return None
    if isinstance(vec, dict):
        if all(ax in vec for ax in _AXES):
            seq = [vec[ax] for ax in _AXES]
        else:
            seq = list(vec.values())
    else:
        seq = vec
    normalized = _normalize_vector(seq)
    return normalized


def _compute_axis_angles(vec: Optional[Tuple[float, float, float]]) -> Optional[Dict[str, float]]:
    if vec is None:
        return None
    angles: Dict[str, float] = {}
    for axis, component in zip(_AXES, vec):
        comp = max(-1.0, min(1.0, component))
        angles[axis] = math.degrees(math.acos(comp))
    return angles


def _compute_orientation_metrics(
    vec: Optional[Tuple[float, float, float]],
    ref_vec: Optional[Tuple[float, float, float]],
    angles: Optional[Dict[str, float]],
    ref_angles: Optional[Dict[str, float]],
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "angle_diff_vs_reference": None,
        "orientation_score_deg": None,
        "vector_angle_vs_reference_deg": None,
        "angle_diff_l2_deg": None,
        "angle_diff_l1_deg": None,
    }
    if vec is None or ref_vec is None:
        return metrics

    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(vec, ref_vec))))
    vector_angle = math.degrees(math.acos(dot))
    metrics["vector_angle_vs_reference_deg"] = vector_angle
    metrics["orientation_score_deg"] = vector_angle

    if angles and ref_angles:
        axis_diffs = {axis: abs(angles[axis] - ref_angles[axis]) for axis in _AXES}
        metrics["angle_diff_vs_reference"] = axis_diffs
        l2 = math.sqrt(sum(val * val for val in axis_diffs.values()))
        l1 = sum(axis_diffs.values())
        metrics["angle_diff_l2_deg"] = l2
        metrics["angle_diff_l1_deg"] = l1
    return metrics


def _convert_ic50_to_nm(value: Any, unit: Optional[str]) -> Optional[float]:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    unit_clean = (unit or "").strip().lower().replace("µ", "u").replace("μ", "u")
    unit_clean = unit_clean.replace("nanomolar", "nm").replace("micromolar", "um").replace("picomolar", "pm")
    factors = {
        "nm": 1.0,
        "n m": 1.0,
        "um": 1e3,
        "u m": 1e3,
        "pm": 1e-3,
        "p m": 1e-3,
        "mm": 1e6,
        "m m": 1e6,
    }
    factor = factors.get(unit_clean)
    if factor is None:
        if unit_clean.endswith("nm"):
            factor = 1.0
        elif unit_clean.endswith("um"):
            factor = 1e3
        elif unit_clean.endswith("pm"):
            factor = 1e-3
        elif unit_clean.endswith("mm"):
            factor = 1e6
        else:
            factor = 1.0
    return numeric_value * factor


def _get_reference_options() -> List[Dict[str, Any]]:
    global _REFERENCE_OPTIONS_CACHE
    if _REFERENCE_OPTIONS_CACHE is not None:
        return [dict(opt) for opt in _REFERENCE_OPTIONS_CACHE]

    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, peptide_code, ic50_value, ic50_unit
        FROM Nav1_7_InhibitorPeptides
        ORDER BY peptide_code
        """
    )
    rows = cur.fetchall()
    conn.close()

    entries = []
    finite_values = []
    for row in rows:
        code = row["peptide_code"]
        ic50_value = row["ic50_value"]
        ic50_unit = row["ic50_unit"]
        try:
            ic50_value_numeric = float(ic50_value) if ic50_value is not None else None
        except (TypeError, ValueError):
            ic50_value_numeric = None
        ic50_nm = _convert_ic50_to_nm(ic50_value_numeric, ic50_unit) if ic50_value_numeric is not None else None
        if ic50_nm is not None:
            finite_values.append(ic50_nm)
        entries.append({
            "value": code,
            "label": code,
            "peptide_code": code,
            "ic50_value": ic50_value_numeric,
            "ic50_unit": ic50_unit,
            "ic50_nm": ic50_nm,
        })

    options: List[Dict[str, Any]] = []

    if finite_values:
        min_value = min(finite_values)
        max_value = max(finite_values)
    else:
        min_value = max_value = None

    normalized_entries: List[Dict[str, Any]] = []
    for entry in entries:
        ic50_nm = entry["ic50_nm"]
        if ic50_nm is not None and min_value is not None and max_value is not None:
            if max_value == min_value:
                normalized = 0.0
            else:
                normalized = (ic50_nm - min_value) / (max_value - min_value)
        else:
            normalized = None
        normalized_entries.append({
            **entry,
            "normalized_ic50": normalized,
        })

    normalized_entries.sort(
        key=lambda opt: (
            opt["normalized_ic50"] is None,
            opt["normalized_ic50"] if opt["normalized_ic50"] is not None else float("inf"),
            opt["peptide_code"],
        )
    )

    for entry in normalized_entries:
        options.append({
            "value": entry["value"],
            "label": entry["label"],
            "peptide_code": entry["peptide_code"],
            "ic50_value": entry["ic50_value"],
            "ic50_unit": entry["ic50_unit"],
            "normalized_ic50": entry["normalized_ic50"],
            "ic50_nm": entry["ic50_nm"],
        })

    _REFERENCE_OPTIONS_CACHE = options
    return [dict(opt) for opt in options]


# Load AI-exported JSON map for ic50 detection (accession -> has_ic50)
_EXPORTS_AI_PATH = os.path.join(os.getcwd(), "exports", "filtered_accessions_nav1_7_analysis.json")
_AI_IC50_CACHE = None

def _load_ai_ic50_map():
    global _AI_IC50_CACHE
    if _AI_IC50_CACHE is not None:
        return _AI_IC50_CACHE
    mapping = {}
    try:
        if os.path.exists(_EXPORTS_AI_PATH):
            with open(_EXPORTS_AI_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                for entry in data:
                    acc = entry.get("accession") or entry.get("accession_number")
                    if not acc:
                        continue
                    has_ic50 = False
                    ai = entry.get("ai_analysis") or entry.get("analysis") or {}
                    if isinstance(ai, dict):
                        ic50_vals = ai.get("ic50_values") or []
                        if isinstance(ic50_vals, list):
                            for v in ic50_vals:
                                if not isinstance(v, dict):
                                    continue
                                if v.get("value") is not None:
                                    has_ic50 = True
                                    break
                                if v.get("value_min") is not None and v.get("value_max") is not None:
                                    has_ic50 = True
                                    break
                    mapping[str(acc)] = has_ic50
    except Exception:
        mapping = {}
    _AI_IC50_CACHE = mapping
    return mapping


def _convert_unit_to_nm(value: Any, unit: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return _convert_ic50_to_nm(value, unit)
    except Exception:
        return None


def _load_ai_ic50_details_map():
    """Return accession -> dict with keys:
    {
      'value_nm': Optional[float],
      'min_nm': Optional[float],
      'max_nm': Optional[float],
      'avg_nm': Optional[float],
    }
    using the exported AI JSON (ai_analysis.ic50_values).
    """
    details: Dict[str, Dict[str, Optional[float]]] = {}
    try:
        if not os.path.exists(_EXPORTS_AI_PATH):
            return details
        with open(_EXPORTS_AI_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            return details
        for entry in data:
            acc = entry.get("accession") or entry.get("accession_number")
            if not acc:
                continue
            ai = entry.get("ai_analysis") or entry.get("analysis") or {}
            if not isinstance(ai, dict):
                continue
            ic50_vals = ai.get("ic50_values") or []
            if not isinstance(ic50_vals, list):
                continue
            # init
            rec = {"value_nm": None, "min_nm": None, "max_nm": None, "avg_nm": None}
            for v in ic50_vals:
                if not isinstance(v, dict):
                    continue
                # Single value
                if rec["value_nm"] is None and v.get("value") is not None:
                    val_nm = _convert_unit_to_nm(v.get("value"), v.get("unit"))
                    if val_nm is not None:
                        rec["value_nm"] = val_nm
                # Range value
                if rec["min_nm"] is None and rec["max_nm"] is None and (
                    v.get("value_min") is not None and v.get("value_max") is not None
                ):
                    min_nm = _convert_unit_to_nm(v.get("value_min"), v.get("unit_min") or v.get("unit"))
                    max_nm = _convert_unit_to_nm(v.get("value_max"), v.get("unit_max") or v.get("unit"))
                    if min_nm is not None and max_nm is not None:
                        rec["min_nm"] = float(min_nm)
                        rec["max_nm"] = float(max_nm)
                        rec["avg_nm"] = (rec["min_nm"] + rec["max_nm"]) / 2.0
                # If we already have both single and range, we can stop early
                if rec["value_nm"] is not None and rec["avg_nm"] is not None:
                    break
            details[str(acc)] = rec
        return details
    except Exception:
        return details


def _lookup_option_by_code(peptide_code: str) -> Optional[Dict[str, Any]]:
    for option in _get_reference_options():
        if option["value"] == peptide_code:
            return option
    return None


def _load_reference_from_files() -> Optional[Dict[str, Any]]:
    global _REFERENCE_CACHE
    if _REFERENCE_PDB is None or _REFERENCE_PSF is None:
        return None
    if not _REFERENCE_PDB.exists() or not _REFERENCE_PSF.exists():
        return None
    if _REFERENCE_CACHE is None:
        cache = _compute_dipole_from_files(_REFERENCE_PDB, _REFERENCE_PSF)
        cache.update({
            "source": "filesystem",
            "pdb_path": str(_REFERENCE_PDB),
            "psf_path": str(_REFERENCE_PSF),
            "peptide_code": "WT",
            "sequence": _REFERENCE_WT_SEQUENCE,
            "display_name": "Proteína WT",
            "normalized_ic50": None,
            "ic50_value": None,
            "ic50_unit": None,
            "ic50_value_nm": None,
        })
        vec = _get_normalized_vector(cache.get("dipole"))
        if vec:
            cache["normalized_vector"] = vec
            angles = _compute_axis_angles(vec)
            if angles:
                cache["angles_deg"] = angles
                cache["angle_with_z_deg"] = angles.get("z")
        _REFERENCE_CACHE = cache
    return _REFERENCE_CACHE


def _fetch_reference_row(db_path: str, peptide_code: str = "μ-TRTX-Cg4a"):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, peptide_code, pdb_blob, psf_blob, ic50_value, ic50_unit
            FROM Nav1_7_InhibitorPeptides
            WHERE peptide_code = ?
            """,
            (peptide_code,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def _load_reference_from_db(peptide_code: str = "μ-TRTX-Cg4a") -> Optional[Dict[str, Any]]:
    global _REFERENCE_DB_CACHE
    if peptide_code in _REFERENCE_DB_CACHE:
        return _REFERENCE_DB_CACHE[peptide_code]

    row = _fetch_reference_row(_DB_PATH, peptide_code=peptide_code)
    if not row:
        return None
    pid, code, pdb_blob, psf_blob, ic50_value, ic50_unit = row
    if not pdb_blob or not psf_blob or _DIP is None:
        return None
    res = _DIP.process_dipole_calculation(pdb_blob, psf_blob)
    if not res.get("success"):
        return None
    pdb_text = (
        pdb_blob.decode("utf-8", errors="replace")
        if isinstance(pdb_blob, (bytes, bytearray))
        else str(pdb_blob)
    )
    cache = {
        "source": "database",
        "peptide_code": code,
        "pid": pid,
        "dipole": res.get("dipole"),
        "pdb_text": pdb_text,
        "ic50_value": float(ic50_value) if ic50_value is not None else None,
        "ic50_unit": ic50_unit,
        "ic50_value_nm": _convert_ic50_to_nm(ic50_value, ic50_unit) if ic50_value is not None else None,
        "display_name": code,
    }
    # intentar recuperar secuencia asociada al peptide_code desde la tabla Nav1_7_InhibitorPeptides
    try:
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT sequence FROM Nav1_7_InhibitorPeptides WHERE peptide_code = ?", (code,))
        prow = cur.fetchone()
        if prow and "sequence" in prow.keys():
            cache["sequence"] = prow["sequence"]
    except Exception:
        # no crítico; la secuencia puede no estar disponible
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    vec = _get_normalized_vector(cache.get("dipole"))
    if vec:
        cache["normalized_vector"] = vec
        angles = _compute_axis_angles(vec)
        if angles:
            cache["angles_deg"] = angles
            cache["angle_with_z_deg"] = angles.get("z")
    option_details = _lookup_option_by_code(code)
    if option_details:
        cache["normalized_ic50"] = option_details.get("normalized_ic50")
    _REFERENCE_DB_CACHE[peptide_code] = cache
    return cache


def _get_reference_data(peptide_code: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], str]:
    requested = (peptide_code or "").strip()
    
    # Si no se especifica un código, usar la primera opción disponible
    if not requested:
        options = _get_reference_options()
        if options and len(options) > 0:
            first_option = options[0]
            requested = first_option.get("value") or first_option.get("peptide_code")
            if not requested:
                return None, ""
        else:
            return None, ""
    
    selected_code = requested
    ref = _load_reference_from_db(selected_code)
    return ref, selected_code


def _get_angle_from_dipole(dipole: Dict[str, Any]) -> Optional[float]:
    if not dipole:
        return None
    angle_block = dipole.get("angle_with_z_axis")
    if isinstance(angle_block, dict):
        angle = angle_block.get("degrees")
        if angle is not None:
            try:
                return float(angle)
            except (TypeError, ValueError):
                return None
    return None


@motif_dipoles_v2.get("/v2/motif_dipoles/reference")
def motif_reference():
    try:
        requested_code = request.args.get("peptide_code")
        ref, selected_code = _get_reference_data(requested_code)
        if not ref:
            return jsonify({"error": "Referencia no encontrada"}), 404
        response = {
            "dipole": ref.get("dipole"),
            "pdb_text": ref.get("pdb_text"),
            "source": ref.get("source"),
            "pdb_path": ref.get("pdb_path"),
            "psf_path": ref.get("psf_path"),
            "selected_reference_code": selected_code,
            "sequence": ref.get("sequence"),
        }
        angles = ref.get("angles_deg")
        if not angles:
            vec = _get_normalized_vector(ref.get("dipole"))
            angles = _compute_axis_angles(vec)
        if angles:
            response["angles_deg"] = angles
            response["angle_with_z_deg"] = angles.get("z")
        if ref.get("normalized_vector"):
            response["normalized_vector"] = ref.get("normalized_vector")
        option_meta = _lookup_option_by_code(selected_code) or {}
        response.update({
            "peptide_code": selected_code,
            "display_name": ref.get("display_name") or option_meta.get("label") or selected_code,
            "normalized_ic50": ref.get("normalized_ic50", option_meta.get("normalized_ic50")),
            "ic50_value": ref.get("ic50_value", option_meta.get("ic50_value")),
            "ic50_unit": ref.get("ic50_unit", option_meta.get("ic50_unit")),
            "ic50_nm": ref.get("ic50_value_nm", option_meta.get("ic50_nm")),
        })
        if ref.get("source") == "database":
            response.update({
                "pid": ref.get("pid"),
            })
        response["reference_options"] = _get_reference_options()
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@motif_dipoles_v2.get("/v2/motif_dipoles/item/download")
def motif_item_download():
    """Descarga PDB y PSF para una toxina filtrada dada su accession (desde _FILTERED_DIR).
    Devuelve un zip con <accession>.pdb y <accession>.psf si existen.
    """
    try:
        accession = (request.args.get("accession") or "").strip()
        # Excluded accessions - do not allow download or visualization
        EXCLUDED_ACCESSIONS = {"P83303", "P84507", "P0DL84", "P84508", "D2Y1X8", "P0DL72", "P0CH54"}
        if accession in EXCLUDED_ACCESSIONS:
            return jsonify({"error": "Accession restringido"}), 403
        if not accession:
            return jsonify({"error": "Parámetro 'accession' requerido"}), 400

        pdb_path = _FILTERED_DIR / f"{accession}.pdb"
        psf_path = _FILTERED_DIR / f"{accession}.psf"

        if not pdb_path.exists() and not psf_path.exists():
            return jsonify({"error": "Archivos PDB/PSF no encontrados para el accession solicitado"}), 404

        pdb_bytes = pdb_path.read_bytes() if pdb_path.exists() else None
        psf_bytes = psf_path.read_bytes() if psf_path.exists() else None

        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zf:
            if pdb_bytes:
                zf.writestr(f"{accession}.pdb", pdb_bytes)
            if psf_bytes:
                zf.writestr(f"{accession}.psf", psf_bytes)
        zip_io.seek(0)

        return send_file(
            zip_io,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{accession}_files.zip",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@motif_dipoles_v2.get("/v2/motif_dipoles/reference/download")
def motif_reference_download():
    """Devuelve un zip con PDB y PSF de la referencia seleccionada.
    Si la referencia es 'WT' y está en filesystem usa las rutas; si está en DB
    lee los blobs y empaqueta ambos archivos en un zip en memoria.
    """
    try:
        requested_code = request.args.get("peptide_code")
        ref, selected_code = _get_reference_data(requested_code)
        if not ref:
            return jsonify({"error": "Referencia no encontrada"}), 404

        pdb_bytes = None
        psf_bytes = None

        # Intentar leer desde rutas si están disponibles
        pdb_path = ref.get("pdb_path")
        psf_path = ref.get("psf_path")
        if pdb_path:
            p = Path(pdb_path)
            if p.exists():
                pdb_bytes = p.read_bytes()
        if psf_path:
            p2 = Path(psf_path)
            if p2.exists():
                psf_bytes = p2.read_bytes()

        # Si no hay bytes, intentar obtener desde objetos en memoria
        if not pdb_bytes and ref.get("pdb_text"):
            pdb_bytes = str(ref.get("pdb_text")).encode("utf-8")

        # Si todavía falta alguno y tenemos pid, consultar DB para blobs
        if (not pdb_bytes or not psf_bytes) and ref.get("pid"):
            row = _fetch_reference_row(_DB_PATH, peptide_code=selected_code)
            if row:
                # row layout: id, peptide_code, pdb_blob, psf_blob, ic50_value, ic50_unit
                try:
                    pdb_blob = row[2]
                    psf_blob = row[3]
                except Exception:
                    pdb_blob = None
                    psf_blob = None
                if pdb_blob and not pdb_bytes:
                    pdb_bytes = pdb_blob if isinstance(pdb_blob, (bytes, bytearray)) else str(pdb_blob).encode("utf-8")
                if psf_blob and not psf_bytes:
                    psf_bytes = psf_blob if isinstance(psf_blob, (bytes, bytearray)) else str(psf_blob).encode("utf-8")

        if not pdb_bytes and not psf_bytes:
            return jsonify({"error": "Archivos PDB/PSF no disponibles para la referencia"}), 404

        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zf:
            if pdb_bytes:
                zf.writestr(f"{selected_code}.pdb", pdb_bytes)
            if psf_bytes:
                zf.writestr(f"{selected_code}.psf", psf_bytes)
        zip_io.seek(0)

        return send_file(
            zip_io,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{selected_code}_reference_files.zip",
        )
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
        requested_reference_code = request.args.get("reference_code") or request.args.get("peptide_code")
        reference, selected_reference_code = _get_reference_data(requested_reference_code)
        reference_vec = None
        reference_angles = None
        ref_angle_z = None
        if reference:
            reference_vec = reference.get("normalized_vector") or _get_normalized_vector(reference.get("dipole"))
            reference_angles = reference.get("angles_deg") or _compute_axis_angles(reference_vec)
            if reference_angles:
                ref_angle_z = reference_angles.get("z")
            else:
                ref_angle_z = _get_angle_from_dipole(reference.get("dipole"))
        else:
            ref_angle_z = None

        # Enriquecer con accession_number/peptide_name
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Accessions to exclude from visualizers
        EXCLUDED_ACCESSIONS = {"P83303", "P84507", "P0DL84", "P84508", "D2Y1X8", "P0DL72", "P0CH54"}
        items = []
        # Preload AI details map once
        ai_details_map = _load_ai_ic50_details_map()
        for h in hits:
            peptide_id = h.get("peptide_id") if isinstance(h, dict) else h
            cur.execute("SELECT accession_number, peptide_name, sequence FROM Peptides WHERE peptide_id = ?", (peptide_id,))
            row = cur.fetchone()
            if not row:
                continue
            acc = row["accession_number"]
            # Skip explicitly excluded accessions even if files exist
            if acc and acc in EXCLUDED_ACCESSIONS:
                continue
            name = row["peptide_name"]
            sequence = row["sequence"] if "sequence" in row.keys() else ""
            pdb_path = _FILTERED_DIR / f"{acc}.pdb"
            psf_path = _FILTERED_DIR / f"{acc}.psf"
            if not pdb_path.exists() or not psf_path.exists():
                # saltar si no está disponible aún
                continue
            comp = _compute_dipole_from_files(pdb_path, psf_path)
            dipole = comp["dipole"]
            vec = _get_normalized_vector(dipole)
            angles = _compute_axis_angles(vec) if vec else None
            metrics = _compute_orientation_metrics(vec, reference_vec, angles, reference_angles)
            item_angle_z = angles.get("z") if angles else _get_angle_from_dipole(dipole)
            # Check Nav1.7 IC50 metadata (if present)
            nav1_7_has_ic50 = False
            nav1_7_ic50_value = None
            nav1_7_ic50_unit = None
            try:
                cur.execute(
                    "SELECT ic50_value, ic50_unit FROM Nav1_7_InhibitorPeptides WHERE accession_number = ? OR peptide_code = ? LIMIT 1",
                    (acc, name),
                )
                nrow = cur.fetchone()
                if nrow:
                    nav1_7_ic50_value = nrow["ic50_value"]
                    nav1_7_ic50_unit = nrow["ic50_unit"] if "ic50_unit" in nrow.keys() else None
                    nav1_7_has_ic50 = nav1_7_ic50_value is not None
            except Exception:
                # non-critical: absence of metadata shouldn't break rendering
                pass
            # Also consult AI-exported JSON cache for ic50 detection
            try:
                ai_map = _load_ai_ic50_map()
                if acc and ai_map.get(str(acc)):
                    nav1_7_has_ic50 = True
            except Exception:
                pass
            # Convert to nM for plotting when possible
            nav1_7_ic50_value_nm = None
            try:
                if nav1_7_ic50_value is not None:
                    nav1_7_ic50_value_nm = _convert_ic50_to_nm(nav1_7_ic50_value, nav1_7_ic50_unit)
            except Exception:
                nav1_7_ic50_value_nm = None

            # AI-derived detailed values (single/range)
            ai_value_nm = None
            ai_min_nm = None
            ai_max_nm = None
            ai_avg_nm = None
            if acc and acc in ai_details_map:
                det = ai_details_map.get(acc) or {}
                ai_value_nm = det.get("value_nm")
                ai_min_nm = det.get("min_nm")
                ai_max_nm = det.get("max_nm")
                ai_avg_nm = det.get("avg_nm")
                if any(v is not None for v in (ai_value_nm, ai_min_nm, ai_max_nm, ai_avg_nm)):
                    nav1_7_has_ic50 = True
            # (Already consulted ai_map above after DB read and before conversion)

            if metrics.get("angle_diff_vs_reference") is None and ref_angle_z is not None and item_angle_z is not None:
                z_delta = abs(item_angle_z - ref_angle_z)
                metrics["angle_diff_vs_reference"] = {"x": None, "y": None, "z": z_delta}
                metrics["orientation_score_deg"] = z_delta if metrics.get("orientation_score_deg") is None else metrics["orientation_score_deg"]
                metrics["vector_angle_vs_reference_deg"] = metrics.get("vector_angle_vs_reference_deg") or z_delta

            items.append({
                "peptide_id": peptide_id,
                "accession_number": acc,
                "name": name,
                "sequence": sequence,
                "dipole": dipole,
                "pdb_text": comp["pdb_text"],
                "normalized_vector": list(vec) if vec else None,
                "angles_deg": angles,
                "angle_with_z_deg": item_angle_z,
                "angle_diff_vs_reference": metrics.get("angle_diff_vs_reference"),
                "orientation_score_deg": metrics.get("orientation_score_deg"),
                "vector_angle_vs_reference_deg": metrics.get("vector_angle_vs_reference_deg"),
                "angle_diff_l2_deg": metrics.get("angle_diff_l2_deg"),
                "angle_diff_l1_deg": metrics.get("angle_diff_l1_deg"),
                # Nav1.7 metadata
                "nav1_7_has_ic50": nav1_7_has_ic50,
                "nav1_7_ic50_value": nav1_7_ic50_value,
                "nav1_7_ic50_unit": nav1_7_ic50_unit,
                "nav1_7_ic50_value_nm": nav1_7_ic50_value_nm,
                # AI-derived values
                "ai_ic50_value_nm": ai_value_nm,
                "ai_ic50_min_nm": ai_min_nm,
                "ai_ic50_max_nm": ai_max_nm,
                "ai_ic50_avg_nm": ai_avg_nm,
            })
        conn.close()

        if reference_vec is not None:
            items.sort(key=lambda it: (
                it.get("orientation_score_deg") is None,
                it.get("orientation_score_deg", math.inf),
                it.get("angle_diff_l2_deg", math.inf),
            ))
        elif ref_angle_z is not None:
            items.sort(key=lambda it: (
                it.get("angle_diff_vs_reference") is None,
                (it.get("angle_diff_vs_reference") or {}).get("z", math.inf),
            ))

        total = len(items)
        if total == 0:
            return jsonify({
                "count": 0,
                "page": 1,
                "page_size": page_size,
                "items": [],
                "reference": {
                    "angle_with_z_deg": ref_angle_z,
                    "angles_deg": reference_angles,
                    "source": reference.get("source") if reference else None,
                    "pdb_path": reference.get("pdb_path") if reference else None,
                    "psf_path": reference.get("psf_path") if reference else None,
                    "normalized_vector": list(reference_vec) if reference_vec else None,
                    "peptide_code": selected_reference_code if reference else None,
                    "display_name": reference.get("display_name") if reference else None,
                    "normalized_ic50": reference.get("normalized_ic50") if reference else None,
                    "ic50_value": reference.get("ic50_value") if reference else None,
                    "ic50_unit": reference.get("ic50_unit") if reference else None,
                    "ic50_nm": reference.get("ic50_value_nm") if reference else None,
                },
                "reference_options": _get_reference_options(),
            })

        max_page = max(1, math.ceil(total / page_size))
        page = min(page, max_page)
        start = (page - 1) * page_size
        end = min(total, start + page_size)
        paged_items = items[start:end]

        return jsonify({
            "count": total,
            "page": page,
            "page_size": page_size,
            "items": paged_items,
            "reference": {
                "angle_with_z_deg": ref_angle_z,
                "angles_deg": reference_angles,
                "source": reference.get("source") if reference else None,
                "pdb_path": reference.get("pdb_path") if reference else None,
                "psf_path": reference.get("psf_path") if reference else None,
                "normalized_vector": list(reference_vec) if reference_vec else None,
                "peptide_code": selected_reference_code if reference else None,
                "display_name": reference.get("display_name") if reference else None,
                "normalized_ic50": reference.get("normalized_ic50") if reference else None,
                "ic50_value": reference.get("ic50_value") if reference else None,
                "ic50_unit": reference.get("ic50_unit") if reference else None,
                "ic50_nm": reference.get("ic50_value_nm") if reference else None,
            },
            "reference_options": _get_reference_options(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
