"""
Script de prueba para verificar que:
1. Los números de residuo corresponden a los originales del PDB
2. Se muestran correctamente los vecinos conectados
3. No hay duplicados de GLU:1 (o cualquier otro residuo)
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.infrastructure.graphein.graph_export_service import GraphExportService
from src.infrastructure.exporters.export_service_v2 import ExportService
import pandas as pd


def test_residue_extraction(pdb_path: str, granularity: str = 'CA'):
    """
    Prueba la extracción de datos de residuos
    """
    print(f"\n{'='*80}")
    print(f"Testing {granularity} granularity with: {pdb_path}")
    print(f"{'='*80}\n")
    
    # Construir grafo
    config = GraphExportService.create_graph_config(
        granularity=granularity,
        long_threshold=5,
        distance_threshold=10.0
    )
    G = GraphExportService.construct_protein_graph(pdb_path, config)
    
    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges\n")
    
    # Extraer datos usando el método actualizado
    residue_data = ExportService.extract_residue_data(G, granularity)
    df = pd.DataFrame(residue_data)
    
    print("Columns in DataFrame:")
    print(df.columns.tolist())
    print()
    
    # Verificar duplicados por Identificador_Residuo
    if 'Identificador_Residuo' in df.columns:
        duplicados = df[df.duplicated(subset=['Identificador_Residuo'], keep=False)]
        if not duplicados.empty:
            print("⚠️  WARNING: Se encontraron residuos duplicados!")
            print(duplicados[['Identificador_Residuo', 'Numero_Conexiones', 'Residuos_Vecinos']].head(20))
        else:
            print("✓ No hay residuos duplicados (correcto)")
    
    print()
    
    # Mostrar primeros 10 residuos con sus vecinos
    print("Primeros 10 residuos con sus conexiones:")
    print("-" * 140)
    
    display_cols = ['Identificador_Residuo', 'Numero_Conexiones', 'Residuos_Vecinos']
    if 'Tipo_Atomo' in df.columns:
        display_cols.insert(1, 'Tipo_Atomo')
    
    for idx, row in df.head(10).iterrows():
        if 'Tipo_Atomo' in df.columns:
            print(f"{row['Identificador_Residuo']:20} | Átomo: {row['Tipo_Atomo']:4} | Conexiones: {row['Numero_Conexiones']:3} | "
                  f"Dist.Seq.Prom: {row.get('Distancia_Secuencial_Promedio', 0):5.2f} | Prop.Largos: {row.get('Proporcion_Contactos_Largos', 0):.3f}")
        else:
            print(f"{row['Identificador_Residuo']:15} | Conexiones: {row['Numero_Conexiones']:3} | "
                  f"Dist.Seq.Prom: {row.get('Distancia_Secuencial_Promedio', 0):5.2f} | Prop.Largos: {row.get('Proporcion_Contactos_Largos', 0):.3f} | "
                  f"Vecinos: {row['Residuos_Vecinos'][:60]}")
    
    print()
    
    # Buscar un residuo específico (ej: GLU) y mostrar todas sus instancias
    if 'Aminoacido' in df.columns:
        glu_rows = df[df['Aminoacido'] == 'GLU']
        if not glu_rows.empty:
            print(f"\nTodos los residuos GLU encontrados ({len(glu_rows)} total):")
            print("-" * 140)
            for idx, row in glu_rows.head(20).iterrows():
                print(f"{row['Identificador_Residuo']:15} | Conexiones: {row['Numero_Conexiones']:3} | "
                      f"Betweenness: {row['Centralidad_Intermediacion']:.6f} | "
                      f"Dist.Seq.Prom: {row.get('Distancia_Secuencial_Promedio', 0):5.2f} | "
                      f"Prop.Largos: {row.get('Proporcion_Contactos_Largos', 0):.3f}")
    
    print()
    
    # Verificar rango de números de residuo
    if 'Posicion_Secuencia' in df.columns:
        nums = df['Posicion_Secuencia'].unique()
        print(f"Rango de números de residuo: {min(nums)} - {max(nums)}")
        print(f"Total de residuos únicos: {len(nums)}")
    
    # Análisis de las nuevas métricas
    if 'Distancia_Secuencial_Promedio' in df.columns and 'Proporcion_Contactos_Largos' in df.columns:
        print(f"\n{'='*80}")
        print("ANÁLISIS DE NUEVAS MÉTRICAS:")
        print(f"{'='*80}")
        
        # Top 5 residuos con mayor distancia secuencial promedio (puentes estructurales)
        top_dist = df.nlargest(5, 'Distancia_Secuencial_Promedio')
        print("\nTop 5 residuos que conectan regiones distantes (Distancia_Secuencial_Promedio alta):")
        print("Estos son residuos clave para el plegamiento, conectan partes lejanas de la secuencia")
        print("-" * 100)
        for idx, row in top_dist.iterrows():
            print(f"{row['Identificador_Residuo']:15} | Dist.Seq.Prom: {row['Distancia_Secuencial_Promedio']:5.2f} | "
                  f"Prop.Largos: {row['Proporcion_Contactos_Largos']:.3f} | Conexiones: {row['Numero_Conexiones']}")
        
        # Top 5 residuos con mayor proporción de contactos largos (interfaces)
        top_long = df.nlargest(5, 'Proporcion_Contactos_Largos')
        print("\nTop 5 residuos en interfaces/superficies (Proporcion_Contactos_Largos alta):")
        print("Estos residuos están en regiones de unión o superficies expuestas")
        print("-" * 100)
        for idx, row in top_long.iterrows():
            print(f"{row['Identificador_Residuo']:15} | Prop.Largos: {row['Proporcion_Contactos_Largos']:.3f} | "
                  f"Dist.Seq.Prom: {row['Distancia_Secuencial_Promedio']:5.2f} | Conexiones: {row['Numero_Conexiones']}")
    
    return df


if __name__ == '__main__':
    # Probar con un PDB de ejemplo
    # Ajusta esta ruta según tu estructura de archivos
    test_pdbs = [
        r"C:\Users\Deux\Desktop\Tesis\pdbs\ω-TRTX-Gr2a_F5A.pdb",
        r"C:\Users\Deux\Desktop\Tesis\pdbs\μ-TRTX-Hh2a.pdb",
        r"C:\Users\Deux\Desktop\Tesis\pdbs\filtered_aligned\A0A0J9X1W9.pdb",
        r"C:\Users\Deux\Desktop\Tesis\cache\structures\nav1_7\7.pdb",
    ]
    
    for pdb_path in test_pdbs:
        if os.path.exists(pdb_path):
            print(f"\n\n{'#'*80}")
            print(f"# Testing with: {os.path.basename(pdb_path)}")
            print(f"{'#'*80}")
            
            # Probar con CA
            df_ca = test_residue_extraction(pdb_path, granularity='CA')
            
            # Probar con atom para ver la diferencia
            print(f"\n{'='*80}")
            print("Probando también con granularidad ATOM (mostrará átomos individuales)")
            print(f"{'='*80}\n")
            df_atom = test_residue_extraction(pdb_path, granularity='atom')
            
            break
        else:
            print(f"⚠️  PDB not found: {pdb_path}")
    else:
        print("\n❌ No se encontró ningún PDB para probar.")
        print("Por favor, ajusta las rutas en el script.")
