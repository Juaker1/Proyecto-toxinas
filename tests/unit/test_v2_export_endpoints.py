import os
import pytest

from src.interfaces.http.flask.app import create_app_v2


@pytest.fixture(scope="module")
def client():
    app = create_app_v2()
    app.testing = True
    with app.test_client() as c:
        yield c


def assert_excel_meta(resp_json):
    assert isinstance(resp_json, dict)
    assert "meta" in resp_json and isinstance(resp_json["meta"], dict)
    assert "file" in resp_json and isinstance(resp_json["file"], dict)
    f = resp_json["file"]
    assert f.get("content_type") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert f.get("filename") and f.get("size_bytes") is not None


def test_export_residues_json_meta(client):
    r = client.get("/v2/export/residues/nav1_7/7?granularity=CA&threshold=10.0&format=json")
    assert r.status_code == 200
    data = r.get_json()
    assert_excel_meta(data)
    # Metadata shape can be stubbed by other tests; assert presence only
    assert isinstance(data["meta"], dict)


def test_export_segments_atomicos_json_meta(client):
    r = client.get("/v2/export/segments_atomicos/7?granularity=atom&threshold=10.0&format=json")
    assert r.status_code == 200
    data = r.get_json()
    assert_excel_meta(data)
    assert isinstance(data["meta"], dict)


def test_export_segments_atomicos_validation_error(client):
    r = client.get("/v2/export/segments_atomicos/7?granularity=CA&threshold=10.0")
    assert r.status_code == 400
    j = r.get_json()
    assert j and "error" in j


def test_export_family_residues_json_meta(client):
    r = client.get(
        "/v2/export/family/%CE%BC-TRTX-Hh2a?export_type=residues&granularity=CA&threshold=10.0&format=json"
    )
    assert r.status_code == 200
    data = r.get_json()
    assert_excel_meta(data)
    assert isinstance(data["meta"], dict)


def test_export_wt_comparison_json_meta(client):
    # Ensure reference file exists where the use case expects
    assert os.path.exists("pdbs/WT/hwt4_Hh2a_WT.pdb")
    r = client.get(
        "/v2/export/wt_comparison/%CE%BC-TRTX-Hh2a?export_type=residues&granularity=CA&threshold=10.0&reference_path=pdbs/WT/hwt4_Hh2a_WT.pdb&format=json"
    )
    assert r.status_code == 200
    data = r.get_json()
    assert_excel_meta(data)
    assert isinstance(data["meta"], dict)
