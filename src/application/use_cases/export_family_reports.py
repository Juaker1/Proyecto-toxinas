from dataclasses import dataclass
from typing import Dict, Any, Tuple, Union
from src.application.ports.repositories import MetadataRepository, StructureRepository
from src.infrastructure.graphein.graph_export_service import GraphExportService as GraphAnalyzer
from src.infrastructure.exporters.export_service_v2 import ExportService, ExportUtilsV2
from src.infrastructure.exporters.excel_export_adapter import ExcelExportAdapter
from src.infrastructure.pdb.pdb_preprocessor_adapter import PDBPreprocessorAdapter
from src.domain.services.segmentation_service import agrupar_por_segmentos_atomicos
import pandas as pd
import networkx as nx
from src.domain.models.value_objects import Granularity, DistanceThreshold


@dataclass
class ExportFamilyInput:
    family_prefix: str
    export_type: str = 'residues'  # 'residues' | 'segments_atomicos'
    granularity: Union[str, Granularity] = 'CA'
    distance_threshold: Union[float, DistanceThreshold] = 10.0


class ExportFamilyReports:
    def __init__(self, metadata: MetadataRepository, structures: StructureRepository, exporter: ExcelExportAdapter, pdb: PDBPreprocessorAdapter = None) -> None:
        self.metadata = metadata
        self.structures = structures
        self.exporter = exporter
        self.pdb = pdb or PDBPreprocessorAdapter()

    def execute(self, inp: ExportFamilyInput) -> Tuple[bytes, str, Dict[str, Any]]:
        family_toxins = self.metadata.get_family_toxins(inp.family_prefix)

        toxin_dataframes: Dict[str, Any] = {}
        processed_count = 0
        from datetime import datetime
        gran = inp.granularity.value if isinstance(inp.granularity, Granularity) else inp.granularity
        dist_thr = float(inp.distance_threshold.value) if isinstance(inp.distance_threshold, DistanceThreshold) else float(inp.distance_threshold)

        metadata = {
            'Familia': inp.family_prefix,
            'Tipo_Analisis': 'Segmentación Atómica' if inp.export_type == 'segments_atomicos' else 'Análisis por Residuos',
            'Numero_Toxinas_Procesadas': len(family_toxins),
            'Umbral_Distancia': dist_thr,
            'Granularidad': gran,
            'Fecha_Exportacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        toxin_ic50_data: Dict[str, Any] = {}

        for toxin_id, peptide_code, ic50_value, ic50_unit in family_toxins:
            pdb_data = self.structures.get_pdb('nav1_7', toxin_id)
            if not pdb_data:
                continue
            pdb_path = self.pdb.prepare_temp_pdb_from_any(pdb_data)
            try:
                config = GraphAnalyzer.create_graph_config(gran, dist_thr)
                G = GraphAnalyzer.construct_protein_graph(pdb_path, config)
                if inp.export_type == 'segments_atomicos':
                    df_segmentos = agrupar_por_segmentos_atomicos(G, gran)
                    if not df_segmentos.empty:
                        df_segmentos.insert(0, 'Toxina', peptide_code)
                        df_segmentos['IC50_Value'] = ic50_value
                        df_segmentos['IC50_Unit'] = ic50_unit
                        toxin_dataframes[ExportUtilsV2.clean_filename(peptide_code)] = df_segmentos
                        processed_count += 1
                else:
                    # Use module-level ExportService alias (monkeypatchable in tests)
                    ES = ExportService
                    residue_data = ES.prepare_residue_export_data(G, peptide_code, ic50_value, ic50_unit, gran)
                    if residue_data:
                        df = pd.DataFrame(residue_data)
                        toxin_dataframes[ExportUtilsV2.clean_filename(peptide_code)] = df
                        processed_count += 1
                metadata[f'Nodos_en_{peptide_code}'] = G.number_of_nodes()
                metadata[f'Aristas_en_{peptide_code}'] = G.number_of_edges()
                metadata[f'Densidad_en_{peptide_code}'] = round(nx.density(G), 6)
                if ic50_value:
                    toxin_ic50_data[f'IC50_{peptide_code}'] = f"{ic50_value} {ic50_unit}"
            finally:
                self.pdb.cleanup([pdb_path])

        metadata.update(toxin_ic50_data)
        if not toxin_dataframes:
            raise RuntimeError("No se pudieron procesar toxinas válidas")
        excel_data, excel_filename = self.exporter.generate_family_excel(
            toxin_dataframes, inp.family_prefix, metadata, inp.export_type, gran
        )
        return excel_data, excel_filename, metadata


# Removed legacy PDBProcessor shim; v2 uses PDBPreprocessorAdapter exclusively.
