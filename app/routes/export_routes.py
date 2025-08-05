"""
Rutas para exportación de datos de análisis.
Este módulo maneja todas las exportaciones a Excel y CSV.
"""

from flask import Blueprint, jsonify, request, send_file
import traceback
import pandas as pd
import networkx as nx

from app.services.database_service import DatabaseService
from app.services.pdb_processor import PDBProcessor, FileUtils
from app.services.graph_analyzer import GraphAnalyzer, ResidueAnalyzer
from app.services.export_service import ExportService
from app.utils.graph_segmentation import agrupar_por_segmentos_atomicos

# Crear blueprint
export_bp = Blueprint('export', __name__)

# Inicializar servicios
db_service = DatabaseService()


@export_bp.route("/export_residues_xlsx/<string:source>/<int:pid>")
def export_residues_xlsx(source, pid):
    """
    Exporta análisis de residuos de una toxina específica a Excel.
    
    Parámetros URL:
    - long: Umbral de interacciones largas (default: 5)
    - threshold: Umbral de distancia (default: 10.0)  
    - granularity: Granularidad del grafo ('CA' o 'atom', default: 'CA')
    """
    try:
        # Obtener parámetros
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        
        # Obtener datos completos de la toxina
        toxin_data = db_service.get_complete_toxin_data(source, pid)
        if not toxin_data:
            return jsonify({"error": "PDB not found"}), 404
        
        pdb_data = toxin_data['pdb_data']
        toxin_name = toxin_data['name']
        ic50_value = toxin_data['ic50_value']
        ic50_unit = toxin_data['ic50_unit']
        
        # Usar nombre por defecto si no existe
        if not toxin_name:
            toxin_name = f"{source}_{pid}"
        
        # Crear archivo temporal
        pdb_content = PDBProcessor.prepare_pdb_data(pdb_data)
        pdb_path = PDBProcessor.create_temp_pdb_file(pdb_content)
        
        try:
            # Construir grafo
            config = GraphAnalyzer.create_graph_config(granularity, long_threshold, distance_threshold)
            G = GraphAnalyzer.construct_protein_graph(pdb_path, config)
            
            print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
            
            # Preparar datos para exportación
            residue_data = ExportService.prepare_residue_export_data(
                G, toxin_name, ic50_value, ic50_unit, granularity
            )
            
            # Crear metadatos
            metadata = ExportService.create_metadata(
                toxin_name, source, pid, granularity, distance_threshold, 
                long_threshold, G, ic50_value, ic50_unit
            )
            
            # Generar archivo Excel
            excel_data, excel_filename = ExportService.generate_single_toxin_excel(
                residue_data, metadata, toxin_name, source
            )
            
            # Retornar archivo
            return send_file(
                excel_data,
                as_attachment=True,
                download_name=excel_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        finally:
            PDBProcessor.cleanup_temp_files(pdb_path)
            print("Temporary file removed")
    
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@export_bp.route("/export_segments_atomicos_xlsx/<string:source>/<int:pid>")
def export_segments_atomicos_xlsx(source, pid):
    """
    Exporta segmentación atómica de una toxina Nav1.7 a Excel.
    Solo disponible para toxinas Nav1.7 con granularidad atómica.
    """
    try:
        # Solo permitir para Nav1.7
        if source != "nav1_7":
            return jsonify({"error": "La segmentación atómica solo está disponible para toxinas Nav1.7"}), 400
        
        # Obtener parámetros
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'atom')
        
        # Validar granularidad
        if granularity != 'atom':
            return jsonify({"error": "La segmentación atómica requiere granularidad 'atom'"}), 400
        
        print(f"🚀 Iniciando exportación de segmentos atómicos para Nav1.7 ID: {pid}")
        
        # Obtener datos de la toxina
        toxin_data = db_service.get_complete_toxin_data(source, pid)
        if not toxin_data:
            return jsonify({"error": "Toxina Nav1.7 no encontrada"}), 404
        
        pdb_data = toxin_data['pdb_data']
        toxin_name = toxin_data['name']
        ic50_value = toxin_data['ic50_value']
        ic50_unit = toxin_data['ic50_unit']
        
        if not toxin_name:
            toxin_name = f"Nav1.7_{pid}"
        
        print(f"📊 Procesando {toxin_name}")
        
        # Crear archivo temporal
        pdb_content = PDBProcessor.prepare_pdb_data(pdb_data)
        pdb_path = PDBProcessor.create_temp_pdb_file(pdb_content)
        
        try:
            # Construir grafo atómico
            config = GraphAnalyzer.create_graph_config(granularity, long_threshold, distance_threshold)
            G = GraphAnalyzer.construct_protein_graph(pdb_path, config)
            
            print(f"✅ Grafo construido: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
            
            if G.number_of_nodes() == 0:
                return jsonify({"error": "El grafo no tiene nodos"}), 500
            
            # Aplicar segmentación atómica
            print(f"🧩 Aplicando segmentación atómica...")
            df_segmentos = agrupar_por_segmentos_atomicos(G, granularity)
            
            if df_segmentos.empty:
                return jsonify({"error": "No se generaron segmentos"}), 500
            
            # Agregar información de la toxina
            df_segmentos.insert(0, 'Toxina', toxin_name)
            
            print(f"📈 Segmentación completada: {len(df_segmentos)} segmentos generados")
            
            # Crear metadatos específicos para segmentación atómica
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
                'Fecha_Exportacion': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Agregar datos de IC50 si están disponibles
            if ic50_value:
                metadata['IC50_Original'] = ic50_value
                metadata['Unidad_IC50'] = ic50_unit
            
            # Generar nombre de archivo
            clean_name = FileUtils.clean_filename(toxin_name)
            filename_prefix = f"Nav1.7-{clean_name}-Segmentos-Atomicos"
            
            print(f"💾 Generando Excel: {filename_prefix}")
            
            # Generar Excel
            from app.utils.excel_export import generate_excel
            excel_data, excel_filename = generate_excel(df_segmentos, filename_prefix, metadata=metadata)
            
            print(f"📁 Archivo Excel generado: {excel_filename}")
            
            # Retornar archivo
            return send_file(
                excel_data,
                as_attachment=True,
                download_name=excel_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        finally:
            PDBProcessor.cleanup_temp_files(pdb_path)
            print("🗑️  Archivo temporal eliminado")
    
    except Exception as e:
        print(f"❌ Error en export_segments_atomicos_xlsx: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@export_bp.route("/export_family_xlsx/<string:family_prefix>")
def export_family_xlsx(family_prefix):
    """
    Exporta análisis completo de una familia de toxinas a Excel.
    
    Parámetros URL:
    - long: Umbral de interacciones largas (default: 5)
    - threshold: Umbral de distancia (default: 10.0)
    - granularity: Granularidad del grafo ('CA' o 'atom', default: 'CA')
    - export_type: Tipo de exportación ('residues' o 'segments_atomicos', default: 'residues')
    """
    try:
        # Obtener parámetros
        long_threshold = int(request.args.get('long', 5))
        distance_threshold = float(request.args.get('threshold', 10.0))
        granularity = request.args.get('granularity', 'CA')
        export_type = request.args.get('export_type', 'residues')
        
        print(f"Procesando familia {family_prefix} con parámetros: long={long_threshold}, dist={distance_threshold}, granularity={granularity}, tipo={export_type}")
        
        # Validación para segmentación atómica
        if export_type == 'segments_atomicos' and granularity != 'atom':
            return jsonify({"error": "La segmentación atómica requiere granularidad 'atom'"}), 400
        
        # Obtener toxinas de esta familia
        family_toxins = db_service.get_family_toxins(family_prefix)
        
        if not family_toxins:
            return jsonify({"error": f"No se encontraron toxinas para la familia {family_prefix}"}), 404
        
        print(f"Procesando familia {family_prefix}: {len(family_toxins)} toxinas encontradas")
        
        # Procesar cada toxina de la familia
        toxin_dataframes = {}
        processed_count = 0
        
        # Crear metadatos para la familia completa
        from datetime import datetime
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
                pdb_data = db_service.get_pdb_data('nav1_7', toxin_id)
                
                if not pdb_data:
                    print(f"No hay datos PDB para {peptide_code}")
                    continue
                
                print(f"PDB obtenido para {peptide_code}")
                
                # Crear archivo temporal
                pdb_content = PDBProcessor.prepare_pdb_data(pdb_data)
                pdb_path = PDBProcessor.create_temp_pdb_file(pdb_content)
                
                try:
                    # Construir grafo
                    config = GraphAnalyzer.create_graph_config(granularity, long_threshold, distance_threshold)
                    G = GraphAnalyzer.construct_protein_graph(pdb_path, config)
                    
                    print(f"Grafo construido para {peptide_code}: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
                    
                    if export_type == 'segments_atomicos':
                        # Segmentación atómica
                        df_segmentos = agrupar_por_segmentos_atomicos(G, granularity)
                        if not df_segmentos.empty:
                            df_segmentos.insert(0, 'Toxina', peptide_code)
                            df_segmentos['IC50_Value'] = ic50_value
                            df_segmentos['IC50_Unit'] = ic50_unit
                            
                            clean_peptide_code = FileUtils.clean_filename(peptide_code)
                            toxin_dataframes[clean_peptide_code] = df_segmentos
                            processed_count += 1
                    else:
                        # Análisis por residuos tradicional
                        residue_data = ExportService.prepare_residue_export_data(
                            G, peptide_code, ic50_value, ic50_unit, granularity
                        )
                        
                        if residue_data:
                            df = pd.DataFrame(residue_data)
                            clean_peptide_code = FileUtils.clean_filename(peptide_code)
                            toxin_dataframes[clean_peptide_code] = df
                            processed_count += 1
                    
                    # Agregar información del grafo a metadatos
                    metadata[f'Nodos_en_{peptide_code}'] = G.number_of_nodes()
                    metadata[f'Aristas_en_{peptide_code}'] = G.number_of_edges()
                    metadata[f'Densidad_en_{peptide_code}'] = round(nx.density(G), 6)
                    
                    # Agregar datos de IC50
                    if ic50_value:
                        toxin_ic50_data[f'IC50_{peptide_code}'] = f"{ic50_value} {ic50_unit}"
                
                finally:
                    PDBProcessor.cleanup_temp_files(pdb_path)
                
            except Exception as e:
                print(f"Error procesando toxina {peptide_code}: {str(e)}")
                traceback.print_exc()
        
        # Agregar información de IC50 a metadatos
        metadata.update(toxin_ic50_data)
        
        if not toxin_dataframes:
            return jsonify({"error": "No se pudieron procesar toxinas válidas"}), 500
        
        # Generar archivo Excel
        excel_data, excel_filename = ExportService.generate_family_excel(
            toxin_dataframes, family_prefix, metadata, export_type, granularity
        )
        
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
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    