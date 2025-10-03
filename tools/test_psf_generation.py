#!/usr/bin/env python3
"""
Script de prueba para validar la generación automática de PSF
Toma el primer PDB de la carpeta pdbs/ y genera su PSF usando VMD/psfgen
"""

import sys
from pathlib import Path
import subprocess
import tempfile
import shutil

# Añadir src al path para importaciones del proyecto
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))

try:
    import vmd
    VMD_AVAILABLE = True
    print("✓ VMD Python disponible")
except ImportError:
    VMD_AVAILABLE = False
    print("✗ VMD Python no disponible - usando subprocess")

class PSFTestGenerator:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.pdbs_dir = self.project_root / "pdbs"
        self.psfs_dir = self.project_root / "psfs"
        self.resources_dir = self.project_root / "resources"
        self.test_output_dir = self.project_root / "tools" / "test_output"
        
        # Crear directorio de pruebas
        self.test_output_dir.mkdir(exist_ok=True)
        
        # Archivos necesarios
        self.tcl_script = self.resources_dir / "psf_gen.tcl"
        self.topology_file = self.resources_dir / "top_all36_prot.rtf"
        
        self._validate_files()
    
    def _validate_files(self):
        """Valida que existan los archivos necesarios"""
        if not self.tcl_script.exists():
            raise FileNotFoundError(f"Script TCL no encontrado: {self.tcl_script}")
        if not self.topology_file.exists():
            raise FileNotFoundError(f"Topología no encontrada: {self.topology_file}")
        if not self.pdbs_dir.exists():
            raise FileNotFoundError(f"Directorio PDB no encontrado: {self.pdbs_dir}")
    
    def get_first_pdb(self):
        """Obtiene el primer archivo PDB del directorio"""
        pdb_files = list(self.pdbs_dir.glob("*.pdb"))
        if not pdb_files:
            raise FileNotFoundError("No hay archivos PDB en el directorio pdbs/")
        
        first_pdb = sorted(pdb_files)[0]
        print(f"📁 PDB seleccionado: {first_pdb.name}")
        return first_pdb
    
    def generate_psf_with_vmd_python(self, pdb_path, output_prefix):
        """Genera PSF usando vmd-python directamente"""
        if not VMD_AVAILABLE:
            raise ImportError("VMD Python no está disponible")
        
        print("🔧 Generando PSF con vmd-python...")
        
        try:
            # Limpiar cualquier molécula existente
            nmols = vmd.molecule.num()
            for i in range(nmols):
                vmd.molecule.delete(i)
            
            # Ejecutar comandos TCL en VMD
            vmd.evaltcl('package require psfgen')
            vmd.evaltcl(f'source "{self.tcl_script}"')
            
            # Preparar comando
            tops_tcl = f'{{"{self.topology_file}"}}'
            cmd = (
                f'set res [build_psf_with_disulfides '
                f'"{pdb_path}" {tops_tcl} "{output_prefix}" "PROA" 2.3]'
            )
            
            print(f"🔧 Ejecutando: {cmd}")
            
            # Ejecutar
            result = vmd.evaltcl(cmd)
            print(f"✓ Comando ejecutado. Resultado: {result}")
            
            # Los archivos se generan automáticamente
            psf_file = Path(f"{output_prefix}.psf")
            pdb_file = Path(f"{output_prefix}.pdb")
            
            return psf_file, pdb_file
            
        except Exception as e:
            print(f"❌ Error en vmd-python: {e}")
            # Intentar obtener más información del error
            try:
                error_info = vmd.evaltcl('puts $errorInfo')
                print(f"Información adicional del error: {error_info}")
            except:
                pass
            raise
    
    def generate_psf_with_subprocess(self, pdb_path, output_prefix):
        """Genera PSF usando VMD como subprocess"""
        print("🔧 Generando PSF con VMD subprocess...")
        
        # Crear script TCL temporal
        tcl_commands = f"""
package require psfgen
source "{self.tcl_script}"
set tops {{"{self.topology_file}"}}
set res [build_psf_with_disulfides "{pdb_path}" $tops "{output_prefix}" "PROA" 2.3]
puts "PSF generado: [lindex $res 0]"
puts "PDB generado: [lindex $res 1]"
exit
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tcl', delete=False) as tmp_tcl:
            tmp_tcl.write(tcl_commands)
            tmp_tcl_path = tmp_tcl.name
        
        try:
            # Ejecutar VMD
            result = subprocess.run([
                'vmd', '-dispdev', 'text', '-e', tmp_tcl_path
            ], capture_output=True, text=True, cwd=self.test_output_dir)
            
            if result.returncode != 0:
                print(f"❌ Error en VMD: {result.stderr}")
                raise RuntimeError(f"VMD falló: {result.stderr}")
            
            print("✓ VMD ejecutado exitosamente")
            print("📄 Salida VMD:")
            print(result.stdout)
            
            # Verificar archivos generados
            psf_file = Path(f"{output_prefix}.psf")
            pdb_file = Path(f"{output_prefix}.pdb")
            
            return psf_file, pdb_file
            
        finally:
            # Limpiar archivo temporal
            Path(tmp_tcl_path).unlink(missing_ok=True)
    
    def compare_with_existing_psf(self, generated_psf, pdb_name):
        """Compara el PSF generado con el existente"""
        # Buscar PSF existente
        existing_psf = None
        for psf_file in self.psfs_dir.glob("*.psf"):
            if pdb_name.stem in psf_file.name:
                existing_psf = psf_file
                break
        
        if not existing_psf:
            print(f"⚠️  No se encontró PSF existente para {pdb_name.stem}")
            return
        
        print(f"🔍 Comparando con PSF existente: {existing_psf.name}")
        
        # Comparación básica de tamaño
        gen_size = generated_psf.stat().st_size
        exist_size = existing_psf.stat().st_size
        
        print(f"📊 Tamaño generado: {gen_size} bytes")
        print(f"📊 Tamaño existente: {exist_size} bytes")
        print(f"📊 Diferencia: {abs(gen_size - exist_size)} bytes ({abs(gen_size - exist_size) / exist_size * 100:.1f}%)")
        
        # Comparación de líneas clave
        self._compare_psf_content(generated_psf, existing_psf)
    
    def _compare_psf_content(self, psf1, psf2):
        """Compara contenido básico de PSF"""
        try:
            with open(psf1) as f1, open(psf2) as f2:
                lines1 = f1.readlines()
                lines2 = f2.readlines()
            
            # Comparar número de átomos
            natoms1 = natoms2 = 0
            for line in lines1:
                if "!NATOM" in line:
                    natoms1 = int(line.split()[0])
                    break
            
            for line in lines2:
                if "!NATOM" in line:
                    natoms2 = int(line.split()[0])
                    break
            
            print(f"🧮 Átomos generado: {natoms1}")
            print(f"🧮 Átomos existente: {natoms2}")
            
            if natoms1 == natoms2:
                print("✅ Mismo número de átomos")
            else:
                print("❌ Diferente número de átomos")
                
        except Exception as e:
            print(f"⚠️  Error comparando contenido: {e}")
    
    def run_test(self):
        """Ejecuta el test completo"""
        print("🚀 Iniciando test de generación PSF")
        print("=" * 50)
        
        try:
            # Obtener primer PDB
            pdb_path = self.get_first_pdb()
            output_prefix = self.test_output_dir / f"test_{pdb_path.stem}"
            
            # Generar PSF
            if VMD_AVAILABLE:
                psf_file, pdb_file = self.generate_psf_with_vmd_python(pdb_path, output_prefix)
            else:
                psf_file, pdb_file = self.generate_psf_with_subprocess(pdb_path, output_prefix)
            
            # Verificar archivos generados
            if psf_file.exists() and pdb_file.exists():
                print("✅ PSF y PDB generados exitosamente")
                print(f"📁 PSF: {psf_file}")
                print(f"📁 PDB: {pdb_file}")
                
                # Comparar con existente
                self.compare_with_existing_psf(psf_file, pdb_path)
                
            else:
                print("❌ Archivos no generados correctamente")
                print(f"PSF existe: {psf_file.exists()}")
                print(f"PDB existe: {pdb_file.exists()}")
                
        except Exception as e:
            print(f"❌ Error en el test: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("=" * 50)
        print("✅ Test completado")
        return True

if __name__ == "__main__":
    tester = PSFTestGenerator()
    success = tester.run_test()
    sys.exit(0 if success else 1)