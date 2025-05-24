from app import create_app
import networkx as nx
import numpy as np
import plotly.graph_objects as go
from graphein.protein.config import ProteinGraphConfig
from graphein.protein.graphs import construct_graph
from graphein.protein.edges.distance import add_distance_threshold
from functools import partial

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
