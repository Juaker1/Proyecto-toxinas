import json


def test_v2_structures_pdb_returns_text_and_contains_atom():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    with app.test_client() as c:
        # Use a known nav1_7 id (1 is used elsewhere in tests)
        r = c.get('/v2/structures/nav1_7/1/pdb')
        assert r.status_code == 200
        assert 'text/plain' in r.content_type
        text = r.get_data(as_text=True)
        assert len(text) > 0
        # Typical PDB lines should appear
        assert ('ATOM' in text) or ('HETATM' in text)


def test_v2_dipole_post_nav1_7_returns_success_result():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    with app.test_client() as c:
        r = c.post('/v2/dipole/nav1_7/1')
        assert r.status_code == 200
        payload = r.get_json()
        assert isinstance(payload, dict)
        assert 'result' in payload
        assert payload['result'].get('success') is True
        assert 'dipole' in payload['result']


def test_v2_graph_returns_expected_keys():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    with app.test_client() as c:
        r = c.get('/v2/proteins/nav1_7/1/graph?threshold=10&granularity=CA')
        assert r.status_code == 200
        payload = r.get_json()
        assert isinstance(payload, dict)
        # Check presenter contract keys
        for key in ('plotData', 'layout', 'properties', 'summary_statistics', 'top_5_residues', 'key_residues'):
            assert key in payload
