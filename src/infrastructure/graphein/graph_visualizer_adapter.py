from typing import Any, Dict, List, Tuple
import networkx as nx


class MolstarGraphVisualizerAdapter:
    """
    WebGL-optimized adapter for Mol* graph rendering.
    Generates minimal node/edge data instead of heavy Plotly traces.
    Reduces payload size and enables sub-second rendering for dense graphs.
    """

    @staticmethod
    def create_complete_visualization(G: Any, granularity: str, protein_id: int) -> Dict[str, Any]:
        """
        Creates a lightweight graph visualization data structure optimized for WebGL rendering.
        
        Args:
            G: NetworkX graph with 3D node positions
            granularity: 'atom' or 'CA' 
            protein_id: Protein identifier
            
        Returns:
            Dict with nodes (coords + labels) and edges (pairs of node indices)
        """
        if not isinstance(G, nx.Graph):
            raise TypeError("Expected a networkx.Graph")

        # Extract 3D positions from node attributes
        pos3d = MolstarGraphVisualizerAdapter._get_positions(G)
        
        # Build node data with coordinates and labels
        nodes = []
        node_to_index = {}
        
        for idx, node in enumerate(G.nodes()):
            x, y, z = pos3d[node]
            label = str(node)
            chain = None
            res_name = None
            res_num = None
            atom_name = None

            try:
                node_data = G.nodes[node]
                chain = node_data.get('chain_id') or node_data.get('chain')
                res_name = node_data.get('residue_name') or node_data.get('residue_name_short')
                res_num = node_data.get('residue_number')
                atom_name = node_data.get('atom_name') or node_data.get('atom_type')

                if atom_name is None and isinstance(node, str):
                    parts = node.split(':')
                    if len(parts) >= 4:
                        atom_name = parts[3]

                if chain and res_name is not None and res_num is not None:
                    if atom_name:
                        label = f"{chain}:{res_name}:{res_num}:{atom_name}"
                    else:
                        label = f"{chain}:{res_name}:{res_num}"
            except Exception:
                pass

            node_entry = {
                'x': float(x),
                'y': float(y),
                'z': float(z),
                'label': label
            }

            if chain:
                node_entry['chain'] = chain
            if res_name is not None:
                node_entry['residueName'] = res_name
            if res_num is not None:
                node_entry['residueNumber'] = res_num
            if atom_name:
                node_entry['atomName'] = atom_name

            nodes.append(node_entry)
            node_to_index[node] = idx
        
        # Build edge data: pairs of node indices
        edges = []
        for u, v in G.edges():
            if u in node_to_index and v in node_to_index:
                edges.append([node_to_index[u], node_to_index[v]])
        
        # Compute bounding box for camera setup
        if nodes:
            xs = [n['x'] for n in nodes]
            ys = [n['y'] for n in nodes]
            zs = [n['z'] for n in nodes]
            bbox = {
                'min': [min(xs), min(ys), min(zs)],
                'max': [max(xs), max(ys), max(zs)],
                'center': [
                    sum(xs) / len(xs),
                    sum(ys) / len(ys),
                    sum(zs) / len(zs)
                ]
            }
        else:
            bbox = {'min': [0, 0, 0], 'max': [0, 0, 0], 'center': [0, 0, 0]}
        
        return {
            'nodes': nodes,
            'edges': edges,
            'metadata': {
                'protein_id': protein_id,
                'granularity': granularity,
                'node_count': len(nodes),
                'edge_count': len(edges),
                'bbox': bbox
            }
        }

    @staticmethod
    def _get_positions(G: nx.Graph) -> Dict[Any, Tuple[float, float, float]]:
        """
        Extracts or generates 3D positions for graph nodes.
        Prefers real PDB coordinates from 'pos' attribute.
        """
        # Try to get positions from node attributes (set by graph builder)
        pos_attr = nx.get_node_attributes(G, "pos")
        
        if pos_attr and all(isinstance(v, (list, tuple)) and len(v) == 3 for v in pos_attr.values()):
            return pos_attr
        
        # Fallback: 3D spring layout if no coordinates available
        return nx.spring_layout(G, seed=42, dim=3)

    @staticmethod
    def convert_numpy_to_lists(obj):
        """
        Recursively converts numpy arrays/scalars to native Python types.
        Ensures JSON serializability.
        """
        try:
            import numpy as np
        except ImportError:
            return obj

        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.floating, np.integer, np.bool_)):
            try:
                return obj.item()
            except Exception:
                return bool(obj) if isinstance(obj, np.bool_) else float(obj)
        if isinstance(obj, dict):
            return {k: MolstarGraphVisualizerAdapter.convert_numpy_to_lists(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [MolstarGraphVisualizerAdapter.convert_numpy_to_lists(x) for x in obj]
        return obj
