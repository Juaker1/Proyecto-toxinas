"""
Servicio para manejar todas las operaciones de base de datos.
Este módulo centraliza todas las consultas y operaciones con la base de datos SQLite.
"""

import sqlite3
from typing import List, Tuple, Optional, Dict, Any


class DatabaseService:
    """Servicio para operaciones de base de datos de toxinas."""
    
    def __init__(self, db_path: str = "database/toxins.db"):
        self.db_path = db_path
    
    def get_connection(self) -> sqlite3.Connection:
        """Obtiene una conexión a la base de datos."""
        return sqlite3.connect(self.db_path)
    
    def fetch_peptides(self, group: str) -> List[Tuple[int, str]]:
        """
        Obtiene la lista de péptidos según el grupo especificado.
        
        Args:
            group: Tipo de grupo ('toxinas' o 'nav1_7')
            
        Returns:
            Lista de tuplas (id, nombre)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            if group == "toxinas":
                cursor.execute("SELECT peptide_id, peptide_name FROM Peptides")
            elif group == "nav1_7":
                cursor.execute("SELECT id, peptide_code FROM Nav1_7_InhibitorPeptides")
            else:
                return []
            
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_all_toxinas(self) -> List[Tuple[int, str]]:
        """Obtiene todas las toxinas disponibles."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT peptide_id, peptide_name FROM Peptides ORDER BY peptide_name")
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_all_nav1_7(self) -> List[Tuple[int, str]]:
        """Obtiene todas las toxinas Nav1.7 disponibles."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id, peptide_code FROM Nav1_7_InhibitorPeptides ORDER BY peptide_code")
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_pdb_data(self, source: str, peptide_id: int) -> Optional[bytes]:
        """
        Obtiene los datos PDB para un péptido específico.
        
        Args:
            source: Fuente de datos ('toxinas' o 'nav1_7')
            peptide_id: ID del péptido
            
        Returns:
            Datos PDB en bytes o None si no se encuentra
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            if source == "toxinas":
                cursor.execute("SELECT pdb_file FROM Peptides WHERE peptide_id = ?", (peptide_id,))
            elif source == "nav1_7":
                cursor.execute("SELECT pdb_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (peptide_id,))
            else:
                return None
            
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            conn.close()
    
    def get_psf_data(self, peptide_id: int) -> Optional[bytes]:
        """
        Obtiene los datos PSF para una toxina Nav1.7.
        
        Args:
            peptide_id: ID del péptido Nav1.7
            
        Returns:
            Datos PSF en bytes o None si no se encuentra
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT psf_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (peptide_id,))
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        finally:
            conn.close()
    
    def get_toxin_info(self, source: str, peptide_id: int) -> Optional[Tuple[str, Optional[float], Optional[str]]]:
        """
        Obtiene información básica de una toxina.
        
        Args:
            source: Fuente de datos ('toxinas' o 'nav1_7')
            peptide_id: ID del péptido
            
        Returns:
            Tupla (nombre, ic50_value, ic50_unit) o None si no se encuentra
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            if source == "toxinas":
                cursor.execute("SELECT peptide_name FROM Peptides WHERE peptide_id = ?", (peptide_id,))
                result = cursor.fetchone()
                return (result[0], None, None) if result else None
            elif source == "nav1_7":
                cursor.execute("SELECT peptide_code, ic50_value, ic50_unit FROM Nav1_7_InhibitorPeptides WHERE id = ?", (peptide_id,))
                result = cursor.fetchone()
                return result if result else None
            else:
                return None
        finally:
            conn.close()
    
    def get_complete_toxin_data(self, source: str, peptide_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene todos los datos disponibles para una toxina.
        
        Args:
            source: Fuente de datos ('toxinas' o 'nav1_7')
            peptide_id: ID del péptido
            
        Returns:
            Diccionario con todos los datos disponibles o None si no se encuentra
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            if source == "toxinas":
                cursor.execute("SELECT pdb_file, peptide_name FROM Peptides WHERE peptide_id = ?", (peptide_id,))
                result = cursor.fetchone()
                if result:
                    return {
                        'pdb_data': result[0],
                        'name': result[1],
                        'ic50_value': None,
                        'ic50_unit': None,
                        'psf_data': None
                    }
            elif source == "nav1_7":
                cursor.execute("SELECT pdb_blob, peptide_code, ic50_value, ic50_unit, psf_blob FROM Nav1_7_InhibitorPeptides WHERE id = ?", (peptide_id,))
                result = cursor.fetchone()
                if result:
                    return {
                        'pdb_data': result[0],
                        'name': result[1],
                        'ic50_value': result[2],
                        'ic50_unit': result[3],
                        'psf_data': result[4]
                    }
            
            return None
        finally:
            conn.close()
    
    def get_family_toxins(self, family_prefix: str) -> List[Tuple[int, str, Optional[float], Optional[str]]]:
        """
        Obtiene todas las toxinas de una familia específica.
        
        Args:
            family_prefix: Prefijo de la familia (ej: 'μ-TRTX', 'β-TRTX')
            
        Returns:
            Lista de tuplas (id, peptide_code, ic50_value, ic50_unit)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Buscar tanto el prefijo original como la versión normalizada
            normalized_prefix = family_prefix.replace('μ', 'mu').replace('β', 'beta').replace('ω', 'omega')
            
            cursor.execute("""
                SELECT id, peptide_code, ic50_value, ic50_unit 
                FROM Nav1_7_InhibitorPeptides 
                WHERE peptide_code LIKE ? OR peptide_code LIKE ?
            """, (f"{family_prefix}%", f"{normalized_prefix}%"))
            
            return cursor.fetchall()
        finally:
            conn.close()

    def get_wt_toxin_by_code(self, peptide_code: str) -> Optional[Tuple[int, str, Optional[float], Optional[str], bytes]]:
        """
        Obtiene una toxina WT específica por su código.
        
        Args:
            peptide_code: Código del péptido
            
        Returns:
            Tupla (id, peptide_code, ic50_value, ic50_unit, pdb_blob) o None si no se encuentra
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, peptide_code, ic50_value, ic50_unit, pdb_blob 
                FROM Nav1_7_InhibitorPeptides 
                WHERE peptide_code = ?
            """, (peptide_code,))
            
            return cursor.fetchone()
        finally:
            conn.close()
    
    def get_family_peptides(self, family_prefix: str) -> List[Dict]:
        """
        Obtiene todos los péptidos de una familia específica incluyendo el original y modificados.
        
        Args:
            family_prefix: Nombre base de la familia (ej: 'μ-TRTX-Hh2a', 'μ-TRTX-Hhn2b', 'β-TRTX')
            
        Returns:
            Lista de diccionarios con información de péptidos
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Caso especial para β-TRTX: buscar todos los péptidos que empiecen con β-TRTX
            if family_prefix == 'β-TRTX':
                cursor.execute("""
                    SELECT id, peptide_code, ic50_value, ic50_unit, sequence, 
                           'original' as peptide_type
                    FROM Nav1_7_InhibitorPeptides 
                    WHERE peptide_code LIKE 'β-TRTX-%'
                    ORDER BY peptide_code ASC
                """, ())
            else:
                # Para otras familias: buscar péptido original (nombre exacto) y modificados
                cursor.execute("""
                    SELECT id, peptide_code, ic50_value, ic50_unit, sequence, 
                           CASE 
                               WHEN peptide_code = ? THEN 'original'
                               ELSE 'modified'
                           END as peptide_type
                    FROM Nav1_7_InhibitorPeptides 
                    WHERE peptide_code = ? OR peptide_code LIKE ?
                    ORDER BY peptide_type ASC, peptide_code ASC
                """, (family_prefix, family_prefix, f"{family_prefix}_%"))
        
            results = cursor.fetchall()
            
            # Convertir a lista de diccionarios
            peptides = []
            for row in results:
                peptides.append({
                    'id': row[0],
                    'peptide_code': row[1],
                    'ic50_value': row[2],
                    'ic50_unit': row[3],
                    'sequence': row[4],
                    'peptide_type': row[5]
                })
            
            return peptides
            
        finally:
            conn.close()
