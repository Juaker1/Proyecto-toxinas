"""
Script de prueba para verificar el cálculo de las nuevas métricas
en el grafo.
"""

import sys
sys.path.insert(0, 'c:\\Users\\Deux\\Desktop\\Tesis')

from src.infrastructure.graph.graphein_adapter import GrapheinGraphAdapter

def test_new_metrics():
    print("=" * 80)
    print("TEST: Verificación de nuevas métricas en grafo")
    print("=" * 80)
    
    # Configuración de prueba
    protein_group = "mu-trtx-hh2a"
    protein_id = "wt"
    granularity = "atom"  # Probando con granularidad atómica
    long_interactions = "1"
    distance_threshold = "4.5"
    
    print(f"\nProtein: {protein_group}/{protein_id}")
    print(f"Granularity: {granularity}")
    print(f"Long interactions: {long_interactions}")
    print(f"Distance threshold: {distance_threshold}")
    
    # Crear adaptador y generar grafo
    print("\n" + "-" * 80)
    print("Generando grafo...")
    print("-" * 80)
    
    adapter = GrapheinGraphAdapter()
    result = adapter.build_graph(
        protein_group=protein_group,
        protein_id=protein_id,
        granularity=granularity,
        long_interactions=long_interactions,
        distance_threshold=distance_threshold
    )
    
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return
    
    print(f"\n✓ Grafo generado exitosamente")
    print(f"  - Nodos: {result['properties']['num_nodes']}")
    print(f"  - Aristas: {result['properties']['num_edges']}")
    
    # Verificar métricas
    centrality = result['properties'].get('centrality', {})
    
    print("\n" + "-" * 80)
    print("Verificando métricas calculadas:")
    print("-" * 80)
    
    metrics = ['degree', 'betweenness', 'closeness', 'clustering', 'seq_distance_avg', 'long_contacts_prop']
    
    for metric_name in metrics:
        metric_data = centrality.get(metric_name, {})
        if metric_data:
            values = list(metric_data.values())
            non_zero = [v for v in values if v > 0]
            
            print(f"\n{metric_name}:")
            print(f"  - Total nodos: {len(metric_data)}")
            print(f"  - Valores > 0: {len(non_zero)}")
            
            if values:
                print(f"  - Min: {min(values):.4f}")
                print(f"  - Max: {max(values):.4f}")
                print(f"  - Promedio: {sum(values)/len(values):.4f}")
                
                # Top 3
                sorted_items = sorted(metric_data.items(), key=lambda x: x[1], reverse=True)[:3]
                print(f"  - Top 3:")
                for node, value in sorted_items:
                    print(f"      {node}: {value:.4f}")
        else:
            print(f"\n{metric_name}: ⚠️  NO HAY DATOS")
    
    print("\n" + "=" * 80)
    print("Test completado")
    print("=" * 80)

if __name__ == "__main__":
    test_new_metrics()
