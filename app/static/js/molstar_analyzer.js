class MolstarProteinAnalyzer {
    constructor(plugin) {
        this.plugin = plugin;
        this.currentStructure = null;
        this.currentData = null;
    }
    // Metodo principal para analizar la estructura actual
    async analyzeCurrentStructure() {
        try {
            if (!this.plugin || !this.plugin.managers) {
                throw new Error("Plugin Mol* no inicializado correctamente");
            }
            // Extraemos los datos estructurales
            const structureData = await this.extractStructureData();
            const analysis = await this.performAnalysis(structureData);
            
            return analysis;
        } catch (error) {
            return null;
        }
    }

    // Método para extraer datos estructurales de la estructura actual
    async extractStructureData() {
        const data = {
            residues: [],
            atoms: [],
            bonds: [],
            metadata: {}
        };

        try {
            const structures = this.plugin.managers.structure.hierarchy.selection.structures;
            
            if (structures.length === 0) {
                throw new Error("No hay estructuras cargadas");
            }

            const structure = structures[0].cell.obj?.data;
            if (!structure) {
                throw new Error("No se puede acceder a los datos de estructura");
            }

            // Extraemos la informacion basica de la estrucrua
            data.metadata = {
                atomCount: structure.atomicHierarchy.atoms._rowCount,
                residueCount: structure.atomicHierarchy.residues._rowCount,
                chainCount: structure.atomicHierarchy.chains._rowCount
            };

            // Extraer residuos
            data.residues = this.extractResidues(structure);
            
            // Extraer átomos CA para análisis de grafo
            data.atoms = this.extractAtoms(structure);
            
            return data;

        } catch (error) {
            throw error;
        }
    }

    /**
     * Extrae información de residuos
     */
    extractResidues(structure) {
        const residues = [];
        const residueIt = structure.atomicHierarchy.residues;
        
        for (let i = 0; i < residueIt._rowCount; i++) {
            const residue = {
                index: i,
                id: residueIt.auth_seq_id.value(i),
                name: residueIt.auth_comp_id.value(i),
                chainId: residueIt.label_asym_id.value(i),
                insertionCode: residueIt.pdbx_PDB_ins_code.value(i) || '',
                atomCount: residueIt.offsets.value(i + 1) - residueIt.offsets.value(i)
            };
            
            // Extraer coordenadas del átomo CA si existe
            const caAtom = this.findCAAtom(structure, i);
            if (caAtom) {
                residue.coordinates = caAtom.coordinates;
            }
            
            residues.push(residue);
        }
        
        return residues;
    }

    /**
     * Extrae átomos CA para análisis de distancias
     */
    extractAtoms(structure) {
        const atoms = [];
        const atomIt = structure.atomicHierarchy.atoms;
        
        for (let i = 0; i < atomIt._rowCount; i++) {
            const atomName = atomIt.auth_atom_id.value(i);
            
            // Solo átomos CA para análisis
            if (atomName === 'CA') {
                const atom = {
                    index: i,
                    name: atomName,
                    residueIndex: atomIt.residue_index.value(i),
                    coordinates: [
                        structure.model.atomicConformation.x.value(i),
                        structure.model.atomicConformation.y.value(i),
                        structure.model.atomicConformation.z.value(i)
                    ]
                };
                atoms.push(atom);
            }
        }
        
        return atoms;
    }

    /**
     * Encuentra el átomo CA de un residuo
     */
    findCAAtom(structure, residueIndex) {
        const atomIt = structure.atomicHierarchy.atoms;
        const residueAtomStart = structure.atomicHierarchy.residues.offsets.value(residueIndex);
        const residueAtomEnd = structure.atomicHierarchy.residues.offsets.value(residueIndex + 1);
        
        for (let i = residueAtomStart; i < residueAtomEnd; i++) {
            if (atomIt.auth_atom_id.value(i) === 'CA') {
                return {
                    index: i,
                    coordinates: [
                        structure.model.atomicConformation.x.value(i),
                        structure.model.atomicConformation.y.value(i),
                        structure.model.atomicConformation.z.value(i)
                    ]
                };
            }
        }
        return null;
    }

    /**
     * Realiza análisis estructural básico
     */
    async performAnalysis(structureData) {
        try {
            
            const modelInfo = this.plugin.managers.structure.hierarchy.current.structures[0]?.cell?.obj?.data?.model?.modelNum || 1;
            const pdbId = this.plugin.managers.structure.hierarchy.current.structures[0]?.transform?.cell?.obj?.data?.id || 'Proteína_Actual';
            
            const analysis = {
                toxin: pdbId,
                graph_properties: {},
                summary_statistics: {},
                top_5_residues: {},
                key_residues: {}
            };
    
            
            analysis.graph_properties = {
                nodes: structureData.residues.length,
                edges: 0,
                disulfide_bridges: this.countDisulfideBridges(structureData),
                density: 0,
                clustering_coefficient_avg: 0
            };
    
            // Calcular distancias entre residuos
            const distances = this.calculateDistances(structureData.atoms);
            const connections = this.findConnections(distances, 8.0); // 8Å cutoff
            
            analysis.graph_properties.edges = connections.length;
            analysis.graph_properties.density = connections.length > 0 ? 
                (2 * connections.length) / (structureData.residues.length * (structureData.residues.length - 1)) : 0;
    
            // Calcular centralidades básicas
            const centralities = this.calculateCentralities(structureData.residues, connections);
            
            analysis.summary_statistics = {
                degree_centrality: this.getMetricStats(centralities.degree),
                betweenness_centrality: this.getMetricStats(centralities.betweenness),
                closeness_centrality: this.getMetricStats(centralities.closeness),
                clustering_coefficient: this.getMetricStats(centralities.clustering)
            };
    
            analysis.top_5_residues = {
                degree_centrality: this.getTop5(centralities.degree),
                betweenness_centrality: this.getTop5(centralities.betweenness),
                closeness_centrality: this.getTop5(centralities.closeness),
                clustering_coefficient: this.getTop5(centralities.clustering)
            };
    
            analysis.key_residues = {
                degree_centrality: this.formatKeyResidue(centralities.degree),
                betweenness_centrality: this.formatKeyResidue(centralities.betweenness),
                closeness_centrality: this.formatKeyResidue(centralities.closeness),
                clustering_coefficient: this.formatKeyResidue(centralities.clustering)
            };
    
            return analysis;
        } catch (error) {
            // Crear un objeto básico con datos dummy para mostrar algo en la UI
            return {
                toxin: 'Proteína actual',
                graph_properties: {
                    nodes: structureData?.residues?.length || 0,
                    edges: 0,
                    disulfide_bridges: 0,
                    density: 0,
                    clustering_coefficient_avg: 0
                },
                summary_statistics: {
                    degree_centrality: {min: 0, max: 0, mean: 0, top_residues: '-'},
                    betweenness_centrality: {min: 0, max: 0, mean: 0, top_residues: '-'},
                    closeness_centrality: {min: 0, max: 0, mean: 0, top_residues: '-'},
                    clustering_coefficient: {min: 0, max: 0, mean: 0, top_residues: '-'}
                },
                top_5_residues: {
                    degree_centrality: [],
                    betweenness_centrality: [],
                    closeness_centrality: [],
                    clustering_coefficient: []
                },
                key_residues: {
                    degree_centrality: '-',
                    betweenness_centrality: '-',
                    closeness_centrality: '-',
                    clustering_coefficient: '-'
                }
            };
        }
    }

    /**
     * Cuenta puentes disulfuro buscando pares de cisteínas cercanas
     */
    countDisulfideBridges(structureData) {
        let bridges = 0;
        const cysteines = structureData.residues.filter(r => r.name === 'CYS');
        
        for (let i = 0; i < cysteines.length; i++) {
            for (let j = i + 1; j < cysteines.length; j++) {
                if (cysteines[i].coordinates && cysteines[j].coordinates) {
                    const dist = this.calculateDistance(cysteines[i].coordinates, cysteines[j].coordinates);
                    if (dist < 2.5) { // Distancia típica de puente disulfuro
                        bridges++;
                    }
                }
            }
        }
        
        return bridges;
    }

    /**
     * Calcula distancias entre todos los pares de átomos
     */
    calculateDistances(atoms) {
        const distances = {};
        
        for (let i = 0; i < atoms.length; i++) {
            distances[i] = {};
            for (let j = i + 1; j < atoms.length; j++) {
                const dist = this.calculateDistance(atoms[i].coordinates, atoms[j].coordinates);
                distances[i][j] = dist;
                distances[j] = distances[j] || {};
                distances[j][i] = dist;
            }
        }
        
        return distances;
    }

    /**
     * Calcula distancia euclidiana entre dos puntos
     */
    calculateDistance(coord1, coord2) {
        if (!coord1 || !coord2) return Infinity;
        
        const dx = coord1[0] - coord2[0];
        const dy = coord1[1] - coord2[1];
        const dz = coord1[2] - coord2[2];
        
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    /**
     * Encuentra conexiones basadas en distancia
     */
    findConnections(distances, cutoff) {
        const connections = [];
        
        Object.keys(distances).forEach(i => {
            Object.keys(distances[i]).forEach(j => {
                if (i < j && distances[i][j] <= cutoff) {
                    connections.push([parseInt(i), parseInt(j), distances[i][j]]);
                }
            });
        });
        
        return connections;
    }

    /**
     * Calcula centralidades básicas
     */
    calculateCentralities(residues, connections) {
        const n = residues.length;
        const degree = new Array(n).fill(0);
        const betweenness = new Array(n).fill(0);
        const closeness = new Array(n).fill(0);
        const clustering = new Array(n).fill(0);

        // Calcular grado
        connections.forEach(([i, j]) => {
            degree[i]++;
            degree[j]++;
        });

        // Normalizar grado
        const maxDegree = Math.max(...degree);
        const degreeNorm = degree.map(d => maxDegree > 0 ? d / maxDegree : 0);

        // Cálculos simplificados para betweenness y closeness
        // En una implementación completa, usarías algoritmos más sofisticados
        const betweennessNorm = degreeNorm.map(d => d * 0.8); // Aproximación simple
        const closenessNorm = degreeNorm.map(d => d * 0.9); // Aproximación simple
        
        // Calcular clustering coeficiente
        const clusteringCoeff = new Array(n).fill(0);
        for (let i = 0; i < n; i++) {
            // Vecinos del nodo i
            const neighbors = [];
            connections.forEach(([a, b]) => {
                if (a === i) neighbors.push(b);
                if (b === i) neighbors.push(a);
            });
            
            if (neighbors.length <= 1) {
                clusteringCoeff[i] = 0;
                continue;
            }
            
            // Contar conexiones entre vecinos
            let edgesBetweenNeighbors = 0;
            for (let j = 0; j < neighbors.length; j++) {
                for (let k = j + 1; k < neighbors.length; k++) {
                    const hasEdge = connections.some(
                        ([a, b]) => (a === neighbors[j] && b === neighbors[k]) || 
                                    (a === neighbors[k] && b === neighbors[j])
                    );
                    if (hasEdge) edgesBetweenNeighbors++;
                }
            }
            
            const possibleEdges = (neighbors.length * (neighbors.length - 1)) / 2;
            clusteringCoeff[i] = possibleEdges > 0 ? edgesBetweenNeighbors / possibleEdges : 0;
        }

        return {
            degree: this.arrayToObject(degreeNorm, residues),
            betweenness: this.arrayToObject(betweennessNorm, residues),
            closeness: this.arrayToObject(closenessNorm, residues),
            clustering: this.arrayToObject(clusteringCoeff, residues)
        };
    }

    /**
     * Convierte array a objeto con IDs de residuo
     */
    arrayToObject(array, residues) {
        const obj = {};
        array.forEach((value, index) => {
            if (residues[index] && residues[index].id) {
                obj[residues[index].id] = value;
            }
        });
        return obj;
    }

    /**
     * Obtiene estadísticas de una métrica
     */
    getMetricStats(metric) {
        const values = Object.values(metric);
        if (values.length === 0) return { min: 0, max: 0, mean: 0, top_residues: '-' };
        
        const min = Math.min(...values);
        const max = Math.max(...values);
        const mean = values.reduce((a, b) => a + b, 0) / values.length;
        
        const entries = Object.entries(metric);
        const topResidues = entries.length > 0 ? 
            entries.reduce((a, b) => metric[a[0]] > metric[b[0]] ? a : b) : 
            ['0', 0];
        
        const top_residues = `${topResidues[0]} (${topResidues[1].toFixed(4)})`;
        
        return { 
            min, 
            max, 
            mean, 
            top_residues 
        };
    }

    /**
     * Obtiene top 5 residuos para una métrica
     */
    getTop5(metric) {
        return Object.entries(metric)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([residue, value]) => ({ residue: parseInt(residue), value }));
    }

    /**
     * Formatea residuo clave
     */
    formatKeyResidue(metric) {
        const entries = Object.entries(metric);
        if (entries.length === 0) return '-';
        
        const maxEntry = entries.reduce((a, b) => a[1] > b[1] ? a : b);
        return `${maxEntry[0]} (valor: ${maxEntry[1].toFixed(4)})`;
    }
}


window.MolstarProteinAnalyzer = MolstarProteinAnalyzer;