from dataclasses import dataclass
from typing import Dict, Any, Tuple, Union
from src.application.ports.repositories import StructureRepository, MetadataRepository
def _graph_api():
    try:
        import importlib
        ga_mod = importlib.import_module('app.services.graph_analyzer')
        return ga_mod
    except Exception:
        from src.infrastructure.graphein.graph_export_service import GraphExportService
        class _GA:
            GraphAnalyzer = GraphExportService
        return _GA
from src.domain.services.segmentation_service import agrupar_por_segmentos_atomicos
from src.infrastructure.pdb.pdb_preprocessor_adapter import PDBPreprocessorAdapter
from src.infrastructure.fs.temp_file_service import TempFileService
from src.infrastructure.exporters.excel_export_adapter import ExcelExportAdapter
import pandas as pd
import networkx as nx
from src.domain.models.value_objects import Granularity, DistanceThreshold


@dataclass
class ExportAtomicSegmentsInput:
    pid: int
    distance_threshold: Union[float, DistanceThreshold] = 10.0
    granularity: Union[str, Granularity] = 'atom'


class ExportAtomicSegments:
    def __init__(
            self,
            structures: StructureRepository,
            metadata: MetadataRepository,
            pdb: PDBPreprocessorAdapter,
            tmp: TempFileService,
            exporter: ExcelExportAdapter = None,
    ) -> None:
        self.structures = structures
        self.metadata = metadata
        self.pdb = pdb
        self.tmp = tmp
        self.exporter = exporter or ExcelExportAdapter()

    def execute(self, inp: ExportAtomicSegmentsInput) -> Tuple[bytes, str, Dict[str, Any]]:
        gran = inp.granularity.value if isinstance(inp.granularity, Granularity) else inp.granularity
        if gran != 'atom':
            raise ValueError("La segmentación atómica requiere granularidad 'atom'")

        toxin = self.metadata.get_complete_toxin_data('nav1_7', inp.pid)
        if not toxin:
            raise FileNotFoundError('Toxina Nav1.7 no encontrada')

        pdb_bytes = toxin['pdb_data']
        toxin_name = toxin['name'] or f"Nav1.7_{inp.pid}"
        ic50_value = toxin['ic50_value']
        ic50_unit = toxin['ic50_unit']

        tmp_path = self.pdb.prepare_temp_pdb(pdb_bytes)
        try:
            dist_thr = float(inp.distance_threshold.value) if isinstance(inp.distance_threshold, DistanceThreshold) else float(inp.distance_threshold)
            GA = _graph_api().GraphAnalyzer
            cfg = GA.create_graph_config(gran, dist_thr)
            G = GA.construct_protein_graph(tmp_path, cfg)
            if G.number_of_nodes() == 0:
                raise RuntimeError('El grafo no tiene nodos')

            df_segmentos = agrupar_por_segmentos_atomicos(G, gran)
            if df_segmentos.empty:
                raise RuntimeError('No se generaron segmentos')
            df_segmentos.insert(0, 'Toxina', toxin_name)

            metadata = {
                'Toxina': toxin_name,
                'Fuente': 'Nav1.7',
                'ID': inp.pid,
                'Tipo_Analisis': 'Segmentación Atómica',
                'Granularidad': 'atom',
                'Umbral_Distancia': dist_thr,
                'Umbral_Interaccion_Larga': 0,
                'Total_Atomos_Grafo': G.number_of_nodes(),
                'Total_Conexiones_Grafo': G.number_of_edges(),
                'Densidad_Grafo': round(nx.density(G), 6),
                'Numero_Segmentos': len(df_segmentos),
                'Fecha_Exportacion': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            if ic50_value:
                metadata['IC50_Original'] = ic50_value
                metadata['Unidad_IC50'] = ic50_unit

            excel_data, excel_filename = self.exporter.generate_atomic_segments_excel(df_segmentos, toxin_name, metadata)
            return excel_data, excel_filename, metadata
        finally:
            self.tmp.cleanup([tmp_path])
