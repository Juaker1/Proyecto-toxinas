from flask import Blueprint, jsonify, request, render_template, redirect, url_for, send_from_directory, current_app
import os

from src.infrastructure.db.sqlite.metadata_repository_sqlite import SqliteMetadataRepository
from src.infrastructure.db.sqlite.toxin_repository_sqlite import SqliteToxinRepository
from src.infrastructure.pdb.pdb_preprocessor_adapter import PDBPreprocessorAdapter
from src.infrastructure.fs.temp_file_service import TempFileService
from src.application.use_cases.calculate_dipole import CalculateDipole, CalculateDipoleInput
from src.infrastructure.graphein.dipole_adapter import DipoleAdapter
from src.infrastructure.db.sqlite.structure_repository_sqlite import SqliteStructureRepository


# Blueprint to serve the main viewer page and legacy-compatible endpoints
legacy_compat = Blueprint("legacy_compat", __name__)

dipole_family_routes = Blueprint("dipole_family_routes", __name__)

_tox_repo = SqliteToxinRepository()
_meta_repo = SqliteMetadataRepository()
_pdb = PDBPreprocessorAdapter()
_tmp = TempFileService()
_structures = SqliteStructureRepository()
_dip = DipoleAdapter()
_dipole_uc = CalculateDipole(_structures, _dip, _meta_repo)

# Resolve absolute path to legacy 'app/static' directory
_CTRL_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CTRL_DIR, "../../../../../.."))
_LEGACY_STATIC_DIR = os.path.join(_PROJECT_ROOT, "app", "static")


@legacy_compat.route("/")
def viewer_root():
    """Render the main viewer page with initial lists (toxinas, nav1_7)."""
    try:
        toxinas = _tox_repo.list_toxins()
        nav1_7 = _tox_repo.list_nav1_7()
    except Exception:
        toxinas, nav1_7 = [], []
    return render_template("viewer.html", toxinas=toxinas, nav1_7=nav1_7)


@legacy_compat.get("/get_pdb/<string:source>/<int:pid>")
def get_pdb(source: str, pid: int):
    try:
        data = _meta_repo.get_complete_toxin_data(source, pid)
        if not data or not data.get("pdb_data"):
            return jsonify({"error": "PDB not found"}), 404
        pdb_data = data["pdb_data"]
        if isinstance(pdb_data, bytes):
            return pdb_data.decode("utf-8"), 200, {"Content-Type": "text/plain"}
        return str(pdb_data), 200, {"Content-Type": "text/plain"}
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@legacy_compat.get("/get_psf/<string:source>/<int:pid>")
def get_psf(source: str, pid: int):
    if source != "nav1_7":
        return jsonify({"error": "PSF files only available for nav1_7"}), 400
    try:
        data = _meta_repo.get_complete_toxin_data(source, pid)
        if not data or not data.get("psf_data"):
            return jsonify({"error": "PSF not found"}), 404
        psf_data = data["psf_data"]
        if isinstance(psf_data, bytes):
            return psf_data.decode("utf-8"), 200, {"Content-Type": "text/plain"}
        return str(psf_data), 200, {"Content-Type": "text/plain"}
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@legacy_compat.get("/get_toxin_name/<string:source>/<int:pid>")
def get_toxin_name(source: str, pid: int):
    try:
        info = _meta_repo.get_toxin_info(source, pid)
        if info:
            return jsonify({"toxin_name": info[0]})
        return jsonify({"toxin_name": f"{source}_{pid}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@legacy_compat.get("/get_protein_graph/<string:source>/<int:pid>")
def legacy_get_graph(source: str, pid: int):
    # Redirect to the v2 graph endpoint with same query params, unless aliases are disabled
    if not current_app.config.get('LEGACY_ALIASES_ENABLED', True):
        return jsonify({"error": "Legacy aliases are disabled"}), 404
    long_threshold = request.args.get("long", type=int)
    threshold = request.args.get("threshold")
    granularity = request.args.get("granularity")
    q = []
    if long_threshold is not None:
        q.append(f"long={long_threshold}")
    if threshold is not None:
        q.append(f"threshold={threshold}")
    if granularity:
        q.append(f"granularity={granularity}")
    qs = ("?" + "&".join(q)) if q else ""
    return redirect(f"/v2/proteins/{source}/{pid}/graph{qs}", code=302)


@legacy_compat.get("/export_residues_xlsx/<string:source>/<int:pid>")
def legacy_export_residues(source: str, pid: int):
    # Redirect to v2 residues export keeping query string
    if not current_app.config.get('LEGACY_ALIASES_ENABLED', True):
        return jsonify({"error": "Legacy aliases are disabled"}), 404
    return redirect(f"/v2/export/residues/{source}/{pid}?" + request.query_string.decode("utf-8"), code=302)


@legacy_compat.get("/export_segments_atomicos_xlsx/<string:source>/<int:pid>")
def legacy_export_segments(source: str, pid: int):
    # For segments, v2 endpoint ignores source and requires atom granularity
    if not current_app.config.get('LEGACY_ALIASES_ENABLED', True):
        return jsonify({"error": "Legacy aliases are disabled"}), 404
    return redirect(f"/v2/export/segments_atomicos/{pid}?" + request.query_string.decode("utf-8"), code=302)


@legacy_compat.get("/export_family_xlsx/<string:family_prefix>")
def legacy_export_family(family_prefix: str):
    if not current_app.config.get('LEGACY_ALIASES_ENABLED', True):
        return jsonify({"error": "Legacy aliases are disabled"}), 404
    return redirect(f"/v2/export/family/{family_prefix}?" + request.query_string.decode("utf-8"), code=302)


@legacy_compat.get("/export_wt_comparison_xlsx/<string:wt_family>")
def legacy_export_wt(wt_family: str):
    if not current_app.config.get('LEGACY_ALIASES_ENABLED', True):
        return jsonify({"error": "Legacy aliases are disabled"}), 404
    return redirect(f"/v2/export/wt_comparison/{wt_family}?" + request.query_string.decode("utf-8"), code=302)


@legacy_compat.post("/calculate_dipole_from_db/<string:source>/<int:pid>")
def legacy_calculate_dipole(source: str, pid: int):
    try:
        if source != "nav1_7":
            return jsonify({"success": False, "error": "Dipole solo disponible para nav1_7"}), 400
        res = _dipole_uc.execute(CalculateDipoleInput(source=source, pid=pid))
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dipole_family_routes.get("/dipole_family_analysis")
def dipole_family_analysis():
    """Serve dipole family analysis page (template copied for v2)."""
    return render_template("dipole_families.html")

# Optional v2-friendly path to the same page
@dipole_family_routes.get("/v2/dipole/families")
def dipole_family_analysis_v2():
    return render_template("dipole_families.html")


# Legacy API alias used by dipole_family_analysis.js
@dipole_family_routes.get("/api/family-dipoles/<string:family_name>")
def legacy_api_family_dipoles(family_name: str):
    if not current_app.config.get('LEGACY_ALIASES_ENABLED', True):
        return jsonify({"error": "Legacy aliases are disabled"}), 404
    return redirect(f"/v2/family-dipoles/{family_name}?" + request.query_string.decode("utf-8"), code=302)


@legacy_compat.get("/legacy-static/<path:filename>")
def legacy_static(filename: str):
    """Serve files from legacy app/static under a namespaced path."""
    return send_from_directory(_LEGACY_STATIC_DIR, filename)
