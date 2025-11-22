import types
import io
import pandas as pd
import networkx as nx


def make_stub_graph(n=3, m=3):
    G = nx.Graph()
    for i in range(n):
        G.add_node(i, residue_name=f"RES{i}")
    for i in range(m):
        u, v = i % n, (i + 1) % n
        G.add_edge(u, v)
    return G


class StubMetadataRepo:
    def __init__(self, toxins):
        self._toxins = toxins

    def get_family_toxins(self, family_prefix):
        return self._toxins


class StubStructureRepo:
    def get_pdb(self, source, peptide_id):
        return b"ATOM FAKE PDB CONTENT"  # content not used by stub graph analyzer


class StubExcelExporter:
    def generate_family_excel(self, toxin_dataframes, family_prefix, metadata, export_type='residues', granularity='CA'):
        # Return a tiny bytes buffer and a filename
        return io.BytesIO(b"excel-bytes"), f"Family-{family_prefix}-{export_type}-{granularity}.xlsx"


def test_export_family_residues_monkeypatched(monkeypatch):
    # Import target module
    from src.application.use_cases import export_family_reports as mod

    # Monkeypatch GraphAnalyzer methods used by the UC
    monkeypatch.setattr(mod.GraphAnalyzer, 'create_graph_config', lambda g, l, d: {'g': g, 'l': l, 'd': d})
    monkeypatch.setattr(mod.GraphAnalyzer, 'construct_protein_graph', lambda path, cfg: make_stub_graph())

    # Monkeypatch PDBProcessor file ops to avoid filesystem
    monkeypatch.setattr(mod.PDBProcessor, 'prepare_pdb_data', lambda pdb: pdb)
    monkeypatch.setattr(mod.PDBProcessor, 'create_temp_pdb_file', lambda content: '/tmp/fake.pdb')
    monkeypatch.setattr(mod.PDBProcessor, 'cleanup_temp_files', lambda path: None)

    # Monkeypatch ExportService call inside residue branch via DataFrame creation path
    # The UC uses ExportService.prepare_residue_export_data, so patch it to simple rows
    class _ES:  # lightweight stub namespace
        @staticmethod
        def prepare_residue_export_data(G, peptide_code, ic50_value, ic50_unit, granularity):
            return [
                {'Residuo': 'RES0', 'Centralidad_Grado': 0.1, 'Centralidad_Intermediacion': 0.2,
                 'Centralidad_Cercania': 0.3, 'Coeficiente_Agrupamiento': 0.4,
                 'Toxina': peptide_code, 'IC50_Value': ic50_value, 'IC50_Unit': ic50_unit}
            ]
    monkeypatch.setattr(mod, 'ExportService', _ES)

    metadata = StubMetadataRepo([
        (1, 'PepA', 12.3, 'nM'),
        (2, 'PepB', None, None),
    ])
    structures = StubStructureRepo()
    exporter = StubExcelExporter()

    uc = mod.ExportFamilyReports(metadata, structures, exporter)
    inp = mod.ExportFamilyInput(family_prefix='mu-TRTX', export_type='residues', granularity='CA', distance_threshold=10.0)
    excel_data, excel_filename, meta = uc.execute(inp)

    assert hasattr(excel_data, 'read')
    assert excel_filename.startswith('Family-mu-TRTX-residues-CA')
    assert meta['Familia'] == 'mu-TRTX'
    assert meta['Numero_Toxinas_Procesadas'] == 2


def test_export_family_segments_monkeypatched(monkeypatch):
    from src.application.use_cases import export_family_reports as mod

    # Monkeypatch GraphAnalyzer to return stub graph
    monkeypatch.setattr(mod.GraphAnalyzer, 'create_graph_config', lambda g, l, d: {'g': g, 'l': l, 'd': d})
    monkeypatch.setattr(mod.GraphAnalyzer, 'construct_protein_graph', lambda path, cfg: make_stub_graph())

    # Monkeypatch PDBProcessor
    monkeypatch.setattr(mod.PDBProcessor, 'prepare_pdb_data', lambda pdb: pdb)
    monkeypatch.setattr(mod.PDBProcessor, 'create_temp_pdb_file', lambda content: '/tmp/fake.pdb')
    monkeypatch.setattr(mod.PDBProcessor, 'cleanup_temp_files', lambda path: None)

    # Monkeypatch atomic segmentation to return a simple DataFrame
    def fake_segment(G, granularity):
        return pd.DataFrame([
            {'Segmento': 'S1', 'Num_Atomos': 3, 'Conexiones_Internas': 2, 'Densidad_Segmento': 0.5,
             'Centralidad_Grado_Promedio': 0.1, 'Centralidad_Intermediacion_Promedio': 0.2,
             'Centralidad_Cercania_Promedio': 0.3, 'Coeficiente_Agrupamiento_Promedio': 0.4}
        ])
    monkeypatch.setattr(mod, 'agrupar_por_segmentos_atomicos', fake_segment)

    metadata = StubMetadataRepo([
        (10, 'PepSeg', 5.0, 'nM'),
    ])
    structures = StubStructureRepo()
    exporter = StubExcelExporter()

    uc = mod.ExportFamilyReports(metadata, structures, exporter)
    inp = mod.ExportFamilyInput(family_prefix='beta-TRTX', export_type='segments_atomicos', granularity='atom', distance_threshold=10.0)
    excel_data, excel_filename, meta = uc.execute(inp)

    assert hasattr(excel_data, 'read')
    assert excel_filename.startswith('Family-beta-TRTX-segments_atomicos-atom')
    assert meta['Tipo_Analisis'] == 'Segmentación Atómica'
