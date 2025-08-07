import os
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from Bio import PDB
from Bio.PDB import NeighborSearch, Selection, DSSP
from Bio.PDB.Polypeptide import is_aa, PPBuilder
from Bio.SeqUtils import seq3, seq1
from Bio.SeqUtils.ProtParam import ProteinAnalysis
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.colors import to_rgb
import pandas as pd
import seaborn as sns
from scipy.spatial.distance import pdist, squareform

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
        except Exception as e:
            print(f"Advertencia: No se pudo calcular estructura secundaria: {e}")
            return {}, {}
    
    def find_disulfide_bridges(self, structure):
        """Identifica puentes disulfuro entre cisteínas (críticos para estructura de toxinas Nav1.7)"""
        cys_sg_atoms = []
        for model in structure:
            for chain in model:
                for residue in chain:
                    if residue.get_resname() == "CYS":
                        for atom in residue:
                            if atom.get_name() == "SG":
                                cys_sg_atoms.append((residue.get_id()[1], atom))
        
        # Búsqueda de pares de átomos SG dentro de distancia de enlace
        disulfide_bridges = []
        ss_bond_max_distance = 2.2  # Angstroms - distancia típica en toxinas ICK
        
        for i, (res_i, atom_i) in enumerate(cys_sg_atoms):
            for j, (res_j, atom_j) in enumerate(cys_sg_atoms):
                if i < j:  # evita duplicados
                    distance = atom_i - atom_j
                    if distance < ss_bond_max_distance:
                        disulfide_bridges.append((res_i, res_j))
        
        return disulfide_bridges
    
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
                    import MDAnalysis as mda
                    
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
                    print("MDAnalysis not available, using BioPython fallback")
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
            
        except Exception as e:
            print(f"Error in dipole calculation: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e

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
            
            print(f"Processed {len(charges)} residues for dipole calculation")
            print(f"Total charge: {np.sum(charges):.1f}")
            print(f"Center of mass: [{center_of_mass[0]:.2f}, {center_of_mass[1]:.2f}, {center_of_mass[2]:.2f}]")
            
            return charges, positions, center_of_mass
            
        except Exception as e:
            print(f"Error extracting charges and positions: {str(e)}")
            raise e

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
        
        # Búsqueda de puentes disulfuro 
        disulfide_bridges = self.find_disulfide_bridges(structure)
        print(f"Encontrados {len(disulfide_bridges)} puentes disulfuro")
        
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
        if len(G) == 0:
            return {"error": "Grafo vacío"}
            
        metrics = {
            'num_nodes': G.number_of_nodes(),
            'num_edges': G.number_of_edges(),
            'avg_degree': round(sum(dict(G.degree()).values()) / len(G), 2),
            'density': round(nx.density(G), 4),
            'clustering_coefficient': round(nx.average_clustering(G), 4),
            'disulfide_count': G.graph.get('disulfide_count', 0),
            'dipole_magnitude': round(G.graph.get('dipole_magnitude', 0), 2),
        }
        
        # Cálculo de métricas de centralidad 
        degree_centrality = nx.degree_centrality(G)
        betweenness_centrality = nx.betweenness_centrality(G)
        closeness_centrality = nx.closeness_centrality(G)
        eigenvector_centrality = nx.eigenvector_centrality_numpy(G)
        
        # Valores promedio de centralidad
        metrics['avg_degree_centrality'] = round(sum(degree_centrality.values()) / len(degree_centrality), 4)
        metrics['avg_betweenness_centrality'] = round(sum(betweenness_centrality.values()) / len(betweenness_centrality), 4)
        metrics['avg_closeness_centrality'] = round(sum(closeness_centrality.values()) / len(closeness_centrality), 4)
        metrics['avg_eigenvector_centrality'] = round(sum(eigenvector_centrality.values()) / len(eigenvector_centrality), 4)
        
        # Almacenamiento de centralidad para cada nodo
        nx.set_node_attributes(G, degree_centrality, 'degree_centrality')
        nx.set_node_attributes(G, betweenness_centrality, 'betweenness_centrality')
        nx.set_node_attributes(G, closeness_centrality, 'closeness_centrality')
        nx.set_node_attributes(G, eigenvector_centrality, 'eigenvector_centrality')
        
        # Cálculo de estadísticas de distribución de carga
        charges = [G.nodes[n]['charge'] for n in G.nodes()]
        metrics['total_charge'] = sum(charges)
        metrics['charge_std_dev'] = np.std(charges)
        
        # Cálculo de distribución de hidrofobicidad
        hydrophobicity = [G.nodes[n]['hydrophobicity'] for n in G.nodes()]
        metrics['avg_hydrophobicity'] = round(np.mean(hydrophobicity), 2)
        metrics['hydrophobicity_std_dev'] = round(np.std(hydrophobicity), 2)
        
        # Cálculo de características superficiales
        surface_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_surface', False)]
        if surface_nodes:
            surface_charges = [G.nodes[n]['charge'] for n in surface_nodes]
            surface_hydrophobicity = [G.nodes[n]['hydrophobicity'] for n in surface_nodes]
            
            metrics['surface_charge'] = sum(surface_charges)
            metrics['surface_hydrophobicity'] = round(np.mean(surface_hydrophobicity), 2)
            metrics['surface_to_total_ratio'] = round(len(surface_nodes) / len(G.nodes()), 2)
        
        # Conteo de residuos pharmacophore
        pharm_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_pharmacophore', False)]
        metrics['pharmacophore_count'] = len(pharm_nodes)
        
        try:
            communities = nx.algorithms.community.greedy_modularity_communities(G)
            metrics['community_count'] = len(communities)
            metrics['modularity'] = nx.algorithms.community.modularity(G, communities)
        except:
            metrics['community_count'] = 0
            metrics['modularity'] = 0
        
        return metrics
    
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
    
    def visualize_enhanced_graph(self, G, title="Grafo de Toxina Nav1.7", plot_3d=False, show_labels=True, highlight_pharmacophore=True):
        """Visualización avanzada del grafo de toxina con características relevantes para Nav1.7"""

        fig, ax = plt.subplots(figsize=(14, 12))
        
        # Obtención de posiciones 
        pos = nx.get_node_attributes(G, 'pos')
        pos_2d = {}
        for node, coord in pos.items():
            pos_2d[node] = (coord[0], coord[1])  
        
        # Obtención de atributos de nodos
        residue_types = nx.get_node_attributes(G, 'residue_type')
        is_disulfide = nx.get_node_attributes(G, 'is_in_disulfide')
        is_surface = nx.get_node_attributes(G, 'is_surface')
        is_pharmacophore = nx.get_node_attributes(G, 'is_pharmacophore')
        centrality = nx.get_node_attributes(G, 'betweenness_centrality')
        
        # Determinación de colores y tamaños de nodos
        node_colors = []
        node_sizes = []
        for node in G.nodes():
            # Color base según tipo de residuo
            res_type = residue_types.get(node, 'other')
            color = RESIDUE_COLORS.get(res_type, RESIDUE_COLORS['other'])
            
            # Modificación de color para residuos especiales
            if highlight_pharmacophore and is_pharmacophore.get(node, False):
                color = 'yellow'
            
            node_colors.append(color)
            
            # Tamaño basado en centralidad y exposición superficial
            base_size = centrality.get(node, 0) * 2000 + 100
            if is_surface.get(node, False):
                base_size *= 1.3
            
            node_sizes.append(base_size)
        
        # Creación de listas de aristas para diferentes tipos
        peptide_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('type') == 'peptide']
        disulfide_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('type') == 'disulfide']
        distance_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('type') == 'distance']
        
        # Dibujo de nodos
        nodes = nx.draw_networkx_nodes(G, pos_2d, 
                                     node_size=node_sizes, 
                                     node_color=node_colors, 
                                     alpha=0.8, 
                                     edgecolors='black',
                                     ax=ax)
        
        # Dibujo de diferentes tipos de aristas
        nx.draw_networkx_edges(G, pos_2d, edgelist=peptide_edges, 
                              width=2, edge_color='black', alpha=0.7, ax=ax)
        nx.draw_networkx_edges(G, pos_2d, edgelist=disulfide_edges, 
                              width=2.5, edge_color='gold', alpha=1.0, ax=ax)
        nx.draw_networkx_edges(G, pos_2d, edgelist=distance_edges, 
                              width=0.5, edge_color='gray', alpha=0.3, ax=ax)
        
        
        if show_labels:
            # Creación de etiquetas personalizadas
            labels = {}
            for node in G.nodes():
                
                pharm_tag = "♦" if is_pharmacophore.get(node, False) else ""
                surf_tag = "◯" if is_surface.get(node, False) else ""
                ss = G.nodes[node].get('secondary_structure', '')
                ss_tag = ""
                if ss == 'helix':
                    ss_tag = "α"
                elif ss == 'beta':
                    ss_tag = "β"
                    
                labels[node] = f"{node}:{G.nodes[node]['amino_acid']}{pharm_tag}{surf_tag}{ss_tag}"
            
            nx.draw_networkx_labels(G, pos_2d, labels=labels, font_size=8, font_color='black', ax=ax)
        
    
        # Creación de leyenda para tipos de residuos
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=RESIDUE_COLORS['hydrophobic'], 
                      markersize=10, label='Hidrofóbico (A,V,I,L,M,F,Y,W) - Interacción con membrana'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=RESIDUE_COLORS['polar'], 
                      markersize=10, label='Polar (S,T,N,Q) - Estabilidad estructural'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=RESIDUE_COLORS['positive'], 
                      markersize=10, label='Positivo (K,R,H) - Crítico para interacción con VSD'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=RESIDUE_COLORS['negative'], 
                      markersize=10, label='Negativo (D,E) - Interacciones electrostáticas'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=RESIDUE_COLORS['cysteine'], 
                      markersize=10, label='Cisteína (C) - Puentes disulfuro'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=RESIDUE_COLORS['other'], 
                      markersize=10, label='Otros residuos (G,P)')
        ]
        
        # Adición de tipos especiales a leyenda
        if highlight_pharmacophore:
            legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                                           markerfacecolor='yellow', markersize=10, 
                                           label='Farmacóforo  - Residuo esencial para actividad'))
        
        # Explicación del tamaño de nodos
        legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='white',
                                        markeredgecolor='black', markersize=15, 
                                        label='Tamaño: Centralidad de intermediación - Importancia estructural'))
        
        # explicaciones
        legend_elements.extend([
            plt.Line2D([0], [0], color='black', lw=2, label='Enlace peptídico - Cadena principal'),
            plt.Line2D([0], [0], color='gold', lw=2.5, label='Puente disulfuro - Estabilidad estructural'),
            plt.Line2D([0], [0], color='gray', lw=0.5, label='Proximidad espacial (< 8Å) - Interacciones')
        ])
        
       
        legend_elements.append(plt.Line2D([0], [0], marker='', color='w', 
                                        label='Etiqueta: #:AAα/β (#: posición, AA: aminoácido)'))
        legend_elements.append(plt.Line2D([0], [0], marker='', color='w', 
                                        label='♦: Farmacóforo, ◯: Superficie, α/β: Estructura secundaria'))
        
        
        ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1, 0.5),
                 title="GUÍA DE LECTURA DEL GRAFO", title_fontsize=12)
        
        # Título con información sobre la toxina
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.axis('off')
        
        # Añadir información sobre el dipolo si está disponible
        if 'dipole_magnitude' in G.graph and G.graph['dipole_magnitude'] > 0:
            magnitude = G.graph['dipole_magnitude']
            ax.text(0.02, 0.02, f"Momento dipolar: {magnitude:.1f} D", 
                   transform=ax.transAxes, fontsize=10, bbox=dict(facecolor='white', alpha=0.7))
        
        plt.tight_layout()
        plt.show()
    
    def visualize_centrality_metrics(self, result):
        """Visualize centrality metrics in a more structured and readable format."""
        if not result:
            print("No results to visualize")
            return
            
        # Extract metrics
        degree_cent = result['centrality_measures']['degree_centrality']
        betweenness_cent = result['centrality_measures']['betweenness_centrality']
        closeness_cent = result['centrality_measures']['closeness_centrality']
        clustering_coeff = result['centrality_measures']['clustering_coefficient']
        
        # Create pandas DataFrame for better display
    
        # Función para formatear residuos top como string
        def format_top_residues(residues_list, metric_dict):
            if not residues_list:
                return "None"
            max_value = max(metric_dict.values())
            return f"{', '.join(map(str, residues_list))} ({max_value:.4f})"
        
        # Summary statistics
        print("\n=== SUMMARY STATISTICS ===")
        metrics_summary = {
            'Metric': ['Degree Centrality', 'Betweenness Centrality', 
                      'Closeness Centrality', 'Clustering Coefficient'],
            'Min': [min(degree_cent.values()), min(betweenness_cent.values()), 
                   min(closeness_cent.values()), min(clustering_coeff.values())],
            'Max': [max(degree_cent.values()), max(betweenness_cent.values()), 
                   max(closeness_cent.values()), max(clustering_coeff.values())],
            'Mean': [sum(degree_cent.values())/len(degree_cent), 
                    sum(betweenness_cent.values())/len(betweenness_cent),
                    sum(closeness_cent.values())/len(closeness_cent),
                    sum(clustering_coeff.values())/len(clustering_coeff)],
            'Top Residues': [
                format_top_residues(result['centrality_measures']['degree_centrality_more'], degree_cent),
                format_top_residues(result['centrality_measures']['betweenness_centrality_more'], betweenness_cent),
                format_top_residues(result['centrality_measures']['closeness_centrality_more'], closeness_cent),
                format_top_residues(result['centrality_measures']['clustering_coefficient_more'], clustering_coeff)
            ]
        }
        
        df_summary = pd.DataFrame(metrics_summary)
        print(df_summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        
        # Top 5 residues for each metric
        print("\n=== TOP 5 RESIDUES BY METRIC ===")
        
        # Function to get top N residues
        def get_top_n(metric_dict, n=5):
            return sorted(metric_dict.items(), key=lambda x: x[1], reverse=True)[:n]
        
        # Create DataFrame for top residues
        top_degree = get_top_n(degree_cent)
        top_betweenness = get_top_n(betweenness_cent)
        top_closeness = get_top_n(closeness_cent)
        top_clustering = get_top_n(clustering_coeff)
        
        df_top = pd.DataFrame({
            'Degree Centrality': [f"Res {r} ({v:.4f})" for r, v in top_degree],
            'Betweenness Centrality': [f"Res {r} ({v:.4f})" for r, v in top_betweenness],
            'Closeness Centrality': [f"Res {r} ({v:.4f})" for r, v in top_closeness],
            'Clustering Coefficient': [f"Res {r} ({v:.4f})" for r, v in top_clustering]
        })
        
        print(df_top.to_string(index=False))
        
        # Graph properties summary
        print("\n=== GRAPH PROPERTIES ===")
        print(f"Number of Nodes: {result['graph_properties']['nodes']}")
        print(f"Number of Edges: {result['graph_properties']['edges']}")
        print(f"Density: {result['graph_properties']['density']:.4f}")
        print(f"Average Clustering Coefficient: {result['graph_properties']['clustering_coefficient_avg']:.4f}")
        print(f"Disulfide Bridges: {result['graph_properties']['disulfide_bridges']}")
        
        # Visualization using matplotlib (optional)
        try:
            self.plot_centrality_metrics(result)
        except Exception as e:
            print(f"Could not generate plots: {e}")
    
    def plot_centrality_metrics(self, result):
        """Generate visual plots for centrality metrics."""
        import matplotlib.pyplot as plt
        import numpy as np
        import seaborn as sns
        
        # Extract metrics
        degree_cent = result['centrality_measures']['degree_centrality']
        betweenness_cent = result['centrality_measures']['betweenness_centrality']
        closeness_cent = result['centrality_measures']['closeness_centrality']
        clustering_coeff = result['centrality_measures']['clustering_coefficient']
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f"Centrality Metrics for {result['toxin']}", fontsize=16)
        
        # Sort residues for consistent ordering
        sorted_residues = sorted(degree_cent.keys())
        
        # Degree Centrality
        ax1 = axes[0, 0]
        values = [degree_cent[r] for r in sorted_residues]
        ax1.bar(sorted_residues, values, color='skyblue')
        ax1.set_title('Degree Centrality')
        ax1.set_xlabel('Residue')
        ax1.set_xticks(sorted_residues[::3])  # Show every 3rd residue for readability
        
        # Betweenness Centrality
        ax2 = axes[0, 1]
        values = [betweenness_cent[r] for r in sorted_residues]
        ax2.bar(sorted_residues, values, color='lightgreen')
        ax2.set_title('Betweenness Centrality')
        ax2.set_xlabel('Residue')
        ax2.set_xticks(sorted_residues[::3])
        
        # Closeness Centrality
        ax3 = axes[1, 0]
        values = [closeness_cent[r] for r in sorted_residues]
        ax3.bar(sorted_residues, values, color='salmon')
        ax3.set_title('Closeness Centrality')
        ax3.set_xlabel('Residue')
        ax3.set_xticks(sorted_residues[::3])
        
        # Clustering Coefficient
        ax4 = axes[1, 1]
        values = [clustering_coeff[r] for r in sorted_residues]
        ax4.bar(sorted_residues, values, color='plum')
        ax4.set_title('Clustering Coefficient')
        ax4.set_xlabel('Residue')
        ax4.set_xticks(sorted_residues[::3])
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        plt.show()
        
        # Heatmap of all metrics
        print("\nGenerating heatmap of centrality metrics...")
        plt.figure(figsize=(12, 8))
        
        # Prepare data for heatmap
        metrics_data = np.array([
            [degree_cent[r] for r in sorted_residues],
            [betweenness_cent[r] for r in sorted_residues],
            [closeness_cent[r] for r in sorted_residues],
            [clustering_coeff[r] for r in sorted_residues]
        ])
        
        # Create heatmap
        sns.heatmap(metrics_data, cmap='viridis', 
                   xticklabels=sorted_residues,
                   yticklabels=['Degree', 'Betweenness', 'Closeness', 'Clustering'],
                   annot=False)
        plt.title(f"Centrality Metrics Heatmap for {result['toxin']}")
        plt.tight_layout()
        plt.show()
    
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
            print(f"=== Análisis de toxina {toxin_name} ===")
            
            # 1. Cargar estructura
            structure = self.load_pdb(pdb_filename)
            print(f"• Estructura cargada desde archivo: {pdb_filename}")
            
            # 2. Extraer secuencia desde estructura
            ppb = PPBuilder()
            seq = None
            for pp in ppb.build_peptides(structure):
                seq = pp.get_sequence()
                print(f"• Secuencia (estructura): {seq}")
                break
            
            # 3. Construcción del grafo
            print(f"\n» Generando grafo molecular (distancia corte: {cutoff_distance}Å)...")
            G = self.build_enhanced_graph(structure, cutoff_distance, pharmacophore_pattern)
            
            # 4. Cálculo de métricas 
            metrics = self.calculate_graph_metrics(G)
            
            degree_centrality = nx.degree_centrality(G)
            betweenness_centrality = nx.betweenness_centrality(G)
            closeness_centrality = nx.closeness_centrality(G)
            clustering_coefficient = nx.clustering(G)  # Por nodo

            # Encontrar todos los residuos con el valor máximo para cada métrica
            def find_all_max_residues(metric_dict):
                max_value = max(metric_dict.values())
                return [res for res, value in metric_dict.items() if abs(value - max_value) < 0.0001]
            
            degree_centrality_more = find_all_max_residues(degree_centrality)
            betweenness_centrality_more = find_all_max_residues(betweenness_centrality)
            closeness_centrality_more = find_all_max_residues(closeness_centrality)
            clustering_coefficient_more = find_all_max_residues(clustering_coefficient)
            
            # 5. Detección de motivos estructurales
            motifs = self.detect_structural_motifs(G)
            
            # 6. Mostrar resultados 
            print("\n=== RESULTADOS DEL ANÁLISIS ===")
            print(f"• Toxina analizada: {toxin_name}")
            print(f"• Información estructural básica:")
            print(f"  - Número de residuos (nodos): {metrics['num_nodes']}")
            print(f"  - Número de interacciones (aristas): {metrics['num_edges']}")
            print(f"  - Puentes disulfuro: {metrics['disulfide_count']}")
            
            # 7. Mostrar motivos estructurales completos
            print("\n• Motivos estructurales identificados:")
            for motif, present in motifs.items():
                status = "✓ PRESENTE" if present else "✗ AUSENTE"
                
                # Mostrar información adicional para cada motivo
                if motif == 'beta_hairpin':
                    detail = f" ({motifs.get('beta_strand_count', 0)} hebras beta)" if present else ""
                    print(f"  - Horquilla beta: {status}{detail}")
                elif motif == 'cystine_knot':
                    print(f"  - Nudo de cistina: {status}")
                elif motif == 'positive_patch':
                    print(f"  - Parche de residuos cargados positivamente: {status}")
                elif motif == 'hydrophobic_patch':
                    print(f"  - Parche hidrofóbico superficial: {status}")
            
            # 8. Visualización del grafo 
            title = f"Toxina Nav1.7: {toxin_name} (corte={cutoff_distance}Å)"
            print("\n» Generando visualización 2D del grafo...")
            self.visualize_enhanced_graph(G, title=title, plot_3d=plot_3d, highlight_pharmacophore=True)

            return {
                'toxin': toxin_name,
                'pharmacophore': pharmacophore_pattern,
                'sequence': str(seq) if seq else "",
                'motifs': motifs,

                'graph_properties': {
                    'nodes': metrics['num_nodes'],
                    'edges': metrics['num_edges'],
                    'disulfide_bridges': metrics['disulfide_count'],
                    'density': nx.density(G),
                    'clustering_coefficient_avg': nx.average_clustering(G)
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
            
        except Exception as e:
            print(f"ERROR ANALIZANDO {pdb_filename}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None


'''if __name__ == "__main__":
    analyzer = Nav17ToxinGraphAnalyzer(pdb_folder="pdbs/")
    
    # Selecciona una toxina para analizar (debe ser un archivo PDB en la carpeta pdbs/)
    toxin_file = "bTRTXCd1a.pdb"
    

    
    result = analyzer.analyze_single_toxin(toxin_file, cutoff_distance=6.0, plot_3d=True)
    
    if result:
        print("\n--- MÉTRICAS DE CENTRALIDAD Y GRAFO ---")
        print(f"Density: {result['graph_properties']['density']:.4f}")
        
        # Función para formatear la lista de residuos como string
        def format_residues(residues_list, metric_dict):
            max_value = max(metric_dict.values())
            return f"{', '.join(map(str, residues_list))} (valor: {max_value:.4f})"
        
        print("\nResiduos con mayor centralidad de grado:", 
              format_residues(result['centrality_measures']['degree_centrality_more'], 
                             result['centrality_measures']['degree_centrality']))
        
        print("Residuos con mayor centralidad de intermediación:", 
              format_residues(result['centrality_measures']['betweenness_centrality_more'], 
                             result['centrality_measures']['betweenness_centrality']))
        
        print("Residuos con mayor centralidad de cercanía:", 
              format_residues(result['centrality_measures']['closeness_centrality_more'], 
                             result['centrality_measures']['closeness_centrality']))
        
        print("Residuos con mayor coeficiente de agrupamiento:", 
              format_residues(result['centrality_measures']['clustering_coefficient_more'], 
                             result['centrality_measures']['clustering_coefficient']))

print("\nRecuerda: Puedes analizar cualquier toxina cambiando el valor de toxin_file")
        
    # Visualizar métricas de centralidad en formato detallado
if result:
    analyzer.visualize_centrality_metrics(result)'''