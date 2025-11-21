import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.application.use_cases.build_protein_graph import BuildProteinGraph, BuildProteinGraphInput

class DummyGraphPort:
    def __init__(self):
        self.called_with = None
    def build_graph(self, pdb_path: str, granularity: str, long_threshold: int, distance_threshold: float):
        self.called_with = (pdb_path, granularity, long_threshold, distance_threshold)
        return {'graph': True}
    def compute_metrics(self, G):
        assert G == {'graph': True}
        return {'num_nodes': 10, 'num_edges': 20}

def test_build_protein_graph_happy_path():
    port = DummyGraphPort()
    usecase = BuildProteinGraph(port)
    inp = BuildProteinGraphInput(
        pdb_path='/tmp/fake.pdb', granularity='CA', long_threshold=5, distance_threshold=10.0
    )
    result = usecase.execute(inp)
    assert result['graph'] == {'graph': True}
    assert result['properties'] == {'num_nodes': 10, 'num_edges': 20}
    assert port.called_with == ('/tmp/fake.pdb', 'CA', 5, 10.0)
