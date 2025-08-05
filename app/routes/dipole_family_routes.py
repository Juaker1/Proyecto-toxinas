from flask import Blueprint, render_template, jsonify, request
from app.services.database_service import DatabaseService
from app.services.dipole_service import DipoleAnalysisService  # Importar el servicio de análisis de dipolos

dipole_family_routes = Blueprint('dipole_family_routes', __name__)

@dipole_family_routes.route('/dipole-family-analysis')
def dipole_family_analysis():
    """Página principal del análisis de dipolo por familia"""
    return render_template('dipole_families.html')

@dipole_family_routes.route('/api/families')
def get_families():
    """Obtener familias de toxinas disponibles"""
    try:
        # Familias específicas basadas en los péptidos originales
        families = [
            {'value': 'μ-TRTX-Hh2a', 'text': 'μ-TRTX-Hh2a (Familia Hh2a)', 'count': 0},
            {'value': 'μ-TRTX-Hhn2b', 'text': 'μ-TRTX-Hhn2b (Familia Hhn2b)', 'count': 0},
            {'value': 'β-TRTX', 'text': 'β-TRTX (Familia Beta)', 'count': 0},  # Cambiado
            {'value': 'ω-TRTX-Gr2a', 'text': 'ω-TRTX-Gr2a (Familia Omega)', 'count': 0}
        ]
        
        # Contar péptidos por familia
        db_service = DatabaseService()
        for family in families:
            peptides = db_service.get_family_peptides(family['value'])
            family['count'] = len(peptides)
        
        return jsonify({
            'success': True,
            'families': families
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dipole_family_routes.route('/api/family-peptides/<family_name>')
def get_family_peptides(family_name):
    """Obtener péptidos de una familia específica"""
    try:
        db_service = DatabaseService()
        peptides = db_service.get_family_peptides(family_name)
        
        # Lógica especial para β-TRTX
        if family_name == 'β-TRTX':
            # Todos son péptidos originales, no hay modificados
            return jsonify({
                'success': True,
                'data': {
                    'family_name': family_name,
                    'family_type': 'multiple_originals',  # Nuevo campo
                    'all_peptides': peptides,
                    'total_count': len(peptides),
                    'original_peptide': None,
                    'modified_peptides': []
                }
            })
        else:
            # Organizar datos para otras familias (original + modificados)
            original_peptide = None
            modified_peptides = []
            
            for peptide in peptides:
                if peptide['peptide_type'] == 'original':
                    original_peptide = peptide
                else:
                    modified_peptides.append(peptide)
            
            return jsonify({
                'success': True,
                'data': {
                    'family_name': family_name,
                    'family_type': 'original_plus_modified',  # Nuevo campo
                    'original_peptide': original_peptide,
                    'modified_peptides': modified_peptides,
                    'total_count': len(peptides),
                    'modified_count': len(modified_peptides)
                }
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dipole_family_routes.route('/api/family-dipoles/<family_name>')
def get_family_dipoles(family_name):
    """Calcular dipolos para toda una familia específica"""
    try:
        db_service = DatabaseService()
        dipole_service = DipoleAnalysisService()
        
        # Obtener péptidos de la familia
        peptides = db_service.get_family_peptides(family_name)
        
        dipole_results = []
        calculation_errors = []
        
        for peptide in peptides:
            try:
                # Obtener datos PDB desde la base de datos
                pdb_data = db_service.get_pdb_data('nav1_7', peptide['id'])
                psf_data = db_service.get_psf_data(peptide['id'])
                
                if pdb_data:
                    # ✅ CORRECCIÓN: No codificar los datos que ya vienen como bytes
                    dipole_result = dipole_service.process_dipole_calculation(
                        pdb_data,  # Sin .encode()
                        psf_data   # Sin .encode()
                    )
                    
                    
                    if dipole_result['success']:
                        # ✅ CORRECCIÓN: Convertir PDB a string para el frontend
                        pdb_text = pdb_data.decode('utf-8') if isinstance(pdb_data, bytes) else pdb_data
                        psf_data = psf_data.decode('utf-8') if isinstance(psf_data, bytes) else psf_data

                        dipole_results.append({
                            'peptide_id': peptide['id'],
                            'peptide_code': peptide['peptide_code'],
                            'ic50_value': peptide['ic50_value'],
                            'ic50_unit': peptide['ic50_unit'],
                            'pdb_data': pdb_text, 
                            'psf_data': psf_data,
                            'dipole_data': dipole_result['dipole']
                        })
                        
                    else:
                        calculation_errors.append({
                            'peptide_code': peptide['peptide_code'],
                            'error': dipole_result.get('error', 'Error desconocido en cálculo dipolar')
                        })
                        
                else:
                    calculation_errors.append({
                        'peptide_code': peptide['peptide_code'],
                        'error': 'No se encontraron datos PDB'
                    })
                    
            except Exception as e:
                calculation_errors.append({
                    'peptide_code': peptide['peptide_code'],
                    'error': f'Error procesando péptido: {str(e)}'
                })
        
        # Calcular estadísticas
        if dipole_results:
            magnitudes = [result['dipole_data']['magnitude'] for result in dipole_results]
            summary = {
                'total_proteins': len(dipole_results),
                'avg_magnitude': sum(magnitudes) / len(magnitudes),
                'min_magnitude': min(magnitudes),
                'max_magnitude': max(magnitudes),
                'calculation_errors': len(calculation_errors)
            }
        else:
            summary = {
                'total_proteins': 0,
                'avg_magnitude': 0,
                'min_magnitude': 0,
                'max_magnitude': 0,
                'calculation_errors': len(calculation_errors)
            }
        
        return jsonify({
            'success': True,
            'data': {
                'family': family_name,
                'dipole_results': dipole_results,
                'summary': summary,
                'errors': calculation_errors
            }
        })
        
    except Exception as e:
        print(f"Error en get_family_dipoles: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500