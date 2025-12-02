from flask import Blueprint, jsonify, request, Response
import os, importlib

from src.infrastructure.db.sqlite.metadata_repository_sqlite import SqliteMetadataRepository
from src.application.use_cases.build_protein_graph import (
    BuildProteinGraph,
    BuildProteinGraphInput,
)
from src.infrastructure.graphein.graphein_graph_adapter import GrapheinGraphAdapter
from src.infrastructure.graphein.graph_visualizer_adapter import MolstarGraphVisualizerAdapter
from src.infrastructure.pdb.pdb_preprocessor_adapter import PDBPreprocessorAdapter
from src.infrastructure.fs.temp_file_service import TempFileService
from src.interfaces.http.flask.presenters.graph_presenter import GraphPresenter
from src.domain.models.value_objects import Granularity, DistanceThreshold


graphs_v2 = Blueprint("graphs_v2", __name__)

# Load central config for sane defaults (overridden via DI in app factory)
try:
    _cfg_mod = importlib.import_module('src.config')
    _CFG = getattr(_cfg_mod, 'load_app_config')(os.getcwd())
except Exception:
    class _CFG:  # type: ignore
        db_path = "database/toxins.db"
        pdb_dir = "pdbs"
        psf_dir = "psfs"

_db = SqliteMetadataRepository(db_path=getattr(_CFG, 'db_path', 'database/toxins.db'))
_graph = GrapheinGraphAdapter()
_pdb = PDBPreprocessorAdapter(pdb_dir=getattr(_CFG, 'pdb_dir', None), psf_dir=getattr(_CFG, 'psf_dir', None))
_tmp = TempFileService()
_viz = MolstarGraphVisualizerAdapter()
_build_graph_uc = None  # type: ignore[var-annotated]


def configure_graphs_dependencies(
    *,
    metadata_repo: SqliteMetadataRepository = None,
    graph_adapter: GrapheinGraphAdapter = None,
    pdb_preprocessor: PDBPreprocessorAdapter = None,
    temp_files: TempFileService = None,
    visualizer: MolstarGraphVisualizerAdapter = None,
    build_graph_uc: BuildProteinGraph = None,
):
    global _db, _graph, _pdb, _tmp, _viz, _build_graph_uc
    if metadata_repo is not None:
        _db = metadata_repo
    if graph_adapter is not None:
        _graph = graph_adapter
    if pdb_preprocessor is not None:
        _pdb = pdb_preprocessor
    if temp_files is not None:
        _tmp = temp_files
    if visualizer is not None:
        _viz = visualizer
    if build_graph_uc is not None:
        _build_graph_uc = build_graph_uc


@graphs_v2.get("/v2/proteins/<string:source>/<int:pid>/graph")
def get_graph_v2(source: str, pid: int):
    try:
        # Params
        distance_threshold = float(request.args.get("threshold", 10.0))
        granularity = request.args.get("granularity", "CA")
        raw = request.args.get("raw", "0") == "1"
        section = request.args.get("section")  # optional: 'props' | 'fig' | 'all'

        # Get PDB from DB
        data = _db.get_complete_toxin_data(source, pid)
        if not data or not data.get("pdb_data"):
            return jsonify({"error": "PDB not found"}), 404

        pdb_path = None
        created_temp = False
        pdb_data = data.get("pdb_data")
        # For 'toxinas', DB may store a filename instead of raw PDB; resolve path
        if source == "toxinas":
            try:
                # Convert bytes to text if needed
                text = pdb_data.decode("utf-8", errors="ignore") if isinstance(pdb_data, (bytes, bytearray)) else str(pdb_data)
                text = text.strip()
                # Heuristic: if looks like a .pdb filename/path, try to resolve on disk
                if text.lower().endswith(".pdb") and len(text) < 256:
                    candidates = []
                    # Absolute path
                    if os.path.isabs(text):
                        candidates.append(text)
                    # Relative to configured pdb_dir if available
                    base_dir = getattr(_pdb, 'pdb_dir', None) or getattr(_CFG, 'pdb_dir', None) or 'pdbs'
                    candidates.append(os.path.join(base_dir, text))
                    # As-is relative to CWD
                    candidates.append(text)
                    for c in candidates:
                        if os.path.exists(c):
                            # Read and preprocess content into a temp file for Graphein
                            try:
                                with open(c, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                pdb_path = _pdb.prepare_temp_pdb(content)
                                created_temp = True
                            except Exception:
                                # If preprocessing fails, still pass original path as last resort
                                pdb_path = c
                            break
            except Exception:
                pass
        # If we couldn't resolve a path, assume raw content and write temp file
        if not pdb_path:
            pdb_path = _pdb.prepare_temp_pdb(pdb_data)
            created_temp = True

        try:
            # Wrap in domain value objects for validation and typing
            inp = BuildProteinGraphInput(
                pdb_path=pdb_path,
                granularity=Granularity.from_string(granularity),
                distance_threshold=DistanceThreshold(distance_threshold),
            )
            uc = _build_graph_uc if _build_graph_uc is not None else BuildProteinGraph(_graph)
            result = uc.execute(inp)

            if raw:
                # Return minimal payload to isolate JSON issues
                minimal = {
                    "ok": True,
                    "meta": {"source": source, "id": pid, "granularity": granularity},
                    "properties": {
                        "num_nodes": result["properties"].get("num_nodes"),
                        "num_edges": result["properties"].get("num_edges"),
                    },
                }
                import json
                return Response(json.dumps(minimal, ensure_ascii=False), mimetype='application/json')
            # Build WebGL-optimized visualization data (nodes + edges)
            graph_data = _viz.create_complete_visualization(result["graph"], granularity, pid)
            payload = GraphPresenter.present(
                properties=result["properties"],
                meta={"source": source, "id": pid, "granularity": granularity},
                graph_data=_viz.convert_numpy_to_lists(graph_data)
            )
            # Optional: allow isolating sections to debug serialization
            if section == 'props':
                obj = {"properties": payload.get("properties", {}), "meta": payload.get("meta", {})}
            elif section == 'fig':
                obj = {"plotData": payload.get("plotData", []), "layout": payload.get("layout", {})}
            else:
                obj = payload

            # Final normalization for any numpy leftovers; always return a plain Response
            import json
            try:
                import numpy as np
            except Exception:
                np = None  # type: ignore

            def normalize(o):
                # Handle numpy types if available
                if np is not None:
                    if isinstance(o, getattr(np, 'ndarray', ())):
                        return o.tolist()
                    if isinstance(o, (getattr(np, 'floating', ()), getattr(np, 'integer', ()), getattr(np, 'bool_', ()))):
                        try:
                            return o.item()
                        except Exception:
                            return bool(o)
                if isinstance(o, dict):
                    return {k: normalize(v) for k, v in o.items()}
                if isinstance(o, (list, tuple, set)):
                    return [normalize(x) for x in o]
                return o

            body = json.dumps(normalize(obj), ensure_ascii=False)
            return Response(body, mimetype='application/json')
        finally:
            if created_temp and 'pdb_path' in locals() and pdb_path:
                try:
                    _tmp.cleanup([pdb_path])
                except Exception:
                    pass
    except Exception as e:
        return jsonify({"error": str(e)}), 500
