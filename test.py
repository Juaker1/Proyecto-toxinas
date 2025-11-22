from Bio.PDB import PDBParser
from graphs.graph_analysis2D import Nav17ToxinGraphAnalyzer

pdb_path = "pdbs/ω-TRTX-Gr2a.pdb"  # ajusta el nombre

parser = PDBParser(QUIET=True)
structure = parser.get_structure("prot", pdb_path)

analyzer = Nav17ToxinGraphAnalyzer(pdb_folder="pdbs")
bridges = analyzer.find_disulfide_bridges(structure)

print("Cys+SG encontrados:", len(bridges) * 2)
print("Puentes disulfuro:", len(bridges))
print("Pares:", bridges)