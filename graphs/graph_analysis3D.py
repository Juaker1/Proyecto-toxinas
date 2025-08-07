from graphein.protein.config import ProteinGraphConfig
from graphein.protein.graphs import construct_graph
from graphein.protein.visualisation import plotly_protein_structure_graph
from graphein.protein.edges.atomic import add_atomic_edges
import os

#Toxina a usar
PEPTIDE_CODE = "bTRTXCd1a"
PDB_FILE = f"pdbs/{PEPTIDE_CODE}.pdb"

# Configuración: grafo atómico con enlaces covalentes
config = ProteinGraphConfig(
    granularity="atom",  # <== TODOS LOS ÁTOMOS
    pdb_dir="pdbs/",
    edge_construction_functions=[
        add_atomic_edges  # enlaces covalentes reales entre átomos
    ],
    save_graphs=False
)

# Construcción del grafo desde archivo PDB local
G = construct_graph(config=config, pdb_code=None, path=PDB_FILE)

# Visualización interactiva con Plotly
fig = plotly_protein_structure_graph(G)
fig.update_layout(title=f"Grafo molecular 3D: {PEPTIDE_CODE}")
fig.write_html("protein_3d_view.html")
