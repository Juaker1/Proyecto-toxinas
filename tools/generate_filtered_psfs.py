#!/usr/bin/env python3
"""
Genera PSF/PDB para los péptidos filtrados (tabla Peptides) y guarda los archivos
en tools/filtered nombrados por accession_number. Captura logs por péptido y
reintenta los fallidos al final mostrando el tail del log para depurar.
"""
import os
import sys
import sqlite3
import tempfile
import subprocess
from pathlib import Path

# Rutas base
root_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(root_dir))

# Import filtro de toxinas
try:
    from extractors.toxins_filter import search_toxins
except Exception as e:
    print(f"ERROR importando search_toxins: {e}")
    sys.exit(1)

# Fallback para crear PDB temporal desde texto/bytes
def create_temp_pdb_file(content: str) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".pdb", prefix="peptide_", text=True)
    os.close(fd)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    return tmp

def tail_text(text: str, n: int = 60) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-n:]) if len(lines) > n else text

class FilteredPSFGenerator:
    def __init__(self,
                 db_path="database/toxins.db",
                 tcl_script_path="resources/psf_gen.tcl",
                 topology_files=None,
                 output_base="tools/filtered"):
        # Rutas absolutas
        self.db_path = (root_dir / db_path).resolve()
        self.tcl_script_path = (root_dir / tcl_script_path).resolve()
        self.output_base = (root_dir / output_base).resolve()
        self.logs_dir = self.output_base / "logs"

        if topology_files is None:
            topology_files = ["resources/top_all36_prot.rtf"]
        self.topology_files = [(root_dir / f).resolve() for f in topology_files]

        # Directorios
        self.output_base.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Verificación
        self._verify_files()

    def _verify_files(self):
        if not self.db_path.exists():
            raise FileNotFoundError(f"No existe la base de datos: {self.db_path}")
        if not self.tcl_script_path.exists():
            raise FileNotFoundError(f"No existe el script Tcl: {self.tcl_script_path}")
        for top in self.topology_files:
            if not top.exists():
                raise FileNotFoundError(f"No existe topología: {top}")
        if not shutil.which("vmd"):
            print("Advertencia: no se encontró 'vmd' en PATH. Asegúrate de tener VMD instalado.")

    def get_filtered_peptides(self, gap_min=3, gap_max=6, require_pair=False):
        hits = search_toxins(
            gap_min=gap_min,
            gap_max=gap_max,
            require_pair=require_pair,
            db_path=str(self.db_path)
        )
        return hits

    def get_peptide_data(self, peptide_id):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT p.peptide_id, p.peptide_name, p.pdb_file, p.accession_number
                FROM Peptides p
                WHERE p.peptide_id = ?
            """, (peptide_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "peptide_id": row[0],
                "peptide_name": row[1],
                "pdb_data": row[2],
                "accession_number": row[3] or f"UNK_{row[0]}",
            }
        finally:
            conn.close()

    def _run_vmd_subprocess(self, pdb_path: Path, out_prefix: Path) -> tuple[bool, str]:
        # Script TCL por peptide
        tops_tcl = "{" + " ".join(f'"{t}"' for t in self.topology_files) + "}"
        tcl_body = f"""
package require psfgen
source "{self.tcl_script_path}"
set res [build_psf_with_disulfides "{pdb_path}" {tops_tcl} "{out_prefix}" "PROA" 2.3]
puts "PSF_OUT:[lindex $res 0]"
puts "PDB_OUT:[lindex $res 1]"
exit
"""
        # Archivo TCL temporal
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tcl", delete=False) as tmp_tcl:
            tmp_tcl.write(tcl_body)
            tcl_path = Path(tmp_tcl.name)

        try:
            # Ejecutar VMD capturando stdout/err
            completed = subprocess.run(
                ["vmd", "-dispdev", "text", "-e", str(tcl_path)],
                capture_output=True,
                text=True,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            ok = completed.returncode == 0
            # Retornar estado y stdout+stderr
            return ok, stdout + ("\n" + stderr if stderr else "")
        finally:
            try:
                tcl_path.unlink(missing_ok=True)
            except Exception:
                pass

    def generate_psf_for_peptide_subprocess(self, peptide_data, verbose=False):
        accession = peptide_data["accession_number"]
        pdb_data = peptide_data["pdb_data"]

        if not pdb_data:
            return False, f"{accession}: sin PDB"

        # Crear PDB temporal si es contenido; si es path existente, úsalo
        created_temp = False
        tmp_pdb = None
        try:
            if isinstance(pdb_data, str) and os.path.exists(pdb_data):
                tmp_pdb = Path(pdb_data).resolve()
            else:
                content = (
                    pdb_data.decode("utf-8", errors="ignore")
                    if isinstance(pdb_data, (bytes, bytearray))
                    else str(pdb_data)
                )
                tmp_pdb = Path(create_temp_pdb_file(content)).resolve()
                created_temp = True

            out_prefix = (self.output_base / accession).resolve()
            ok, out_text = self._run_vmd_subprocess(tmp_pdb, out_prefix)

            # Guardar log
            log_path = self.logs_dir / f"{accession}.log"
            log_path.write_text(out_text, encoding="utf-8")

            # Verificar archivos
            psf = Path(str(out_prefix) + ".psf")
            pdb = Path(str(out_prefix) + ".pdb")
            success = ok and psf.exists() and pdb.exists()

            if verbose:
                print(tail_text(out_text, 80))

            return success, str(log_path)
        finally:
            if created_temp and tmp_pdb:
                try:
                    tmp_pdb.unlink(missing_ok=True)
                except Exception:
                    pass

    def process_all_filtered(self, gap_min=3, gap_max=6, require_pair=False):
        hits = self.get_filtered_peptides(gap_min, gap_max, require_pair)
        total = len(hits)
        print(f"Filtrados: {total}")

        successes = []
        failures = []

        for i, hit in enumerate(hits, 1):
            peptide_id = hit.get("peptide_id") if isinstance(hit, dict) else hit
            pdata = self.get_peptide_data(peptide_id)
            if not pdata:
                print(f"[{i}/{total}] {peptide_id}: sin datos")
                failures.append((peptide_id, "sin_datos", None))
                continue

            accession = pdata["accession_number"]
            print(f"[{i}/{total}] {accession}: generando...", end="", flush=True)
            ok, log_path = self.generate_psf_for_peptide_subprocess(pdata, verbose=False)
            if ok:
                successes.append(accession)
                print(" OK")
            else:
                failures.append((peptide_id, accession, log_path))
                print(" FAIL")

        print(f"\nResumen: OK={len(successes)} FAIL={len(failures)}")
        if failures:
            print("Reintentando fallidos en modo verbose...")
            for idx, (peptide_id, accession, log_path) in enumerate(failures, 1):
                pdata = self.get_peptide_data(peptide_id)
                if not pdata:
                    continue
                print(f"\n[Retry {idx}/{len(failures)}] {accession}")
                ok, retry_log = self.generate_psf_for_peptide_subprocess(pdata, verbose=True)
                print(f"Log: {retry_log}")
                if ok:
                    print("Retry OK")
                else:
                    print("Retry FAIL")

        print(f"\nLogs: {self.logs_dir}")
        print(f"Outputs: {self.output_base}")
        return successes, failures

    def find_toxin_for_comparison(self, target_peptide_code="μ-TRTX-Cg4a"):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT id, peptide_code, sequence, ic50_value, ic50_unit
                FROM Nav1_7_InhibitorPeptides
                WHERE peptide_code = ?
            """, (target_peptide_code,))
            row = cur.fetchone()
            if row:
                print(f"Referencia: {row[1]} (ID {row[0]}) IC50={row[3]} {row[4]}")
        finally:
            conn.close()

def main():
    gen = FilteredPSFGenerator()
    gen.find_toxin_for_comparison("μ-TRTX-Cg4a")
    gen.process_all_filtered(gap_min=3, gap_max=6, require_pair=False)
    return 0


if __name__ == "__main__":
    import shutil
    sys.exit(main())