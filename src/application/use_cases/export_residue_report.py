from dataclasses import dataclass
from typing import Dict, Any, Tuple, Union
from src.application.ports.repositories import StructureRepository, MetadataRepository
from src.infrastructure.graphein.graph_export_service import GraphExportService as GraphAnalyzer
from src.infrastructure.exporters.export_service_v2 import ExportService
from src.infrastructure.exporters.excel_export_adapter import ExcelExportAdapter
from src.infrastructure.pdb.pdb_preprocessor_adapter import PDBPreprocessorAdapter
from src.infrastructure.fs.temp_file_service import TempFileService
from src.domain.models.value_objects import Granularity, DistanceThreshold


@dataclass
class ExportResidueReportInput:
    source: str
    pid: int
    granularity: Union[str, Granularity] = 'CA'
    distance_threshold: Union[float, DistanceThreshold] = 10.0


class ExportResidueReport:
    def __init__(
        self,
        structures: StructureRepository,
        exporter: ExcelExportAdapter,
        pdb: PDBPreprocessorAdapter,
        tmp: TempFileService,
        metadata_repo: MetadataRepository,
    ) -> None:
        self.structures = structures
        self.exporter = exporter
        self.pdb = pdb
        self.tmp = tmp
        self.metadata_repo = metadata_repo

    def execute(self, inp: ExportResidueReportInput) -> Tuple[bytes, str, Dict[str, Any]]:
        toxin = self.metadata_repo.get_complete_toxin_data(inp.source, inp.pid)
        if not toxin:
            raise FileNotFoundError('PDB not found')

        pdb_bytes = toxin['pdb_data']
        toxin_name = toxin['name'] or f"{inp.source}_{inp.pid}"
        ic50_value = toxin['ic50_value']
        ic50_unit = toxin['ic50_unit']

        tmp_path = self.pdb.prepare_temp_pdb(pdb_bytes)
        try:
            gran = inp.granularity.value if isinstance(inp.granularity, Granularity) else inp.granularity
            dist_thr = float(inp.distance_threshold.value) if isinstance(inp.distance_threshold, DistanceThreshold) else float(inp.distance_threshold)
            cfg = GraphAnalyzer.create_graph_config(gran, dist_thr)
            G = GraphAnalyzer.construct_protein_graph(tmp_path, cfg)
            residue_data = ExportService.prepare_residue_export_data(G, toxin_name, ic50_value, ic50_unit, gran)
            metadata = ExportService.create_metadata(
                toxin_name,
                inp.source,
                inp.pid,
                gran,
                dist_thr,
                G,
                ic50_value,
                ic50_unit,
            )
            excel_data, excel_filename = self.exporter.generate_single_toxin_excel(
                residue_data, metadata, toxin_name, inp.source
            )
            return excel_data, excel_filename, metadata
        finally:
            self.tmp.cleanup([tmp_path])
