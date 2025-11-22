import os
import sys
from typing import Any, Dict

import networkx as nx
import numpy as np
from Bio.PDB import PDBParser
from Bio.PDB.Polypeptide import is_aa
from Bio.SeqUtils import seq1
from src.utils.disulfide import find_disulfide_pairs


HYDROPHOBICITY = {
    'A': 1.8, 'R': -4.5, 'N': -3.5, 'D': -3.5, 'C': 2.5,
    'Q': -3.5, 'E': -3.5, 'G': -0.4, 'H': -3.2, 'I': 4.5,
    'L': 3.8, 'K': -3.9, 'M': 1.9, 'F': 2.8, 'P': -1.6,
    'S': -0.8, 'T': -0.7, 'W': -0.9, 'Y': -1.3, 'V': 4.2
}

CHARGES = {
    'A': 0, 'R': 1, 'N': 0, 'D': -1, 'C': 0,
    'Q': 0, 'E': -1, 'G': 0, 'H': 0.5, 'I': 0,
    'L': 0, 'K': 1, 'M': 0, 'F': 0, 'P': 0,
    'S': 0, 'T': 0, 'W': 0, 'Y': 0, 'V': 0
}

# Allow importing optional analyzer module (graphs/graph_analysis2D.py)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from graphs.graph_analysis2D import Nav17ToxinGraphAnalyzer
    _ANALYZER = Nav17ToxinGraphAnalyzer()
except Exception:
    _ANALYZER = None


class GrapheinGraphAdapter:
    """Graph adapter that builds atom/residue graphs directly from PDB structures."""

    def __init__(self) -> None:
        self._parser = PDBParser(QUIET=True)


    def build_graph(
        self,
        pdb_path: str,
        granularity: str,
        distance_threshold: float,
    ) -> Any:
        gran = str(granularity).lower()
        structure = self._parser.get_structure(os.path.basename(pdb_path) or "prot", pdb_path)

        threshold = float(distance_threshold)

        if gran == "atom":
            return self._build_atom_graph(structure, threshold)

        if gran in {"ca", "residue"}:
            return self._build_ca_graph(structure, threshold)

        if _ANALYZER is not None:
            try:
                return _ANALYZER.build_enhanced_graph(structure, cutoff_distance=threshold)
            except Exception:
                # Fall back to internal builder if analyzer fails
                pass

        return self._build_residue_graph(structure, threshold)

    def _build_ca_graph(self, structure, distance_threshold: float) -> nx.Graph:
        """Builds a CA-only graph reusing the atom pipeline for consistent metadata."""
        G = self._build_atom_graph(
            structure,
            distance_threshold,
            atom_selector=lambda atom: atom.get_name().strip().upper() == "CA",
        )
        # Add disulfide count
        disulfide_bridges = find_disulfide_pairs(structure)
        G.graph['disulfide_count'] = len(disulfide_bridges)
        return G

    def _build_residue_graph(self, structure, distance_threshold: float) -> nx.Graph:
        model = structure[0]

        residues = []
        coords = []

        for chain in model:
            for residue in chain:
                if not is_aa(residue, standard=True):
                    continue
                if "CA" not in residue:
                    continue
                res_seq = residue.id[1]
                res_name = residue.resname.strip()
                try:
                    aa = seq1(res_name)
                except Exception:
                    aa = res_name.strip()
                coord = residue["CA"].get_coord()
                coord_list = coord.tolist()
                node_id = f"{chain.id}:{res_name}:{res_seq}"
                residues.append({
                    "node_id": node_id,
                    "chain_id": chain.id,
                    "residue_number": int(res_seq),
                    "residue_name": res_name,
                    "amino_acid": aa,
                    "pos": coord_list,
                    "hydrophobicity": HYDROPHOBICITY.get(aa, 0.0),
                    "charge": CHARGES.get(aa, 0.0),
                })
                coords.append(coord)

        coords_arr = np.asarray(coords, dtype=float)
        G = nx.Graph()
        residue_ids = []

        for res in residues:
            node_id = res.pop("node_id")
            residue_ids.append(node_id)
            G.add_node(node_id, **res)

        if not len(coords_arr):
            return G

        cutoff = float(distance_threshold)
        n = len(residues)
        for i in range(n):
            for j in range(i + 1, n):
                dist = float(np.linalg.norm(coords_arr[i] - coords_arr[j]))
                if dist <= cutoff:
                    G.add_edge(residue_ids[i], residue_ids[j], weight=dist)

        # Add disulfide count and edges
        disulfide_bridges = find_disulfide_pairs(structure)
        G.graph['disulfide_count'] = len(disulfide_bridges)
        # Add disulfide edges between residues
        for res1, res2 in disulfide_bridges:
            node1 = next((nid for nid in residue_ids if f":{res1}" in nid), None)
            node2 = next((nid for nid in residue_ids if f":{res2}" in nid), None)
            if node1 and node2 and node1 != node2:
                G.add_edge(node1, node2, weight=1.0, type='disulfide', interaction_strength=10.0)

        return G

    def _build_atom_graph(self, structure, distance_threshold: float, atom_selector=None) -> nx.Graph:
        """Construye un grafo atómico simple usando Bio.PDB para evitar dependencias externas."""
        model = structure[0]

        atoms = []
        coords = []
        node_ids = []

        for chain in model:
            for residue in chain:
                res_id = residue.id[1]
                res_name = residue.resname.strip()
                try:
                    aa = seq1(res_name)
                except Exception:
                    aa = res_name.strip()
                for atom in residue:
                    if atom_selector is not None and not atom_selector(atom):
                        continue
                    coord = atom.get_coord()
                    coord_list = coord.tolist()
                    element = getattr(atom, "element", "").strip() or atom.get_name().strip()[:1]
                    atoms.append({
                        "chain_id": chain.id,
                        "residue_number": int(res_id),
                        "residue_name": res_name,
                        "atom_name": atom.get_name().strip(),
                        "element": element,
                        "pos": coord_list,
                        "amino_acid": aa,
                        "hydrophobicity": HYDROPHOBICITY.get(aa, 0.0),
                        "charge": CHARGES.get(aa, 0.0),
                    })
                    coords.append(coord)

        coords = np.asarray(coords, dtype=float)
        G = nx.Graph()

        for atom in atoms:
            node_id = f"{atom['chain_id']}:{atom['residue_name']}:{atom['residue_number']}:{atom['atom_name']}"
            node_ids.append(node_id)
            G.add_node(node_id, **atom)

        if len(coords) == 0:
            return G

        diffs = coords[:, None, :] - coords[None, :, :]
        dists = np.linalg.norm(diffs, axis=-1)
        cutoff = float(distance_threshold)

        n = len(atoms)
        for i in range(n):
            for j in range(i + 1, n):
                if dists[i, j] <= cutoff:
                    G.add_edge(node_ids[i], node_ids[j], weight=float(dists[i, j]))

        # Add disulfide count
        disulfide_bridges = find_disulfide_pairs(structure)
        G.graph['disulfide_count'] = len(disulfide_bridges)

        return G

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