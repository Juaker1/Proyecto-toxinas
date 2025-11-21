import io


def test_export_residues_json_meta_uses_stub_uc(monkeypatch):
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()

    # Inject a stub use case that returns a tiny excel buffer and meta
    from src.interfaces.http.flask.controllers.v2 import export_controller as mod

    class StubExportUC:
        def __init__(self):
            self.calls = []

        def execute(self, inp):
            # record minimal attributes for verification if needed
            self.calls.append(inp)
            meta = {"source": getattr(inp, 'source', None), "pid": getattr(inp, 'pid', None)}
            return io.BytesIO(b"excel-bytes"), "Residues_test.xlsx", meta

    stub = StubExportUC()
    mod.configure_export_dependencies(export_uc=stub)

    with app.test_client() as c:
        r = c.get('/v2/export/residues/nav1_7/1?long=5&threshold=10&granularity=CA&format=json')
        assert r.status_code == 200
        payload = r.get_json()
        assert 'meta' in payload and 'file' in payload
        assert payload['file']['filename'].endswith('.xlsx')
        assert payload['file']['size_bytes'] > 0


def test_export_segments_atomicos_requires_atom_granularity():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    with app.test_client() as c:
        r = c.get('/v2/export/segments_atomicos/1?granularity=CA&format=json')
        assert r.status_code == 400
        payload = r.get_json()
        assert 'error' in payload


def test_export_segments_atomicos_json_meta_with_stub_uc():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    from src.interfaces.http.flask.controllers.v2 import export_controller as mod

    class StubSegmentsUC:
        def __init__(self):
            self.calls = []

        def execute(self, inp):
            self.calls.append(inp)
            return io.BytesIO(b"seg-bytes"), "Segments_test.xlsx", {"pid": getattr(inp, 'pid', None)}

    stub = StubSegmentsUC()
    mod.configure_export_dependencies(segments_uc=stub)

    with app.test_client() as c:
        r = c.get('/v2/export/segments_atomicos/1?long=5&threshold=10&granularity=atom&format=json')
        assert r.status_code == 200
        payload = r.get_json()
        assert 'meta' in payload and 'file' in payload
        assert payload['file']['filename'].endswith('.xlsx')
        assert payload['file']['size_bytes'] > 0


def test_export_wt_comparison_uses_default_reference_path_when_missing():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    from src.interfaces.http.flask.controllers.v2 import export_controller as mod

    class CapturingWTUC:
        def __init__(self):
            self.last_input = None

        def execute(self, inp):
            # capture the input object to inspect reference_path
            self.last_input = inp
            return io.BytesIO(b"wt-bytes"), "WT_Comparison.xlsx", {"wt_family": getattr(inp, 'wt_family', None)}

    stub = CapturingWTUC()
    # Ensure the module has a default reference path configured (via app factory DI)
    # Then override the wt_uc only, keeping default_reference_path from app wiring
    mod.configure_export_dependencies(wt_uc=stub)

    with app.test_client() as c:
        r = c.get('/v2/export/wt_comparison/μ-TRTX-Hh2a?long=5&threshold=10&granularity=CA&format=json')
        assert r.status_code == 200
        payload = r.get_json()
        assert 'meta' in payload and 'file' in payload
        # Validate the controller provided a non-empty reference_path via default
        assert stub.last_input is not None
        ref = getattr(stub.last_input, 'reference_path', None)
        assert isinstance(ref, str) and len(ref) > 0


def test_export_family_json_meta_with_stub_uc():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    from src.interfaces.http.flask.controllers.v2 import export_controller as mod

    class StubFamilyUC:
        def __init__(self):
            self.calls = []

        def execute(self, inp):
            self.calls.append(inp)
            return io.BytesIO(b"family-bytes"), "Family_test.xlsx", {"family": getattr(inp, 'family_prefix', None)}

    stub = StubFamilyUC()
    mod.configure_export_dependencies(family_uc=stub)

    with app.test_client() as c:
        r = c.get('/v2/export/family/%CE%BC-TRTX-Hh2a?long=5&threshold=10&granularity=CA&export_type=residues&format=json')
        assert r.status_code == 200
        payload = r.get_json()
        assert 'meta' in payload and 'file' in payload
        assert payload['file']['filename'].endswith('.xlsx')
        assert payload['file']['size_bytes'] > 0
