"""
Rutas para análisis de momento dipolar.
Este módulo maneja los cálculos de momento dipolar de toxinas.
"""

from flask import Blueprint, jsonify, request, render_template
import traceback

from app.services.database_service import DatabaseService
from app.services.dipole_service import DipoleAnalysisService

# Crear blueprint
dipole_bp = Blueprint('dipole', __name__)

# Inicializar servicios
db_service = DatabaseService()
dipole_service = DipoleAnalysisService()


@dipole_bp.route("/calculate_dipole", methods=['POST'])
def calculate_dipole():
    """
    Calcula momento dipolar desde archivos PDB y PSF subidos.
    Acepta archivos PDB (requerido) y PSF (opcional) vía formulario.
    """
    try:
        # Obtener archivos subidos
        if 'pdb_file' not in request.files:
            return jsonify({"error": "No PDB file provided"}), 400
        
        pdb_file = request.files['pdb_file']
        psf_file = request.files.get('psf_blob')  # PSF es opcional
        
        if pdb_file.filename == '':
            return jsonify({"error": "No PDB file selected"}), 400
        
        # Leer contenido de archivos
        pdb_content = pdb_file.read()
        psf_content = psf_file.read() if psf_file and psf_file.filename != '' else None
        
        # Validar datos de entrada
        is_valid, error_msg = dipole_service.validate_dipole_inputs(pdb_content, psf_content)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Procesar cálculo
        result = dipole_service.process_dipole_calculation(pdb_content, psf_content)
        
        return jsonify(result)
    
    except Exception as e:
        print(f"Error calculating dipole: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dipole_bp.route("/calculate_dipole_from_db/<string:source>/<int:pid>", methods=['POST'])
def calculate_dipole_from_db(source, pid):
    """
    Calcula momento dipolar desde archivos PDB y PSF almacenados en la base de datos.
    Solo disponible para toxinas Nav1.7.
    """
    try:
        if source != "nav1_7":
            return jsonify({
                'success': False,
                'error': 'Dipole calculation only available for nav1_7'
            }), 400
        
        # Obtener datos de la base de datos
        toxin_data = db_service.get_complete_toxin_data(source, pid)
        if not toxin_data:
            return jsonify({
                'success': False,
                'error': 'Toxin not found'
            }), 404
        
        pdb_data = toxin_data['pdb_data']
        psf_data = toxin_data['psf_data']
        
        if not pdb_data:
            return jsonify({
                'success': False,
                'error': 'No PDB data available'
            }), 404
        
        # Validar datos de entrada
        is_valid, error_msg = dipole_service.validate_dipole_inputs(pdb_data, psf_data)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Procesar cálculo
        result = dipole_service.process_dipole_calculation(pdb_data, psf_data)
        
        return jsonify(result)
    
    except Exception as e:
        print(f"Error calculating dipole from DB: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
