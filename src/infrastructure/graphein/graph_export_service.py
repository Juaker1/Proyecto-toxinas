from dataclasses import dataclass

from src.infrastructure.graphein.graphein_graph_adapter import GrapheinGraphAdapter


@dataclass(frozen=True)
class GraphConfig:
    granularity: str
    distance_threshold: float


class GraphExportService:
    """Lightweight replacement for legacy GraphAnalyzer used by export UCs."""

    @staticmethod
    def create_graph_config(granularity: str, distance_threshold: float) -> GraphConfig:
        return GraphConfig(granularity=granularity, distance_threshold=distance_threshold)

    @staticmethod
    def construct_protein_graph(pdb_path: str, config: GraphConfig):
        adapter = GrapheinGraphAdapter()
        return adapter.build_graph(
            pdb_path=pdb_path,
            granularity=config.granularity,
            distance_threshold=config.distance_threshold,
        )
