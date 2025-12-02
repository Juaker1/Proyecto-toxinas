import json


def test_app_factory_and_config():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    cfg = app.config.get('APP_CONFIG')
    assert isinstance(cfg, dict)
    assert 'db_path' in cfg and 'pdb_dir' in cfg and 'psf_dir' in cfg and 'wt_reference_path' in cfg


def test_root_serves_template():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    with app.test_client() as c:
        r = c.get('/')
        # Should serve HTML
        assert r.status_code == 200
        assert 'text/html' in r.content_type


def test_legacy_api_family_dipoles_removed():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    with app.test_client() as c:
        fam = 'β-TRTX'
        r = c.get(f'/api/family-dipoles/{fam}', follow_redirects=False)
        assert r.status_code == 404


def test_legacy_get_protein_graph_removed():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    with app.test_client() as c:
        r = c.get('/get_protein_graph/nav1_7/1?long=5&threshold=10&granularity=CA', follow_redirects=False)
        assert r.status_code == 404


def test_v2_families_endpoint_exists_and_returns_json():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    with app.test_client() as c:
        r = c.get('/v2/families')
        assert r.status_code == 200
        payload = r.get_json()
        assert isinstance(payload, dict)
        assert 'success' in payload


def test_no_legacy_aliases_registered():
    from src.interfaces.http.flask.app import create_app_v2
    app = create_app_v2()
    aliases = [
        str(r) for r in app.url_map.iter_rules()
        if any(str(r).startswith(p) for p in [
            '/get_', '/calculate_dipole_from_db',
            '/export_residues_xlsx', '/export_segments_atomicos_xlsx',
            '/api/family-dipoles'
        ])
    ]
    assert len(aliases) == 0
