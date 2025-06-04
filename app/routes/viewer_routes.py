from flask import Blueprint, render_template, request, jsonify
from functools import partial
import sqlite3
import tempfile
import os
import sys
import numpy as np

from graphein.protein.config import ProteinGraphConfig
from graphein.protein.graphs import construct_graph
from graphein.protein.edges.distance import add_distance_threshold
from graphein.protein.visualisation import plotly_protein_structure_graph
from graphein.protein.features.nodes.amino_acid import amino_acid_one_hot
from graphein.protein.features.nodes.geometry import add_sidechain_vector
from graphein.protein.edges.atomic import add_atomic_edges, add_bond_order
from graphein.protein.edges.distance import add_k_nn_edges
from plotly.utils import PlotlyJSONEncoder
import networkx as nx

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'graphs'))
from graphs.graph_analysis2D import Nav17ToxinGraphAnalyzer

viewer_bp = Blueprint('viewer', __name__)

DB_PATH = "database/toxins.db"
PDB_DIR = "pdbs"


toxin_analyzer = Nav17ToxinGraphAnalyzer()

def fetch_peptides(group):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if group == "toxinas":
        cursor.execute("SELECT peptide_id, peptide_name FROM Peptides")
    elif group == "nav1_7":
        cursor.execute("SELECT id, peptide_code FROM Nav1_7_InhibitorPeptides")
    else:
        return []

    return cursor.fetchall()


@viewer_bp.route("/")
def viewer():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT peptide_id, peptide_name FROM Peptides")
    toxinas = cursor.fetchall()

    cursor.execute("SELECT id, peptide_code FROM Nav1_7_InhibitorPeptides")
    nav1_7 = cursor.fetchall()

    conn.close()

    return render_template("viewer.html", toxinas=toxinas, nav1_7=nav1_7)


@viewer_bp.route("/get_pdb/<string:source>/<int:pid>")
def get_pdb(source, pid):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if source == "toxinas":
        cursor.execute("SELECT pdb_file FROM Peptides WHERE peptide_id = ?", (pid,))
    elif source == "nav1_7":
        cursor.execute("SELECT pdb_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (pid,))
    else:
        return jsonify({"error": "Invalid source"}), 400

    result = cursor.fetchone()
    if not result:
        return jsonify({"error": "PDB not found"}), 404

    pdb_data = result[0]

    try:
        if isinstance(pdb_data, bytes):
            return pdb_data.decode('utf-8'), 200, {'Content-Type': 'text/plain'}
        else:
            return str(pdb_data), 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        return jsonify({"error": f"Error processing PDB: {str(e)}"}), 500



def compute_graph_properties(G):
    props = {}
    props["num_nodes"] = G.number_of_nodes()
    props["num_edges"] = G.number_of_edges()
    props["density"] = nx.density(G)
    
    degrees = list(dict(G.degree()).values())
    props["avg_degree"] = sum(degrees) / len(degrees) if degrees else 0.0
    
    props["avg_clustering"] = nx.average_clustering(G)
    
    # Componentes conectados
    comps = list(nx.connected_components(G)) if not G.is_directed() else list(nx.weakly_connected_components(G))
    props["num_components"] = len(comps)
    
    # Calcular métricas de centralidad
    props["centrality"] = {
        "degree": nx.degree_centrality(G),
        "betweenness": nx.betweenness_centrality(G),
        "closeness": nx.closeness_centrality(G),
        "clustering": nx.clustering(G)
    }
    
    # Calcular estadísticas de centralidad (min, max, mean)
    for metric_name, metric_values in props["centrality"].items():
        values = list(metric_values.values())
        if values:
            props[f"{metric_name}_min"] = min(values)
            props[f"{metric_name}_max"] = max(values)
            props[f"{metric_name}_mean"] = sum(values) / len(values)
            
            # Encontrar residuos con valor máximo (top residues)
            max_value = max(values)
            top_residues = [node for node, value in metric_values.items() 
                           if abs(value - max_value) < 0.0001]
            props[f"{metric_name}_top"] = {
                "residues": top_residues,
                "value": max_value
            }
            
            # Top 5 residuos para cada métrica - CORREGIR AQUÍ
            top5 = sorted(metric_values.items(), key=lambda x: x[1], reverse=True)[:5]
            formatted_top5 = []
            for node_id, value in top5:
                # Procesar el node_id que viene como "A:LYS:14:CE"
                parts = str(node_id).split(':')
                if len(parts) >= 3:
                    formatted_top5.append({
                        "residue": parts[2],        # número del residuo
                        "value": value,
                        "residueName": parts[1],    # nombre del aminoácido
                        "chain": parts[0]           # cadena
                    })
                else:
                    formatted_top5.append({
                        "residue": str(node_id),
                        "value": value,
                        "residueName": "UNK",
                        "chain": "A"
                    })
            
            props[f"{metric_name}_top5"] = formatted_top5
    
    return props


@viewer_bp.route("/get_protein_graph/<string:source>/<int:pid>")
def get_protein_graph(source, pid):
    try:
        print(f"🚀 Iniciando análisis de grafo para {source}/{pid}")
        
    
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if source == "toxinas":
            cursor.execute("SELECT pdb_file FROM Peptides WHERE peptide_id = ?", (pid,))
        elif source == "nav1_7":
            cursor.execute("SELECT pdb_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (pid,))
        else:
            return jsonify({"error": "Invalid source"}), 400
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({"error": "PDB not found"}), 404
        
        pdb_data = result[0]

        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
            if isinstance(pdb_data, bytes):
                temp_file.write(pdb_data)
            else:
                temp_file.write(pdb_data.encode('utf-8'))
            temp_path = temp_file.name
        
        try:

            if granularity == 'atom':
                cfg = ProteinGraphConfig(
                    granularity="atom",
                    edge_construction_functions=[
                        partial(add_distance_threshold,
                                long_interaction_threshold=long_threshold,
                                threshold=distance_threshold)
                    ]
                )
                plot_title = f"Grafo de Átomos (ID: {pid})"
            else:  
                cfg = ProteinGraphConfig(
                    granularity="CA",
                    edge_construction_functions=[
                        partial(add_distance_threshold,
                                long_interaction_threshold=long_threshold,
                                threshold=distance_threshold)
                    ]
                )
                plot_title = f"Grafo de CA (ID: {pid})"
            
     
            G = construct_graph(config=cfg, pdb_code=None, path=temp_path)
            
           
            # Calcular las propiedades del grafo
            props = compute_graph_properties(G)
            
            fig = plotly_protein_structure_graph(
                G,
                colour_nodes_by="seq_position",
                colour_edges_by="kind",
                label_node_ids=False,
                node_size_multiplier=0,
                plot_title=plot_title
            )
            
            fig.update_layout(
                scene=dict(
                    xaxis=dict(title='X', showgrid=True, zeroline=True, backgroundcolor='rgba(240,240,240,0.9)', showbackground=True, gridcolor='lightgray', showticklabels=True, tickfont=dict(size=10)),
                    yaxis=dict(title='Y', showgrid=True, zeroline=True, backgroundcolor='rgba(240,240,240,0.9)', showbackground=True, gridcolor='lightgray', showticklabels=True, tickfont=dict(size=10)),
                    zaxis=dict(title='Z', showgrid=True, zeroline=True, backgroundcolor='rgba(240,240,240,0.9)', showbackground=True, gridcolor='lightgray', showticklabels=True, tickfont=dict(size=10)),
                    aspectmode='data',
                    bgcolor='white'
                ),
                paper_bgcolor='white',
                plot_bgcolor='white',
                showlegend=True,
                legend=dict(x=0.85, y=0.9, bgcolor='rgba(255,255,255,0.5)', bordercolor='black', borderwidth=1)
            )
            
            fig.update_traces(marker=dict(opacity=0.9), selector=dict(mode='markers'))
            fig.update_traces(line=dict(width=2), selector=dict(mode='lines'))
            
            for trace in fig.data:
                if trace.mode == 'markers':
                    trace.name = "Residuos" if granularity == 'CA' else "Átomos"
                elif trace.mode == 'lines':
                    trace.name = "Conexiones"

           
            fig_json = fig.to_plotly_json()

            
            # Crear payload
            payload = {
                "plotData": fig_json["data"],
                "layout": fig_json["layout"],
                "properties": props,
                "pdb_data": pdb_data.decode('utf-8') if isinstance(pdb_data, bytes) else str(pdb_data),
                # Añadir métricas en un formato amigable para el frontend
                "summary_statistics": {
                    "degree_centrality": {
                        "min": props.get("degree_min", 0),
                        "max": props.get("degree_max", 0),
                        "mean": props.get("degree_mean", 0),
                        "top_residues": f"{', '.join(map(str, props.get('degree_top', {}).get('residues', [])))} (valor: {props.get('degree_top', {}).get('value', 0):.4f})"
                    },
                    "betweenness_centrality": {
                        "min": props.get("betweenness_min", 0),
                        "max": props.get("betweenness_max", 0),
                        "mean": props.get("betweenness_mean", 0),
                        "top_residues": f"{', '.join(map(str, props.get('betweenness_top', {}).get('residues', [])))} (valor: {props.get('betweenness_top', {}).get('value', 0):.4f})"
                    },
                    "closeness_centrality": {
                        "min": props.get("closeness_min", 0),
                        "max": props.get("closeness_max", 0),
                        "mean": props.get("closeness_mean", 0),
                        "top_residues": f"{', '.join(map(str, props.get('closeness_top', {}).get('residues', [])))} (valor: {props.get('closeness_top', {}).get('value', 0):.4f})"
                    },
                    "clustering_coefficient": {
                        "min": props.get("clustering_min", 0),
                        "max": props.get("clustering_max", 0),
                        "mean": props.get("clustering_mean", 0),
                        "top_residues": f"{', '.join(map(str, props.get('clustering_top', {}).get('residues', [])))} (valor: {props.get('clustering_top', {}).get('value', 0):.4f})"
                    }
                },
                "top_5_residues": {
                    "degree_centrality": props.get("degree_top5", []),
                    "betweenness_centrality": props.get("betweenness_top5", []),
                    "closeness_centrality": props.get("closeness_top5", []),
                    "clustering_coefficient": props.get("clustering_top5", [])
                }
            }
            
            # Convertir arrays NumPy a listas
            payload = convert_numpy_to_lists(payload)
            
            print(f"📤 Enviando payload para análisis en frontend")
            return jsonify(payload)

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        print(f"💥 Error generating graph: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def convert_numpy_to_lists(obj):
    """Convierte recursivamente arrays de NumPy a listas Python para serialización JSON."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_to_lists(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_to_lists(i) for i in obj]
    else:
        return obj

