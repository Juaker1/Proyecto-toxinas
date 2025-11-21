from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional, Union
import os
import pandas as pd
import networkx as nx

from src.application.ports.repositories import MetadataRepository, StructureRepository
from src.infrastructure.exporters.excel_export_adapter import ExcelExportAdapter
from src.infrastructure.pdb.pdb_preprocessor_adapter import PDBPreprocessorAdapter
from src.domain.services.segmentation_service import agrupar_por_segmentos_atomicos
from src.domain.models.value_objects import Granularity, DistanceThreshold
from src.infrastructure.graphein.graph_export_service import GraphExportService as GraphAnalyzer
from src.infrastructure.exporters.export_service_v2 import ExportService


@dataclass
class ExportWTComparisonInput:
    wt_family: str
    export_type: str = 'residues'  # 'residues' | 'segments_atomicos'
    granularity: Union[str, Granularity] = 'CA'
    distance_threshold: Union[float, DistanceThreshold] = 10.0
    reference_path: str = "pdbs/WT/hwt4_Hh2a_WT.pdb"


class ExportWTComparison:
    def __init__(self, metadata: MetadataRepository, structures: StructureRepository, exporter: ExcelExportAdapter) -> None:
        self.metadata = metadata
        self.structures = structures
        self.exporter = exporter
        self.pdb = PDBPreprocessorAdapter()

    def _process_single(self, pdb_data, toxin_name: str, ic50_value: Optional[float], ic50_unit: Optional[str],
                         granularity: str, distance_threshold: float, toxin_type: str,
                         export_type: str):
        pdb_path = self.pdb.prepare_temp_pdb_from_any(pdb_data)
        try:
            cfg = GraphAnalyzer.create_graph_config(granularity, distance_threshold)
            G = GraphAnalyzer.construct_protein_graph(pdb_path, cfg)
            if export_type == 'segments_atomicos':
                df = agrupar_por_segmentos_atomicos(G, granularity)
                if df is None or df.empty:
                    return None, G
                df.insert(0, 'Toxina', toxin_name)
                df['Tipo'] = toxin_type
                if ic50_value and ic50_unit:
                    df['IC50_Value'] = ic50_value
                    df['IC50_Unit'] = ic50_unit
                else:
                    df['IC50_Value'] = None
                    df['IC50_Unit'] = None
                return df, G
            else:
                residue_data = ExportService.prepare_residue_export_data(
                    G, toxin_name, ic50_value, ic50_unit, granularity
                )
                if not residue_data:
                    return None, G
                for row in residue_data:
                    row['Tipo'] = toxin_type
                return pd.DataFrame(residue_data), G
        finally:
            self.pdb.cleanup([pdb_path])

    def execute(self, inp: ExportWTComparisonInput) -> Tuple[bytes, str, Dict[str, Any]]:
        # Map WT family to peptide code used in DB
        wt_mapping = {
            'μ-TRTX-Hh2a': 'μ-TRTX-Hh2a',
            'μ-TRTX-Hhn2b': 'μ-TRTX-Hhn2b',
            'β-TRTX-Cd1a': 'β-TRTX-Cd1a',
            'ω-TRTX-Gr2a': 'ω-TRTX-Gr2a',
        }
        if inp.wt_family not in wt_mapping:
            raise ValueError(f"Familia WT no reconocida: {inp.wt_family}")

        wt_peptide_code = wt_mapping[inp.wt_family]
        wt_toxin = self.metadata.get_wt_toxin_data(wt_peptide_code)
        if not wt_toxin:
            raise RuntimeError(f"Toxina WT no encontrada: {wt_peptide_code}")

        gran = inp.granularity.value if isinstance(inp.granularity, Granularity) else inp.granularity
        dist_thr = float(inp.distance_threshold.value) if isinstance(inp.distance_threshold, DistanceThreshold) else float(inp.distance_threshold)

        if inp.export_type == 'segments_atomicos' and gran != 'atom':
            raise ValueError("La segmentación atómica requiere granularidad 'atom'")

        if not os.path.exists(inp.reference_path):
            raise FileNotFoundError(f"Archivo de referencia no encontrado: {inp.reference_path}")

        with open(inp.reference_path, 'r') as ref_file:
            reference_pdb = ref_file.read()

        comparison_frames: Dict[str, Any] = {}

        # Process WT target
        wt_df, wt_G = self._process_single(
            wt_toxin['pdb_data'], wt_toxin['name'], wt_toxin['ic50_value'], wt_toxin['ic50_unit'],
            gran, dist_thr, "WT_Target", inp.export_type
        )
        if wt_df is not None:
            comparison_frames['WT_Target'] = wt_df

        # Process reference
        ref_df, ref_G = self._process_single(
            reference_pdb, "hwt4_Hh2a_WT", None, None,
            gran, dist_thr, "Reference", inp.export_type
        )
        if ref_df is not None:
            comparison_frames['Reference'] = ref_df

        # Optional summary if both present
        if 'WT_Target' in comparison_frames and 'Reference' in comparison_frames:
            wt_df_local = comparison_frames['WT_Target']
            ref_df_local = comparison_frames['Reference']
            if hasattr(ExportService, 'create_summary_comparison_dataframe'):
                summary_df = ExportService.create_summary_comparison_dataframe(
                    wt_df_local, ref_df_local, wt_toxin['name'], inp.export_type
                )
                comparison_frames['Resumen_Comparativo'] = summary_df

        from datetime import datetime
        meta = {
            'Toxina_WT': wt_toxin['name'],
            'Toxina_Referencia': 'hwt4_Hh2a_WT',
            'Familia': inp.wt_family,
            'Tipo_Analisis': 'Segmentación Atómica' if inp.export_type == 'segments_atomicos' else 'Análisis por Residuos',
            'IC50_WT': f"{wt_toxin['ic50_value']} {wt_toxin['ic50_unit']}" if wt_toxin['ic50_value'] and wt_toxin['ic50_unit'] else 'No disponible',
            'Granularidad': gran,
            'Umbral_Distancia': dist_thr,
            'Fecha_Exportacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        excel_data, excel_filename = self.exporter.generate_comparison_excel(
            comparison_frames, inp.wt_family, meta, inp.export_type, gran
        )
        return excel_data, excel_filename, meta
# Removed legacy PDBProcessor shim; v2 uses PDBPreprocessorAdapter exclusively.
