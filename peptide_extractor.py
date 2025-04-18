import os
import sqlite3
import xml.etree.ElementTree as ET
import requests
import asyncio
import aiohttp
import tempfile
from typing import Dict, List, Tuple, Optional, Union
from Bio.PDB import PDBParser, PPBuilder
from cortar_pdb import PDBHandler

class PeptideExtractor:
    """
    Clase para extraer péptidos de archivos PDB basados en información de UniProt.
    Permite descargar, cortar y almacenar péptidos en la base de datos.
    """
    
    def __init__(self, db_path: str = "database/toxins.db", data_dir: str = "data/pdb_raw/"):
        """
        Inicializa el extractor de péptidos.
        
        Args:
            db_path (str): Ruta a la base de datos SQLite.
            data_dir (str): Directorio para almacenar archivos PDB descargados.
        """
        self.db_path = db_path
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
    def _connect_db(self) -> sqlite3.Connection:
        """Establece una conexión con la base de datos."""
        return sqlite3.connect(self.db_path)
    
    async def download_pdb_file(self, pdb_id: str, chain_id: Optional[str] = None) -> str:
        """
        Descarga un archivo PDB desde el RCSB PDB o AlphaFold.
        
        Args:
            pdb_id (str): Identificador PDB (4 caracteres) o UniProt (para AlphaFold).
            chain_id (str, opcional): Identificador de cadena específica.
            
        Returns:
            str: Ruta al archivo PDB descargado.
        """
        # Normaliza el ID para el nombre de archivo pero preserva el original para URLs
        original_id = pdb_id  # Mantener el ID original con su capitalización
        file_id = pdb_id.lower()
        file_path = os.path.join(self.data_dir, f"{file_id}.pdb")
        
        # Si ya existe, solo devolvemos la ruta
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            print(f"Usando archivo local existente: {file_path}")
            return file_path
        
        # Determinar si es un ID de PDB (4 caracteres) o no
        is_pdb_id = len(pdb_id) == 4 and all(c.isalnum() for c in pdb_id)
        
        try:
            async with aiohttp.ClientSession() as session:
                # Primero intenta RCSB PDB si el ID es compatible
                if is_pdb_id:
                    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
                    print(f"Intentando descarga desde RCSB: {url}")
                    
                    async with session.get(url) as response:
                        if response.status == 200:
                            pdb_content = await response.text()
                            with open(file_path, 'w') as f:
                                f.write(pdb_content)
                            print(f"Archivo PDB descargado con éxito desde RCSB: {file_path}")
                            return file_path
                
                # Si llegamos aquí, intentamos AlphaFold
                # IMPORTANTE: Usar el ID original con su capitalización correcta
                if original_id.startswith("AF-"):
                    alphafold_id = original_id
                else:
                    # Usar el ID original con capitalización preservada
                    alphafold_id = f"AF-{original_id}-F1-model_v4"
                    
                alphafold_url = f"https://alphafold.ebi.ac.uk/files/{alphafold_id}.pdb"
                print(f"Intentando descarga desde AlphaFold: {alphafold_url}")
                
                async with session.get(alphafold_url) as af_response:
                    if af_response.status == 200:
                        pdb_content = await af_response.text()
                        with open(file_path, 'w') as f:
                            f.write(pdb_content)
                        print(f"Archivo PDB descargado con éxito desde AlphaFold: {file_path}")
                        return file_path
                    
                # Intentar con versiones alternativas del modelo de AlphaFold
                alternative_models = ["F2", "F3"]
                for model_version in alternative_models:
                    if original_id.startswith("AF-"):
                        # Si ya tiene el prefijo, no podemos modificar fácilmente
                        continue
                        
                    alt_alphafold_id = f"AF-{original_id}-{model_version}-model_v4"
                    alt_url = f"https://alphafold.ebi.ac.uk/files/{alt_alphafold_id}.pdb"
                    print(f"Intentando descarga alternativa: {alt_url}")
                    
                    async with session.get(alt_url) as alt_response:
                        if alt_response.status == 200:
                            pdb_content = await alt_response.text()
                            with open(file_path, 'w') as f:
                                f.write(pdb_content)
                            print(f"Archivo PDB descargado con éxito desde AlphaFold (modelo alternativo): {file_path}")
                            return file_path
                    
                # Si llegamos aquí, no pudimos descargar el archivo
                print(f"No se pudo encontrar estructura para {original_id} en AlphaFold ni RCSB PDB")
                raise ValueError(f"No se pudo descargar el archivo PDB: {original_id}")
        except Exception as e:
            print(f"Error descargando archivo PDB: {str(e)}")
            raise
    
    def extract_peptides_from_xml(self, xml_path: str) -> List[Dict]:
        """
        Extrae información de péptidos de un archivo XML de UniProt.
        
        Args:
            xml_path (str): Ruta al archivo XML.
            
        Returns:
            list: Lista de diccionarios con información de péptidos.
        """
        peptides = []
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        for protein in root.findall("protein"):
            accession = protein.get("accession")
            sequence = protein.find("sequence").text if protein.find("sequence") is not None else ""
            
            if not accession or not sequence:
                continue
                
            # Buscar todos los peptides en el XML
            for peptide_elem in protein.findall(".//peptides/feature"):
                peptide_type = peptide_elem.get("type")
                if peptide_type not in ["peptide", "chain"]:
                    continue
                    
                description = peptide_elem.get("description", "")
                begin = int(peptide_elem.get("begin", 0))
                end = int(peptide_elem.get("end", 0))
                
                if begin == 0 or end == 0 or begin > end:
                    continue
                    
                # Extraer la secuencia del péptido
                peptide_seq = sequence[begin-1:end] if begin-1 < len(sequence) and end <= len(sequence) else ""
                
                # Buscar estructuras asociadas
                structures = []
                for struct in protein.findall(".//structures/structure"):
                    struct_type = struct.get("type")
                    struct_id = struct.get("id")
                    resolution = struct.get("resolution", "")
                    
                    if struct_type and struct_id:
                        # Verificar que el struct_id sea válido
                        if struct_type == "PDB" and len(struct_id) != 4:
                            print(f"Advertencia: ID PDB inválido '{struct_id}' para {accession}")
                            continue
                            
                        if struct_type == "AlphaFoldDB" and not struct_id.startswith(tuple(['A', 'P', 'Q', 'O'])):
                            # Los IDs de AlphaFold suelen comenzar con estas letras
                            print(f"Advertencia: ID AlphaFold inválido '{struct_id}' para {accession}")
                            
                        structures.append({
                            "type": struct_type,
                            "id": struct_id,
                            "resolution": resolution
                        })
                
                if not structures:
                    print(f"Sin estructuras disponibles para {description} de {accession}")
                    continue
                    
                peptides.append({
                    "accession_number": accession,
                    "peptide_name": description,
                    "start_position": begin,
                    "end_position": end,
                    "sequence": peptide_seq,
                    "structures": structures
                })
                    
        print(f"Extraídos {len(peptides)} péptidos con estructuras asociadas")
        return peptides
    
    async def process_peptide(self, peptide: Dict) -> Optional[Dict]:
        """
        Procesa un péptido descargando su estructura y cortándola según sus coordenadas.
        Si no se puede cortar, usa la estructura completa como respaldo.
        
        Args:
            peptide (dict): Información del péptido.
            
        Returns:
            dict: Información del péptido procesado o None si no se pudo procesar.
        """
        structures = peptide.get("structures", [])
        if not structures:
            print(f"Sin estructuras disponibles para péptido {peptide['peptide_name']} de {peptide['accession_number']}")
            return None
            
        # Priorizar estructuras PDB sobre AlphaFold
        pdb_structs = [s for s in structures if s["type"] == "PDB"]
        af_structs = [s for s in structures if s["type"] == "AlphaFoldDB"]
        
        target_structs = pdb_structs if pdb_structs else af_structs
        if not target_structs:
            print(f"No se encontraron estructuras PDB o AlphaFold para {peptide['peptide_name']} de {peptide['accession_number']}")
            return None
            
        # Tomar la primera estructura disponible
        struct = target_structs[0]
        struct_id = struct["id"]
        struct_type = struct["type"]
        
        # Debug para verificar IDs correctos
        print(f"Procesando péptido: {peptide['peptide_name']}, AccNum: {peptide['accession_number']}, Struct: {struct_type} - {struct_id}")
        
        try:
            # Descargar el archivo PDB
            pdb_file = await self.download_pdb_file(struct_id)
            
            # Variable para indicar si estamos usando estructura completa o fragmento
            using_full_structure = False
            cut_successful = False
            
            # Crear un archivo temporal para el péptido cortado
            with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as temp_file:
                peptide_pdb_path = temp_file.name
            
            # Intentar cortar el archivo PDB
            try:
                PDBHandler.cut_pdb_by_residue_indices(
                    pdb_file, 
                    peptide_pdb_path, 
                    peptide["start_position"], 
                    peptide["end_position"]
                )
                cut_successful = True
            except ValueError as ve:
                print(f"Error al cortar el PDB para {peptide['peptide_name']}: {str(ve)}")
                # Tratar de ajustar los índices si el rango está fuera de los límites
                try:
                    # Extrae la secuencia del PDB para obtener el rango válido
                    seq = PDBHandler.extract_primary_sequence(pdb_file)
                    print(f"Secuencia PDB tiene {len(seq)} residuos vs. rango solicitado: {peptide['start_position']}-{peptide['end_position']}")
                    
                    # Intenta usar rango ajustado si es necesario
                    start_adjusted = min(max(1, peptide["start_position"]), len(seq))
                    end_adjusted = min(peptide["end_position"], len(seq))
                    
                    if start_adjusted < end_adjusted:
                        print(f"Reintentando con rango ajustado: {start_adjusted}-{end_adjusted}")
                        PDBHandler.cut_pdb_by_residue_indices(
                            pdb_file, 
                            peptide_pdb_path, 
                            start_adjusted, 
                            end_adjusted
                        )
                        cut_successful = True
                    else:
                        print(f"Rango inválido después de ajuste: {start_adjusted}-{end_adjusted}, usando estructura completa")
                        using_full_structure = True
                except Exception as inner_e:
                    print(f"Fallo en ajuste de rango: {str(inner_e)}, usando estructura completa")
                    using_full_structure = True
            
            # Si no se pudo cortar, usar la estructura completa
            if using_full_structure:
                print(f"Usando estructura completa para {peptide['peptide_name']} de {peptide['accession_number']}")
                # Copiar el archivo completo en lugar del recorte
                import shutil
                shutil.copy(pdb_file, peptide_pdb_path)
            
            # Leer el contenido del archivo final (recortado o completo)
            with open(peptide_pdb_path, 'r') as f:
                pdb_content = f.read()
                
            # Construir el enlace adecuado según el tipo de estructura
            if struct_type == "PDB":
                model_link = f"https://www.rcsb.org/structure/{struct_id}"
            else:  # AlphaFoldDB
                model_link = f"https://alphafold.ebi.ac.uk/entry/{struct_id}"
                
            # Actualizar el péptido con la información de la estructura
            peptide.update({
                "model_source": struct_type,
                "model_id": struct_id,
                "model_link": model_link,
                "pdb_file": pdb_content,
                "is_full_structure": using_full_structure  # Marca para saber si es estructura completa
            })
            
            # Limpiar el archivo temporal
            os.unlink(peptide_pdb_path)
            
            return peptide
            
        except Exception as e:
            print(f"Error procesando péptido {peptide['peptide_name']} de {peptide['accession_number']}: {str(e)}")
            import traceback
            print(f"Detalles: {traceback.format_exc()}")
            return None
    
    def save_peptide_to_db(self, peptide: Dict) -> int:
        """
        Guarda un péptido en la base de datos.
        
        Args:
            peptide (dict): Información del péptido procesado.
            
        Returns:
            int: ID del péptido insertado.
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        
        try:
            # Verificar si la columna is_full_structure existe en la tabla Peptides
            cursor.execute("PRAGMA table_info(Peptides)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if "is_full_structure" in columns:
                cursor.execute("""
                    INSERT INTO Peptides (
                        accession_number, peptide_name, start_position, end_position, 
                        sequence, model_source, model_id, model_link, pdb_file, is_full_structure
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    peptide["accession_number"],
                    peptide["peptide_name"],
                    peptide["start_position"],
                    peptide["end_position"],
                    peptide["sequence"],
                    peptide["model_source"],
                    peptide["model_id"],
                    peptide["model_link"],
                    peptide.get("pdb_file"),  # Puede ser None
                    1 if peptide.get("is_full_structure", False) else 0
                ))
            else:
                # Compatibilidad con esquema antiguo
                cursor.execute("""
                    INSERT INTO Peptides (
                        accession_number, peptide_name, start_position, end_position, 
                        sequence, model_source, model_id, model_link, pdb_file
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    peptide["accession_number"],
                    peptide["peptide_name"],
                    peptide["start_position"],
                    peptide["end_position"],
                    peptide["sequence"],
                    peptide["model_source"],
                    peptide["model_id"],
                    peptide["model_link"],
                    peptide.get("pdb_file")  # Puede ser None
                ))
            
            peptide_id = cursor.lastrowid
            conn.commit()
            return peptide_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    async def process_xml_file(self, xml_path: str, max_concurrent: int = 5) -> List[int]:
        """
        Procesa un archivo XML completo, extrayendo y guardando todos los péptidos.
        
        Args:
            xml_path (str): Ruta al archivo XML.
            max_concurrent (int): Número máximo de descargas concurrentes.
            
        Returns:
            list: Lista de IDs de péptidos insertados.
        """
        peptides = self.extract_peptides_from_xml(xml_path)
        print(f"Encontrados {len(peptides)} péptidos en {xml_path}")
        
        # Procesar péptidos con limitación de concurrencia
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(peptide):
            async with semaphore:
                return await self.process_peptide(peptide)
        
        tasks = [process_with_semaphore(peptide) for peptide in peptides]
        processed_peptides = await asyncio.gather(*tasks)
        
        # Filtrar péptidos que no se pudieron procesar
        valid_peptides = [p for p in processed_peptides if p is not None]
        print(f"Procesados exitosamente {len(valid_peptides)} péptidos")
        
        # Guardar en la base de datos
        peptide_ids = []
        for peptide in valid_peptides:
            try:
                peptide_id = self.save_peptide_to_db(peptide)
                peptide_ids.append(peptide_id)
            except Exception as e:
                print(f"Error guardando péptido en la base de datos: {str(e)}")
        
        print(f"Guardados {len(peptide_ids)} péptidos en la base de datos")
        return peptide_ids

# Función auxiliar para ejecución fácil desde la línea de comandos
async def extract_peptides_from_file(xml_path, db_path="database/toxins.db"):
    extractor = PeptideExtractor(db_path=db_path)
    peptide_ids = await extractor.process_xml_file(xml_path)
    return peptide_ids
    
# Punto de entrada para ejecución directa
if __name__ == "__main__":
    import sys

    # Rutas por defecto
    default_xml_path = "data/processed/knottin_venom_data.xml"
    default_db_path = "database/toxins.db"

    # Revisar si se entregaron argumentos
    xml_path = sys.argv[1] if len(sys.argv) > 1 else default_xml_path
    db_path = sys.argv[2] if len(sys.argv) > 2 else default_db_path

    if not os.path.exists(xml_path):
        print(f"Error: No se encuentra el archivo XML: {xml_path}")
        sys.exit(1)

    print(f"[RUN] Procesando archivo {xml_path} → BD {db_path}")
    asyncio.run(extract_peptides_from_file(xml_path, db_path))
    print("[END] Proceso completado.")