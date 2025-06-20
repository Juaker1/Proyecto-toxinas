from flask import Blueprint, render_template, jsonify, request, send_file
from functools import partial
import sqlite3
import tempfile
import os
import sys
import io
import csv
import numpy as np
import re
import unicodedata
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
from flask import Response
import openpyxl
import pandas as pd
from app.utils.excel_export import generate_excel

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


# Modificar la ruta raíz para que acepte también solicitudes POST
@viewer_bp.route("/", methods=['GET', 'POST'])
def viewer():
    # Si es una solicitud POST, simplemente devuelve un estado 200 OK
    if request.method == 'POST':
        return jsonify({"status": "ok"}), 200
        
    # Si es GET, mostrar la página normal como antes
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT peptide_id, peptide_name FROM Peptides ORDER BY peptide_name")
    toxinas = cursor.fetchall()
    
    cursor.execute("SELECT id, peptide_code FROM Nav1_7_InhibitorPeptides ORDER BY peptide_code")
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


@viewer_bp.route("/get_toxin_name/<string:source>/<int:pid>")
def get_toxin_name(source, pid):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if source == "toxinas":
            cursor.execute("SELECT peptide_name FROM Peptides WHERE peptide_id = ?", (pid,))
        elif source == "nav1_7":
            cursor.execute("SELECT peptide_code FROM Nav1_7_InhibitorPeptides WHERE id = ?", (pid,))
        else:
            conn.close()
            return jsonify({"error": "Invalid source"}), 400
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({"toxin_name": result[0]})
        else:
            return jsonify({"toxin_name": f"{source}_{pid}"})
            
    except Exception as e:
        print(f"❌ Error en get_toxin_name: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@viewer_bp.route("/export_residues_xlsx/<string:source>/<int:pid>")
def export_residues_xlsx(source, pid):
    try:
        # Obtain parameters - same as in export_residues_csv
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        
        # Get PDB data, toxin name, and IC50
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        toxin_name = None
        ic50_value = None
        ic50_unit = None
        
        if source == "toxinas":
            cursor.execute("SELECT pdb_file, peptide_name FROM Peptides WHERE peptide_id = ?", (pid,))
            result = cursor.fetchone()
            if result:
                pdb_data, toxin_name = result
        elif source == "nav1_7":
            cursor.execute("SELECT pdb_blob, peptide_code, ic50_value, ic50_unit FROM Nav1_7_InhibitorPeptides WHERE id = ?", (pid,))
            result = cursor.fetchone()
            if result:
                pdb_data, toxin_name, ic50_value, ic50_unit = result
        else:
            conn.close()
            return jsonify({"error": "Invalid source"}), 400
        
        conn.close()
        
        if not result:
            return jsonify({"error": "PDB not found"}), 404
        
        # If we don't have a name, use a fallback
        if not toxin_name:
            toxin_name = f"{source}_{pid}"
        
        # Clean the name for use in filename
        normalized_name = unicodedata.normalize('NFKD', toxin_name)
        
        # Convert special Greek characters to ASCII
        clean_name = normalized_name.replace('μ', 'mu').replace('β', 'beta').replace('ω', 'omega').replace('δ', 'delta')
        
        # Remove any non-ASCII alphanumeric, dash, or underscore characters
        clean_name = re.sub(r'[^\w\-_]', '', clean_name, flags=re.ASCII)
        
        if not clean_name:
            clean_name = f"{source}_{pid}"
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
            if isinstance(pdb_data, bytes):
                temp_file.write(pdb_data)
            else:
                temp_file.write(pdb_data.encode('utf-8'))
            temp_path = temp_file.name
        
        try:
            # Build graph - same logic as in export_residues_csv
            if granularity == 'atom':
                cfg = ProteinGraphConfig(
                    granularity="atom",
                    edge_construction_functions=[
                        partial(add_distance_threshold,
                                long_interaction_threshold=long_threshold,
                                threshold=distance_threshold)
                    ]
                )
            else:
                cfg = ProteinGraphConfig(
                    granularity="CA",
                    edge_construction_functions=[
                        partial(add_distance_threshold,
                                long_interaction_threshold=long_threshold,
                                threshold=distance_threshold)
                    ]
                )
            
            print(f"Building graph for {toxin_name}...")
            G = construct_graph(config=cfg, pdb_code=None, path=temp_path)
            print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
            
            # Calculate centrality metrics
            print(f"Calculating centrality metrics...")
            degree_centrality = nx.degree_centrality(G)
            betweenness_centrality = nx.betweenness_centrality(G)
            closeness_centrality = nx.closeness_centrality(G)
            clustering_coefficient = nx.clustering(G)
            
            # Normalize IC50 to consistent units (nM)
            ic50_nm = None
            if ic50_value and ic50_unit:
                if ic50_unit.lower() == "nm":
                    ic50_nm = ic50_value
                elif ic50_unit.lower() == "μm" or ic50_unit.lower() == "um":
                    ic50_nm = ic50_value * 1000
                elif ic50_unit.lower() == "mm":
                    ic50_nm = ic50_value * 1000000
                else:
                    ic50_nm = ic50_value
            
            # Process each node/residue
            csv_data = []
            for node in G.nodes():
                if granularity == 'CA':
                    parts = str(node).split(':')
                    if len(parts) >= 3:
                        chain = parts[0]
                        residue_name = parts[1]
                        residue_number = parts[2]
                    else:
                        chain = G.nodes[node].get('chain_id', 'A')
                        residue_name = G.nodes[node].get('residue_name', 'UNK')
                        residue_number = str(node)
                else:  # atom level
                    chain = G.nodes[node].get('chain_id', 'A')
                    residue_name = G.nodes[node].get('residue_name', 'UNK')
                    residue_number = str(G.nodes[node].get('residue_number', node))
                
                csv_data.append({
                    'Toxina': toxin_name,
                    'Cadena': chain,
                    'Residuo_Nombre': residue_name,
                    'Residuo_Numero': residue_number,
                    'IC50_Original': ic50_value,
                    'IC50_Unidad': ic50_unit,
                    'IC50_nM': round(ic50_nm, 3) if ic50_nm else None,
                    'Centralidad_Grado': round(degree_centrality.get(node, 0), 6),
                    'Centralidad_Intermediacion': round(betweenness_centrality.get(node, 0), 6),
                    'Centralidad_Cercania': round(closeness_centrality.get(node, 0), 6),
                    'Coeficiente_Agrupamiento': round(clustering_coefficient.get(node, 0), 6),
                    'Grado_Nodo': G.degree(node)
                })
            
            # Convert to DataFrame for Excel export
            df = pd.DataFrame(csv_data)
            
            # Generate Excel file
            if source == "nav1_7":
                filename_prefix = f"Nav1.7-{clean_name}"
            else:
                filename_prefix = f"Toxinas-{clean_name}"
                
            # Create a sheet name based on toxin name
            sheet_name = clean_name if clean_name else "Toxina"
                
            excel_data, excel_filename = generate_excel(df, filename_prefix, [sheet_name])
            
            # Return the Excel file
            return send_file(
                excel_data,
                as_attachment=True,
                download_name=excel_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
        finally:
            os.unlink(temp_path)
            print(f"Temporary file removed")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@viewer_bp.route("/export_family_xlsx/<string:family_prefix>")
def export_family_xlsx(family_prefix):
    try:
        # Get parameters
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        
        print(f"Processing family {family_prefix} with parameters: long={long_threshold}, dist={distance_threshold}, granularity={granularity}")
        
        # Get toxins for this family
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, peptide_code, ic50_value, ic50_unit 
            FROM Nav1_7_InhibitorPeptides 
            WHERE peptide_code LIKE ? OR peptide_code LIKE ?
        """, (f"{family_prefix}%", f"{family_prefix.replace('μ', 'mu').replace('β', 'beta').replace('ω', 'omega')}%"))
        
        family_toxins = cursor.fetchall()
        conn.close()
        
        if not family_toxins:
            print(f"No toxins found for family {family_prefix}")
            return jsonify({"error": f"No toxins found for family {family_prefix}"}), 404
        
        print(f"Processing family {family_prefix}: {len(family_toxins)} toxins found")
        
        # Dictionary to store dataframes for each toxin (one sheet per toxin)
        toxin_dataframes = {}
        processed_count = 0
        
        for toxin_id, peptide_code, ic50_value, ic50_unit in family_toxins:
            print(f"Processing {peptide_code} (IC₅₀: {ic50_value} {ic50_unit})")
            
            try:
                # Get PDB data
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT pdb_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (toxin_id,))
                result = cursor.fetchone()
                conn.close()
                
                if not result or not result[0]:
                    print(f"No PDB data for {peptide_code}")
                    continue
                
                pdb_data = result[0]
                print(f"PDB obtained for {peptide_code} ({len(pdb_data)} bytes)")
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
                    if isinstance(pdb_data, bytes):
                        temp_file.write(pdb_data)
                    else:
                        temp_file.write(pdb_data.encode('utf-8'))
                    temp_path = temp_file.name
                
                print(f"Temporary file created: {temp_path}")
                
                try:
                    # Build graph with appropriate configuration
                    if granularity == 'atom':
                        cfg = ProteinGraphConfig(
                            granularity="atom",
                            edge_construction_functions=[
                                partial(add_distance_threshold,
                                        long_interaction_threshold=long_threshold,
                                        threshold=distance_threshold)
                            ]
                        )
                    else:
                        cfg = ProteinGraphConfig(
                            granularity="CA",
                            edge_construction_functions=[
                                partial(add_distance_threshold,
                                        long_interaction_threshold=long_threshold,
                                        threshold=distance_threshold)
                            ]
                        )
                    
                    print(f"Building graph for {peptide_code}...")
                    G = construct_graph(config=cfg, pdb_code=None, path=temp_path)
                    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
                    
                    # Calculate centrality metrics
                    print(f"Calculating centrality metrics...")
                    degree_centrality = nx.degree_centrality(G)
                    betweenness_centrality = nx.betweenness_centrality(G)
                    closeness_centrality = nx.closeness_centrality(G)
                    clustering_coefficient = nx.clustering(G)
                    
                    # Normalize IC50 to consistent units (nM)
                    ic50_nm = None
                    if ic50_value and ic50_unit:
                        if ic50_unit.lower() == "nm":
                            ic50_nm = ic50_value
                        elif ic50_unit.lower() == "μm" or ic50_unit.lower() == "um":
                            ic50_nm = ic50_value * 1000
                        elif ic50_unit.lower() == "mm":
                            ic50_nm = ic50_value * 1000000
                        else:
                            ic50_nm = ic50_value
                    
                    print(f"IC50 normalized: {ic50_nm} nM")
                    
                    # Process each node/residue
                    toxin_data = []
                    for node in G.nodes():
                        if granularity == 'CA':
                            parts = str(node).split(':')
                            if len(parts) >= 3:
                                chain = parts[0]
                                residue_name = parts[1]
                                residue_number = parts[2]
                            else:
                                chain = G.nodes[node].get('chain_id', 'A')
                                residue_name = G.nodes[node].get('residue_name', 'UNK')
                                residue_number = str(node)
                        else:  # atom level
                            chain = G.nodes[node].get('chain_id', 'A')
                            residue_name = G.nodes[node].get('residue_name', 'UNK')
                            residue_number = str(G.nodes[node].get('residue_number', node))
                        
                        toxin_data.append({
                            'Familia': family_prefix,
                            'Toxina': peptide_code,
                            'Cadena': chain,
                            'Residuo_Nombre': residue_name,
                            'Residuo_Numero': residue_number,
                            'IC50_Original': ic50_value,
                            'IC50_Unidad': ic50_unit,
                            'IC50_nM': round(ic50_nm, 3) if ic50_nm else None,
                            'Centralidad_Grado': round(degree_centrality.get(node, 0), 6),
                            'Centralidad_Intermediacion': round(betweenness_centrality.get(node, 0), 6),
                            'Centralidad_Cercania': round(closeness_centrality.get(node, 0), 6),
                            'Coeficiente_Agrupamiento': round(clustering_coefficient.get(node, 0), 6),
                            'Grado_Nodo': G.degree(node),
                            'Densidad_Grafo': round(nx.density(G), 6)

                        })
                    
                    # Create DataFrame and sort by residue number
                    df = pd.DataFrame(toxin_data)
                    df = df.sort_values(by=['Residuo_Numero'], key=lambda x: x.astype(str).str.extract('(\d+)', expand=False).astype(float))
                    
                    # Add to dictionary of dataframes, using peptide_code as sheet name
                    clean_peptide_code = peptide_code.replace('μ', 'mu').replace('β', 'beta').replace('ω', 'omega').replace('δ', 'delta')
                    toxin_dataframes[clean_peptide_code] = df
                    
                    processed_count += 1
                    print(f"Processed {len(toxin_data)} residues from {peptide_code}")
                    
                finally:
                    os.unlink(temp_path)
                    print(f"Temporary file removed")
                
            except Exception as e:
                print(f"Error processing toxin {peptide_code}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        if not toxin_dataframes:
            return jsonify({"error": "No valid toxins to process"}), 500
        
        # Create descriptive filename
        family_names = {
            'μ': 'Mu-TRTX',
            'β': 'Beta-TRTX', 
            'ω': 'Omega-TRTX',
        }
        
        family_name = family_names.get(family_prefix, f"{family_prefix}-TRTX")
        filename_prefix = f"Dataset_Familia_{family_name}_IC50_Topologia_{granularity}"
        
        # Generate Excel file with multiple sheets
        excel_data, excel_filename = generate_excel(toxin_dataframes, filename_prefix)
        
        print(f"Complete dataset generated: {processed_count} toxins")
        
        # Return the Excel file
        return send_file(
            excel_data,
            as_attachment=True,
            download_name=excel_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"Error: {str(e)}")
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

@viewer_bp.route("/calculate_dipole", methods=['POST'])
def calculate_dipole():
    """Calculate dipole moment from uploaded PDB and PSF files"""
    try:
        # Get uploaded files from request
        if 'pdb_file' not in request.files:
            return jsonify({"error": "No PDB file provided"}), 400
        
        pdb_file = request.files['pdb_file']
        psf_file = request.files.get('psf_file')  # PSF is optional
        
        if pdb_file.filename == '':
            return jsonify({"error": "No PDB file selected"}), 400
        
        # Save files temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as pdb_temp:
            pdb_file.save(pdb_temp.name)
            pdb_path = pdb_temp.name
        
        psf_path = None
        if psf_file and psf_file.filename != '':
            with tempfile.NamedTemporaryFile(suffix='.psf', delete=False) as psf_temp:
                psf_file.save(psf_temp.name)
                psf_path = psf_temp.name
        
        try:
            # Calculate dipole using your existing analyzer
            dipole_data = toxin_analyzer.calculate_dipole_moment_with_psf(pdb_path, psf_path)
            
            return jsonify({
                'success': True,
                'dipole': dipole_data
            })
            
        finally:
            # Clean up temporary files
            import os
            os.unlink(pdb_path)
            if psf_path:
                os.unlink(psf_path)
                
    except Exception as e:
        print(f"Error calculating dipole: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@viewer_bp.route("/export_wt_comparison_xlsx/<string:wt_family>")
def export_wt_comparison_xlsx(wt_family):
    try:
        # Get parameters
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        
        print(f"Processing WT comparison for {wt_family} with parameters: long={long_threshold}, dist={distance_threshold}, granularity={granularity}")
        
        # Mapping of family identifiers to peptide codes
        wt_mapping = {
            'μ-TRTX-Hh2a': 'μ-TRTX-Hh2a',
            'μ-TRTX-Hhn2b': 'μ-TRTX-Hhn2b',
            'β-TRTX-Cd1a': 'β-TRTX-Cd1a',
            'ω-TRTX-Gr2a': 'ω-TRTX-Gr2a'
        }
        
        if wt_family not in wt_mapping:
            return jsonify({"error": f"Unrecognized WT family: {wt_family}"}), 400
        
        wt_peptide_code = wt_mapping[wt_family]
        
        # Get data for the WT toxin from database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, peptide_code, ic50_value, ic50_unit, pdb_blob 
            FROM Nav1_7_InhibitorPeptides 
            WHERE peptide_code = ?
        """, (wt_peptide_code,))
        
        wt_result = cursor.fetchone()
        conn.close()
        
        if not wt_result:
            return jsonify({"error": f"WT toxin not found: {wt_peptide_code}"}), 404
            
        wt_id, wt_code, wt_ic50, wt_unit, wt_pdb_data = wt_result
        print(f"WT toxin found: {wt_code} (IC₅₀: {wt_ic50} {wt_unit})")
        
        # Load reference toxin from file
        reference_path = os.path.join("pdbs", "WT", "hwt4_Hh2a_WT.pdb")
        if not os.path.exists(reference_path):
            return jsonify({"error": f"Reference file not found: {reference_path}"}), 404
        
        print(f"Reference file found: {reference_path}")
        
        # Dictionary to store dataframes
        comparison_dataframes = {}
        
        # === PROCESS WT TOXIN ===
        print(f"Processing WT toxin: {wt_code}")
        wt_data = process_single_toxin_for_comparison(
            pdb_data=wt_pdb_data,
            toxin_name=wt_code,
            ic50_value=wt_ic50,
            ic50_unit=wt_unit,
            granularity=granularity,
            long_threshold=long_threshold,
            distance_threshold=distance_threshold,
            toxin_type="WT_Target"
        )
        
        if wt_data:
            comparison_dataframes['WT_Target'] = pd.DataFrame(wt_data)
        
        # === PROCESS REFERENCE TOXIN ===
        print(f"Processing reference toxin: hwt4_Hh2a_WT")
        with open(reference_path, 'r') as ref_file:
            ref_pdb_content = ref_file.read()
        
        ref_data = process_single_toxin_for_comparison(
            pdb_data=ref_pdb_content,
            toxin_name="hwt4_Hh2a_WT",
            ic50_value=None,  # Reference without IC50 data
            ic50_unit=None,
            granularity=granularity,
            long_threshold=long_threshold,
            distance_threshold=distance_threshold,
            toxin_type="Reference"
        )
        
        if ref_data:
            comparison_dataframes['Reference'] = pd.DataFrame(ref_data)
            
        if not comparison_dataframes:
            return jsonify({"error": "Could not process toxins for comparison"}), 500
        
        # Create summary sheet with comparison metrics if both toxins were processed
        if 'WT_Target' in comparison_dataframes and 'Reference' in comparison_dataframes:
            # Add summary sheet with key differences and similarities
            wt_df = comparison_dataframes['WT_Target']
            ref_df = comparison_dataframes['Reference']
            
            # Calculate overall graph properties for comparison
            summary_data = {
                'Property': [
                    'Toxina WT', 'Toxina Referencia',
                    'Número de Residuos', 'Aristas Totales',
                    'Densidad Promedio', 'Centralidad Grado Promedio',
                    'Centralidad Intermediación Promedio', 'Centralidad Cercanía Promedio',
                    'Coeficiente Agrupamiento Promedio'
                ],
                'WT_Target': [
                    wt_code, 'N/A',
                    wt_df['Num_Nodos_Grafo'].iloc[0], wt_df['Num_Aristas_Grafo'].iloc[0],
                    wt_df['Densidad_Grafo'].iloc[0], wt_df['Centralidad_Grado'].mean(),
                    wt_df['Centralidad_Intermediacion'].mean(), wt_df['Centralidad_Cercania'].mean(),
                    wt_df['Coeficiente_Agrupamiento'].mean()
                ],
                'Reference': [
                    'N/A', 'hwt4_Hh2a_WT',
                    ref_df['Num_Nodos_Grafo'].iloc[0], ref_df['Num_Aristas_Grafo'].iloc[0],
                    ref_df['Densidad_Grafo'].iloc[0], ref_df['Centralidad_Grado'].mean(),
                    ref_df['Centralidad_Intermediacion'].mean(), ref_df['Centralidad_Cercania'].mean(),
                    ref_df['Coeficiente_Agrupamiento'].mean()
                ]
            }
            
            comparison_dataframes['Resumen_Comparativo'] = pd.DataFrame(summary_data)
        else:
            print(f"Warning: Not all toxins were processed for comparison: {comparison_dataframes.keys()}")
        
        # Create descriptive filename
        family_clean = wt_family.replace('μ', 'mu').replace('β', 'beta').replace('ω', 'omega').replace('δ', 'delta')
        filename_prefix = f"Comparacion_WT_{family_clean}_vs_hwt4_Hh2a_WT_{granularity}"
        
        # Generate Excel file with multiple sheets
        excel_data, excel_filename = generate_excel(comparison_dataframes, filename_prefix)
        
        print(f"Comparison dataset generated")
        
        # Return the Excel file
        return send_file(
            excel_data,
            as_attachment=True,
            download_name=excel_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def process_single_toxin_for_comparison(pdb_data, toxin_name, ic50_value, ic50_unit, granularity, long_threshold, distance_threshold, toxin_type):
    """
    Procesa una sola toxina para análisis comparativo
    """
    try:
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
            if isinstance(pdb_data, bytes):
                temp_file.write(pdb_data)
            else:
                temp_file.write(pdb_data.encode('utf-8'))
            temp_path = temp_file.name
        
        try:
            # Construir grafo
            if granularity == 'atom':
                cfg = ProteinGraphConfig(
                    granularity="atom",
                    edge_construction_functions=[
                        partial(add_distance_threshold,
                                long_interaction_threshold=long_threshold,
                                threshold=distance_threshold)
                    ]
                )
            else:
                cfg = ProteinGraphConfig(
                    granularity="CA",
                    edge_construction_functions=[
                        partial(add_distance_threshold,
                                long_interaction_threshold=long_threshold,
                                threshold=distance_threshold)
                    ]
                )
            
            print(f"    🔗 Construyendo grafo para {toxin_name}...")
            G = construct_graph(config=cfg, pdb_code=None, path=temp_path)
            print(f"    ✅ Grafo construido: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
            
            # Calcular métricas de centralidad
            print(f"    📊 Calculando métricas de centralidad...")
            degree_centrality = nx.degree_centrality(G)
            betweenness_centrality = nx.betweenness_centrality(G)
            closeness_centrality = nx.closeness_centrality(G)
            clustering_coefficient = nx.clustering(G)
            
            # Normalizar IC50 a unidades consistentes (nM)
            ic50_nm = None
            if ic50_value and ic50_unit:
                if ic50_unit.lower() == "nm":
                    ic50_nm = ic50_value
                elif ic50_unit.lower() == "μm" or ic50_unit.lower() == "um":
                    ic50_nm = ic50_value * 1000
                elif ic50_unit.lower() == "mm":
                    ic50_nm = ic50_value * 1000000
                else:
                    ic50_nm = ic50_value
            
            print(f"     IC50 normalizado: {ic50_nm} nM")
            
            # Extraer familia WT
            family_wt = None
            if toxin_type == "WT_Target":
                if "μ-TRTX-Hh2a" in toxin_name:
                    family_wt = "Mu-TRTX-2a"
                elif "μ-TRTX-Hhn2b" in toxin_name:
                    family_wt = "Mu-TRTX-2b"
                elif "β-TRTX" in toxin_name:
                    family_wt = "Beta-TRTX"
                elif "ω-TRTX" in toxin_name:
                    family_wt = "Omega-TRTX"
                else:
                    family_wt = "Unknown"
            else:
                family_wt = "Reference"
            
            # Procesar cada nodo/residuo
            toxin_data = []
            node_count = 0
            for node, data in G.nodes(data=True):
                if granularity == 'CA':
                    parts = str(node).split(':')
                    if len(parts) >= 3:
                        chain = parts[0]
                        residue_name = parts[1]
                        residue_number = parts[2]
                    else:
                        chain = data.get('chain_id', 'A')
                        residue_name = data.get('residue_name', 'UNK')
                        residue_number = str(node)
                else:  # atom level
                    chain = data.get('chain_id', 'A')
                    residue_name = data.get('residue_name', 'UNK')
                    residue_number = str(data.get('residue_number', node))
                
                toxin_data.append({
                    # Identificadores
                    'Tipo_Toxina': toxin_type,
                    'Familia_WT': family_wt,
                    'Toxina': toxin_name,
                    'Cadena': chain,
                    'Residuo_Nombre': residue_name,
                    'Residuo_Numero': residue_number,
                    
                    # Actividad farmacológica
                    'IC50_Original': ic50_value,
                    'IC50_Unidad': ic50_unit,
                    'IC50_nM': round(ic50_nm, 3) if ic50_nm else None,
                    
                    # Métricas de centralidad
                    'Centralidad_Grado': round(degree_centrality.get(node, 0), 6),
                    'Centralidad_Intermediacion': round(betweenness_centrality.get(node, 0), 6),
                    'Centralidad_Cercania': round(closeness_centrality.get(node, 0), 6),
                    'Coeficiente_Agrupamiento': round(clustering_coefficient.get(node, 0), 6),
                    
                    # Propiedades estructurales
                    'Grado_Nodo': G.degree(node),
                    'Densidad_Grafo': round(nx.density(G), 6)

                })
                node_count += 1
            
            print(f"     Procesados {node_count} residuos de {toxin_name}")
            return toxin_data
            
        finally:
            os.unlink(temp_path)
            print(f"     Archivo temporal eliminado")
            
    except Exception as e:
        print(f"     Error procesando {toxin_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

