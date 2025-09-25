from flask import Blueprint, jsonify, request, render_template
import os, importlib

from extractors.toxins_filter import search_toxins

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
        hits = search_toxins(gap_min=gap_min, gap_max=gap_max, require_pair=require_pair, db_path=_DB_PATH)
        return jsonify({"count": len(hits), "results": hits})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@toxin_filter_v2.get("/toxin_filter")
def toxin_filter_page():
    return render_template("toxin_filter.html")
