from flask import Flask, jsonify
import os, importlib
import os
import importlib


def create_app_v2() -> Flask:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(base_dir, 'web')
    templates = os.path.join(web_dir, 'templates')
    static = os.path.join(web_dir, 'static')

    app = Flask(__name__, template_folder=templates, static_folder=static)
    # Ensure proper unicode in JSON (e.g., Greek letters) and fast template reload in dev
    app.config["JSON_AS_ASCII"] = False
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    # Feature flags
    env_flag = os.environ.get('LEGACY_ALIASES_ENABLED', '0').strip().lower()
    app.config['LEGACY_ALIASES_ENABLED'] = env_flag not in ('0', 'false', 'no')

    # --- Composition Root: instantiate infrastructure and use cases (simple manual DI) ---
    # Config
    try:
        _cfg_mod = importlib.import_module('src.config')
        load_app_config = getattr(_cfg_mod, 'load_app_config')
        project_root = os.path.abspath(os.path.join(base_dir, '../../../../'))
        cfg = load_app_config(project_root)
    except Exception:
        class _CF:  # fallback minimal
            db_path = "database/toxins.db"
            pdb_dir = "pdbs"
            psf_dir = "psfs"
            wt_reference_path = os.path.join("pdbs", "WT", "hwt4_Hh2a_WT.pdb")
        cfg = _CF()
    # Expose config for debugging/diagnostics
    try:
        app.config['APP_CONFIG'] = {
            'db_path': getattr(cfg, 'db_path', None),
            'pdb_dir': getattr(cfg, 'pdb_dir', None),
            'psf_dir': getattr(cfg, 'psf_dir', None),
            'wt_reference_path': getattr(cfg, 'wt_reference_path', None),
        }
    except Exception:
        pass
    # Repositories
    from src.infrastructure.db.sqlite.structure_repository_sqlite import SqliteStructureRepository
    from src.infrastructure.db.sqlite.metadata_repository_sqlite import SqliteMetadataRepository
    from src.infrastructure.db.sqlite.family_repository_sqlite import SqliteFamilyRepository
    from src.infrastructure.db.sqlite.toxin_repository_sqlite import SqliteToxinRepository

    structures_repo = SqliteStructureRepository(db_path=cfg.db_path)
    metadata_repo = SqliteMetadataRepository(db_path=cfg.db_path)
    family_repo = SqliteFamilyRepository(db_path=cfg.db_path)
    toxin_repo = SqliteToxinRepository(db_path=cfg.db_path)

    # Infrastructure services / adapters
    from src.infrastructure.graphein.graphein_graph_adapter import GrapheinGraphAdapter
    from src.infrastructure.graphein.graph_visualizer_adapter import PlotlyGraphVisualizerAdapter
    from src.infrastructure.exporters.excel_export_adapter import ExcelExportAdapter
    from src.infrastructure.pdb.pdb_preprocessor_adapter import PDBPreprocessorAdapter
    from src.infrastructure.fs.temp_file_service import TempFileService

    graphein_adapter = GrapheinGraphAdapter()
    graph_visualizer = PlotlyGraphVisualizerAdapter()
    excel_exporter = ExcelExportAdapter()
    pdb_preprocessor = PDBPreprocessorAdapter(pdb_dir=getattr(cfg, 'pdb_dir', None), psf_dir=getattr(cfg, 'psf_dir', None))
    temp_files = TempFileService()

    # Use cases
    from src.application.use_cases.build_protein_graph import BuildProteinGraph
    from src.application.use_cases.calculate_dipole import CalculateDipole
    from src.application.use_cases.export_residue_report import ExportResidueReport
    from src.application.use_cases.export_atomic_segments import ExportAtomicSegments
    from src.application.use_cases.export_family_reports import ExportFamilyReports
    from src.application.use_cases.list_peptides import ListPeptides

    # Use new DipoleAdapter instead of legacy service
    from src.infrastructure.graphein.dipole_adapter import DipoleAdapter

    build_graph_uc = BuildProteinGraph(graphein_adapter)
    dipole_service = DipoleAdapter()
    calculate_dipole_uc = CalculateDipole(structures_repo, dipole_service, metadata_repo, pdb_preprocessor)
    export_residues_uc = ExportResidueReport(structures_repo, excel_exporter, pdb_preprocessor, temp_files, metadata_repo)
    export_segments_uc = ExportAtomicSegments(structures_repo, metadata_repo, pdb_preprocessor, temp_files)
    export_family_uc = ExportFamilyReports(metadata_repo, structures_repo, excel_exporter, pdb_preprocessor)
    list_peptides_uc = ListPeptides  # class; instantiated per request where needed

    # Register only v2 blueprints from the new architecture. Routes already include /v2.
    try:
        from src.interfaces.http.flask.controllers.v2.export_controller import export_v2, configure_export_dependencies
        # Inject dependencies into controller module before registering blueprint
        configure_export_dependencies(
            pdb_preprocessor=pdb_preprocessor,
            excel_exporter=excel_exporter,
            structures_repo=structures_repo,
            metadata_repo=metadata_repo,
            export_uc=export_residues_uc,
            segments_uc=export_segments_uc,
            family_uc=export_family_uc,
            wt_uc=None,
            default_reference_path=getattr(cfg, 'wt_reference_path', None),
        )
        app.register_blueprint(export_v2)
    except Exception as e:
        app.logger.warning(f"v2 export blueprint not registered: {e}")
    try:
        from src.interfaces.http.flask.controllers.v2.dipole_controller import dipole_v2, configure_dipole_dependencies
        configure_dipole_dependencies(
            dipole_service=dipole_service,
            pdb_preprocessor=pdb_preprocessor,
            temp_files=temp_files,
            structures_repo=structures_repo,
            metadata_repo=metadata_repo,
            use_case=calculate_dipole_uc,
        )
        app.register_blueprint(dipole_v2)
    except Exception as e:
        app.logger.warning(f"v2 dipole blueprint not registered: {e}")
    try:
        from src.interfaces.http.flask.controllers.v2.structures_controller import structures_v2, configure_structures_dependencies
        configure_structures_dependencies(structures_repo=structures_repo)
        app.register_blueprint(structures_v2)  # blueprint has url_prefix=/v2/structures
    except Exception as e:
        app.logger.warning(f"v2 structures blueprint not registered: {e}")
    try:
        from src.interfaces.http.flask.controllers.v2.metadata_controller import metadata_v2, configure_metadata_dependencies
        configure_metadata_dependencies(metadata_repo=metadata_repo)
        app.register_blueprint(metadata_v2)
    except Exception as e:
        app.logger.warning(f"v2 metadata blueprint not registered: {e}")
    try:
        from src.interfaces.http.flask.controllers.v2.families_controller import families_v2, configure_families_dependencies
        configure_families_dependencies(
            families_repo=family_repo,
            structures_repo=structures_repo,
            dipole_service=dipole_service,
        )
        app.register_blueprint(families_v2)
    except Exception as e:
        app.logger.warning(f"v2 families blueprint not registered: {e}")
    # Toxin filter (motif) page
    try:
        from src.interfaces.http.flask.controllers.v2.toxins_filter_controller import toxin_filter_v2
        app.register_blueprint(toxin_filter_v2)
    except Exception as e:
        app.logger.warning(f"v2 toxin_filter blueprint not registered: {e}")
    try:
        from src.interfaces.http.flask.controllers.graphs_controller import graphs_v2, configure_graphs_dependencies
        configure_graphs_dependencies(
            metadata_repo=metadata_repo,
            graph_adapter=graphein_adapter,
            pdb_preprocessor=pdb_preprocessor,
            temp_files=temp_files,
            visualizer=graph_visualizer,
            build_graph_uc=build_graph_uc,
        )
        app.register_blueprint(graphs_v2)  # routes already start with /v2
    except Exception as e:
        app.logger.warning(f"v2 graphs blueprint not registered: {e}")
    try:
        from src.interfaces.http.flask.controllers.toxins_controller import toxins_v2, configure_toxins_dependencies
        configure_toxins_dependencies(toxin_repo=toxin_repo)
        app.register_blueprint(toxins_v2)  # routes already start with /v2
    except Exception as e:
        app.logger.warning(f"v2 toxins blueprint not registered: {e}")
    # Serve pages (viewer, dipole families) from v2 pages controller
    try:
        from src.interfaces.http.flask.controllers.v2.pages_controller import pages_v2, configure_pages_dependencies
        configure_pages_dependencies(toxin_repo=toxin_repo)
        app.register_blueprint(pages_v2)
    except Exception as e:
        app.logger.warning(f"v2 pages blueprint not registered: {e}")

    # Lightweight health endpoint for diagnostics
    def health_v2():
        try:
            info = {
                "ok": True,
                "blueprints": sorted(list(app.blueprints.keys())),
                "static_folder": app.static_folder,
                "template_folder": app.template_folder,
                "config": app.config.get("APP_CONFIG", {}),
            }
            return jsonify(info)
        except Exception as ex:
            return jsonify({"ok": False, "error": str(ex)}), 500

    app.add_url_rule('/v2/health', 'health_v2', health_v2, methods=['GET'])

    # Optionally expose legacy-compatible alias routes for the UI during migration
    if app.config.get('LEGACY_ALIASES_ENABLED', False):
        try:
            from src.interfaces.http.flask.controllers.legacy_compat_controller import legacy_compat, dipole_family_routes
            app.register_blueprint(legacy_compat)
            app.register_blueprint(dipole_family_routes)
            app.logger.info("Legacy alias routes enabled (LEGACY_ALIASES_ENABLED=1)")
        except Exception as e:
            app.logger.warning(f"Legacy alias blueprints not registered: {e}")
    return app
