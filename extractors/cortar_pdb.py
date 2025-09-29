import MDAnalysis as mda
from MDAnalysis.coordinates.PDB import PDBWriter
from Bio.PDB import PDBParser, PPBuilder
import numpy as np

class PDBHandler:
    """
    Clase para manejar operaciones relacionadas con archivos PDB.
    """

    @staticmethod
    def extract_primary_sequence(pdb_file):
        """
        Obtiene la secuencia primaria de aminoácidos de un archivo PDB.

        Args:
            pdb_file (str): Ruta al archivo PDB.

        Returns:
            str: Secuencia primaria de aminoácidos como una cadena.
        """
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure('protein', pdb_file)
        ppb = PPBuilder()
        sequence = "".join([str(pp.get_sequence()) for pp in ppb.build_peptides(structure)])

        if not sequence:
            raise ValueError("No se encontró una cadena de proteínas en el archivo PDB.")

        return sequence

    @staticmethod
    def cut_pdb_by_residue_indices(input_pdb, output_pdb, start_residue, end_residue):
        """
        Recorta un archivo PDB para incluir únicamente los residuos dentro del rango especificado.

        Args:
            input_pdb (str): Ruta del archivo PDB de entrada.
            output_pdb (str): Ruta del archivo PDB de salida.
            start_residue (int): Índice inicial del residuo.
            end_residue (int): Índice final del residuo.
        """
        u = mda.Universe(input_pdb)
        selection = u.select_atoms(f"resid {start_residue}:{end_residue}")

        if selection.n_atoms == 0:
            raise ValueError(f"No se encontraron residuos en el rango {start_residue}-{end_residue}.")

        with PDBWriter(output_pdb) as writer:
            writer.write(selection)


class VSDAnalyzer:
    """
    Clase para analizar la orientación de hélices de dominio VSD en un archivo PDB.
    """

    def __init__(self, pdb_file):
        """
        Inicializa el analizador de VSD con el archivo PDB.

        Args:
            pdb_file (str): Ruta al archivo PDB de entrada.
        """
        self.u = mda.Universe(pdb_file)
        self.protein = self.u.select_atoms("protein")
        self.center_of_mass = self.protein.center_of_mass()

    def analyze_helices_orientation(self, helices_residues, output_pdb, vmd_output, cutoff=5.0):
        """
        Analiza la orientación de las hélices en relación con el eje Z.

        Args:
            helices_residues (dict): Diccionario con las hélices y sus residuos (inicio, fin).
            output_pdb (str): Ruta para guardar el archivo PDB con las marcas de orientación.
            vmd_output (str): Ruta para guardar el archivo VMD para visualización.
            cutoff (float): Distancia umbral para clasificar residuos orientados hacia el interior.

        Returns:
            list: Lista de residuos orientados hacia el interior.
        """
        z_axis = np.array([self.center_of_mass[0], self.center_of_mass[1], 1e3])
        z_direction = z_axis - self.center_of_mass
        z_direction /= np.linalg.norm(z_direction)

        residues_to_center = []

        for helix, (start, end) in helices_residues.items():
            helix_residues = self.protein.select_atoms(f"resid {start}:{end}").residues

            for res in helix_residues:
                res_center = res.atoms.center_of_mass()
                vector_to_center = self.center_of_mass - res_center
                projection = np.dot(vector_to_center, z_direction)
                normal_vector = vector_to_center - projection * z_direction
                normal_distance = np.linalg.norm(normal_vector)

                if normal_distance < cutoff:
                    residues_to_center.append(res)
                    res.atoms.tempfactors = 1.0
                else:
                    res.atoms.tempfactors = 0.0

        self.protein.write(output_pdb)
        self._generate_vmd_file(vmd_output, z_axis)

        return residues_to_center

    def _generate_vmd_file(self, vmd_output, z_axis):
        """
        Genera un archivo de visualización para VMD con el eje Z y el centro de masa.

        Args:
            vmd_output (str): Ruta del archivo VMD de salida.
            z_axis (np.ndarray): Coordenadas del eje Z.
        """
        with open(vmd_output, 'w') as vmd_file:
            vmd_file.write("display projection orthographic\n")
            vmd_file.write("axes location off\n")
            vmd_file.write("color Display Background white\n")

            vmd_file.write(f"graphics 0 color red\n")
            vmd_file.write(f"graphics 0 line {{{self.center_of_mass[0]} {self.center_of_mass[1]} {self.center_of_mass[2]}}} \
                                {{{z_axis[0]} {z_axis[1]} {z_axis[2]}}} 2.0\n")
            vmd_file.write(f"graphics 0 color blue\n")
            vmd_file.write(f"graphics 0 sphere {{{self.center_of_mass[0]} {self.center_of_mass[1]} {self.center_of_mass[2]}}} radius 1.0\n")
"""
# Ejemplo de uso
if __name__ == "__main__":
    # Ejemplo de extracción de secuencia primaria
    input_pdb = "FoldSeek/vsd_water_bk_test.pdb"
    sequence = PDBHandler.extract_primary_sequence(input_pdb)
    print(f"Secuencia primaria de aminoácidos:\n{sequence}")

    # Ejemplo de recorte de PDB
    input_pdb = "FoldSeek/AF-Q54SN2-F1-model_v4.pdb"
    output_pdb = "FoldSeek/output_cut2.pdb"
    PDBHandler.cut_pdb_by_residue_indices(input_pdb, output_pdb, 37, 182)

    # Ejemplo de análisis de orientación de hélices
    helices_residues = {
        "S1": (110, 129),
        "S2": (148, 170),
        "S3": (181, 199),
        "S4": (207, 223)
    }
    vsd_analyzer = VSDAnalyzer(input_pdb="FoldSeek/vsd_water_bk_test.pdb")
    residues_oriented_inward = vsd_analyzer.analyze_helices_orientation(
        helices_residues, "vsd_marked_helices.pdb", "vsd_visualization.vmd", cutoff=5.0
    )

    for res in residues_oriented_inward:
        print(f"Hélice: {res.segid}, Residuo: {res.resname} {res.resid}")
"""