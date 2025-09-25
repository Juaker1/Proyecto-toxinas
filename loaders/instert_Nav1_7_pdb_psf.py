import os
import sqlite3
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class PDBAndPSFInserter:
    def __init__(self, db_path: str = "database/toxins.db", pdb_folder: str = "pdbs/", psf_folder: str = "psfs/"):
        self.db_path = db_path
        self.pdb_folder = pdb_folder
        self.psf_folder = psf_folder
        os.makedirs(self.pdb_folder, exist_ok=True)
        os.makedirs(self.psf_folder, exist_ok=True)

    def _connect_db(self):
        return sqlite3.connect(self.db_path)

    def fetch_peptides(self):
        """Obtiene peptide_code desde Nav1_7_InhibitorPeptides."""
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT peptide_code FROM Nav1_7_InhibitorPeptides")
        peptides = [row[0] for row in cursor.fetchall()]
        conn.close()
        return peptides

    def read_file_as_blob(self, folder: str, filename: str, extension: str) -> bytes:
        """Lee un archivo y lo devuelve como bytes, o None si no existe."""
        path = os.path.join(folder, f"{filename}{extension}")
        if not os.path.isfile(path):
            print(f"  [!] No se encontró {extension.upper()} para {filename}: {path}")
            return None
        with open(path, "rb") as f:
            return f.read()

    def update_blobs_in_database(self, peptide_code: str, pdb_blob: bytes, psf_blob: bytes):
        """Actualiza los campos pdb_blob y psf_blob para un peptide_code."""
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Nav1_7_InhibitorPeptides
            SET pdb_blob = ?, psf_blob = ?
            WHERE peptide_code = ?
        """, (pdb_blob, psf_blob, peptide_code))
        conn.commit()
        conn.close()

    def process_all_peptides(self):
        peptides = self.fetch_peptides()
        print(f"[•] Procesando {len(peptides)} péptidos...")

        for peptide_code in peptides:
            try:
                print(f"→ Procesando {peptide_code}...")
                pdb_blob = self.read_file_as_blob(self.pdb_folder, peptide_code, ".pdb")
                psf_blob = self.read_file_as_blob(self.psf_folder, peptide_code, ".psf")

                if pdb_blob or psf_blob:
                    self.update_blobs_in_database(peptide_code, pdb_blob, psf_blob)
                    print(f"  [✓] {peptide_code} actualizado en la base de datos.")
                else:
                    print(f"  [!] Sin archivos encontrados para {peptide_code}, no se actualizó.")

            except Exception as e:
                print(f"  [!] Error en {peptide_code}: {str(e)}")


if __name__ == "__main__":
    inserter = PDBAndPSFInserter(db_path="database/toxins.db", pdb_folder="pdbs/", psf_folder="psfs/")
    inserter.process_all_peptides()
