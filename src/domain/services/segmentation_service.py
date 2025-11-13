from typing import Any
from numbers import Number
import networkx as nx
import pandas as pd


def _to_hashable_residue_number(value: Any) -> Any:
    """Return a hashable representation for residue numbering.

    Prefers integers when possible; otherwise falls back to trimmed strings.
    """
    if value is None:
        return '?'

    # Handle numpy scalars transparently
    try:  # noqa: SIM105 - using try keeps numpy optional
        import numpy as np  # local import to avoid hard dependency when unavailable
        if isinstance(value, np.generic):
            return _to_hashable_residue_number(value.item())
    except Exception:
        np = None  # type: ignore[assignment]

    if isinstance(value, Number):
        # Convert floats that are effectively integers
        if isinstance(value, float) and not value.is_integer():
            return round(value, 4)
        try:
            return int(value)
        except Exception:
            return value

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return '?'
        try:
            return int(stripped)
        except Exception:
            return stripped

    if isinstance(value, dict):
        for key in ('residue_number', 'seq_id', 'resSeq', 'number', 'id', 'residue_index'):
            if key in value and value[key] not in (None, ''):
                candidate = _to_hashable_residue_number(value[key])
                if candidate not in (None, '?'):
                    return candidate
        return str(value)

    if hasattr(value, 'item'):
        try:
            return _to_hashable_residue_number(value.item())
        except Exception:
            return str(value)

    return str(value)


def _residue_seq_index(value: Any) -> int | None:
    """Extract an integer sequence index when possible."""
    normalized = _to_hashable_residue_number(value)
    try:
        return int(normalized)  # Works for ints or numeric strings
    except Exception:
        return None


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

        res_num_norm = _to_hashable_residue_number(res_num)

        if not atom_name:
            # si no hay nombre de átomo, omitir (como legacy)
            continue

        key = f"{chain}_{res_num_norm}"
        bucket = residuos_atomicos.setdefault(key, {
            'cadena': chain,
            'residuo_nombre': res_name,
            'residuo_numero': res_num_norm,
            'atomos': []
        })
        bucket['atomos'].append({'nodo': nodo, 'atomo_nombre': atom_name})

    segmentos_data = []
    for key, residuo_info in residuos_atomicos.items():
        res_num = residuo_info['residuo_numero']
        res_num_int = _residue_seq_index(res_num)

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

        # Calcular métricas de vecinos externas y distancias secuenciales
        vecinos_map: dict[tuple, set[str]] = {}
        vecinos_conexiones = 0
        sequential_distances: list[float] = []
        long_contacts = 0

        for atom_node in atom_nodes:
            for neighbor in G.neighbors(atom_node):
                neighbor_data = G.nodes[neighbor]
                neighbor_chain = neighbor_data.get('chain_id', 'A')
                neighbor_res_name = neighbor_data.get('residue_name', 'UNK')
                neighbor_res_num = neighbor_data.get('residue_number')
                neighbor_res_norm = _to_hashable_residue_number(neighbor_res_num)
                neighbor_atom = neighbor_data.get('atom_type') or neighbor_data.get('atom_name')

                neighbor_key = (neighbor_chain, neighbor_res_name, neighbor_res_norm)
                if neighbor_key == (residuo_info['cadena'], residuo_info['residuo_nombre'], residuo_info['residuo_numero']):
                    continue

                vecinos_conexiones += 1
                bucket = vecinos_map.setdefault(neighbor_key, set())
                if neighbor_atom:
                    bucket.add(str(neighbor_atom))

                neighbor_seq_index = _residue_seq_index(neighbor_res_norm)
                if res_num_int is not None and neighbor_seq_index is not None:
                    try:
                        seq_distance = abs(neighbor_seq_index - res_num_int)
                        sequential_distances.append(seq_distance)
                        if seq_distance > 5:
                            long_contacts += 1
                    except (TypeError, ValueError):
                        pass

        vecinos_base = []
        vecinos_detalle = []
        for (n_chain, n_name, n_num), atoms in vecinos_map.items():
            base = f"{n_chain}:{n_name}:{n_num}"
            vecinos_base.append(base)
            if atoms:
                detalle = f"{base} ({', '.join(sorted(atoms))})"
            else:
                detalle = base
            vecinos_detalle.append(detalle)

        vecinos_base.sort()
        vecinos_detalle.sort()

        if sequential_distances:
            distancia_promedio = sum(sequential_distances) / len(sequential_distances)
        else:
            distancia_promedio = 0.0

        if vecinos_conexiones:
            proporcion_largos = long_contacts / vecinos_conexiones
        else:
            proporcion_largos = 0.0

        # Normalize position to integer when possible for consistency
        pos_seq = residuo_info['residuo_numero']
        pos_int = _residue_seq_index(pos_seq)
        posicion_val = pos_int if pos_int is not None else pos_seq

        identificador_segmento = f"{residuo_info['cadena']}:{residuo_info['residuo_nombre']}:{posicion_val}"

        segmentos_data.append({
            # Identificador alineado al reporte por residuos
            'Identificador_Segmento': identificador_segmento,
            'Cadena': residuo_info['cadena'],
            'Aminoacido': residuo_info['residuo_nombre'],
            'Posicion_Secuencia': posicion_val,

            # Composición y conectividad
            'Num_Atomos': num_atomos,
            'Atomos_Lista': ', '.join(atom_names),
            'Conexiones_Internas': internal_edges,
            'Numero_Contactos_Externos': vecinos_conexiones,

            # Métricas de estructura local
            'Grado_Promedio': round(grado_promedio, 6),
            'Grado_Maximo': grado_max,
            'Grado_Minimo': grado_min,
            'Densidad_Segmento': round(densidad_segmento, 6),

            # Centralidades (promedios sobre átomos del segmento)
            'Centralidad_Grado_Promedio': round(degree_avg, 6),
            'Centralidad_Intermediacion_Promedio': round(between_avg, 6),
            'Centralidad_Cercania_Promedio': round(close_avg, 6),
            'Coeficiente_Agrupamiento_Promedio': round(cluster_avg, 6),

            # Métricas de contacto y vecindad
            'Distancia_Secuencial_Promedio': round(distancia_promedio, 6),
            'Proporcion_Contactos_Largos': round(proporcion_largos, 6),
            'Residuos_Vecinos': ', '.join(vecinos_base) if vecinos_base else 'Ninguno',
            'Residuos_Vecinos_Detalle': ', '.join(vecinos_detalle) if vecinos_detalle else 'Ninguno',
        })

    def _sort_key(item: dict) -> tuple:
        cadena = item.get('Cadena', '') or ''
        pos_val = item.get('Posicion_Secuencia')
        if isinstance(pos_val, (int, float)):
            return cadena, pos_val
        try:
            return cadena, int(pos_val)
        except Exception:
            return cadena, float('inf')

    segmentos_data.sort(key=_sort_key)
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
