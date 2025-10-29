from flask import Blueprint, jsonify, request, render_template
import os, importlib, json

import sqlite3
from extractors.toxins_filter import search_toxins

# Path to AI-exported JSON that may contain ic50 extraction results per accession
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
                    acc = entry.get("accession") or entry.get("accession_number") or entry.get("accession_number")
                    # support alternative keys
                    if not acc:
                        # some entries might use peptide_name; skip those
                        continue
                    has_ic50 = False
                    ai = entry.get("ai_analysis") or entry.get("analysis") or {}
                    if isinstance(ai, dict):
                        ic50_vals = ai.get("ic50_values") or ai.get("ic50_values_extracted") or []
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

toxin_filter_v2 = Blueprint("toxin_filter", __name__)

# Allow overriding db path via central config if available
try:
    _cfg_mod = importlib.import_module('src.config')
    _CFG = getattr(_cfg_mod, 'load_app_config')(os.getcwd())
    _DB_PATH = getattr(_CFG, 'db_path', 'database/toxins.db')
except Exception:
    _DB_PATH = 'database/toxins.db'


@toxin_filter_v2.get("/v2/toxin_filter")
def toxin_filter_api():
    try:
        gap_min = int(request.args.get("gap_min", 3))
        gap_max = int(request.args.get("gap_max", 6))
        require_pair = request.args.get("require_pair", "0") in ("1", "true", "True")
        # Accessions to exclude from views and visualizers
        EXCLUDED_ACCESSIONS = {"P83303", "P84507", "P0DL84", "P84508", "D2Y1X8", "P0DL72", "P0CH54"}

        hits = search_toxins(gap_min=gap_min, gap_max=gap_max, require_pair=require_pair, db_path=_DB_PATH)

        # Enrich hits with accession_number and Nav1.7 flags and apply exclusions
        enriched: list[dict] = []
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        for h in hits:
            pid = h.get("peptide_id")
            accession = None
            try:
                cur.execute("SELECT accession_number FROM Peptides WHERE peptide_id = ?", (pid,))
                row = cur.fetchone()
                if row:
                    accession = row["accession_number"]
            except Exception:
                accession = None

            # Skip explicitly excluded accessions
            if accession and accession in EXCLUDED_ACCESSIONS:
                continue

            # Nav1.7 table check: existence and IC50 presence
            nav_exists = False
            nav_has_ic50 = False
            try:
                cur.execute(
                    "SELECT ic50_value FROM Nav1_7_InhibitorPeptides WHERE accession_number = ? OR peptide_code = ? LIMIT 1",
                    (accession, h.get("name")),
                )
                nrow = cur.fetchone()
                if nrow:
                    nav_exists = True
                    # consider non-null ic50_value as having IC50
                    nav_has_ic50 = nrow["ic50_value"] is not None
            except Exception:
                pass
            # Also consult AI-exported JSON cache for ic50 detection
            try:
                ai_map = _load_ai_ic50_map()
                if accession and ai_map.get(str(accession)):
                    nav_has_ic50 = True
                    nav_exists = True
            except Exception:
                pass

            new_h = dict(h)
            new_h["accession_number"] = accession
            new_h["nav1_7_exists"] = nav_exists
            new_h["nav1_7_has_ic50"] = nav_has_ic50
            enriched.append(new_h)

        conn.close()
        return jsonify({"count": len(enriched), "results": enriched})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@toxin_filter_v2.get("/toxin_filter")
def toxin_filter_page():
    return render_template("toxin_filter.html")
