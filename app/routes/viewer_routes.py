from flask import Blueprint, render_template, jsonify, request, send_file, make_response
from functools import partial
import sqlite3
import tempfile
import os
import sys
import io
import csv
import numpy as np
import pandas as pd
import re
import unicodedata
import traceback
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
from datetime import datetime
import pandas as pd
from app.utils.excel_export import generate_excel
from app.utils.graph_segmentation import agrupar_por_segmentos_atomicos

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


# Agregar esta función después de las importaciones y antes de las rutas
def preprocess_pdb_for_graphein(pdb_content):
    """
    Preprocesa el contenido PDB para convertir residuos no estándar a códigos reconocidos por Graphein
    """
    # Diccionario de conversiones de residuos no estándar
    residue_conversions = {
        'HSD': 'HIS',  # Histidina delta-protonada
        'HSE': 'HIS',  # Histidina epsilon-protonada  
        'HSP': 'HIS',  # Histidina positivamente cargada
        'CYX': 'CYS',  # Cisteína en puente disulfuro
        'HIE': 'HIS',  # Otra variante de histidina
        'HID': 'HIS',  # Otra variante de histidina
        'HIP': 'HIS',  # Otra variante de histidina
        'CYM': 'CYS',  # Cisteína desprotonada
        'ASH': 'ASP',  # Ácido aspártico protonado
        'GLH': 'GLU',  # Ácido glutámico protonado
        'LYN': 'LYS',  # Lisina desprotonada
        'ARN': 'ARG',  # Arginina desprotonada
        'TYM': 'TYR',  # Tirosina desprotonada
        'MSE': 'MET',  # Selenometionina
        'PCA': 'GLU',  # Piroglutamato
        'TPO': 'THR',  # Treonina fosforilada
        'SEP': 'SER',  # Serina fosforilada
        'PTR': 'TYR',  # Tirosina fosforilada
    }
    
    lines = pdb_content.split('\n')
    processed_lines = []
    
    for line in lines:
        if line.startswith(('ATOM', 'HETATM')):
            # El nombre del residuo está en las columnas 18-20 (0-indexed: 17-20)
            if len(line) >= 20:
                residue_name = line[17:20].strip()
                if residue_name in residue_conversions:
                    # Reemplazar el nombre del residuo
                    new_residue = residue_conversions[residue_name]
                    # Asegurar que tenga 3 caracteres con espacios a la derecha si es necesario
                    new_residue_padded = f"{new_residue:<3}"
                    line = line[:17] + new_residue_padded + line[20:]
        
        processed_lines.append(line)
    
    return '\n'.join(processed_lines)

# Modificar la función get_protein_graph existente
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

        # Procesar el contenido PDB antes de crear el archivo temporal
        if isinstance(pdb_data, bytes):
            pdb_content = pdb_data.decode('utf-8')
        else:
            pdb_content = str(pdb_data)
        
        # ✨ NUEVA LÍNEA: Preprocesar el PDB para convertir residuos no estándar
        processed_pdb_content = preprocess_pdb_for_graphein(pdb_content)

        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
            # Escribir el contenido procesado en lugar del original
            temp_file.write(processed_pdb_content.encode('utf-8'))
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
            
            print(f"📊 Construyendo grafo con granularidad: {granularity}")
            G = construct_graph(config=cfg, pdb_code=None, path=temp_path)
            print(f"✅ Grafo construido exitosamente: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
            
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
                # Devolver el PDB original, no el procesado
                "pdb_data": pdb_content,
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
            
            # Preparar los datos
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
                
                # Excluir columnas redundantes y normalización IC50
                csv_data.append({
                    'Toxina': toxin_name,
                    'Cadena': chain,
                    'Residuo_Nombre': residue_name,
                    'Residuo_Numero': residue_number,
                    'Centralidad_Grado': round(degree_centrality.get(node, 0), 6),
                    'Centralidad_Intermediacion': round(betweenness_centrality.get(node, 0), 6),
                    'Centralidad_Cercania': round(closeness_centrality.get(node, 0), 6),
                    'Coeficiente_Agrupamiento': round(clustering_coefficient.get(node, 0), 6),
                    'Grado_Nodo': G.degree(node)
                })
            
            # Crear DataFrame
            df = pd.DataFrame(csv_data)
            
            # Crear metadatos para hoja separada
            metadata = {
                'Toxina': toxin_name,
                'Fuente': source,
                'ID': pid,
                'Densidad del grafo': round(nx.density(G), 6),
                'Número de nodos': G.number_of_nodes(),
                'Número de aristas': G.number_of_edges()
            }
            
            # Agregar IC50 si está disponible
            if ic50_value:
                metadata['IC50 Original'] = ic50_value
                metadata['Unidad IC50'] = ic50_unit
            
            # Generar nombre de archivo
            if source == "nav1_7":
                filename_prefix = f"Nav1.7-{clean_name}"
            else:
                filename_prefix = f"Toxinas-{clean_name}"
                
            # Crear nombre de hoja
            sheet_name = clean_name if clean_name else "Toxina"
                
            # Generar Excel con metadatos
            excel_data, excel_filename = generate_excel(df, filename_prefix, [sheet_name], metadata)
            
            # Retornar el archivo
            return send_file(
                excel_data,
                as_attachment=True,
                download_name=excel_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        finally:
            # Limpiar archivo temporal
            os.unlink(temp_path)
            print("Temporary file removed")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@viewer_bp.route("/export_segments_atomicos_xlsx/<string:source>/<int:pid>")
def export_segments_atomicos_xlsx(source, pid):
    """
    Exporta segmentos atómicos conectados para toxinas Nav1.7
    Cada segmento representa una región conectada del grafo atómico
    """
    try:
        # Solo permitir para Nav1.7
        if source != "nav1_7":
            print(f"❌ Error: Segmentación atómica solo para Nav1.7, recibido: {source}")
            return jsonify({"error": "La segmentación atómica solo está disponible para toxinas Nav1.7"}), 400
        
        # Obtener parámetros
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'atom')  # Forzar a atom para segmentación
        
        # Validar que la granularidad sea atómica
        if granularity != 'atom':
            print(f"❌ Error: Granularidad incorrecta: {granularity}")
            return jsonify({"error": "La segmentación atómica requiere granularidad 'atom'"}), 400
        
        print(f"🚀 Iniciando exportación de segmentos atómicos para Nav1.7 ID: {pid}")
        print(f"📋 Parámetros: long={long_threshold}, threshold={distance_threshold}, granularity={granularity}")
        
        # Obtener datos de la toxina
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT pdb_blob, peptide_code, ic50_value, ic50_unit FROM Nav1_7_InhibitorPeptides WHERE id = ?", (pid,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print(f"❌ Error: Toxina Nav1.7 ID {pid} no encontrada")
            return jsonify({"error": "Toxina Nav1.7 no encontrada"}), 404
        
        pdb_data, toxin_name, ic50_value, ic50_unit = result
        
        if not toxin_name:
            toxin_name = f"Nav1.7_{pid}"
        
        print(f"📊 Procesando {toxin_name}")
        
        # Limpiar nombre para archivo
        normalized_name = unicodedata.normalize('NFKD', toxin_name)
        clean_name = normalized_name.replace('μ', 'mu').replace('β', 'beta').replace('ω', 'omega').replace('δ', 'delta')
        clean_name = re.sub(r'[^\w\-_]', '', clean_name, flags=re.ASCII)
        
        if not clean_name:
            clean_name = f"Nav1.7_{pid}"
        
        print(f"📁 Nombre de archivo limpio: {clean_name}")
        
        # Preprocesar PDB para graphein
        if isinstance(pdb_data, bytes):
            pdb_content = pdb_data.decode('utf-8')
        else:
            pdb_content = str(pdb_data)
        
        # Aplicar preprocesamiento
        processed_pdb_content = preprocess_pdb_for_graphein(pdb_content)
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
            temp_file.write(processed_pdb_content.encode('utf-8'))
            temp_path = temp_file.name
        
        print(f"📄 Archivo temporal creado: {temp_path}")
        
        try:
            # Construir grafo atómico
            cfg = ProteinGraphConfig(
                granularity="atom",
                edge_construction_functions=[
                    partial(add_distance_threshold,
                            long_interaction_threshold=long_threshold,
                            threshold=distance_threshold)
                ]
            )
            
            print(f"🔬 Construyendo grafo atómico...")
            G = construct_graph(config=cfg, pdb_code=None, path=temp_path)
            print(f"✅ Grafo construido: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
            
            if G.number_of_nodes() == 0:
                print(f"❌ Error: El grafo no tiene nodos")
                return jsonify({"error": "El grafo construido está vacío"}), 500
            
            # Aplicar segmentación atómica
            print(f"🧩 Aplicando segmentación atómica...")
            df_segmentos = agrupar_por_segmentos_atomicos(G, granularity)
            
            if df_segmentos.empty:
                print(f"❌ Error: No se generaron segmentos")
                return jsonify({"error": "No se pudieron generar segmentos atómicos"}), 500
            
            # Agregar información de la toxina
            df_segmentos.insert(0, 'Toxina', toxin_name)
            
            print(f"📈 Segmentación completada: {len(df_segmentos)} segmentos generados")
            print(f"📊 Columnas del DataFrame: {list(df_segmentos.columns)}")
            print(f"📊 Primeras 3 filas:\n{df_segmentos.head(3)}")
            
            # Crear metadatos
            metadata = {
                'Toxina': toxin_name,
                'Fuente': 'Nav1.7',
                'ID': pid,
                'Tipo_Analisis': 'Segmentación Atómica',
                'Granularidad': 'atom',
                'Umbral_Distancia': distance_threshold,
                'Umbral_Interaccion_Larga': long_threshold,
                'Total_Atomos_Grafo': G.number_of_nodes(),
                'Total_Conexiones_Grafo': G.number_of_edges(),
                'Densidad_Grafo': round(nx.density(G), 6),
                'Numero_Segmentos': len(df_segmentos),
                'Fecha_Exportacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Agregar datos de IC50 si están disponibles
            if ic50_value:
                metadata['IC50_Original'] = ic50_value
                metadata['Unidad_IC50'] = ic50_unit
            
            # Generar nombre de archivo
            filename_prefix = f"Nav1.7-{clean_name}-Segmentos-Atomicos"
            
            print(f"💾 Generando Excel: {filename_prefix}")
            
            # Generar Excel con el DataFrame de segmentos
            excel_data, excel_filename = generate_excel(df_segmentos, filename_prefix, metadata=metadata)
            
            print(f"📁 Archivo Excel generado: {excel_filename}")
            
            # Retornar el archivo
            return send_file(
                excel_data,
                as_attachment=True,
                download_name=excel_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        finally:
            # Limpiar archivo temporal
            try:
                os.unlink(temp_path)
                print("🗑️  Archivo temporal eliminado")
            except Exception as cleanup_error:
                print(f"⚠️  Error limpiando archivo temporal: {cleanup_error}")
            
    except Exception as e:
        print(f"❌ Error en export_segments_atomicos_xlsx: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@viewer_bp.route("/export_family_xlsx/<string:family_prefix>")
def export_family_xlsx(family_prefix):
    try:
        # Obtener parámetros
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        export_type = request.args.get('export_type', 'residues')  # 'residues' o 'segments_atomicos'
        
        print(f"Procesando familia {family_prefix} con parámetros: long={long_threshold}, dist={distance_threshold}, granularity={granularity}, tipo={export_type}")
        
        # Validación para segmentación atómica
        if export_type == 'segments_atomicos' and granularity != 'atom':
            return jsonify({"error": "La segmentación atómica requiere granularidad 'atom'"}), 400
        
        # Obtener toxinas de esta familia
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
            print(f"No se encontraron toxinas para la familia {family_prefix}")
            return jsonify({"error": f"No se encontraron toxinas para la familia {family_prefix}"}), 404
        
        print(f"Procesando familia {family_prefix}: {len(family_toxins)} toxinas encontradas")
        
        # Diccionario para almacenar DataFrames de cada toxina
        toxin_dataframes = {}
        processed_count = 0
        
        # Crear metadatos para la familia completa
        metadata = {
            'Familia': family_prefix,
            'Tipo_Analisis': 'Segmentación Atómica' if export_type == 'segments_atomicos' else 'Análisis por Residuos',
            'Numero_Toxinas_Procesadas': len(family_toxins),
            'Umbral_Distancia': distance_threshold,
            'Umbral_Interaccion_Larga': long_threshold,
            'Granularidad': granularity,
            'Fecha_Exportacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Información de IC50 para metadatos
        toxin_ic50_data = {}
        
        for toxin_id, peptide_code, ic50_value, ic50_unit in family_toxins:
            print(f"Procesando {peptide_code} (IC₅₀: {ic50_value} {ic50_unit})")
            
            try:
                # Obtener datos PDB
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT pdb_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (toxin_id,))
                result = cursor.fetchone()
                conn.close()
                
                if not result or not result[0]:
                    print(f"No hay datos PDB para {peptide_code}")
                    continue
                
                pdb_data = result[0]
                print(f"PDB obtenido para {peptide_code} ({len(pdb_data)} bytes)")
                
                # Preprocesar PDB para graphein
                if isinstance(pdb_data, bytes):
                    pdb_content = pdb_data.decode('utf-8')
                else:
                    pdb_content = pdb_data
                
                processed_pdb_content = preprocess_pdb_for_graphein(pdb_content)
                
                # Crear archivo temporal
                with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
                    temp_file.write(processed_pdb_content.encode('utf-8'))
                    temp_path = temp_file.name
                
                print(f"Archivo temporal creado: {temp_path}")
                
                try:
                    # Construir grafo con configuración apropiada
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
                    
                    print(f"Construyendo grafo para {peptide_code}...")
                    G = construct_graph(config=cfg, pdb_code=None, path=temp_path)
                    print(f"Grafo construido: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
                    
                    # Agregar información de IC50 a metadatos
                    if ic50_value and ic50_unit:
                        toxin_ic50_data[f'IC50_{peptide_code}'] = f"{ic50_value} {ic50_unit}"
                    
                    # Procesar según el tipo de exportación
                    if export_type == 'segments_atomicos':
                        # Usar segmentación atómica
                        print(f"Aplicando segmentación atómica para {peptide_code}...")
                        df_segmentos = agrupar_por_segmentos_atomicos(G, granularity=granularity)
                        
                        if not df_segmentos.empty:
                            # Agregar información de la toxina
                            df_segmentos['Toxina'] = peptide_code
                            df_segmentos['IC50_Value'] = ic50_value
                            df_segmentos['IC50_Unit'] = ic50_unit
                            
                            # Reordenar columnas para que la toxina aparezca primero
                            cols = ['Toxina', 'IC50_Value', 'IC50_Unit'] + [col for col in df_segmentos.columns if col not in ['Toxina', 'IC50_Value', 'IC50_Unit']]
                            df_segmentos = df_segmentos[cols]
                            
                            clean_peptide_code = peptide_code.replace('μ', 'mu').replace('β', 'beta').replace('ω', 'omega').replace('δ', 'delta')
                            toxin_dataframes[clean_peptide_code] = df_segmentos
                            
                            print(f"Segmentación completada: {len(df_segmentos)} segmentos procesados para {peptide_code}")
                        else:
                            print(f"⚠️ No se generaron segmentos para {peptide_code}")
                    
                    else:
                        # Análisis por residuos tradicional
                        print(f"Calculando métricas de centralidad para {peptide_code}...")
                        degree_centrality = nx.degree_centrality(G)
                        betweenness_centrality = nx.betweenness_centrality(G)
                        closeness_centrality = nx.closeness_centrality(G)
                        clustering_coefficient = nx.clustering(G)
                        
                        # Procesar cada nodo/residuo eliminando redundancias
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
                            else:  # nivel atómico
                                chain = G.nodes[node].get('chain_id', 'A')
                                residue_name = G.nodes[node].get('residue_name', 'UNK')
                                residue_number = str(G.nodes[node].get('residue_number', node))
                            
                            # Solo incluir datos esenciales
                            toxin_data.append({
                                'Toxina': peptide_code,
                                'IC50_Value': ic50_value,
                                'IC50_Unit': ic50_unit,
                                'Cadena': chain,
                                'Residuo_Nombre': residue_name,
                                'Residuo_Numero': residue_number,
                                'Centralidad_Grado': round(degree_centrality.get(node, 0), 6),
                                'Centralidad_Intermediacion': round(betweenness_centrality.get(node, 0), 6),
                                'Centralidad_Cercania': round(closeness_centrality.get(node, 0), 6),
                                'Coeficiente_Agrupamiento': round(clustering_coefficient.get(node, 0), 6),
                                'Grado_Nodo': G.degree(node)
                            })
                        
                        # Crear DataFrame y ordenar por número de residuo
                        df = pd.DataFrame(toxin_data)
                        df = df.sort_values(by=['Residuo_Numero'], key=lambda x: x.astype(str).str.extract('(\d+)', expand=False).astype(float))
                        
                        # Agregar al diccionario usando codigo limpio como nombre de hoja
                        clean_peptide_code = peptide_code.replace('μ', 'mu').replace('β', 'beta').replace('ω', 'omega').replace('δ', 'delta')
                        toxin_dataframes[clean_peptide_code] = df
                        
                        print(f"Procesados {len(toxin_data)} residuos de {peptide_code}")
                    
                    # Agregar información del grafo a metadatos
                    metadata[f'Nodos_en_{peptide_code}'] = G.number_of_nodes()
                    metadata[f'Aristas_en_{peptide_code}'] = G.number_of_edges()
                    metadata[f'Densidad_en_{peptide_code}'] = round(nx.density(G), 6)
                    
                    processed_count += 1
                    
                finally:
                    os.unlink(temp_path)
                    print(f"Archivo temporal eliminado")
                
            except Exception as e:
                print(f"Error procesando toxina {peptide_code}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Agregar información de IC50 a metadatos
        metadata.update(toxin_ic50_data)
        
        if not toxin_dataframes:
            return jsonify({"error": "No se pudieron procesar toxinas válidas"}), 500
        
        # Crear nombre descriptivo del archivo
        family_names = {
            'μ': 'Mu-TRTX',
            'β': 'Beta-TRTX', 
            'ω': 'Omega-TRTX',
        }
        
        family_name = family_names.get(family_prefix, f"{family_prefix}-TRTX")
        
        # Ajustar nombre según tipo de análisis
        if export_type == 'segments_atomicos':
            filename_prefix = f"Dataset_Familia_{family_name}_Segmentacion_Atomica_{granularity}"
        else:
            filename_prefix = f"Dataset_Familia_{family_name}_IC50_Topologia_{granularity}"
        
        # Generar archivo Excel con múltiples hojas
        excel_data, excel_filename = generate_excel(toxin_dataframes, filename_prefix, metadata=metadata)
        
        print(f"Dataset completo generado: {processed_count} toxinas procesadas")
        
        # Devolver el archivo Excel
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
        psf_file = request.files.get('psf_blob')  # PSF is optional
        
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
        # Obtener parámetros
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        export_type = request.args.get('export_type', 'residues')  # 'residues' o 'segments_atomicos'
        
        print(f"Procesando comparación WT para {wt_family} con parámetros: long={long_threshold}, dist={distance_threshold}, granularity={granularity}, tipo={export_type}")
        
        # Validación para segmentación atómica
        if export_type == 'segments_atomicos' and granularity != 'atom':
            return jsonify({"error": "La segmentación atómica requiere granularidad atómica"}), 400
        
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
        
        # === PROCESAR TOXINA WT ===
        print(f"Procesando toxina WT: {wt_code}")
        wt_data = process_single_toxin_for_comparison(
            pdb_data=wt_pdb_data,
            toxin_name=wt_code,
            ic50_value=wt_ic50,
            ic50_unit=wt_unit,
            granularity=granularity,
            long_threshold=long_threshold,
            distance_threshold=distance_threshold,
            toxin_type="WT_Target",
            export_type=export_type
        )
        
        # === PROCESAR TOXINA DE REFERENCIA ===
        print(f"Procesando toxina de referencia: hwt4_Hh2a_WT")
        with open(reference_path, 'r') as ref_file:
            ref_pdb_content = ref_file.read()
        
        ref_data = process_single_toxin_for_comparison(
            pdb_data=ref_pdb_content,
            toxin_name="hwt4_Hh2a_WT",
            ic50_value=None,
            ic50_unit=None,
            granularity=granularity,
            long_threshold=long_threshold,
            distance_threshold=distance_threshold,
            toxin_type="Reference",
            export_type=export_type
        )
        
        # Diccionario para almacenar dataframes
        comparison_dataframes = {}
        
        if wt_data:
            if export_type == 'segments_atomicos':
                # Para segmentación atómica, wt_data ya es un DataFrame
                comparison_dataframes['WT_Target'] = wt_data
            else:
                # Para análisis por residuos, convertir lista a DataFrame
                wt_df = pd.DataFrame(wt_data)
                comparison_dataframes['WT_Target'] = wt_df
        
        if ref_data:
            if export_type == 'segments_atomicos':
                # Para segmentación atómica, ref_data ya es un DataFrame
                comparison_dataframes['Reference'] = ref_data
            else:
                # Para análisis por residuos, convertir lista a DataFrame
                ref_df = pd.DataFrame(ref_data)
                comparison_dataframes['Reference'] = ref_df
            
        # Crear metadatos completos
        metadata = {
            'Toxina_WT': wt_code,
            'Toxina_Referencia': 'hwt4_Hh2a_WT',
            'Familia': wt_family,
            'Tipo_Analisis': 'Segmentación Atómica' if export_type == 'segments_atomicos' else 'Análisis por Residuos',
            'IC50_WT': f"{wt_ic50} {wt_unit}" if wt_ic50 and wt_unit else "No disponible",
            'Granularidad': granularity,
            'Umbral_Distancia': distance_threshold,
            'Umbral_Interaccion_Larga': long_threshold,
            'Fecha_Exportacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Añadir datos de grafo si están disponibles (se eliminan referencias erróneas)
        # Las métricas de grafo ahora se incluyen en process_single_toxin_for_comparison
            
        # Crear hoja de resumen con métricas comparativas si ambas toxinas fueron procesadas
        if 'WT_Target' in comparison_dataframes and 'Reference' in comparison_dataframes:
            # Agregar hoja de resumen con diferencias y similitudes clave
            wt_df = comparison_dataframes['WT_Target']
            ref_df = comparison_dataframes['Reference']
            
            # Calcular propiedades generales del grafo para comparación
            if export_type == 'segments_atomicos':
                # Para segmentación atómica, usar métricas específicas
                summary_data = {
                    'Propiedad': [
                        'Toxina_WT', 'Toxina_Referencia',
                        'Numero_Segmentos_Atomicos', 
                        'Conexiones_Internas_Promedio',
                        'Densidad_Segmento_Promedio', 
                        'Centralidad_Grado_Promedio',
                        'Centralidad_Intermediacion_Promedio'
                    ],
                    'WT_Target': [
                        wt_code, 'N/A',
                        len(wt_df),
                        wt_df['Conexiones_Internas'].mean() if 'Conexiones_Internas' in wt_df.columns else 0,
                        wt_df['Densidad_Segmento'].mean() if 'Densidad_Segmento' in wt_df.columns else 0,
                        wt_df['Centralidad_Grado_Promedio'].mean() if 'Centralidad_Grado_Promedio' in wt_df.columns else 0,
                        wt_df['Centralidad_Intermediacion_Promedio'].mean() if 'Centralidad_Intermediacion_Promedio' in wt_df.columns else 0
                    ],
                    'Reference': [
                        'N/A', 'hwt4_Hh2a_WT',
                        len(ref_df),
                        ref_df['Conexiones_Internas'].mean() if 'Conexiones_Internas' in ref_df.columns else 0,
                        ref_df['Densidad_Segmento'].mean() if 'Densidad_Segmento' in ref_df.columns else 0,
                        ref_df['Centralidad_Grado_Promedio'].mean() if 'Centralidad_Grado_Promedio' in ref_df.columns else 0,
                        ref_df['Centralidad_Intermediacion_Promedio'].mean() if 'Centralidad_Intermediacion_Promedio' in ref_df.columns else 0
                    ]
                }
            else:
                # Para análisis por residuos, usar métricas tradicionales
                summary_data = {
                    'Propiedad': [
                        'Toxina_WT', 'Toxina_Referencia',
                        'Numero_Residuos', 
                        'Centralidad_Grado_Promedio',
                        'Centralidad_Intermediacion_Promedio', 
                        'Centralidad_Cercania_Promedio',
                        'Coeficiente_Agrupamiento_Promedio'
                    ],
                    'WT_Target': [
                        wt_code, 'N/A',
                        len(wt_df),
                        wt_df['Centralidad_Grado'].mean() if 'Centralidad_Grado' in wt_df.columns else 0,
                        wt_df['Centralidad_Intermediacion'].mean() if 'Centralidad_Intermediacion' in wt_df.columns else 0,
                        wt_df['Centralidad_Cercania'].mean() if 'Centralidad_Cercania' in wt_df.columns else 0,
                        wt_df['Coeficiente_Agrupamiento'].mean() if 'Coeficiente_Agrupamiento' in wt_df.columns else 0
                    ],
                    'Reference': [
                        'N/A', 'hwt4_Hh2a_WT',
                        len(ref_df),
                        ref_df['Centralidad_Grado'].mean() if 'Centralidad_Grado' in ref_df.columns else 0,
                        ref_df['Centralidad_Intermediacion'].mean() if 'Centralidad_Intermediacion' in ref_df.columns else 0,
                        ref_df['Centralidad_Cercania'].mean() if 'Centralidad_Cercania' in ref_df.columns else 0,
                        ref_df['Coeficiente_Agrupamiento'].mean() if 'Coeficiente_Agrupamiento' in ref_df.columns else 0
                    ]
                }
            
            comparison_dataframes['Resumen_Comparativo'] = pd.DataFrame(summary_data)
            
        # Generar archivo Excel con metadatos
        family_clean = wt_family.replace('μ', 'mu').replace('β', 'beta').replace('ω', 'omega').replace('δ', 'delta')
        
        if export_type == 'segments_atomicos':
            filename_prefix = f"Comparacion_WT_{family_clean}_vs_hwt4_Hh2a_WT_Segmentacion_Atomica_{granularity}"
        else:
            filename_prefix = f"Comparacion_WT_{family_clean}_vs_hwt4_Hh2a_WT_{granularity}"
            
        excel_data, excel_filename = generate_excel(comparison_dataframes, filename_prefix, metadata=metadata)
        
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


def process_single_toxin_for_comparison(pdb_data, toxin_name, ic50_value, ic50_unit, granularity, long_threshold, distance_threshold, toxin_type, export_type='residues'):
    """
    Procesa una sola toxina para análisis comparativo.
    Ahora soporta tanto análisis por residuos como segmentación atómica.
    """
    try:
        # Preprocesar PDB para graphein
        if isinstance(pdb_data, bytes):
            pdb_content = pdb_data.decode('utf-8')
        else:
            pdb_content = pdb_data
        
        processed_pdb_content = preprocess_pdb_for_graphein(pdb_content)
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
            temp_file.write(processed_pdb_content.encode('utf-8'))
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
                    ],
                    node_metadata_functions=[
                        amino_acid_one_hot,
                        add_sidechain_vector
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
            
            # Procesar según el tipo de exportación
            if export_type == 'segments_atomicos':
                # Usar segmentación atómica
                print(f"    🧩 Aplicando segmentación atómica para {toxin_name}...")
                df_segmentos = agrupar_por_segmentos_atomicos(G, granularity=granularity)
                
                if not df_segmentos.empty:
                    # Agregar información de la toxina
                    df_segmentos['Toxina'] = toxin_name
                    df_segmentos['Tipo_Toxina'] = toxin_type
                    if ic50_value and ic50_unit:
                        df_segmentos['IC50_Value'] = ic50_value
                        df_segmentos['IC50_Unit'] = ic50_unit
                    else:
                        df_segmentos['IC50_Value'] = None
                        df_segmentos['IC50_Unit'] = None
                    
                    # Normalizar IC50 a unidades consistentes (nM)
                    if ic50_value and ic50_unit:
                        if ic50_unit.lower() == "nm":
                            ic50_nm = ic50_value
                        elif ic50_unit.lower() == "μm" or ic50_unit.lower() == "um":
                            ic50_nm = ic50_value * 1000
                        elif ic50_unit.lower() == "mm":
                            ic50_nm = ic50_value * 1000000
                        else:
                            ic50_nm = ic50_value
                        df_segmentos['IC50_nM'] = ic50_nm
                    else:
                        df_segmentos['IC50_nM'] = None
                    
                    # Extraer familia WT
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
                    
                    df_segmentos['Familia_WT'] = family_wt
                    
                    # Reordenar columnas para que la información de toxina aparezca primero
                    cols = ['Toxina', 'Tipo_Toxina', 'Familia_WT', 'IC50_Value', 'IC50_Unit', 'IC50_nM'] + [col for col in df_segmentos.columns if col not in ['Toxina', 'Tipo_Toxina', 'Familia_WT', 'IC50_Value', 'IC50_Unit', 'IC50_nM']]
                    df_segmentos = df_segmentos[cols]
                    
                    print(f"    ✅ Segmentación completada: {len(df_segmentos)} segmentos procesados")
                    return df_segmentos
                else:
                    print(f"    ⚠️ No se generaron segmentos para {toxin_name}")
                    return pd.DataFrame()
            
            else:
                # Análisis por residuos tradicional
                print(f"    📊 Calculando métricas de centralidad para {toxin_name}...")
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
                    else:  # nivel atómico
                        chain = data.get('chain_id', 'A')
                        residue_name = data.get('residue_name', 'UNK')
                        residue_number = str(data.get('residue_number', node))
                    
                    # Incluir datos esenciales y métricas
                    toxin_data.append({
                        # Identificadores
                        'Toxina': toxin_name,
                        'Tipo_Toxina': toxin_type,
                        'Familia_WT': family_wt,
                        'Cadena': chain,
                        'Residuo_Nombre': residue_name,
                        'Residuo_Numero': residue_number,
                        
                        # Información de IC50
                        'IC50_Value': ic50_value,
                        'IC50_Unit': ic50_unit,
                        'IC50_nM': ic50_nm,
                        
                        # Métricas de centralidad
                        'Centralidad_Grado': round(degree_centrality.get(node, 0), 6),
                        'Centralidad_Intermediacion': round(betweenness_centrality.get(node, 0), 6),
                        'Centralidad_Cercania': round(closeness_centrality.get(node, 0), 6),
                        'Coeficiente_Agrupamiento': round(clustering_coefficient.get(node, 0), 6),
                        
                        # Propiedades estructurales
                        'Grado_Nodo': G.degree(node)
                    })
                
                print(f"     ✅ Procesados {len(toxin_data)} residuos de {toxin_name}")
                return toxin_data
            
        finally:
            os.unlink(temp_path)
            print(f"     Archivo temporal eliminado")
            
    except Exception as e:
        print(f"     Error procesando {toxin_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return [] if export_type != 'segments_atomicos' else pd.DataFrame()
        
# Agregar este nuevo endpoint después de get_pdb
@viewer_bp.route("/get_psf/<string:source>/<int:pid>")
def get_psf(source, pid):
    """Obtener archivo PSF desde la base de datos"""
    if source != "nav1_7":
        return jsonify({"error": "PSF files only available for nav1_7"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT psf_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (pid,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or not result[0]:
        return jsonify({"error": "PSF not found"}), 404
    
    psf_data = result[0]
    
    try:
        if isinstance(psf_data, bytes):
            return psf_data.decode('utf-8'), 200, {'Content-Type': 'text/plain'}
        else:
            return str(psf_data), 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        return jsonify({"error": f"Error processing PSF: {str(e)}"}), 500

# Modificar el endpoint calculate_dipole para trabajar con archivos de BD
@viewer_bp.route("/calculate_dipole_from_db/<string:source>/<int:pid>", methods=['POST'])
def calculate_dipole_from_db(source, pid):
    """Calculate dipole moment from database PDB and PSF files"""
    try:
        if source != "nav1_7":
            return jsonify({"error": "Dipole calculation only available for nav1_7"}), 400
        
        # Get PDB and PSF data from database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT pdb_blob, psf_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (pid,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({"error": "Data not found"}), 404
        
        pdb_data, psf_data = result
        
        if not pdb_data:
            return jsonify({"error": "No PDB data found"}), 404
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as pdb_temp:
            if isinstance(pdb_data, bytes):
                pdb_temp.write(pdb_data)
            else:
                pdb_temp.write(pdb_data.encode('utf-8'))
            pdb_path = pdb_temp.name
        
        psf_path = None
        if psf_data:
            with tempfile.NamedTemporaryFile(suffix='.psf', delete=False) as psf_temp:
                if isinstance(psf_data, bytes):
                    psf_temp.write(psf_data)
                else:
                    psf_temp.write(psf_data.encode('utf-8'))
                psf_path = psf_temp.name
        
        try:
            # Calculate dipole using the analyzer
            dipole_data = toxin_analyzer.calculate_dipole_moment_with_psf(pdb_path, psf_path)
            
            return jsonify({
                'success': True,
                'dipole': dipole_data
            })
            
        finally:
            # Clean up temporary files
            os.unlink(pdb_path)
            if psf_path:
                os.unlink(psf_path)
                
    except Exception as e:
        print(f"Error calculating dipole from DB: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@viewer_bp.route('/export_segment_nodes/<source>/<int:pid>')
def export_segment_nodes(source, pid):
    try:
        long_val = int(request.args.get('long', 5))
        threshold = float(request.args.get('threshold', 10.0))
        granularity = 'atom'  # obligatorio para nodos atómicos

        # Obtener PDB
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if source == "toxinas":
            cursor.execute("SELECT pdb_file, peptide_name FROM Peptides WHERE peptide_id = ?", (pid,))
        elif source == "nav1_7":
            cursor.execute("SELECT pdb_blob, peptide_code FROM Nav1_7_InhibitorPeptides WHERE id = ?", (pid,))
        else:
            return jsonify({"error": "Fuente inválida"}), 400
        result = cursor.fetchone()
        conn.close()
        if not result:
            return jsonify({"error": "PDB no encontrado"}), 404

        pdb_data, toxin_name = result
        clean_name = re.sub(r'[^\w]', '_', toxin_name)[:31]

        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
            temp_file.write(pdb_data if isinstance(pdb_data, bytes) else pdb_data.encode('utf-8'))
            pdb_path = temp_file.name

        # Construcción del grafo y segmentación
        from app.utils.graph_segmentation import generate_segment_groupings
        df_segmentos = generate_segment_groupings(
            pdb_path=pdb_path,
            source=source,
            protein_id=pid,
            long_range=long_val,
            threshold=threshold,
            granularity=granularity,
            toxin_name=toxin_name
        )

        # Exportar a XLSX
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_segmentos.to_excel(writer, index=False, sheet_name=clean_name[:31])
        output.seek(0)

        filename = f"SegmentosAgrupados_{clean_name}.xlsx"
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        print(f"❌ Error en export_segment_nodes: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
