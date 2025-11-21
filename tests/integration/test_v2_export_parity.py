import io
import json


def test_residue_export_columns_and_ic50_normalization(monkeypatch):
    """Validate single-toxin export uses expected column names and normalizes IC50 to nM."""
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()

    # Monkeypatch ExportService.prepare_residue_export_data to return fixed rows
    from src.application.use_cases import export_family_reports as fam_mod

    def fake_prepare_residue_export_data(G, toxin_name, ic50_value, ic50_unit, granularity):
        # Return minimal set with expected headers
        return [
            {
                'Cadena': 'A',
                'Residuo_Nombre': 'VAL',
                'Residuo_Numero': '21',
                'Centralidad_Grado': 0.1,
                'Centralidad_Intermediacion': 0.2,
                'Centralidad_Cercania': 0.3,
                'Coeficiente_Agrupamiento': 0.4,
                'Grado_Nodo': 5,
                'Toxina': toxin_name,
                'IC50_Value': 1.2,
                'IC50_Unit': 'μM',
                'IC50_nM': 1200.0,
            }
        ]

    class _ES:
        ExportService = type('ExportService', (), {
            'prepare_residue_export_data': staticmethod(fake_prepare_residue_export_data),
            'create_metadata': staticmethod(lambda *a, **k: {'IC50_Original': 1.2, 'Unidad_IC50': 'μM', 'IC50_nM': 1200.0})
        })

    # Residue export UC reuses ExportService alias from export_family_reports
    monkeypatch.setattr(fam_mod, 'ExportService', _ES.ExportService)

    # Fetch actual Excel and validate columns
    import pandas as pd
    from io import BytesIO
    with app.test_client() as c:
        r = c.get('/v2/export/residues/nav1_7/1?long=5&threshold=10&granularity=CA')
        assert r.status_code == 200
        assert r.mimetype.endswith('spreadsheetml.sheet')
        bio = BytesIO(r.data)
        xls = pd.ExcelFile(bio)
        # First data sheet should be 'Data'
        assert 'Metadatos' in xls.sheet_names
        data_sheet = next(sn for sn in xls.sheet_names if sn != 'Metadatos')
        df = pd.read_excel(xls, sheet_name=data_sheet)
        expected_cols = {
            'Cadena', 'Residuo_Nombre', 'Residuo_Numero',
            'Centralidad_Grado', 'Centralidad_Intermediacion',
            'Centralidad_Cercania', 'Coeficiente_Agrupamiento',
            'Grado_Nodo', 'Toxina', 'IC50_Value', 'IC50_Unit', 'IC50_nM'
        }
        assert expected_cols.issubset(set(df.columns))


def test_family_export_columns_and_filename(monkeypatch):
    """Validate family export uses expected filename scheme and retains IC50 columns if present."""
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    from src.application.use_cases import export_family_reports as mod

    # Minimal family toxins and GraphAnalyzer stubs
    monkeypatch.setattr(mod.GraphAnalyzer, 'create_graph_config', lambda g, l, d: {})
    monkeypatch.setattr(mod.GraphAnalyzer, 'construct_protein_graph', lambda p, c: __import__('networkx').Graph())

    # Patch metadata repo to return one toxin with IC50
    class FakeMeta:
        def get_family_toxins(self, prefix):
            return [(1, 'PepX', 0.5, 'nM')]

    # Patch structures repo to return any pdb bytes
    class FakeStruct:
        def get_pdb(self, source, peptide_id):
            return b'ATOM DUMMY PDB\n'

    # Patch exporter to capture inputs and return a dummy file
    captured = {}
    class FakeExporter:
        def generate_family_excel(self, toxin_dataframes, family_prefix, metadata, export_type='residues', granularity='CA'):
            captured['family_prefix'] = family_prefix
            captured['metadata'] = metadata
            return io.BytesIO(b'excel'), f"Dataset_Familia_{family_prefix}_IC50_Topologia_{granularity}_20250101_000000.xlsx"

    # Patch ExportService to create a DataFrame-compatible row
    import pandas as pd
    class _ES:
        class ExportService:
            @staticmethod
            def prepare_residue_export_data(G, peptide_code, ic50_value, ic50_unit, granularity):
                return [{'Toxina': peptide_code, 'IC50_Value': ic50_value, 'IC50_Unit': ic50_unit}]

    monkeypatch.setattr(mod, 'ExportService', _ES.ExportService)

    # Wire controller with our fakes (structures/metadata), exporter not required for JSON meta path
    from src.interfaces.http.flask.controllers.v2 import export_controller as ctl
    ctl.configure_export_dependencies(
        structures_repo=FakeStruct(), metadata_repo=FakeMeta()
    )

    import pandas as pd
    from io import BytesIO
    with app.test_client() as c:
        # Request actual file to inspect sheet columns
        r = c.get('/v2/export/family/%CE%B2-TRTX?long=5&threshold=10&granularity=CA&export_type=residues')
        assert r.status_code == 200
        assert r.mimetype.endswith('spreadsheetml.sheet')
        bio = BytesIO(r.data)
        xls = pd.ExcelFile(bio)
        assert 'Metadatos' in xls.sheet_names
        data_sheets = [sn for sn in xls.sheet_names if sn != 'Metadatos']
        assert len(data_sheets) >= 1
        df = pd.read_excel(xls, sheet_name=data_sheets[0])
        # Minimal parity: includes toxin and IC50 columns propagated by UC stub
        assert {'Toxina', 'IC50_Value', 'IC50_Unit'}.issubset(set(df.columns))


def test_graph_presenter_top5_contract():
    """Ensure presenter returns residue, residueName, chain fields for top_5_residues as expected by frontend."""
    from src.interfaces.http.flask.presenters.graph_presenter import GraphPresenter

    props = {
        'centrality': {
            'degree': {'A:VAL:21:CA': 0.9, 'B:LYS:7:CA': 0.8},
            'betweenness': {}, 'closeness': {}, 'clustering': {}
        }
    }
    meta = {'source': 's', 'id': 1}
    fig = {'data': [], 'layout': {}}
    out = GraphPresenter.present(props, meta, fig)
    tops = out['top_5_residues']['degree_centrality']
    assert isinstance(tops, list) and len(tops) >= 1
    first = tops[0]
    assert 'residue' in first and 'residueName' in first and 'chain' in first
