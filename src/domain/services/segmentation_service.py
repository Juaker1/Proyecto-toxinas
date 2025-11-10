from typing import Any
import networkx as nx
import pandas as pd


def agrupar_por_segmentos_atomicos(G: Any, granularity: str = "atom") -> pd.DataFrame:
    """
    Agrupa átomos en segmentos basados en residuos.
    Mantiene compatibilidad de columnas con la implementación legacy.
    """
    if granularity != "atom":
        return pd.DataFrame()

    # Métricas sobre el grafo completo (reutilizadas para promedios por residuo)
    degree_centrality = nx.degree_centrality(G)
    betweenness_centrality = nx.betweenness_centrality(G)
    closeness_centrality = nx.closeness_centrality(G)
    clustering_coeff = nx.clustering(G)

    # Agrupar átomos por residuo (parseando ID del nodo o usando atributos)
    residuos_atomicos: dict[str, dict] = {}
    for nodo, data in G.nodes(data=True):
        chain = data.get('chain_id')
        res_name = data.get('residue_name')
        res_num = data.get('residue_number')
        atom_name = data.get('atom_type') or data.get('atom_name')

        if (not chain or not res_name or res_num is None) and isinstance(nodo, str) and ':' in nodo:
            parts = nodo.split(':')
            if len(parts) >= 4:
                chain = chain or parts[0]
                res_name = res_name or parts[1]
                res_num = res_num if res_num is not None else parts[2]
                atom_name = atom_name or parts[3]

        if not chain:
            chain = 'A'
        if not res_name:
            res_name = 'UNK'
        if res_num is None:
            res_num = 1

        try:
            res_num_int = int(res_num)
        except Exception:
            res_num_int = res_num

        if not atom_name:
            # si no hay nombre de átomo, omitir (como legacy)
            continue

        key = f"{chain}_{res_num}"
        bucket = residuos_atomicos.setdefault(key, {
            'cadena': chain,
            'residuo_nombre': res_name,
            'residuo_numero': res_num_int,
            'atomos': []
        })
        bucket['atomos'].append({'nodo': nodo, 'atomo_nombre': atom_name})

    segmentos_data = []
    for key, residuo_info in residuos_atomicos.items():
        res_num = residuo_info['residuo_numero']
        if isinstance(res_num, int):
            segmento_id = f"RES_{res_num:03d}"
        else:
            segmento_id = f"RES_{res_num}"

        atom_nodes = [a['nodo'] for a in residuo_info['atomos']]
        atom_names = [a['atomo_nombre'] for a in residuo_info['atomos']]
        num_atomos = len(atom_nodes)

        sub = G.subgraph(atom_nodes)
        internal_edges = sub.number_of_edges()

        if internal_edges == 0:
            internal_edges = sum(G.degree(n) for n in atom_nodes)

        if num_atomos > 1:
            if sub.number_of_edges() == 0 and internal_edges > 0:
                grado_promedio = internal_edges / num_atomos
                max_grado_teorico = G.number_of_nodes() - 1
                densidad_segmento = (grado_promedio / max_grado_teorico) if max_grado_teorico > 0 else 0
            else:
                max_posibles = (num_atomos * (num_atomos - 1)) // 2
                densidad_segmento = (sub.number_of_edges() / max_posibles) if max_posibles > 0 else 0
        else:
            densidad_segmento = 0

        if num_atomos > 0:
            grados = [G.degree(n) for n in atom_nodes]
            grado_promedio = sum(grados) / len(grados)
            grado_max = max(grados)
            grado_min = min(grados)
        else:
            grado_promedio = grado_max = grado_min = 0

        if num_atomos > 0:
            degree_vals = [degree_centrality.get(n, 0) for n in atom_nodes]
            between_vals = [betweenness_centrality.get(n, 0) for n in atom_nodes]
            close_vals = [closeness_centrality.get(n, 0) for n in atom_nodes]
            cluster_vals = [clustering_coeff.get(n, 0) for n in atom_nodes]
            degree_avg = sum(degree_vals) / len(degree_vals)
            between_avg = sum(between_vals) / len(between_vals)
            close_avg = sum(close_vals) / len(close_vals)
            cluster_avg = sum(cluster_vals) / len(cluster_vals)
        else:
            degree_avg = between_avg = close_avg = cluster_avg = 0

        # Obtener residuos vecinos conectados (únicos, fuera del segmento actual)
        vecinos_externos = set()
        for atom_node in atom_nodes:
            for neighbor in G.neighbors(atom_node):
                neighbor_data = G.nodes[neighbor]
                neighbor_chain = neighbor_data.get('chain_id', 'A')
                neighbor_res_name = neighbor_data.get('residue_name', 'UNK')
                neighbor_res_num = neighbor_data.get('residue_number', '?')
                
                # Solo agregar si es de un residuo diferente
                neighbor_key = f"{neighbor_chain}_{neighbor_res_num}"
                if neighbor_key != key:
                    vecinos_externos.add(f"{neighbor_res_name}:{neighbor_res_num}")
        
        vecinos_list = sorted(list(vecinos_externos))

        segmentos_data.append({
            'Segmento_ID': segmento_id,
            'Num_Atomos': num_atomos,
            'Conexiones_Internas': internal_edges,
            'Atomos_Lista': ', '.join(atom_names),
            'Aminoacido': residuo_info['residuo_nombre'],
            'Posicion_Secuencia': residuo_info['residuo_numero'],
            'Cadena': residuo_info['cadena'],
            'Grado_Promedio': round(grado_promedio, 6),
            'Grado_Maximo': grado_max,
            'Grado_Minimo': grado_min,
            'Densidad_Segmento': round(densidad_segmento, 6),
            'Centralidad_Grado_Promedio': round(degree_avg, 6),
            'Centralidad_Intermediacion_Promedio': round(between_avg, 6),
            'Centralidad_Cercania_Promedio': round(close_avg, 6),
            'Coeficiente_Agrupamiento_Promedio': round(cluster_avg, 6),
            'Residuos_Vecinos_Conectados': ', '.join(vecinos_list) if vecinos_list else 'Ninguno'
        })

    segmentos_data.sort(key=lambda x: (x['Cadena'], x['Residuo_Numero'] if isinstance(x['Residuo_Numero'], int) else 999))
    return pd.DataFrame(segmentos_data)


def agrupar_por_segmentos(G: Any, granularity: str = "atom") -> pd.DataFrame:
    if granularity == "atom":
        return agrupar_por_segmentos_atomicos(G, granularity)

    segmentos = []
    for node, data in G.nodes(data=True):
        chain = data.get('chain_id', 'A')
        residue_name = data.get('residue_name', 'UNK')
        residue_number = data.get('residue_number', 1)
        
        # Obtener vecinos conectados
        neighbors = list(G.neighbors(node))
        neighbor_list = []
        for neighbor in neighbors:
            neighbor_data = G.nodes[neighbor]
            neighbor_res_name = neighbor_data.get('residue_name', 'UNK')
            neighbor_res_num = neighbor_data.get('residue_number', '?')
            neighbor_list.append(f"{neighbor_res_name}:{neighbor_res_num}")
        
        segmentos.append({
            'Segmento_ID': f"{chain}:{residue_name}:{residue_number}",
            'Cadena': chain,
            'Aminoacido': residue_name,
            'Posicion_Secuencia': residue_number,
            'Atomos_Lista': f"{residue_name}{residue_number}:CA",
            'Num_Atomos': 1,
            'Numero_Conexiones': G.degree(node),
            'Vecinos_Conectados': ', '.join(neighbor_list) if neighbor_list else 'Ninguno'
        })
    return pd.DataFrame(segmentos)
