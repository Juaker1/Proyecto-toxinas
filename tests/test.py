from flask import Flask
import dash
from dash import html, dcc, dash_table
from graphein.protein.config import ProteinGraphConfig
from graphein.protein.graphs import construct_graph
from graphein.protein.visualisation import plotly_protein_structure_graph
from graphein.protein.edges.distance import (
    add_peptide_bonds,
    add_hydrogen_bond_interactions,
    add_disulfide_interactions,
    add_ionic_interactions,
    add_aromatic_interactions,
    add_aromatic_sulphur_interactions,
    add_cation_pi_interactions,
    add_k_nn_edges,
    add_distance_threshold,
    add_delaunay_triangulation
)
from graphein.protein.edges.atomic import add_atomic_edges
from functools import partial
import networkx as nx

# ----------------------------
# 1) Función para calcular propiedades del grafo
# ----------------------------
def compute_graph_properties(G):
    props = {}
    props["num_nodes"] = G.number_of_nodes()
    props["num_edges"] = G.number_of_edges()
    props["density"] = nx.density(G)
    degrees = list(dict(G.degree()).values())
    props["avg_degree"] = sum(degrees) / len(degrees) if degrees else 0.0
    props["avg_clustering"] = nx.average_clustering(G)
    comps = list(nx.connected_components(G)) if not G.is_directed() else list(nx.weakly_connected_components(G))
    props["num_components"] = len(comps)
    props["largest_component_size"] = max((len(c) for c in comps), default=0)
    if props["largest_component_size"] > 1:
        giant = G.subgraph(max(comps, key=len))
        try:
            props["avg_shortest_path"] = nx.average_shortest_path_length(giant)
            props["diameter"] = nx.diameter(giant)
        except nx.NetworkXError:
            props["avg_shortest_path"] = None
            props["diameter"] = None
    deg_cent = nx.degree_centrality(G)
    vals = list(deg_cent.values())
    props["mean_degree_centrality"] = sum(vals) / len(vals) if vals else 0.0
    props["max_degree_centrality"] = max(vals) if vals else 0.0
    return props

# ----------------------------
# 2) Servidor Flask & Dash
# ----------------------------
server = Flask(__name__)
app = dash.Dash(__name__, server=server, url_base_pathname="/grafo/")

# Parámetros por defecto
default_long = 5
default_threshold = 10.0

# ----------------------------
# 3) Preparar gráficos estáticos
# ----------------------------
graph_funcs = {
    "basic": [],
    "hbonds": [add_peptide_bonds, add_hydrogen_bond_interactions],
    "all": [
        add_peptide_bonds, add_hydrogen_bond_interactions,
        add_disulfide_interactions, add_ionic_interactions,
        add_aromatic_interactions, add_aromatic_sulphur_interactions,
        add_cation_pi_interactions
    ],
    "knn": [partial(add_k_nn_edges, k=3, long_interaction_threshold=0)],
    "delaunay": [add_delaunay_triangulation],
    "atomic": []
}
G_static = {}
for name, funcs in graph_funcs.items():
    if name == "atomic":
        cfg = ProteinGraphConfig(granularity="atom", edge_construction_functions=[add_atomic_edges])
    else:
        cfg = ProteinGraphConfig(edge_construction_functions=funcs)
    G_static[name] = construct_graph(config=cfg, pdb_code="3eiy")
# Generar figuras
titles = {
    "basic": ("Backbone (Degree)", {"colour_nodes_by": "degree"}),
    "hbonds": ("Backbone + H-Bonds", {"colour_nodes_by": "seq_position"}),
    "all": ("Full Interactions", {"colour_nodes_by": "seq_position"}),
    "knn": ("K-NN (k=3)", {"colour_nodes_by": "seq_position"}),
    "delaunay": ("Delaunay Triangulation", {"colour_nodes_by": "seq_position"}),
    "atomic": ("Atom Level", {"colour_nodes_by": "atom_type"})
}
figures = {}
for key, graph in G_static.items():
    title, node_kwargs = titles[key]
    figures[key] = plotly_protein_structure_graph(
        graph,
        colour_edges_by="kind",
        label_node_ids=False,
        plot_title=title,
        node_size_multiplier=1,
        **node_kwargs
    )

# ----------------------------
# 4) Función para grafo dinámico Threshold
# ----------------------------
def build_threshold(long_interaction_threshold, threshold):
    cfg = ProteinGraphConfig(
        edge_construction_functions=[
            partial(add_distance_threshold,
                    long_interaction_threshold=int(long_interaction_threshold),
                    threshold=float(threshold))
        ]
    )
    G_t = construct_graph(config=cfg, pdb_code="3eiy")
    fig_t = plotly_protein_structure_graph(
        G_t,
        colour_edges_by="kind",
        colour_nodes_by="seq_position",
        label_node_ids=False,
        plot_title=(
            f"Distance Threshold (<{threshold}Å & gap≥{long_interaction_threshold})"
        ),
        node_size_multiplier=1
    )
    props_t = compute_graph_properties(G_t)
    return fig_t, props_t

# Inicial Threshold
init_fig, init_props = build_threshold(default_long, default_threshold)

# ----------------------------
# 5) Layout combinado
# ----------------------------
div_style = {"width": "30%", "display": "inline-block", "vertical-align": "top", "margin": "1%"}

app.layout = html.Div([
    html.H1("Graphein Protein Graph Dashboard"),
    # Parámetros dinámicos
    html.Div([
        html.Label("Sequence separation (long_interaction_threshold):"),
        dcc.Input(id='long-input', type='number', value=default_long, min=0, step=1),
        html.Label("Distance threshold (Å):", style={'margin-left':'1rem'}),
        dcc.Input(id='dist-input', type='number', value=default_threshold, min=0, step=0.1)
    ], style={'margin-bottom':'2rem'}),
    # Gráfico Threshold dinámico
    html.Div([dcc.Graph(id='graph-threshold', figure=init_fig)], style={'margin-bottom':'2rem'}),
    # Tabla propiedades
    html.Div([
        html.H3("Threshold Graph Properties"),
        dash_table.DataTable(
            id='table-threshold',
            columns=[{"name": k.replace('_',' ').title(), "id": k} for k in init_props.keys()],
            data=[init_props],
            style_cell={"textAlign":"left","padding":"5px"}
        )
    ], style={'margin-bottom':'2rem'}),
    # Gráficos estáticos
    html.Div([
        html.Div([html.H4(titles[key][0]), dcc.Graph(figure=figures[key])], style=div_style)
        for key in ["basic","hbonds","all","knn","delaunay","atomic"]
    ])
], style={"padding":"2rem"})

# ----------------------------
# 6) Callbacks
# ----------------------------
@app.callback(
    [dash.dependencies.Output('graph-threshold', 'figure'),
     dash.dependencies.Output('table-threshold', 'data')],
    [dash.dependencies.Input('long-input', 'value'),
     dash.dependencies.Input('dist-input', 'value')]
)
def update_threshold(long_val, dist_val):
    fig_u, props_u = build_threshold(long_val, dist_val)
    return fig_u, [props_u]

# Ruta base de Flask
@server.route("/")
def index():
    return (
        "<h2>Servidor Flask + Dash de Graphein</h2>"
        "<p>Ve a <a href='/grafo/'>/grafo/</a> para ver el dashboard.</p>"
    )

if __name__ == "__main__":
    server.run(debug=True)
