from flask import Blueprint, render_template, request, jsonify
import sqlite3
import os
import io
import tempfile
from functools import partial
import networkx as nx
import numpy as np
import plotly.graph_objects as go

from graphein.protein.config import ProteinGraphConfig
from graphein.protein.graphs import construct_graph
from graphein.protein.edges.distance import add_distance_threshold

viewer_bp = Blueprint('viewer', __name__)

DB_PATH = "database/toxins.db"
PDB_DIR = "pdbs"

def fetch_peptides(group):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if group == "toxinas":
        cursor.execute("SELECT peptide_id, peptide_name FROM Peptides")
        #print("Fetching peptides from Peptides table")
    elif group == "nav1_7":
        cursor.execute("SELECT id, peptide_code FROM Nav1_7_InhibitorPeptides")
    else:
        return []

    return cursor.fetchall()


@viewer_bp.route("/viewer")
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
    #print(f"[DEBUG] Solicitud PDB recibida: source={source}, pid={pid}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if source == "toxinas":
        cursor.execute("SELECT pdb_file FROM Peptides WHERE peptide_id = ?", (pid,))
    elif source == "nav1_7":
        cursor.execute("SELECT pdb_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (pid,))
    else:
        #print(f"[ERROR] Fuente inválida: {source}")
        return jsonify({"error": "Invalid source"}), 400

    result = cursor.fetchone()
    if not result:
        #print(f"[ERROR] PDB no encontrado: {source}/{pid}")
        return jsonify({"error": "PDB not found"}), 404

    pdb_data = result[0]
    #print(f"[DEBUG] Tipo de datos PDB: {type(pdb_data)}")

    try:
        # Decode si es binario
        if isinstance(pdb_data, bytes):
            pdb_text = pdb_data.decode('utf-8')
        else:
            pdb_text = str(pdb_data)
            
        # Inspeccionar los primeros 100 caracteres
        #print(f"[DEBUG] Primeros 100 caracteres: {pdb_text[:100]}")
    except Exception as e:
        #print(f"[ERROR] Fallo en decodificación: {e}")
        return jsonify({"error": "PDB decoding error"}), 500

    # Validación mejorada
    if len(pdb_text.strip()) < 100:
        #print("[ERROR] PDB demasiado corto")
        return jsonify({"error": "PDB content too short"}), 500

    if not any(line.startswith("ATOM") or line.startswith("HETATM") for line in pdb_text.splitlines()):
        #print("[ERROR] No se encontraron líneas ATOM o HETATM")
        return jsonify({"error": "No atomic data found"}), 500

    # OK
    #print(f"[DEBUG] PDB enviado correctamente ({len(pdb_text)} caracteres)")
    # Establecer el Content-Type correcto para archivos PDB
    return pdb_text, 200, {'Content-Type': 'chemical/x-pdb'}

# Function to calculate graph properties (copied from test.py)
def compute_graph_properties(G):
    props = {}
    props["num_nodes"] = G.number_of_nodes()
    props["num_edges"] = G.number_of_edges()
    props["density"] = nx.density(G)
    degrees = list(dict(G.degree()).values())
    props["avg_degree"] = sum(degrees) / len(degrees) if degrees else 0.0
    props["avg_clustering"] = nx.average_clustering(G)
    comps = list(nx.connected_components(G)) if not G.is_directed() else list(nx.weakly_connected_components(G))
    props["num_components"] = len(comps)
    props["largest_component_size"] = max((len(c) for c in comps), default=0)
    if props["largest_component_size"] > 1:
        giant = G.subgraph(max(comps, key=len))
        try:
            props["avg_shortest_path"] = nx.average_shortest_path_length(giant)
            props["diameter"] = nx.diameter(giant)
        except nx.NetworkXError:
            props["avg_shortest_path"] = None
            props["diameter"] = None
    deg_cent = nx.degree_centrality(G)
    vals = list(deg_cent.values())
    props["mean_degree_centrality"] = sum(vals) / len(vals) if vals else 0.0
    props["max_degree_centrality"] = max(vals) if vals else 0.0
    return props

# Function to generate Plotly-friendly graph data
def create_plotly_graph_data(G):
    # Extract node positions from graph
    positions = {}
    for node, data in G.nodes(data=True):
        if 'coords' in data:
            positions[node] = data['coords']
    
    # Extract node properties
    seq_positions = {node: data.get('residue_number', 0) for node, data in G.nodes(data=True)}
    
    # Create node traces
    node_x = []
    node_y = []
    node_z = []
    node_colors = []
    node_text = []
    
    for node in G.nodes():
        if node in positions:
            pos = positions[node]
            node_x.append(pos[0])
            node_y.append(pos[1])
            node_z.append(pos[2])
            node_colors.append(seq_positions[node])
            
            # Create hover text
            data = G.nodes[node]
            name = data.get('residue_name', 'UNK')
            num = data.get('residue_number', '?')
            chain = data.get('chain_id', '?')
            node_text.append(f"{name}{num} (Chain {chain})")
    
    # Create edge traces
    edge_x = []
    edge_y = []
    edge_z = []
    
    for u, v in G.edges():
        if u in positions and v in positions:
            pos_u = positions[u]
            pos_v = positions[v]
            
            # Add coordinates for the line
            edge_x.extend([pos_u[0], pos_v[0], None])
            edge_y.extend([pos_u[1], pos_v[1], None])
            edge_z.extend([pos_u[2], pos_v[2], None])
    
    # Create node trace
    node_trace = go.Scatter3d(
        x=node_x, y=node_y, z=node_z,
        mode='markers',
        marker=dict(
            size=6,
            color=node_colors,
            colorscale='Viridis',
            colorbar=dict(title='Seq Position'),
            opacity=0.8
        ),
        text=node_text,
        hoverinfo='text',
        name='Residues'
    )
    
    # Create edge trace
    edge_trace = go.Scatter3d(
        x=edge_x, y=edge_y, z=edge_z,
        mode='lines',
        line=dict(color='#999999', width=1),
        hoverinfo='none',
        name='Connections'
    )
    
    return [edge_trace, node_trace]

@viewer_bp.route("/get_protein_graph/<string:source>/<int:pid>")
def get_protein_graph(source, pid):
    try:
        # Get threshold parameters
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        
        # Get PDB data from the database
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
        
        # Write PDB data to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
            if isinstance(pdb_data, bytes):
                temp_file.write(pdb_data)
            else:
                temp_file.write(pdb_data.encode('utf-8'))
            temp_path = temp_file.name
        
        try:
            # Configure and create graph
            cfg = ProteinGraphConfig(
                edge_construction_functions=[
                    partial(add_distance_threshold,
                            long_interaction_threshold=long_threshold,
                            threshold=distance_threshold)
                ]
            )
            
            # Construct graph from temp file
            G = construct_graph(config=cfg, pdb_code=None, path=temp_path)
            
            # Calculate graph properties
            props = compute_graph_properties(G)
            
            # Create plot data for Plotly
            plot_data = create_plotly_graph_data(G)
            
            # Return data
            return jsonify({
                "plotData": [trace.to_plotly_json() for trace in plot_data],
                "properties": props
            })
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        print(f"Error generating graph: {str(e)}")
        return jsonify({"error": str(e)}), 500

