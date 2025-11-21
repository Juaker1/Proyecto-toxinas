from typing import Protocol, Any, Dict

class GraphServicePort(Protocol):
    def build_graph(self, pdb_path: str, granularity: str, distance_threshold: float) -> Any:
        """Build a graph from a PDB path.

        Accepts raw primitives. Upstream use cases may pass domain value objects
        and normalize to primitives before calling this port.
        """

    def compute_metrics(self, G: Any) -> Dict[str, Any]:
        ...
