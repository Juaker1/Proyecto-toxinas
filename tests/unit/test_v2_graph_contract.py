import os, sys

root = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir, os.pardir)))
if root not in sys.path:
    sys.path.insert(0, root)

from app import create_app as create_app_v1
from src.interfaces.http.flask.app import create_app_v2
from app.services.database_service import DatabaseService


def pick_sample():
    db = DatabaseService()
    src = 'nav1_7'
    peptides = db.get_all_nav1_7()
    if not peptides:
        src = 'toxinas'
        peptides = db.get_all_toxinas()
    assert peptides, 'No peptides found in database.'
    return src, peptides[0][0]


def test_graph_contract_v1_vs_v2():
    source, pid = pick_sample()

    app1 = create_app_v1()
    app2 = create_app_v2()

    with app1.test_client() as c1, app2.test_client() as c2:
        r1 = c1.get(f"/get_protein_graph/{source}/{pid}?granularity=CA&threshold=10.0")
        r2 = c2.get(f"/v2/proteins/{source}/{pid}/graph?granularity=CA&threshold=10.0")

        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.is_json and r2.is_json
        j1, j2 = r1.get_json(), r2.get_json()

        # Core keys expected by frontend
        for key in ['plotData','layout','properties','summary_statistics','top_5_residues']:
            assert key in j1, f"v1 missing {key}"
            assert key in j2, f"v2 missing {key}"

        # Property subset
        for k in ['num_nodes','num_edges','density','avg_clustering']:
            assert k in j1['properties'], f"v1 properties missing {k}"
            assert k in j2['properties'], f"v2 properties missing {k}"
