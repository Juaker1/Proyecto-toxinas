from typing import Any, Dict
import networkx as nx
import numpy as np
import sys
import os

# Add project root to path to import from graphs/
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the analyzer from graphs/
try:
    from graphs.graph_analysis2D import Nav17ToxinGraphAnalyzer
    _analyzer = Nav17ToxinGraphAnalyzer()
except ImportError:
    # Fallback if import fails
    _analyzer = None


class GrapheinGraphAdapter:
    """Adapter that implements the graph port using the analyzer in graphs/* (no legacy)."""

    def build_graph(
        self,
        pdb_path: str,
        granularity: str,
        long_threshold: int,
        distance_threshold: float,
    ) -> Any:
        # When atom-level granularity is requested, use Graphein for construction like legacy
        # Build with Graphein using distance-threshold edges (required)
        from functools import partial
        from graphein.protein.config import ProteinGraphConfig
        from graphein.protein.graphs import construct_graph
        from graphein.protein.edges.distance import add_distance_threshold

        try:
            edge_fns = [
                partial(
                    add_distance_threshold,
                    long_interaction_threshold=int(long_threshold),
                    threshold=float(distance_threshold),
                )
            ]
            config = ProteinGraphConfig(
                granularity=("atom" if str(granularity).lower() == "atom" else "CA"),
                edge_construction_functions=edge_fns,
                save_graphs=False,
                pdb_dir=None,
            )
            G = construct_graph(config=config, pdb_code=None, path=pdb_path)
            return G
        except Exception as e:
            # Graphein must be used; surface a clear error
            raise RuntimeError(f"Graphein graph construction failed for {pdb_path}: {e}")

    def compute_metrics(self, G: Any) -> Dict[str, Any]:
        """Calcula métricas de grafo usando el módulo común para evitar duplicación"""
        if not isinstance(G, nx.Graph):
            raise TypeError("Expected a networkx.Graph")

        if len(G) == 0:
            return {
                "num_nodes": 0,
                "num_edges": 0,
                "density": 0.0,
                "avg_clustering": 0.0,
                "centrality": {
                    "degree": {},
                    "betweenness": {},
                    "closeness": {},
                    "clustering": {},
                    "seq_distance_avg": {},
                    "long_contacts_prop": {},
                },
                "error": "Grafo vacío"
            }

        # Usar el módulo común para métricas
        from src.infrastructure.graph.graph_metrics import compute_comprehensive_metrics
        result = compute_comprehensive_metrics(G)

        # Adaptar al formato esperado por el controlador Flask
        centrality_data = result.get('centrality', {})

        return {
            "num_nodes": result['properties']['num_nodes'],
            "num_edges": result['properties']['num_edges'],
            "density": result['properties']['density'],
            "avg_clustering": result['properties']['avg_clustering'],
            "centrality": {
                "degree": centrality_data.get('degree', {}),
                "betweenness": centrality_data.get('betweenness', {}),
                "closeness": centrality_data.get('closeness', {}),
                "clustering": centrality_data.get('clustering', {}),
                "seq_distance_avg": centrality_data.get('seq_distance_avg', {}),
                "long_contacts_prop": centrality_data.get('long_contacts_prop', {}),
            },
            # Métricas adicionales
            "disulfide_count": result['properties'].get('disulfide_count', 0),
            "dipole_magnitude": result['properties'].get('dipole_magnitude', 0.0),
            "avg_degree_centrality": result['summary_statistics'].get('degree', {}).get('mean', 0.0),
            "avg_betweenness_centrality": result['summary_statistics'].get('betweenness', {}).get('mean', 0.0),
            "avg_closeness_centrality": result['summary_statistics'].get('closeness', {}).get('mean', 0.0),
            "total_charge": result['properties'].get('total_charge', 0.0),
            "avg_hydrophobicity": result['properties'].get('avg_hydrophobicity', 0.0),
            "surface_charge": result['properties'].get('surface_charge', 0.0),
            "pharmacophore_count": result['properties'].get('pharmacophore_count', 0),
            "community_count": result['properties'].get('community_count', 0),
        }

    def _prepare_graph_attributes(self, G: Any) -> None:
        """Prepara el grafo con atributos básicos necesarios (simplificado)"""
        # El módulo común graph_metrics maneja la preparación de atributos
        # Esta función se mantiene por compatibilidad pero está obsoleta
        pass