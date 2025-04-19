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
        Aplica lógicas diferentes según el tipo de estructura:
        - Para PDB: utiliza los rangos de residuos específicos de las cadenas PDB
        - Para AlphaFold: utiliza la lógica de péptidos superpuestos/separados
        
        Args:
            xml_path (str): Ruta al archivo XML.
            
        Returns:
            list: Lista de diccionarios con información de péptidos.
        """
        peptides = []
        tree = ET.parse(xml_path)
        root = tree.getroot()
        protein_count = 0
        multicut_count = 0
        pdb_count = 0
        
        for protein in root.findall("protein"):
            protein_count += 1
            accession = protein.get("accession")
            sequence = protein.find("sequence").text if protein.find("sequence") is not None else ""
            
            if not accession or not sequence:
                continue
                
            # Buscar estructuras asociadas a esta proteína
            pdb_structures = []
            alphafold_structures = []
            
            for struct in protein.findall(".//structures/structure"):
                struct_type = struct.get("type")
                struct_id = struct.get("id")
                
                if not struct_type or not struct_id:
                    continue
                    
                if struct_type == "PDB":
                    # Extraer información de cadenas y rangos de residuos para PDB
                    method = struct.get("method", "")
                    resolution = struct.get("resolution", "")
                    chains_info = struct.get("chains", "")
                    
                    # Procesar información de chains (ejemplo: "A=46-72")
                    chain_ranges = []
                    if chains_info:
                        for chain_part in chains_info.split("/"):
                            parts = chain_part.split("=")
                            if len(parts) == 2:
                                chain_id = parts[0]
                                try:
                                    start, end = map(int, parts[1].split("-"))
                                    chain_ranges.append((chain_id, start, end))
                                except (ValueError, IndexError):
                                    continue
                    
                    pdb_structures.append({
                        "type": struct_type,
                        "id": struct_id,
                        "method": method,
                        "resolution": resolution,
                        "chain_ranges": chain_ranges
                    })
                elif struct_type == "AlphaFoldDB":
                    alphafold_structures.append({
                        "type": struct_type,
                        "id": struct_id
                    })
            
            # Determinar qué estructuras usar (priorizar PDB sobre AlphaFold)
            if pdb_structures:
                # Si hay estructuras PDB, usar los rangos de residuos específicos
                pdb_count += 1
                print(f"Proteína {accession} tiene {len(pdb_structures)} estructuras PDB")
                
                # Extraer todos los rangos de residuos disponibles en las estructuras PDB
                all_pdb_ranges = []
                for pdb_struct in pdb_structures:
                    for chain_id, start, end in pdb_struct.get("chain_ranges", []):
                        all_pdb_ranges.append((start, end, chain_id))
                
                if all_pdb_ranges:
                    # Ordenar por longitud del rango (de mayor a menor)
                    all_pdb_ranges.sort(key=lambda x: x[1] - x[0], reverse=True)
                    
                    # Usar el rango más largo de las estructuras PDB
                    start, end, chain_id = all_pdb_ranges[0]
                    
                    # Extraer la secuencia del péptido basada en este rango
                    peptide_seq = ""
                    if 1 <= start <= len(sequence) and start <= end <= len(sequence):
                        peptide_seq = sequence[start-1:end]
                    
                    peptide_info = {
                        "accession_number": accession,
                        "peptide_name": f"PDB-derived peptide ({pdb_structures[0]['id']} chain {chain_id})",
                        "start_position": start,
                        "end_position": end,
                        "sequence": peptide_seq,
                        "structures": pdb_structures + alphafold_structures  # Incluir todas las estructuras
                    }
                    
                    peptides.append(peptide_info)
                    print(f"  - Usando rango de PDB: {start}-{end} (chain {chain_id})")
                else:
                    # Si no hay información de rango en las estructuras PDB, usar rango de péptidos
                    print(f"  - No hay información de rangos en PDB, buscando péptidos definidos")
                    # Proceder con la lógica de péptidos (similar al caso de AlphaFold)
                    self._process_peptide_features(protein, accession, sequence, pdb_structures + alphafold_structures, peptides)
                    
            elif alphafold_structures:
                # Si solo hay estructuras AlphaFold, aplicar la lógica de péptidos
                self._process_peptide_features(protein, accession, sequence, alphafold_structures, peptides)
        
        print(f"Extraídos {len(peptides)} péptidos de {protein_count} proteínas "
              f"({pdb_count} con estructura PDB, {multicut_count} con múltiples regiones de péptidos)")
        return peptides

    def _process_peptide_features(self, protein, accession, sequence, structures, peptides_list):
        """
        Procesa las características de péptidos para una proteína.
        
        Args:
            protein: Elemento XML de la proteína
            accession: Número de acceso
            sequence: Secuencia completa
            structures: Lista de estructuras
            peptides_list: Lista donde agregar los péptidos procesados
        """
        # Recolectar todos los péptidos válidos para esta proteína
        protein_peptides = []
        for peptide_elem in protein.findall(".//peptides/feature"):
            peptide_type = peptide_elem.get("type")
            if peptide_type not in ["peptide", "chain"]:
                continue
                
            description = peptide_elem.get("description", "")
            begin = int(peptide_elem.get("begin", 0))
            end = int(peptide_elem.get("end", 0))
            
            if begin == 0 or end == 0 or begin > end:
                continue
                
            # Calcular longitud del péptido y extraer secuencia
            peptide_length = end - begin + 1
            peptide_seq = sequence[begin-1:end] if begin-1 < len(sequence) and end <= len(sequence) else ""
            
            protein_peptides.append({
                "accession_number": accession,
                "peptide_name": description,
                "start_position": begin,
                "end_position": end,
                "sequence": peptide_seq,
                "length": peptide_length,
                "structures": structures,
                "region": (begin, end)
            })
        
        # Si no hay péptidos válidos, terminar
        if not protein_peptides:
            return
            
        # Determinar si los péptidos están superpuestos o separados
        if len(protein_peptides) > 1:
            # Ordenar péptidos por posición de inicio
            protein_peptides.sort(key=lambda p: p["start_position"])
            
            # Verificar si hay superposición
            peptides_overlap = False
            for i in range(1, len(protein_peptides)):
                prev_end = protein_peptides[i-1]["end_position"]
                curr_start = protein_peptides[i]["start_position"]
                if curr_start <= prev_end:
                    peptides_overlap = True
                    break
            
            # Estrategia basada en superposición
            if peptides_overlap:
                # CASO 1: Péptidos superpuestos - seleccionar el más largo
                protein_peptides.sort(key=lambda p: p["length"], reverse=True)
                selected_peptide = protein_peptides[0]
                print(f"Proteína {accession} tiene {len(protein_peptides)} péptidos superpuestos. "
                      f"Seleccionando el más largo: {selected_peptide['peptide_name']} ({selected_peptide['length']} aa)")
                # Eliminar campos auxiliares
                del selected_peptide["length"]
                del selected_peptide["region"]
                peptides_list.append(selected_peptide)
            else:
                # CASO 2: Péptidos separados - procesar todos como cortes independientes
                print(f"Proteína {accession} tiene {len(protein_peptides)} péptidos en regiones distintas - procesando todos:")
                for i, pep in enumerate(protein_peptides):
                    # Modificar el nombre para indicar que es un corte específico
                    original_name = pep["peptide_name"]
                    pep["peptide_name"] = f"{original_name} (CUT {i+1}/{len(protein_peptides)})"
                    # Eliminar campos auxiliares
                    del pep["length"]
                    del pep["region"]
                    print(f"  - {pep['peptide_name']}: pos {pep['start_position']}-{pep['end_position']} ({pep['end_position']-pep['start_position']+1} aa)")
                    peptides_list.append(pep)
        else:
            # Solo hay un péptido
            del protein_peptides[0]["length"]
            del protein_peptides[0]["region"]
            peptides_list.append(protein_peptides[0])
    
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