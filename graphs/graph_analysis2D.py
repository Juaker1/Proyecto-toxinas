import os
import networkx as nx
import numpy as np
from Bio import PDB
from Bio.PDB import NeighborSearch, Selection, DSSP
from Bio.PDB.Polypeptide import is_aa, PPBuilder
from Bio.SeqUtils import seq3, seq1
from Bio.SeqUtils.ProtParam import ProteinAnalysis
import MDAnalysis as mda
from scipy.spatial.distance import pdist, squareform
from src.utils.disulfide import find_disulfide_pairs

# Diccionarios de propiedades fisicoquímicas relevantes para interacción con Nav1.7
HYDROPHOBICITY = {'A': 1.8, 'R': -4.5, 'N': -3.5, 'D': -3.5, 'C': 2.5, 'Q': -3.5, 'E': -3.5, 
                 'G': -0.4, 'H': -3.2, 'I': 4.5, 'L': 3.8, 'K': -3.9, 'M': 1.9, 'F': 2.8, 
                 'P': -1.6, 'S': -0.8, 'T': -0.7, 'W': -0.9, 'Y': -1.3, 'V': 4.2}

CHARGES = {'A': 0, 'R': 1, 'N': 0, 'D': -1, 'C': 0, 'Q': 0, 'E': -1, 
           'G': 0, 'H': 0.5, 'I': 0, 'L': 0, 'K': 1, 'M': 0, 'F': 0, 
           'P': 0, 'S': 0, 'T': 0, 'W': 0, 'Y': 0, 'V': 0}

# Colores para visualización según propiedades relevantes para interacción con Nav1.7
RESIDUE_COLORS = {
    'hydrophobic': '#1E88E5',     # Azul - importante para interacciones con membrana
    'polar': '#26A69A',           # Verde azulado - estabilidad estructural
    'positive': '#D81B60',        # Rojo - crítico para interacción con VSD de Nav1.7
    'negative': '#8E24AA',        # Púrpura - importante para interacciones electrostáticas
    'cysteine': '#FFC107',        # Amarillo - esencial para puentes disulfuro en toxinas
    'other': '#78909C'            # Gris - residuos no clasificados
}

# Clasificación de residuos según su relevancia para unión a Nav1.7
def classify_residue(aa):
    """Clasifica aminoácidos según propiedades fisicoquímicas relevantes para Nav1.7"""
    if aa in "AVILMFYW":
        return "hydrophobic"
    elif aa in "STNQ":
        return "polar"
    elif aa in "KRH":
        return "positive"
    elif aa in "DE":
        return "negative"
    elif aa == "C":
        return "cysteine"
    else:
        return "other"

class Nav17ToxinGraphAnalyzer:
    def __init__(self, pdb_folder="pdbs/"):
        self.pdb_folder = pdb_folder
        self.parser = PDB.PDBParser(QUIET=True)
    
    def load_pdb(self, pdb_filename):
        """Carga archivo PDB de toxina para análisis estructural"""
        pdb_path = os.path.join(self.pdb_folder, pdb_filename)
        if not os.path.exists(pdb_path):
            raise FileNotFoundError(f"Archivo PDB no encontrado: {pdb_path}")
        
        structure = self.parser.get_structure('protein', pdb_path)
        return structure
    
    def calculate_secondary_structure(self, structure):
        """Calcula estructura secundaria mediante DSSP"""
        try:
            model = structure[0]
            dssp = DSSP(model, structure.id, dssp='mkdssp')
            
            # Mapeo de estructura secundaria
            ss_map = {
                'H': 'helix',      # α-hélice
                'B': 'beta',       # Puente β
                'E': 'beta',       # Lámina β - común en toxinas ICK
                'G': 'helix',      # Hélice 3-10
                'I': 'helix',      # Hélice π
                'T': 'turn',       # Giro - crítico para sitios de unión de toxinas
                'S': 'bend',       # Curva - crítico para sitios de unión de toxinas
                ' ': 'loop',       # Loop/irregular
                '-': 'loop'        # Ausente
            }
            
            residue_ss = {}
            sasa_values = {}
            
            for k in dssp.keys():
                chain_id, res_id = k[0], k[1][1]
                ss = ss_map.get(dssp[k][1], 'loop')
                residue_ss[res_id] = ss
                
                # Extracción de SASA  importante para identificar sitios de interacción
                sasa_values[res_id] = dssp[k][2]
                
            return residue_ss, sasa_values
        except Exception:
            # Failed to compute DSSP; return empty maps
            return {}, {}
    
    
    def calculate_dipole_moment(self, structure):
        """Calcula momento dipolar (crítico para interacciones con VSD de Nav1.7)"""
        dipole = np.zeros(3)
        center_of_mass = np.zeros(3)
        total_mass = 0
        
        for model in structure:
            for chain in model:
                for residue in chain:
                    if is_aa(residue):
                        try:
                            aa = seq1(residue.get_resname())
                            charge = CHARGES.get(aa, 0)
                            
                            # Uso de átomo CA para posición
                            if "CA" in residue:
                                pos = residue["CA"].get_coord()
                                mass = 1.0  # Simplified mass
                                
                                center_of_mass += mass * pos
                                total_mass += mass
                        except:
                            continue
        
        # Calculate center of mass
        if total_mass > 0:
            center_of_mass = center_of_mass / total_mass
        
        # Calculate dipole moment
        for model in structure:
            for chain in model:
                for residue in chain:
                    if is_aa(residue):
                        try:
                            aa = seq1(residue.get_resname())
                            charge = CHARGES.get(aa, 0)
                            
                            if "CA" in residue:
                                pos = residue["CA"].get_coord()
                                dipole += charge * (pos - center_of_mass)
                        except:
                            continue
        
        # Store dipole vector for compatibility
        self.dipole_moment_vector = dipole
        
        # Normalización del vector dipolar
        magnitude = np.linalg.norm(dipole)
        if magnitude > 0:
            dipole_norm = dipole / magnitude
        else:
            dipole_norm = np.zeros(3)
        
        # Calculate angle with Z-axis
        z_axis = np.array([0, 0, 1])
        cos_angle = np.dot(dipole_norm, z_axis)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle_radians = np.arccos(cos_angle)
        angle_degrees = np.degrees(angle_radians)
        
        return {
            'vector': dipole,
            'magnitude': magnitude,
            'normalized': dipole_norm,
            'center_of_mass': center_of_mass,
            'end_point': center_of_mass + dipole_norm * 20,
            'angle_with_z_axis': {
                'degrees': float(angle_degrees),
                'radians': float(angle_radians)
            }
        }
    
    def calculate_dipole_moment_with_psf(self, pdb_path, psf_path=None):
        """Enhanced dipole calculation using PSF file for better charge assignment"""
        try:
            # Try MDAnalysis first if PSF is provided
            if psf_path and os.path.exists(psf_path):
                try:
                    
                    
                    u = mda.Universe(psf_path, pdb_path)
                    protein = u.select_atoms("protein")
                    
                    if len(protein) == 0:
                        raise ValueError("No protein atoms found")
                    
                    # Use PSF charges directly
                    charges = protein.charges
                    positions = protein.positions
                    center_of_mass = protein.center_of_mass()
                    
                    # Calculate dipole vector
                    dipole_vector = np.sum(charges[:, np.newaxis] * (positions - center_of_mass), axis=0)
                    
                    # Store for compatibility with other methods
                    self.dipole_moment_vector = dipole_vector
                    
                except ImportError:
                    # MDAnalysis not available, fallback to BioPython method
                    charges, positions, center_of_mass = self._extract_charges_positions_from_file(pdb_path)
                    dipole_vector = np.sum(charges[:, np.newaxis] * (positions - center_of_mass), axis=0)
                    self.dipole_moment_vector = dipole_vector
                
            else:
                # Fallback to BioPython method
                charges, positions, center_of_mass = self._extract_charges_positions_from_file(pdb_path)
                dipole_vector = np.sum(charges[:, np.newaxis] * (positions - center_of_mass), axis=0)
                self.dipole_moment_vector = dipole_vector
            
            # Calculate magnitude
            magnitude = np.linalg.norm(dipole_vector)
            
            # Normalize the dipole vector
            normalized = dipole_vector / magnitude if magnitude > 0 else np.zeros(3)
            
            # Calculate angle with Z-axis
            z_axis = np.array([0, 0, 1])
            
            # Calculate the angle using dot product
            cos_angle = np.dot(normalized, z_axis)
            
            # Ensure cosine is in valid range [-1, 1] to avoid numerical errors
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            
            # Calculate angle in radians and convert to degrees
            angle_radians = np.arccos(cos_angle)
            angle_degrees = np.degrees(angle_radians)
            
            # Scale for visualization (20 Angstroms)
            visualization_end = center_of_mass + normalized * 20
            
            return {
                'vector': dipole_vector.tolist(),
                'magnitude': float(magnitude),
                'normalized': normalized.tolist(),
                'center_of_mass': center_of_mass.tolist(),
                'end_point': visualization_end.tolist(),
                'angle_with_z_axis': {
                    'degrees': float(angle_degrees),
                    'radians': float(angle_radians)
                },
                'method': 'PSF' if (psf_path and os.path.exists(psf_path)) else 'calculated'
            }
            
        except Exception:
            # propagate exception to caller
            raise

    def load_pdb_structure(self, pdb_path):
        """Load PDB structure using BioPython"""
        from Bio.PDB import PDBParser
        parser = PDBParser(QUIET=True)
        return parser.get_structure("protein", pdb_path)

    def _extract_charges_positions(self, structure):
        """Extract charges and positions from BioPython structure"""
        # Simplified charge assignment (you can improve this)
        amino_acid_charges = {
            'ARG': 1.0, 'LYS': 1.0, 'ASP': -1.0, 'GLU': -1.0,
            'HIS': 0.5  # pH dependent
        }
        
        charges = []
        positions = []
        
        for model in structure:
            for chain in model:
                for residue in chain:
                    if residue.get_resname() in amino_acid_charges:
                        charge = amino_acid_charges[residue.get_resname()]
                    else:
                        charge = 0.0
                    
                    try:
                        ca_atom = residue['CA']
                        charges.append(charge)
                        positions.append(ca_atom.get_coord())
                    except KeyError:
                        continue
        
        charges = np.array(charges)
        positions = np.array(positions)
        center_of_mass = np.mean(positions, axis=0)
        
        return charges, positions, center_of_mass
    
    def _extract_charges_positions_from_file(self, pdb_path):
        """Extract charges and positions from PDB file using BioPython"""
        try:
            from Bio.PDB import PDBParser
            from Bio.PDB.Polypeptide import is_aa
            
            parser = PDBParser(QUIET=True)
            structure = parser.get_structure("protein", pdb_path)
            
            # Enhanced charge assignment based on amino acid properties
            amino_acid_charges = {
                'ARG': 1.0,   # Arginine - positively charged
                'LYS': 1.0,   # Lysine - positively charged
                'ASP': -1.0,  # Aspartic acid - negatively charged
                'GLU': -1.0,  # Glutamic acid - negatively charged
                'HIS': 0.5,   # Histidine - partially charged (pH dependent)
                'CYS': 0.0,   # Cysteine - can form disulfide bonds
                'SER': 0.0,   # Serine - polar
                'THR': 0.0,   # Threonine - polar
                'ASN': 0.0,   # Asparagine - polar
                'GLN': 0.0,   # Glutamine - polar
                'TYR': 0.0,   # Tyrosine - polar
                'TRP': 0.0,   # Tryptophan - nonpolar
                'PHE': 0.0,   # Phenylalanine - nonpolar
                'ILE': 0.0,   # Isoleucine - nonpolar
                'LEU': 0.0,   # Leucine - nonpolar
                'VAL': 0.0,   # Valine - nonpolar
                'MET': 0.0,   # Methionine - nonpolar
                'ALA': 0.0,   # Alanine - nonpolar
                'GLY': 0.0,   # Glycine - nonpolar
                'PRO': 0.0    # Proline - nonpolar
            }
            
            charges = []
            positions = []
            
            for model in structure:
                for chain in model:
                    for residue in chain:
                        if is_aa(residue):
                            resname = residue.get_resname()
                            charge = amino_acid_charges.get(resname, 0.0)
                            
                            try:
                                ca_atom = residue['CA']
                                charges.append(charge)
                                positions.append(ca_atom.get_coord())
                            except KeyError:
                                # Skip residues without CA atom
                                continue
        
            if len(charges) == 0:
                raise ValueError("No valid residues found for dipole calculation")
            
            charges = np.array(charges)
            positions = np.array(positions)
            center_of_mass = np.mean(positions, axis=0)
            
            # processed residues and center_of_mass computed
            
            return charges, positions, center_of_mass
            
        except Exception:
            raise

    def identify_pharmacophore_residues(self, G, pharmacophore_pattern=None):
        """
        Identifica residuos que coinciden con patrón farmacofórico para toxinas Nav1.7
        """
        if not pharmacophore_pattern:
            return {}
        
        parts = pharmacophore_pattern.split('–')
        if len(parts) < 3:
            return {}
        
        target_residues = {}
        
        # Obtención de aminoácidos en orden de secuencia
        nodes = sorted(G.nodes())
        amino_acids = [G.nodes[n]['amino_acid'] for n in nodes]
        sequence = ''.join(amino_acids)
        
        # Para cada parte del farmacóforo, busca coincidencias
        for i, part in enumerate(parts):
            if len(part) > 0:
                for j in range(len(sequence) - len(part) + 1):
                    if sequence[j:j+len(part)] == part:
                        # Coincidencia encontrada, marca estos residuos
                        for k in range(len(part)):
                            residue_idx = nodes[j+k]
                            target_residues[residue_idx] = f"Parte farmacofórica {i+1}"
        
        return target_residues
    
    def identify_surface_residues(self, G, sasa_values, threshold=25):
        """
        Identifica residuos superficiales basados en valores SASA (crucial para interacción con Nav1.7)
        """
        surface_residues = {}
        for node in G.nodes():
            if node in sasa_values and sasa_values[node] > threshold:
                surface_residues[node] = sasa_values[node]
        return surface_residues
    
    def build_enhanced_graph(self, structure, cutoff_distance=8.0, pharmacophore_pattern=None):
        """Construye grafo mejorado con atributos detallados relevantes para interacciones con Nav1.7"""
        model = structure[0]
        G = nx.Graph()
        
        # Obtención de estructura secundaria y SASA si es posible
        ss_info, sasa_values = self.calculate_secondary_structure(structure)
        
        # Búsqueda de puentes disulfuro centralizada
        disulfide_bridges = find_disulfide_pairs(structure)
    # number of disulfide bridges computed
        
        # Cálculo de momento dipolar
        dipole = self.calculate_dipole_moment(structure)
        
        # Obtención de todos los átomos y átomos CA
        atoms = Selection.unfold_entities(model, 'A')
        ca_atoms = [atom for atom in atoms if atom.get_id() == 'CA' and is_aa(atom.get_parent(), standard=True)]
        
        # Adición de nodos con atributos mejorados
        for atom in ca_atoms:
            res = atom.get_parent()
            res_id = res.get_id()[1]  # Número de residuo
            resname = res.get_resname()  # Nombre de residuo 
            
            try:
                aa = seq1(resname)
            except:
                aa = 'X' 
            
            # Cálculo de propiedades fisicoquímicas
            hydrophobicity = HYDROPHOBICITY.get(aa, 0)
            charge = CHARGES.get(aa, 0)
            residue_type = classify_residue(aa)
            is_in_disulfide = any(res_id in bridge for bridge in disulfide_bridges)
            secondary_structure = ss_info.get(res_id, 'unknown')
            sasa = sasa_values.get(res_id, 0)
            
            # Adición de nodo con atributos comprensivos
            G.add_node(res_id, 
                      amino_acid=aa, 
                      name=resname,
                      pos=atom.get_coord(),  # Coordenadas 3D
                      pos_2d=(atom.get_coord()[0], atom.get_coord()[1]),  # Proyección 2D
                      hydrophobicity=hydrophobicity,
                      charge=charge,
                      residue_type=residue_type,
                      secondary_structure=secondary_structure,
                      is_in_disulfide=is_in_disulfide,
                      sasa=sasa)
        
        # Adición de aristas estándar basadas en distancia
        ns = NeighborSearch(ca_atoms)
        for atom in ca_atoms:
            res_id = atom.get_parent().id[1]
            neighbors = ns.search(atom.coord, cutoff_distance, level='A')
            for neighbor in neighbors:
                neighbor_res_id = neighbor.get_parent().id[1]
                if res_id != neighbor_res_id:
                    # Cálculo de distancia real para peso de arista
                    distance = np.linalg.norm(atom.coord - neighbor.coord)
                    G.add_edge(res_id, neighbor_res_id, 
                              weight=distance,
                              type='distance',
                              interaction_strength=1.0/distance)
        
        # Adición de enlaces peptídicos 
        residue_ids = sorted(G.nodes())
        for i in range(len(residue_ids)-1):
            if residue_ids[i+1] - residue_ids[i] == 1:  # residuos adyacentes
                G.add_edge(residue_ids[i], residue_ids[i+1], 
                          weight=1.0,
                          type='peptide',
                          interaction_strength=5.0)  
        
        # Adición de puentes disulfuro
        for res1, res2 in disulfide_bridges:
            if res1 in G.nodes() and res2 in G.nodes():
                G.add_edge(res1, res2, 
                          weight=1.0,
                          type='disulfide',
                          interaction_strength=10.0)  
        
        # Almacenamiento de atributos globales como atributos de grafo
        G.graph['dipole_vector'] = dipole['vector']
        G.graph['dipole_magnitude'] = dipole['magnitude'] 
        G.graph['disulfide_count'] = len(disulfide_bridges)
        
        # Identificación de residuos pharmacophore y superficiales
        pharmacophore_residues = self.identify_pharmacophore_residues(G, pharmacophore_pattern)
        surface_residues = self.identify_surface_residues(G, sasa_values)
        
        # Adición de atributos a nodos
        for node in G.nodes():
            G.nodes[node]['is_pharmacophore'] = node in pharmacophore_residues
            G.nodes[node]['is_surface'] = node in surface_residues
            G.nodes[node]['pharmacophore_part'] = pharmacophore_residues.get(node, "")
        
        return G
    
    def calculate_graph_metrics(self, G):
        """Calcula métricas de grafo centradas en características relevantes para Nav1.7"""
        # Usar el módulo común para evitar duplicación
        from src.infrastructure.graph.graph_metrics import compute_comprehensive_metrics
        
        result = compute_comprehensive_metrics(G)
        
        # Agregar métricas específicas del dominio si es necesario
        # (por ahora, el módulo común cubre todo)
        
        return result['properties']
    
    def detect_structural_motifs(self, G):
        """Detecta motivos estructurales comunes en toxinas que interactúan con Nav1.7"""
        motifs = {}
        
        # Búsqueda de horquillas beta 
        beta_strands = [n for n, attr in G.nodes(data=True) 
                      if attr.get('secondary_structure') == 'beta']
        
        if len(beta_strands) >= 4:
            #  horquilla beta
            motifs['beta_hairpin'] = True
            motifs['beta_strand_count'] = len(beta_strands)
        else:
            motifs['beta_hairpin'] = False
            motifs['beta_strand_count'] = len(beta_strands)
        
        # Detección de patrón de nudo de cistina
        disulfide_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_in_disulfide', False)]
        if G.graph.get('disulfide_count', 0) >= 3 and len(disulfide_nodes) >= 6:
            # Potencial nudo de cistina 
            motifs['cystine_knot'] = True
        else:
            motifs['cystine_knot'] = False
        
        # Búsqueda de parches cargados 
        positive_nodes = [n for n, attr in G.nodes(data=True) 
                        if attr.get('charge', 0) > 0 and attr.get('is_surface', False)]
        
        if len(positive_nodes) >= 3:
            # Comprobación si forman un cluster 
            pos = nx.get_node_attributes(G, 'pos')
            if pos:
                coordinates = np.array([pos[n] for n in positive_nodes])
                if len(coordinates) >= 2:
                    distances = pdist(coordinates)
                    if np.min(distances) < 10.0:  # Ångstroms
                        motifs['positive_patch'] = True
                    else:
                        motifs['positive_patch'] = False
                else:
                    motifs['positive_patch'] = False
            else:
                motifs['positive_patch'] = False
        else:
            motifs['positive_patch'] = False
            
        # Búsqueda de parches hidrofóbicos 
        hydrophobic_nodes = [n for n, attr in G.nodes(data=True) 
                           if attr.get('hydrophobicity', 0) > 1.0 and attr.get('is_surface', False)]
        
        if len(hydrophobic_nodes) >= 3:
            # Comprobación si forman un cluster
            pos = nx.get_node_attributes(G, 'pos')
            if pos:
                coordinates = np.array([pos[n] for n in hydrophobic_nodes])
                if len(coordinates) >= 2:
                    distances = pdist(coordinates)
                    if np.min(distances) < 10.0:  # Ångstroms
                        motifs['hydrophobic_patch'] = True
                    else:
                        motifs['hydrophobic_patch'] = False
                else:
                    motifs['hydrophobic_patch'] = False
            else:
                motifs['hydrophobic_patch'] = False
        else:
            motifs['hydrophobic_patch'] = False
            
        return motifs
    
    def analyze_single_toxin(self, pdb_filename, cutoff_distance=8.0, plot_3d=False, pharmacophore_pattern=None):
        """
        Análisis estructural de una toxina por archivo PDB, mostrando información simplificada
        relevante para la interacción con Nav1.7
        
        Args:
            pdb_filename (str): Nombre del archivo PDB a analizar (debe estar en pdb_folder)
            cutoff_distance (float): Distancia de corte para interacciones entre residuos
            plot_3d (bool): Si se debe usar visualización 3D (ignorado actualmente)
            pharmacophore_pattern (str): Patrón farmacofórico para resaltar residuos importantes
        """
        try:
            toxin_name = os.path.splitext(pdb_filename)[0]
            # analysis started for toxin
            
            # 1. Cargar estructura
            structure = self.load_pdb(pdb_filename)
            # structure loaded
            
            # 2. Extraer secuencia desde estructura
            ppb = PPBuilder()
            seq = None
            for pp in ppb.build_peptides(structure):
                seq = pp.get_sequence()
                # sequence extracted
                break
            
            # 3. Construcción del grafo
            # building molecular graph
            G = self.build_enhanced_graph(structure, cutoff_distance, pharmacophore_pattern)
            
            # 4. Cálculo de métricas usando el módulo común
            from src.infrastructure.graph.graph_metrics import compute_comprehensive_metrics
            metrics_result = compute_comprehensive_metrics(G)
            metrics = metrics_result['properties']
            
            # Extraer centralidades para compatibilidad
            centrality = metrics_result['summary_statistics']
            top_5 = metrics_result['top_5_residues']
            
            degree_centrality = metrics_result['centrality']['degree'] if 'centrality' in metrics_result else {}
            betweenness_centrality = metrics_result['centrality']['betweenness'] if 'centrality' in metrics_result else {}
            closeness_centrality = metrics_result['centrality']['closeness'] if 'centrality' in metrics_result else {}
            clustering_coefficient = metrics_result['centrality']['clustering'] if 'centrality' in metrics_result else {}

            # Encontrar todos los residuos con el valor máximo para cada métrica (legacy)
            def find_all_max_residues(metric_dict):
                if not metric_dict:
                    return []
                max_value = max(metric_dict.values())
                return [res for res, value in metric_dict.items() if abs(value - max_value) < 0.0001]
            
            degree_centrality_more = find_all_max_residues(degree_centrality)
            betweenness_centrality_more = find_all_max_residues(betweenness_centrality)
            closeness_centrality_more = find_all_max_residues(closeness_centrality)
            clustering_coefficient_more = find_all_max_residues(clustering_coefficient)
            
            # 5. Detección de motivos estructurales
            motifs = self.detect_structural_motifs(G)
            
            # 6. Mostrar resultados 
            # results computed
            
            # 7. Mostrar motivos estructurales completos
            # motifs computed
            
            # 8. Visualización del grafo 
            title = f"Toxina Nav1.7: {toxin_name} (corte={cutoff_distance}Å)"
            # analysis completed successfully

            return {
                'toxin': toxin_name,
                'pharmacophore': pharmacophore_pattern,
                'sequence': str(seq) if seq else "",
                'motifs': motifs,
                'properties': metrics,  # Para compatibilidad
                'summary_statistics': centrality,  # Nuevo formato para JS
                'top_5_residues': top_5,  # Nuevo formato para JS
                'graph_properties': {
                    'nodes': metrics['num_nodes'],
                    'edges': metrics['num_edges'],
                    'disulfide_bridges': metrics['disulfide_count'],
                    'density': metrics['density'],
                    'clustering_coefficient_avg': metrics['avg_clustering']
                },
                'centrality_measures': {
                    'degree_centrality': degree_centrality,
                    'betweenness_centrality': betweenness_centrality,
                    'closeness_centrality': closeness_centrality,
                    'clustering_coefficient': clustering_coefficient,
                    'degree_centrality_more': degree_centrality_more,
                    'betweenness_centrality_more': betweenness_centrality_more,
                    'closeness_centrality_more': closeness_centrality_more,
                    'clustering_coefficient_more': clustering_coefficient_more
                },
                'graph': G
            }
            
        except Exception:
            # Let caller handle exceptions; return None to indicate failure
            return None
