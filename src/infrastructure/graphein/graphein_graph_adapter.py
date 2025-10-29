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
        """Calcula métricas de grafo usando la función calculate_graph_metrics de graph_analysis2D.py"""
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
                },
                "error": "Grafo vacío"
            }

        # Preparar el grafo con atributos básicos necesarios para calculate_graph_metrics
        self._prepare_graph_attributes(G)

        # Use the analyzer from graph_analysis2D.py if available
        if _analyzer is not None:
            try:
                # Call the original calculate_graph_metrics function
                metrics = _analyzer.calculate_graph_metrics(G)

                # Adapt the result to the format expected by the Flask controller
                return {
                    "num_nodes": metrics['num_nodes'],
                    "num_edges": metrics['num_edges'],
                    "density": float(metrics['density']),
                    "avg_clustering": float(metrics['clustering_coefficient']),
                    "centrality": {
                        "degree": nx.get_node_attributes(G, 'degree_centrality'),
                        "betweenness": nx.get_node_attributes(G, 'betweenness_centrality'),
                        "closeness": nx.get_node_attributes(G, 'closeness_centrality'),
                        "clustering": nx.get_node_attributes(G, 'clustering_coefficient'),
                    },
                    # Additional metrics from graph_analysis2D.py
                    "disulfide_count": metrics.get('disulfide_count', 0),
                    "dipole_magnitude": metrics.get('dipole_magnitude', 0.0),
                    "avg_degree_centrality": metrics.get('avg_degree_centrality', 0.0),
                    "avg_betweenness_centrality": metrics.get('avg_betweenness_centrality', 0.0),
                    "avg_closeness_centrality": metrics.get('avg_closeness_centrality', 0.0),
                    "total_charge": metrics.get('total_charge', 0.0),
                    "avg_hydrophobicity": metrics.get('avg_hydrophobicity', 0.0),
                    "surface_charge": metrics.get('surface_charge', 0.0),
                    "pharmacophore_count": metrics.get('pharmacophore_count', 0),
                    "community_count": metrics.get('community_count', 0),
                }
            except nx.AmbiguousSolution as e:
                # Handle eigenvector centrality failure for disconnected graphs
                print(f"Warning: Eigenvector centrality failed for disconnected graph: {e}")
                print("Using fallback metrics calculation without eigenvector centrality")

                # Calculate basic metrics without eigenvector centrality
                degree_centrality = nx.degree_centrality(G)
                betweenness_centrality = nx.betweenness_centrality(G)
                closeness_centrality = nx.closeness_centrality(G)
                clustering_coefficient = nx.clustering(G)

                # Set eigenvector centrality to zeros for disconnected graphs
                eigenvector_centrality = {node: 0.0 for node in G.nodes()}

                # Calculate averages
                avg_degree_centrality = sum(degree_centrality.values()) / len(degree_centrality) if degree_centrality else 0.0
                avg_betweenness_centrality = sum(betweenness_centrality.values()) / len(betweenness_centrality) if betweenness_centrality else 0.0
                avg_closeness_centrality = sum(closeness_centrality.values()) / len(closeness_centrality) if closeness_centrality else 0.0
                avg_clustering = sum(clustering_coefficient.values()) / len(clustering_coefficient) if clustering_coefficient else 0.0

                # Set node attributes for centrality measures
                nx.set_node_attributes(G, degree_centrality, 'degree_centrality')
                nx.set_node_attributes(G, betweenness_centrality, 'betweenness_centrality')
                nx.set_node_attributes(G, closeness_centrality, 'closeness_centrality')
                nx.set_node_attributes(G, eigenvector_centrality, 'eigenvector_centrality')
                nx.set_node_attributes(G, clustering_coefficient, 'clustering_coefficient')

                # Calculate basic charge and hydrophobicity metrics
                charges = [G.nodes[n].get('charge', 0.0) for n in G.nodes()]
                hydrophobicity = [G.nodes[n].get('hydrophobicity', 0.0) for n in G.nodes()]

                total_charge = sum(charges)
                avg_hydrophobicity = sum(hydrophobicity) / len(hydrophobicity) if hydrophobicity else 0.0

                # Surface metrics
                surface_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_surface', False)]
                surface_charge = sum(G.nodes[n].get('charge', 0.0) for n in surface_nodes) if surface_nodes else 0.0

                # Pharmacophore count
                pharm_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_pharmacophore', False)]
                pharmacophore_count = len(pharm_nodes)

                # Community detection (with error handling)
                try:
                    communities = list(nx.algorithms.community.greedy_modularity_communities(G))
                    community_count = len(communities)
                except Exception:
                    community_count = 1  # Assume single community if detection fails

                return {
                    "num_nodes": G.number_of_nodes(),
                    "num_edges": G.number_of_edges(),
                    "density": float(nx.density(G)),
                    "avg_clustering": float(avg_clustering),
                    "centrality": {
                        "degree": degree_centrality,
                        "betweenness": betweenness_centrality,
                        "closeness": closeness_centrality,
                        "clustering": clustering_coefficient,
                    },
                    # Additional metrics with fallback values
                    "disulfide_count": G.graph.get('disulfide_count', 0),
                    "dipole_magnitude": float(G.graph.get('dipole_magnitude', 0)),
                    "avg_degree_centrality": round(avg_degree_centrality, 4),
                    "avg_betweenness_centrality": round(avg_betweenness_centrality, 4),
                    "avg_closeness_centrality": round(avg_closeness_centrality, 4),
                    "total_charge": float(total_charge),
                    "avg_hydrophobicity": round(avg_hydrophobicity, 2),
                    "surface_charge": float(surface_charge),
                    "pharmacophore_count": pharmacophore_count,
                    "community_count": community_count,
                }
            except Exception as e:
                # If the analyzer fails for any other reason, fall back to basic NetworkX calculations
                print(f"Warning: Using fallback metrics calculation: {e}")
                import traceback
                traceback.print_exc()

        # Fallback: basic NetworkX calculations (same as before)
        degree_centrality = nx.degree_centrality(G)
        betweenness_centrality = nx.betweenness_centrality(G)
        closeness_centrality = nx.closeness_centrality(G)
        clustering_coefficient = nx.clustering(G)

        avg_degree_centrality = sum(degree_centrality.values()) / len(degree_centrality) if degree_centrality else 0.0
        avg_betweenness_centrality = sum(betweenness_centrality.values()) / len(betweenness_centrality) if betweenness_centrality else 0.0
        avg_closeness_centrality = sum(closeness_centrality.values()) / len(closeness_centrality) if closeness_centrality else 0.0
        avg_clustering = sum(clustering_coefficient.values()) / len(clustering_coefficient) if clustering_coefficient else 0.0

        return {
            "num_nodes": G.number_of_nodes(),
            "num_edges": G.number_of_edges(),
            "density": float(nx.density(G)),
            "avg_clustering": float(avg_clustering),
            "centrality": {
                "degree": degree_centrality,
                "betweenness": betweenness_centrality,
                "closeness": closeness_centrality,
                "clustering": clustering_coefficient,
            },
            # Default values for additional metrics
            "disulfide_count": G.graph.get('disulfide_count', 0),
            "dipole_magnitude": float(G.graph.get('dipole_magnitude', 0)),
            "avg_degree_centrality": round(avg_degree_centrality, 4),
            "avg_betweenness_centrality": round(avg_betweenness_centrality, 4),
            "avg_closeness_centrality": round(avg_closeness_centrality, 4),
            "total_charge": 0.0,
            "avg_hydrophobicity": 0.0,
            "surface_charge": 0.0,
            "pharmacophore_count": 0,
            "community_count": 0,
        }

    def _prepare_graph_attributes(self, G: Any) -> None:
        """Prepara el grafo con atributos básicos necesarios para calculate_graph_metrics"""
        # Importar constantes necesarias
        try:
            from graphs.graph_analysis2D import HYDROPHOBICITY, CHARGES
        except ImportError:
            # Fallback constants if import fails
            HYDROPHOBICITY = {'A': 1.8, 'R': -4.5, 'N': -3.5, 'D': -3.5, 'C': 2.5, 'Q': -3.5, 'E': -3.5,
                             'G': -0.4, 'H': -3.2, 'I': 4.5, 'L': 3.8, 'K': -3.9, 'M': 1.9, 'F': 2.8,
                             'P': -1.6, 'S': -0.8, 'T': -0.7, 'W': -0.9, 'Y': -1.3, 'V': 4.2}
            CHARGES = {'A': 0, 'R': 1, 'N': 0, 'D': -1, 'C': 0, 'Q': 0, 'E': -1,
                      'G': 0, 'H': 0.5, 'I': 0, 'L': 0, 'K': 1, 'M': 0, 'F': 0,
                      'P': 0, 'S': 0, 'T': 0, 'W': 0, 'Y': 0, 'V': 0}

        # Agregar atributos básicos a los nodos si no existen
        for node in G.nodes():
            node_attrs = G.nodes[node]

            # Intentar extraer información del residuo desde los atributos de Graphein
            # Graphein normalmente tiene atributos como 'residue_name', 'amino_acid', etc.
            amino_acid = node_attrs.get('amino_acid', node_attrs.get('residue_name', 'X'))

            # Si amino_acid es un código de 3 letras, convertirlo a 1 letra
            if len(amino_acid) == 3:
                try:
                    from Bio.SeqUtils import seq1
                    amino_acid = seq1(amino_acid)
                except:
                    # Fallback mapping for common residues
                    aa_map = {'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
                             'GLN': 'Q', 'GLU': 'E', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
                             'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
                             'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'}
                    amino_acid = aa_map.get(amino_acid.upper(), 'X')

            # Agregar atributos requeridos por calculate_graph_metrics
            if 'charge' not in node_attrs:
                G.nodes[node]['charge'] = CHARGES.get(amino_acid.upper(), 0.0)

            if 'hydrophobicity' not in node_attrs:
                G.nodes[node]['hydrophobicity'] = HYDROPHOBICITY.get(amino_acid.upper(), 0.0)

            if 'amino_acid' not in node_attrs:
                G.nodes[node]['amino_acid'] = amino_acid

            # Atributos por defecto para otros campos requeridos
            if 'is_surface' not in node_attrs:
                G.nodes[node]['is_surface'] = False

            if 'is_pharmacophore' not in node_attrs:
                G.nodes[node]['is_pharmacophore'] = False

            if 'secondary_structure' not in node_attrs:
                G.nodes[node]['secondary_structure'] = 'unknown'

            if 'is_in_disulfide' not in node_attrs:
                G.nodes[node]['is_in_disulfide'] = False

        # Agregar atributos del grafo si no existen
        if 'disulfide_count' not in G.graph:
            G.graph['disulfide_count'] = 0

        if 'dipole_magnitude' not in G.graph:
            G.graph['dipole_magnitude'] = 0.0