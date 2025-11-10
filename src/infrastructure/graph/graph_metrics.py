"""
Módulo común para cálculos de métricas de grafos moleculares.
Elimina redundancias entre graph_analysis2D.py y graphein_graph_adapter.py.
"""

# Importaciones pesadas solo cuando se necesitan
def _import_networkx():
    import networkx as nx
    return nx

def _import_numpy():
    import numpy as np
    return np


def calculate_centrality_metrics(G):
    """
    Calcula métricas de centralidad de manera eficiente.
    Retorna diccionarios con valores por nodo.
    Ahora incluye: degree, betweenness, closeness, clustering, seq_distance_avg, long_contacts_prop
    """
    nx = _import_networkx()
    
    if len(G) == 0:
        return {
            'degree': {},
            'betweenness': {},
            'closeness': {},
            'clustering': {},
            'seq_distance_avg': {},
            'long_contacts_prop': {}
        }

    # Calcular centralidades tradicionales
    degree_centrality = nx.degree_centrality(G)
    betweenness_centrality = nx.betweenness_centrality(G)
    closeness_centrality = nx.closeness_centrality(G)
    clustering_coefficient = nx.clustering(G)
    
    # Nuevas métricas: distancia secuencial promedio y proporción de contactos largos
    seq_distance_avg = {}
    long_contacts_prop = {}
    
    for node in G.nodes():
        node_attrs = G.nodes[node]
        node_res_num = node_attrs.get('residue_number', None)
        node_chain = node_attrs.get('chain_id', None)
        
        neighbors = list(G.neighbors(node))
        if not neighbors:
            seq_distance_avg[node] = 0.0
            long_contacts_prop[node] = 0.0
            continue
        
        # Calcular distancias secuenciales
        seq_distances = []
        long_range_count = 0
        
        for neighbor in neighbors:
            neighbor_attrs = G.nodes[neighbor]
            neighbor_res_num = neighbor_attrs.get('residue_number', None)
            neighbor_chain = neighbor_attrs.get('chain_id', None)
            
            # Solo calcular distancias para residuos de la misma cadena
            if node_chain != neighbor_chain:
                continue
            
            try:
                current_num = int(node_res_num) if node_res_num is not None else None
                neighbor_num = int(neighbor_res_num) if neighbor_res_num is not None else None
                
                if current_num is not None and neighbor_num is not None:
                    seq_dist = abs(neighbor_num - current_num)
                    seq_distances.append(seq_dist)
                    
                    if seq_dist > 5:
                        long_range_count += 1
            except (ValueError, TypeError):
                pass  # Ignorar si no se pueden convertir a números
        
        # Promedios
        if seq_distances:
            seq_distance_avg[node] = sum(seq_distances) / len(seq_distances)
            long_contacts_prop[node] = long_range_count / len(seq_distances)
        else:
            seq_distance_avg[node] = 0.0
            long_contacts_prop[node] = 0.0

    # Almacenar en nodos para compatibilidad
    nx.set_node_attributes(G, degree_centrality, 'degree_centrality')
    nx.set_node_attributes(G, betweenness_centrality, 'betweenness_centrality')
    nx.set_node_attributes(G, closeness_centrality, 'closeness_centrality')
    nx.set_node_attributes(G, clustering_coefficient, 'clustering_coefficient')
    nx.set_node_attributes(G, seq_distance_avg, 'seq_distance_avg')
    nx.set_node_attributes(G, long_contacts_prop, 'long_contacts_prop')

    return {
        'degree': degree_centrality,
        'betweenness': betweenness_centrality,
        'closeness': closeness_centrality,
        'clustering': clustering_coefficient,
        'seq_distance_avg': seq_distance_avg,
        'long_contacts_prop': long_contacts_prop
    }


def calculate_summary_statistics(centrality_dict):
    """
    Calcula estadísticas resumen (min, max, mean, top_residues) para métricas de centralidad.
    """
    if not centrality_dict:
        return {}

    stats = {}
    for metric_name, values in centrality_dict.items():
        if values:
            values_list = list(values.values())
            # Encontrar top residuos (los que tienen el valor máximo)
            max_value = max(values_list)
            top_residues = [str(k) for k, v in values.items() if abs(v - max_value) < 1e-9]
            top_residues_str = ', '.join(top_residues[:3])  # Top 3 como string
            
            stats[metric_name] = {
                'min': min(values_list),
                'max': max_value,
                'mean': sum(values_list) / len(values_list),
                'top_residues': top_residues_str
            }
        else:
            stats[metric_name] = {'min': 0, 'max': 0, 'mean': 0, 'top_residues': '-'}

    return stats


def find_top_residues(centrality_dict, top_n=5):
    """
    Encuentra los top N residuos por métrica de centralidad.
    """
    top_residues = {}
    for metric_name, values in centrality_dict.items():
        if values:
            # Ordenar por valor descendente y tomar top N
            sorted_items = sorted(values.items(), key=lambda x: x[1], reverse=True)
            top_residues[metric_name] = [res_id for res_id, _ in sorted_items[:top_n]]
        else:
            top_residues[metric_name] = []

    return top_residues


def calculate_basic_graph_properties(G):
    """
    Calcula propiedades básicas del grafo.
    """
    nx = _import_networkx()
    
    if len(G) == 0:
        return {
            'num_nodes': 0,
            'num_edges': 0,
            'density': 0.0,
            'avg_clustering': 0.0
        }

    return {
        'num_nodes': G.number_of_nodes(),
        'num_edges': G.number_of_edges(),
        'density': float(nx.density(G)),
        'avg_clustering': float(nx.average_clustering(G))
    }


def calculate_charge_and_hydrophobicity_stats(G):
    """
    Calcula estadísticas de carga e hidrofobicidad.
    """
    np = _import_numpy()
    
    charges = [G.nodes[n].get('charge', 0.0) for n in G.nodes()]
    hydrophobicity = [G.nodes[n].get('hydrophobicity', 0.0) for n in G.nodes()]

    return {
        'total_charge': sum(charges),
        'charge_std_dev': float(np.std(charges)) if charges else 0.0,
        'avg_hydrophobicity': round(np.mean(hydrophobicity), 2) if hydrophobicity else 0.0,
        'hydrophobicity_std_dev': round(np.std(hydrophobicity), 2) if hydrophobicity else 0.0
    }


def calculate_surface_properties(G):
    """
    Calcula propiedades superficiales.
    """
    np = _import_numpy()
    
    surface_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_surface', False)]

    if not surface_nodes:
        return {
            'surface_charge': 0.0,
            'surface_hydrophobicity': 0.0,
            'surface_to_total_ratio': 0.0
        }

    surface_charges = [G.nodes[n].get('charge', 0.0) for n in surface_nodes]
    surface_hydrophobicity = [G.nodes[n].get('hydrophobicity', 0.0) for n in surface_nodes]

    return {
        'surface_charge': sum(surface_charges),
        'surface_hydrophobicity': round(np.mean(surface_hydrophobicity), 2),
        'surface_to_total_ratio': round(len(surface_nodes) / len(G.nodes()), 2)
    }


def calculate_community_metrics(G):
    """
    Calcula métricas de comunidades.
    """
    nx = _import_networkx()
    
    try:
        communities = list(nx.algorithms.community.greedy_modularity_communities(G))
        community_count = len(communities)
        modularity = nx.algorithms.community.modularity(G, communities)
    except Exception:
        community_count = 0
        modularity = 0.0

    return {
        'community_count': community_count,
        'modularity': float(modularity)
    }


def calculate_pharmacophore_count(G):
    """
    Cuenta residuos farmacofóricos.
    """
    pharm_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_pharmacophore', False)]
    return len(pharm_nodes)


def compute_comprehensive_metrics(G):
    """
    Función principal que calcula todas las métricas necesarias.
    Retorna formato compatible con el frontend.
    """
    if len(G) == 0:
        return {
            'properties': {
                'num_nodes': 0,
                'num_edges': 0,
                'density': 0.0,
                'avg_clustering': 0.0,
                'disulfide_count': 0,
                'dipole_magnitude': 0.0
            },
            'summary_statistics': {},
            'top_5_residues': {}
        }

    # Propiedades básicas
    properties = calculate_basic_graph_properties(G)
    properties['disulfide_count'] = G.graph.get('disulfide_count', 0)
    properties['dipole_magnitude'] = float(G.graph.get('dipole_magnitude', 0))

    # Métricas de centralidad
    centrality = calculate_centrality_metrics(G)

    # Estadísticas resumen
    summary_stats = calculate_summary_statistics(centrality)

    # Top residuos
    top_5 = find_top_residues(centrality, top_n=5)

    # Agregar top_residues a summary_stats para compatibilidad con JS
    for metric_name in summary_stats:
        if metric_name in top_5:
            summary_stats[metric_name]['top_residues'] = ', '.join(map(str, top_5[metric_name][:3]))  # Top 3 como string

    # Estadísticas adicionales (carga, hidrofobicidad, etc.)
    charge_stats = calculate_charge_and_hydrophobicity_stats(G)
    surface_stats = calculate_surface_properties(G)
    community_stats = calculate_community_metrics(G)
    pharmacophore_count = calculate_pharmacophore_count(G)

    # Combinar todo
    properties.update(charge_stats)
    properties.update(surface_stats)
    properties.update(community_stats)
    properties['pharmacophore_count'] = pharmacophore_count

    return {
        'properties': properties,
        'summary_statistics': summary_stats,
        'top_5_residues': top_5,
        'centrality': centrality  # Agregado para compatibilidad con adaptador
    }