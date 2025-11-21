from flask import Blueprint, jsonify, request, send_file
from typing import Optional
from src.infrastructure.pdb.pdb_preprocessor_adapter import PDBPreprocessorAdapter
from src.infrastructure.fs.temp_file_service import TempFileService
from src.infrastructure.exporters.excel_export_adapter import ExcelExportAdapter
from src.interfaces.http.flask.presenters.export_presenter import ExportPresenter
from src.application.use_cases.export_residue_report import ExportResidueReport, ExportResidueReportInput
from src.infrastructure.db.sqlite.structure_repository_sqlite import SqliteStructureRepository
from src.infrastructure.db.sqlite.metadata_repository_sqlite import SqliteMetadataRepository
from src.application.use_cases.export_atomic_segments import ExportAtomicSegments, ExportAtomicSegmentsInput
from src.application.use_cases.export_family_reports import ExportFamilyReports, ExportFamilyInput
from src.application.use_cases.export_wt_comparison import ExportWTComparison, ExportWTComparisonInput
from src.domain.models import Granularity, DistanceThreshold

export_v2 = Blueprint("export_v2", __name__)
_pdb = PDBPreprocessorAdapter()
_tmp = TempFileService()
_export = ExcelExportAdapter()
_structures = SqliteStructureRepository()
_metadata = SqliteMetadataRepository()
_default_reference_path: Optional[str] = None
_export_uc = ExportResidueReport(_structures, _export, _pdb, _tmp, _metadata)
_segments_uc = ExportAtomicSegments(_structures, _metadata, _pdb, _tmp)
_family_uc = ExportFamilyReports(_metadata, _structures, _export)
_wt_uc = ExportWTComparison(_metadata, _structures, _export)


def configure_export_dependencies(
    *,
    pdb_preprocessor: PDBPreprocessorAdapter = None,
    temp_files: TempFileService = None,
    excel_exporter: ExcelExportAdapter = None,
    structures_repo: SqliteStructureRepository = None,
    metadata_repo: SqliteMetadataRepository = None,
    export_uc: ExportResidueReport = None,
    segments_uc: ExportAtomicSegments = None,
    family_uc: ExportFamilyReports = None,
    wt_uc: ExportWTComparison = None,
    default_reference_path: Optional[str] = None,
):
    global _pdb, _tmp, _export, _structures, _metadata, _export_uc, _segments_uc, _family_uc, _wt_uc, _default_reference_path
    if pdb_preprocessor is not None:
        _pdb = pdb_preprocessor
    if temp_files is not None:
        _tmp = temp_files
    if excel_exporter is not None:
        _export = excel_exporter
    if structures_repo is not None:
        _structures = structures_repo
    if metadata_repo is not None:
        _metadata = metadata_repo
    if export_uc is not None:
        _export_uc = export_uc
    if segments_uc is not None:
        _segments_uc = segments_uc
    if family_uc is not None:
        _family_uc = family_uc
    if wt_uc is not None:
        _wt_uc = wt_uc
    if default_reference_path is not None:
        _default_reference_path = default_reference_path


@export_v2.get("/v2/export/residues/<string:source>/<int:pid>")
def export_residues_v2(source, pid):
    try:
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')

        # Wrap into Value Objects
        granularity_vo = Granularity.from_string(granularity)
        dist_vo = DistanceThreshold(distance_threshold)

        inp = ExportResidueReportInput(
            source=source,
            pid=pid,
            granularity=granularity_vo,
            distance_threshold=dist_vo,
        )
        try:
            excel_data, excel_filename, metadata = _export_uc.execute(inp)

            # JSON metadata response if requested
            if request.args.get('format') == 'json':
                # excel_data may be BytesIO or bytes; get size
                try:
                    size_bytes = excel_data.getbuffer().nbytes  # type: ignore[attr-defined]
                except Exception:
                    size_bytes = len(excel_data) if hasattr(excel_data, '__len__') else 0
                return jsonify(ExportPresenter.present_excel_meta(metadata, excel_filename, size_bytes))

            # send_file requiere un file-like; ExportService retorna ya un buffer BytesIO + filename
            return send_file(
                excel_data,
                as_attachment=True,
                download_name=excel_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        finally:
            pass
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@export_v2.get("/v2/export/segments_atomicos/<int:pid>")
def export_segments_atomicos_v2(pid):
    try:
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'atom')
        # Wrap into Value Objects
        granularity_vo = Granularity.from_string(granularity)
        dist_vo = DistanceThreshold(distance_threshold)
        if granularity_vo != Granularity.ATOM:
            return jsonify({"error": "La segmentación atómica requiere granularidad 'atom'"}), 400

        inp = ExportAtomicSegmentsInput(
            pid=pid,
            distance_threshold=dist_vo,
            granularity=granularity_vo,
        )
        excel_data, excel_filename, metadata = _segments_uc.execute(inp)

        if request.args.get('format') == 'json':
            try:
                size_bytes = excel_data.getbuffer().nbytes  # type: ignore[attr-defined]
            except Exception:
                size_bytes = len(excel_data) if hasattr(excel_data, '__len__') else 0
            return jsonify(ExportPresenter.present_excel_meta(metadata, excel_filename, size_bytes))

        return send_file(
            excel_data,
            as_attachment=True,
            download_name=excel_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@export_v2.get("/v2/export/family/<string:family_prefix>")
def export_family_v2(family_prefix: str):
    try:
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        export_type = request.args.get('export_type', 'residues')  # 'residues' | 'segments_atomicos'

        # Wrap into Value Objects
        granularity_vo = Granularity.from_string(granularity)
        dist_vo = DistanceThreshold(distance_threshold)

        if export_type == 'segments_atomicos' and granularity_vo != Granularity.ATOM:
            return jsonify({"error": "La segmentación atómica requiere granularidad 'atom'"}), 400

        inp = ExportFamilyInput(
            family_prefix=family_prefix,
            export_type=export_type,
            granularity=granularity_vo,
            distance_threshold=dist_vo,
        )
        excel_data, excel_filename, metadata = _family_uc.execute(inp)

        if request.args.get('format') == 'json':
            try:
                size_bytes = excel_data.getbuffer().nbytes  # type: ignore[attr-defined]
            except Exception:
                size_bytes = len(excel_data) if hasattr(excel_data, '__len__') else 0
            return jsonify(ExportPresenter.present_excel_meta(metadata, excel_filename, size_bytes))

        return send_file(
            excel_data,
            as_attachment=True,
            download_name=excel_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@export_v2.get("/v2/export/wt_comparison/<string:wt_family>")
def export_wt_comparison_v2(wt_family: str):
    try:
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        export_type = request.args.get('export_type', 'residues')
        reference_path = request.args.get('reference_path') or _default_reference_path or 'pdbs/WT/hwt4_Hh2a_WT.pdb'

        # Wrap into Value Objects
        granularity_vo = Granularity.from_string(granularity)
        dist_vo = DistanceThreshold(distance_threshold)

        if export_type == 'segments_atomicos' and granularity_vo != Granularity.ATOM:
            return jsonify({"error": "La segmentación atómica requiere granularidad 'atom'"}), 400

        inp = ExportWTComparisonInput(
            wt_family=wt_family,
            export_type=export_type,
            granularity=granularity_vo,
            distance_threshold=dist_vo,
            reference_path=reference_path,
        )
        excel_data, excel_filename, metadata = _wt_uc.execute(inp)

        if request.args.get('format') == 'json':
            try:
                size_bytes = excel_data.getbuffer().nbytes  # type: ignore[attr-defined]
            except Exception:
                size_bytes = len(excel_data) if hasattr(excel_data, '__len__') else 0
            return jsonify(ExportPresenter.present_excel_meta(metadata, excel_filename, size_bytes))

        return send_file(
            excel_data,
            as_attachment=True,
            download_name=excel_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
