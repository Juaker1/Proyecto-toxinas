from flask import Blueprint, render_template, request, jsonify
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

@viewer_bp.route("/export_residues_csv/<string:source>/<int:pid>")
def export_residues_csv(source, pid):
    try:
        # Obtener parámetros
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        
        # Obtener datos PDB, nombre de la toxina e IC50
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
        
        # Si no tenemos nombre, usar un fallback
        if not toxin_name:
            toxin_name = f"{source}_{pid}"
        
        # Limpiar el nombre para uso en archivo
        import re
        import unicodedata
        
        # Normalizar caracteres Unicode
        normalized_name = unicodedata.normalize('NFKD', toxin_name)
        
        # Convertir caracteres especiales griegos a ASCII
        char_replacements = {
            'μ': 'u', 'β': 'b', 'ω': 'w', 'α': 'a', 'γ': 'g', 'δ': 'd',
            'ε': 'e', 'ζ': 'z', 'η': 'h', 'θ': 't', 'ι': 'i', 'κ': 'k',
            'λ': 'l', 'ν': 'n', 'ξ': 'x', 'ο': 'o', 'π': 'p', 'ρ': 'r',
            'σ': 's', 'τ': 't', 'υ': 'u', 'φ': 'f', 'χ': 'c', 'ψ': 'p', 'ω': 'w'
        }
        
        clean_name = normalized_name
        for greek, ascii_char in char_replacements.items():
            clean_name = clean_name.replace(greek, ascii_char)
        
        # Remover cualquier carácter que no sea ASCII alfanumérico, guión o guión bajo
        clean_name = re.sub(r'[^\w\-_]', '', clean_name, flags=re.ASCII)
        
        if not clean_name:
            clean_name = f"{source}_{pid}"
        
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
            
            G = construct_graph(config=cfg, pdb_code=None, path=temp_path)
            
            # Calcular métricas de centralidad principales
            degree_centrality = nx.degree_centrality(G)
            betweenness_centrality = nx.betweenness_centrality(G)
            closeness_centrality = nx.closeness_centrality(G)
            clustering_coefficient = nx.clustering(G)
            
            # Preparar datos para CSV
            csv_data = []
            
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
            
            for node in G.nodes():
                # Procesar ID del nodo
                parts = str(node).split(':')
                if len(parts) >= 3:
                    chain = parts[0]
                    residue_name = parts[1]
                    residue_number = parts[2]
                else:
                    chain = "A"
                    residue_name = "UNK"
                    residue_number = str(node)
                
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
            
            # Ordenar por centralidad de grado (descendente)
            csv_data.sort(key=lambda x: x['Centralidad_Grado'], reverse=True)
            
            
            output = io.StringIO()
            fieldnames = ['Toxina', 'Cadena', 'Residuo_Nombre', 'Residuo_Numero', 
                         'IC50_Original', 'IC50_Unidad', 'IC50_nM',
                         'Centralidad_Grado', 'Centralidad_Intermediacion', 
                         'Centralidad_Cercania', 'Coeficiente_Agrupamiento',
                         'Grado_Nodo']
            
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)
            
            csv_content = output.getvalue()
            output.close()
            
            # Crear nombre de archivo descriptivo
            if source == "nav1_7":
                filename = f"Nav1.7-{clean_name}.csv"
            else:
                filename = f"Toxinas-{clean_name}.csv"
            
            safe_filename = filename.encode('ascii', 'ignore').decode('ascii')
            
            from flask import Response
            return Response(
                csv_content,
                mimetype="text/csv",
                headers={"Content-disposition": f"attachment; filename={safe_filename}"}
            )
            
        finally:
            os.unlink(temp_path)
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@viewer_bp.route("/export_family_csv/<string:family_prefix>")
def export_family_csv(family_prefix):
    try:
        print(f"🚀 INICIANDO exportación de familia {family_prefix}")
        
        # Obtener parámetros
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        
        print(f"📋 Parámetros: long={long_threshold}, threshold={distance_threshold}, granularity={granularity}")
        
        # Obtener todas las toxinas de la familia seleccionada
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Buscar toxinas que empiecen con el prefijo de familia
        cursor.execute("""
            SELECT id, peptide_code, ic50_value, ic50_unit 
            FROM Nav1_7_InhibitorPeptides 
            WHERE peptide_code LIKE ?
            ORDER BY peptide_code
        """, (f"{family_prefix}%",))
        
        family_toxins = cursor.fetchall()
        conn.close()
        
        if not family_toxins:
            print(f"❌ No se encontraron toxinas para la familia {family_prefix}")
            return jsonify({"error": f"No se encontraron toxinas para la familia {family_prefix}"}), 404
        
        print(f"🧬 Procesando familia {family_prefix}: {len(family_toxins)} toxinas encontradas")
        
        # Dataset completo que contendrá todos los residuos de todas las toxinas
        complete_dataset = []
        processed_count = 0
        
        for toxin_id, peptide_code, ic50_value, ic50_unit in family_toxins:
            print(f"  📊 Procesando {peptide_code} (IC₅₀: {ic50_value} {ic50_unit})")
            
            try:
                # Obtener datos PDB
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT pdb_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (toxin_id,))
                result = cursor.fetchone()
                conn.close()
                
                if not result or not result[0]:
                    print(f"    ⚠️ Sin datos PDB para {peptide_code}")
                    continue
                
                pdb_data = result[0]
                print(f"    ✅ PDB obtenido para {peptide_code} ({len(pdb_data)} bytes)")
                
                # Crear archivo temporal
                with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
                    if isinstance(pdb_data, bytes):
                        temp_file.write(pdb_data)
                    else:
                        temp_file.write(pdb_data.encode('utf-8'))
                    temp_path = temp_file.name
                
                print(f"    📄 Archivo temporal creado: {temp_path}")
                
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
                    
                    print(f"    🔗 Construyendo grafo para {peptide_code}...")
                    G = construct_graph(config=cfg, pdb_code=None, path=temp_path)
                    print(f"    ✅ Grafo construido: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
                    
                    # Calcular métricas de centralidad principales
                    print(f"    📊 Calculando métricas de centralidad...")
                    degree_centrality = nx.degree_centrality(G)
                    betweenness_centrality = nx.betweenness_centrality(G)
                    closeness_centrality = nx.closeness_centrality(G)
                    clustering_coefficient = nx.clustering(G)
                    
                    print(f"    ✅ Métricas calculadas para {peptide_code}")
                    
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
                    
                    print(f"    💊 IC50 normalizado: {ic50_nm} nM")
                    
                    # Procesar cada nodo/residuo
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
                        
                        complete_dataset.append({
                            # Identificadores básicos
                            'Familia': family_prefix,
                            'Toxina': peptide_code,
                            'Cadena': chain,
                            'Residuo_Nombre': residue_name,
                            'Residuo_Numero': residue_number,
                            
                            # Actividad farmacológica
                            'IC50_Original': ic50_value,
                            'IC50_Unidad': ic50_unit,
                            'IC50_nM': round(ic50_nm, 3) if ic50_nm else None,
                            
                            # Métricas de centralidad principales
                            'Centralidad_Grado': round(degree_centrality.get(node, 0), 6),
                            'Centralidad_Intermediacion': round(betweenness_centrality.get(node, 0), 6),
                            'Centralidad_Cercania': round(closeness_centrality.get(node, 0), 6),
                            'Coeficiente_Agrupamiento': round(clustering_coefficient.get(node, 0), 6),
                            
                            # Propiedades del residuo individual
                            'Grado_Nodo': G.degree(node)
                        })
                        
                        node_count += 1
                    
                    print(f"    ✅ Procesados {node_count} residuos de {peptide_code}")
                    processed_count += 1
                        
                finally:
                    os.unlink(temp_path)
                    print(f"    🗑️ Archivo temporal eliminado")
                    
            except Exception as e:
                print(f"    ❌ Error procesando {peptide_code}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        if not complete_dataset:
            print(f"❌ No se pudieron procesar toxinas de la familia")
            return jsonify({"error": "No se pudieron procesar toxinas de la familia"}), 500
        
        print(f"📊 RESUMEN: Procesadas {processed_count}/{len(family_toxins)} toxinas")
        print(f"📊 Total de residuos en dataset: {len(complete_dataset)}")
        
        # Ordenar dataset por toxina y número de residuo
        print(f"🔄 Ordenando dataset...")
        complete_dataset.sort(key=lambda x: (x['Toxina'], int(x['Residuo_Numero']) if x['Residuo_Numero'].isdigit() else 0))
        
        # Crear CSV con dataset simplificado 
        print(f"📝 Generando CSV...")
        output = io.StringIO()
        fieldnames = [
            # Identificadores
            'Familia', 'Toxina', 'Cadena', 'Residuo_Nombre', 'Residuo_Numero',
            # Actividad farmacológica
            'IC50_Original', 'IC50_Unidad', 'IC50_nM',
            # Métricas de centralidad
            'Centralidad_Grado', 'Centralidad_Intermediacion', 'Centralidad_Cercania', 'Coeficiente_Agrupamiento',
            # Propiedades del residuo
            'Grado_Nodo'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(complete_dataset)
        
        csv_content = output.getvalue()
        output.close()
        
        # Crear nombre descriptivo del archivo
        family_names = {
            'μ': 'Mu-TRTX',
            'β': 'Beta-TRTX', 
            'ω': 'Omega-TRTX',
            
        }
        
        family_name = family_names.get(family_prefix, f"{family_prefix}-TRTX")
        filename = f"Dataset_Familia_{family_name}_IC50_Topologia_{granularity}.csv"
        safe_filename = filename.encode('ascii', 'ignore').decode('ascii')
        
        print(f"✅ Dataset completo generado: {len(complete_dataset)} residuos de {len(set(row['Toxina'] for row in complete_dataset))} toxinas")
        print(f"📁 Nombre de archivo: {safe_filename}")
        print(f"📤 Enviando archivo CSV al navegador...")
        
        from flask import Response
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={safe_filename}"}
        )
        
    except Exception as e:
        print(f"💥 Error generando dataset familiar: {str(e)}")
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

@viewer_bp.route("/export_wt_comparison/<string:wt_family>")
def export_wt_comparison(wt_family):
    try:
        print(f"🧬 INICIANDO comparación WT: {wt_family} vs hwt4_Hh2a_WT")
        
        # Obtener parámetros
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        
        print(f"📋 Parámetros: long={long_threshold}, threshold={distance_threshold}, granularity={granularity}")
        
        # Mapeo de familias WT a códigos exactos en la BD
        wt_mapping = {
            'μ-TRTX-Hh2a': 'μ-TRTX-Hh2a',
            'μ-TRTX-Hhn2b': 'μ-TRTX-Hhn2b', 
            'β-TRTX-Cd1a': 'β-TRTX-Cd1a',
            'ω-TRTX-Gr2a': 'ω-TRTX-Gr2a'
        }
        
        if wt_family not in wt_mapping:
            return jsonify({"error": f"Familia WT no reconocida: {wt_family}"}), 400
        
        wt_peptide_code = wt_mapping[wt_family]
        
        # Obtener datos de la toxina WT desde la base de datos
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
            return jsonify({"error": f"No se encontró la toxina WT: {wt_peptide_code}"}), 404
        
        wt_id, wt_code, wt_ic50, wt_unit, wt_pdb_data = wt_result
        print(f"✅ Toxina WT encontrada: {wt_code} (IC₅₀: {wt_ic50} {wt_unit})")
        
        # Cargar la toxina de referencia desde archivo
        reference_path = os.path.join("pdbs", "WT", "hwt4_Hh2a_WT.pdb")
        if not os.path.exists(reference_path):
            return jsonify({"error": f"Archivo de referencia no encontrado: {reference_path}"}), 404
        
        print(f"✅ Archivo de referencia encontrado: {reference_path}")
        
        # Dataset comparativo
        comparison_dataset = []
        
        # === PROCESAR TOXINA WT ===
        print(f"📊 Procesando toxina WT: {wt_code}")
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
        comparison_dataset.extend(wt_data)
        
        # === PROCESAR TOXINA DE REFERENCIA ===
        print(f"📊 Procesando toxina de referencia: hwt4_Hh2a_WT")
        with open(reference_path, 'r') as ref_file:
            ref_pdb_content = ref_file.read()
        
        ref_data = process_single_toxin_for_comparison(
            pdb_data=ref_pdb_content,
            toxin_name="hwt4_Hh2a_WT",
            ic50_value=None,  # Referencia sin datos IC50
            ic50_unit=None,
            granularity=granularity,
            long_threshold=long_threshold,
            distance_threshold=distance_threshold,
            toxin_type="Reference"
        )
        comparison_dataset.extend(ref_data)
        
        if not comparison_dataset:
            return jsonify({"error": "No se pudieron procesar las toxinas para comparación"}), 500
        
        # Ordenar dataset: primero WT, luego referencia
        comparison_dataset.sort(key=lambda x: (x['Tipo_Toxina'], x['Toxina'], int(x['Residuo_Numero']) if x['Residuo_Numero'].isdigit() else 0))
        
        # Crear CSV comparativo
        print(f"📝 Generando CSV comparativo...")
        output = io.StringIO()
        fieldnames = [
            # Identificadores
            'Tipo_Toxina', 'Familia_WT', 'Toxina', 'Cadena', 'Residuo_Nombre', 'Residuo_Numero',
            # Actividad farmacológica
            'IC50_Original', 'IC50_Unidad', 'IC50_nM',
            # Métricas de centralidad
            'Centralidad_Grado', 'Centralidad_Intermediacion', 'Centralidad_Cercania', 'Coeficiente_Agrupamiento',
            # Propiedades estructurales
            'Grado_Nodo', 'Densidad_Grafo', 'Num_Nodos_Grafo', 'Num_Aristas_Grafo'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comparison_dataset)
        
        csv_content = output.getvalue()
        output.close()
        
        # Crear nombre descriptivo del archivo
        family_clean = wt_family.replace('μ', 'mu').replace('β', 'beta').replace('ω', 'omega').replace('δ', 'delta')
        filename = f"Comparacion_WT_{family_clean}_vs_hwt4_Hh2a_WT_{granularity}.csv"
        safe_filename = re.sub(r'[^\w\-_.]', '_', filename)
        
        print(f"✅ Dataset comparativo generado: {len(comparison_dataset)} residuos")
        print(f"📁 Nombre de archivo: {safe_filename}")
        print(f"📤 Enviando archivo CSV al navegador...")
        
        from flask import Response
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={safe_filename}"}
        )
        
    except Exception as e:
        print(f"💥 Error en comparación WT: {str(e)}")
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
            
            print(f"    💊 IC50 normalizado: {ic50_nm} nM")
            
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
                    'Densidad_Grafo': round(nx.density(G), 6),
                    'Num_Nodos_Grafo': G.number_of_nodes(),
                    'Num_Aristas_Grafo': G.number_of_edges()
                })
                node_count += 1
            
            print(f"    ✅ Procesados {node_count} residuos de {toxin_name}")
            return toxin_data
            
        finally:
            os.unlink(temp_path)
            print(f"    🗑️ Archivo temporal eliminado")
            
    except Exception as e:
        print(f"    ❌ Error procesando {toxin_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

