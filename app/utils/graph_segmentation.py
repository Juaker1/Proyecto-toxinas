import networkx as nx
import pandas as pd
from functools import partial
from graphein.protein.config import ProteinGraphConfig
from graphein.protein.graphs import construct_graph
from graphein.protein.edges.distance import add_distance_threshold


def agrupar_por_segmentos_atomicos(G, granularity="atom"):
    """
    Agrupa átomos en segmentos basados en residuos del archivo PDB.
    Cada segmento representa un residuo individual con todos sus átomos.
    
    Args:
        G: Grafo de NetworkX a nivel atómico
        granularity: Granularidad del grafo (debe ser "atom")
        
    Returns:
        DataFrame con datos de segmentos atómicos por residuo
    """
    if granularity != "atom":
        print("La segmentación atómica requiere granularidad 'atom'")
        return pd.DataFrame()
    
    print(f"Iniciando segmentación atómica por residuos para grafo con {G.number_of_nodes()} nodos")
    
    # Calcular métricas de centralidad del grafo completo
    # Es más eficiente calcularlas una vez para todo el grafo
    degree_centrality = nx.degree_centrality(G)
    betweenness_centrality = nx.betweenness_centrality(G)
    closeness_centrality = nx.closeness_centrality(G)
    clustering_coeff = nx.clustering(G)
    
    # Agrupar átomos por residuo parseando el ID del nodo
    residuos_atomicos = {}
    
    for nodo, data in G.nodes(data=True):
        # Parsear información del ID del nodo
        # Formato: "P:ASP:1:N" (cadena:residuo:numero:atomo)
        if isinstance(nodo, str) and ':' in nodo:
            partes = nodo.split(':')
            if len(partes) >= 4:
                cadena = partes[0]
                residuo_nombre = partes[1]
                residuo_numero = partes[2]
                atomo_nombre = partes[3] 
            else:
                continue
        else:
            # Obtener de los atributos de Graphein si el parseo falla
            cadena = data.get('chain_id', 'A')
            residuo_nombre = data.get('residue_name', 'UNK')
            residuo_numero = str(data.get('residue_number', 1))
            atomo_nombre = data.get('atom_type', 'UNK')  # Usar atom_type para obtener nombre correcto
            
            if atomo_nombre == 'UNK':
                continue
        
        # Clave del residuo basada en cadena y número
        residuo_key = f"{cadena}_{residuo_numero}"
        
        if residuo_key not in residuos_atomicos:
            residuos_atomicos[residuo_key] = {
                'cadena': cadena,
                'residuo_nombre': residuo_nombre,
                'residuo_numero': int(residuo_numero) if residuo_numero.isdigit() else residuo_numero,
                'atomos': []
            }
        
        residuos_atomicos[residuo_key]['atomos'].append({
            'nodo': nodo,
            'atomo_nombre': atomo_nombre
        })
    
    print(f"Encontrados {len(residuos_atomicos)} residuos con átomos")
    
    segmentos_data = []
    
    for idx, (residuo_key, residuo_info) in enumerate(residuos_atomicos.items()):
        residuo_num = residuo_info['residuo_numero']
        if isinstance(residuo_num, int):
            segmento_id = f"RES_{residuo_num:03d}"
        else:
            segmento_id = f"RES_{residuo_num}"
        
        # Lista de nodos de átomos para este residuo (mantener orden original)
        atomos_nodos = [atomo['nodo'] for atomo in residuo_info['atomos']]
        atomos_nombres = [atomo['atomo_nombre'] for atomo in residuo_info['atomos']]
        
        # Calcular métricas estructurales del residuo
        num_atomos = len(atomos_nodos)
        
        # Crear subgrafo para análisis de conexiones internas
        subgrafo = G.subgraph(atomos_nodos)
        
        # Calcular conexiones internas: enlaces entre átomos del mismo residuo
        conexiones_internas = subgrafo.number_of_edges()
        
        # Si no hay conexiones internas directas, usar suma de grados
        # Común en grafos de distancia donde átomos se conectan a otros residuos
        if conexiones_internas == 0:
            conexiones_internas = sum(G.degree(nodo) for nodo in atomos_nodos)
        
        # Calcular densidad del segmento
        if num_atomos > 1:
            if subgrafo.number_of_edges() == 0 and conexiones_internas > 0:
                # Métrica alternativa basada en conectividad promedio
                grado_promedio_residuo = conexiones_internas / num_atomos
                max_grado_teorico = G.number_of_nodes() - 1
                densidad_segmento = grado_promedio_residuo / max_grado_teorico if max_grado_teorico > 0 else 0
            else:
                # Cálculo tradicional de densidad interna
                max_conexiones_posibles = (num_atomos * (num_atomos - 1)) // 2
                densidad_segmento = subgrafo.number_of_edges() / max_conexiones_posibles if max_conexiones_posibles > 0 else 0
        else:
            densidad_segmento = 0
        
        # Grado promedio del residuo basado en el grafo completo
        if num_atomos > 0:
            grados = [G.degree(nodo) for nodo in atomos_nodos]
            grado_promedio = sum(grados) / len(grados)
            grado_max = max(grados)
            grado_min = min(grados)
        else:
            grado_promedio = grado_max = grado_min = 0
        
        # Promediar las métricas de centralidad para este residuo
        # Cada átomo tiene su centralidad calculada en el contexto del grafo completo
        if num_atomos > 0:
            degree_cent_values = [degree_centrality.get(nodo, 0) for nodo in atomos_nodos]
            between_cent_values = [betweenness_centrality.get(nodo, 0) for nodo in atomos_nodos]
            close_cent_values = [closeness_centrality.get(nodo, 0) for nodo in atomos_nodos]
            cluster_values = [clustering_coeff.get(nodo, 0) for nodo in atomos_nodos]
            
            degree_cent_avg = sum(degree_cent_values) / len(degree_cent_values)
            between_cent_avg = sum(between_cent_values) / len(between_cent_values)
            close_cent_avg = sum(close_cent_values) / len(close_cent_values)
            cluster_avg = sum(cluster_values) / len(cluster_values)
        else:
            degree_cent_avg = between_cent_avg = close_cent_avg = cluster_avg = 0
        
        # Crear entrada del DataFrame
        segmento_info = {
            'Segmento_ID': segmento_id,
            'Num_Atomos': num_atomos,
            'Conexiones_Internas': conexiones_internas,  # Conexiones entre átomos del mismo residuo
            'Atomos_Lista': ', '.join(atomos_nombres),  # Mantener orden original
            'Residuo_Nombre': residuo_info['residuo_nombre'],
            'Residuo_Numero': residuo_info['residuo_numero'],
            'Cadena': residuo_info['cadena'],
            'Grado_Promedio': round(grado_promedio, 6),
            'Grado_Maximo': grado_max,
            'Grado_Minimo': grado_min,
            'Densidad_Segmento': round(densidad_segmento, 6),
            'Centralidad_Grado_Promedio': round(degree_cent_avg, 6),
            'Centralidad_Intermediacion_Promedio': round(between_cent_avg, 6),
            'Centralidad_Cercania_Promedio': round(close_cent_avg, 6),
            'Coeficiente_Agrupamiento_Promedio': round(cluster_avg, 6)
        }
        
        segmentos_data.append(segmento_info)
    
    # Ordenar por número de residuo
    segmentos_data.sort(key=lambda x: (x['Cadena'], x['Residuo_Numero'] if isinstance(x['Residuo_Numero'], int) else 999))
    
    print(f"Segmentación completada: {len(segmentos_data)} residuos procesados")
    
    return pd.DataFrame(segmentos_data)


def agrupar_por_segmentos(G, granularity="atom"):
    """
    Función principal de segmentación que decide el método según la granularidad
    """
    if granularity == "atom":
        return agrupar_por_segmentos_atomicos(G, granularity)
    
    # Para granularidad CA, devolver análisis por residuo individual
    segmentos = []
    for node, data in G.nodes(data=True):
        chain = data.get('chain_id', 'A')
        residue_name = data.get('residue_name', 'UNK')
        residue_number = data.get('residue_number', 1)
            
        segmentos.append({
            'Segmento_ID': f"{chain}:{residue_name}:{residue_number}",
            'Cadena': chain,
            'Residuo_Nombre': residue_name,
            'Residuo_Numero': residue_number,
            'Atomos_Lista': f"{residue_name}{residue_number}:CA",
            'Num_Atomos': 1,
            'Grado_Nodo': G.degree(node)
        })
    
    return pd.DataFrame(segmentos)


def validar_segmentacion(df_segmentos):
    """
    Valida que la segmentación sea correcta y muestra estadísticas.
    """
    if df_segmentos.empty:
        print("DataFrame de segmentos está vacío")
        return False
    
    total_atomos = df_segmentos['Num_Atomos'].sum()
    num_segmentos = len(df_segmentos)
    
    print(f"Validación de segmentación:")
    print(f"   - Total de segmentos: {num_segmentos}")
    print(f"   - Total de átomos procesados: {total_atomos}")
    print(f"   - Segmento más grande: {df_segmentos['Num_Atomos'].max()} átomos")
    print(f"   - Segmento más pequeño: {df_segmentos['Num_Atomos'].min()} átomos")
    print(f"   - Promedio de átomos por segmento: {df_segmentos['Num_Atomos'].mean():.2f}")
    
    return True

def generate_segment_groupings(pdb_path, source, protein_id, long_range, threshold, granularity, toxin_name):
    cfg = ProteinGraphConfig(
        granularity=granularity,
        edge_construction_functions=[
            partial(add_distance_threshold,
                    long_interaction_threshold=long_range,
                    threshold=threshold)
        ]
    )
    G = construct_graph(config=cfg, path=pdb_path)
    G = G.to_undirected()
    return agrupar_por_segmentos(G, granularity=granularity)
