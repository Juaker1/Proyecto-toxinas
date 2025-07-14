class MolstarProteinAnalyzer {
    constructor(plugin) {
        this.plugin = plugin;
        this.currentStructure = null;
        this.currentData = null;
        this.lastStructureData = null;
        this.dipoleShape = null;
        // Remover loadedFiles ya que no manejamos archivos locales
    }

    // Metodo principal para analizar la estructura actual
    async analyzeCurrentStructure() {
        try {
            const structureData = await this.extractStructureData();
            this.lastStructureData = structureData; // Guardar para uso posterior
            return await this.performAnalysis(structureData);
        } catch (error) {
            console.error("Error analyzing structure:", error);
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
        const labels = [];
        
        const structureView = structure.root;
        const atomIt = structureView.getAtomIterator();
        
        let i = 0;
        while (atomIt.hasNext) {
            const atom = atomIt.move();
            
            const x = atom.x;
            const y = atom.y;
            const z = atom.z;

            const atomName = atomIt.label_atom_id.value(i);
            const residueName = atomIt.auth_comp_id.value(i);
            const residueNumber = atomIt.auth_seq_id.value(i);
            const chainId = atomIt.label_asym_id.value(i);

            const label = `${chainId}:${residueName}:${residueNumber}:${atomName}`;
            labels.push(label);

            atoms.push({
                index: i,
                name: atomName,
                residueIndex: atomIt.residue_index.value(i),
                residueName: residueName,
                residueNumber: residueNumber,
                chainId: chainId,
                coordinates: [x, y, z],
                label: label
            });

            i++;
        }

        return { atoms, labels };
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
        const r = residues[index];
        if (r && r.id && r.name && r.chainId) {
            const key = `${r.chainId}:${r.name}:${r.id}:CA`;
            obj[key] = value;
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





    getTop5(metric) {
        const entries = Object.entries(metric);
        if (entries.length === 0) return [];
        
        // Ordenar por valor de métrica (descendente)
        entries.sort((a, b) => b[1] - a[1]);
        
        // Tomar los 5 primeros y formatear correctamente
        return entries.slice(0, 5).map(([residueKey, value]) => {
            const parts = residueKey.split(':');
            if (parts.length >= 3) {
                return {
                    residue: parts[2],              // ID del residuo (número)
                    value,
                    residueName: parts[1],          // Nombre del aminoácido (VAL, LYS, etc.)
                    chain: parts[0]                 // Cadena (A, B, etc.)
                };
            } else {
                return {
                    residue: residueKey,
                    value,
                    residueName: 'UNK',
                    
                };
            }
        });
    }

    /**
     * Encuentra un residuo por su ID
     */
    findResidueById(id) {
        return this.lastStructureData?.residues?.find(r => r.id === id);
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

    /**
     * Show dipole using py3Dmol visualization - simplificado para BD
     */
    async showDipoleInPy3Dmol(dipoleData, pdbText) {
        try {
            console.log("Creating py3Dmol visualization with dipole vector from database");
            
            // Get or create py3Dmol container
            const py3dmolDiv = this.getOrCreatePy3DmolDiv();
            
            // Clear any existing viewer
            const container = document.getElementById('py3dmol-container');
            container.innerHTML = '';
            
            // Create py3Dmol viewer
            const viewer = $3Dmol.createViewer(container, {
                defaultcolors: $3Dmol.rasmolElementColors,
                backgroundColor: 'white'
            });
            
            // Add protein structure
            viewer.addModel(pdbText, "pdb");
            
            // Set protein style - cartoon representation
            viewer.setStyle({}, {
                cartoon: {
                    color: 'spectrum',
                    thickness: 0.5,
                    opacity: 0.8
                }
            });
            
            // Add dipole vector as arrow
            this.addDipoleArrowToPy3Dmol(viewer, dipoleData);
            
            // Render and adjust view
            viewer.zoomTo();
            viewer.render();
            
            // Store viewer reference
            this.py3dmolViewer = viewer;
            
            console.log("py3Dmol visualization created successfully");
            
        } catch (error) {
            console.error("Error creating py3Dmol visualization:", error);
            throw error;
        }
    }

    /**
     * Add dipole arrow to py3Dmol viewer - versión mejorada
     */
    addDipoleArrowToPy3Dmol(viewer, dipoleData) {
        const start = dipoleData.center_of_mass;
        const end = dipoleData.end_point;
        
        // Add arrow shape for dipole vector
        viewer.addArrow({
            start: { x: start[0], y: start[1], z: start[2] },
            end: { x: end[0], y: end[1], z: end[2] },
            radius: 1.0,
            radiusRatio: 1.5,
            mid: 0.8,
            color: 'red'
        });
        
        // Add sphere at center of mass
        viewer.addSphere({
            center: { x: start[0], y: start[1], z: start[2] },
            radius: 2.0,
            color: 'red',
            alpha: 0.8
        });
        
        // Add comprehensive label at the arrow tip
        const dipoleInfo = `Vector Dipolo
Magnitud: ${dipoleData.magnitude.toFixed(2)} D
Ángulo Z: ${dipoleData.angle_with_z_axis.degrees.toFixed(1)}°
Dirección: [${dipoleData.normalized.map(x => x.toFixed(2)).join(', ')}]`;
        
        viewer.addLabel(dipoleInfo, {
            position: { x: end[0] + 2, y: end[1] + 2, z: end[2] + 2 },
            backgroundColor: 'rgba(220, 53, 69, 0.9)',
            fontColor: 'white',
            fontSize: 11,
            showBackground: true,
            alignment: 'center'
        });
        
        // Add center of mass label with coordinates
        viewer.addLabel(`Centro de Masa
[${start[0].toFixed(1)}, ${start[1].toFixed(1)}, ${start[2].toFixed(1)}]`, {
            position: { x: start[0] - 2, y: start[1] - 2, z: start[2] - 2 },
            backgroundColor: 'rgba(23, 162, 184, 0.9)',
            fontColor: 'white',
            fontSize: 9,
            showBackground: true,
            alignment: 'center'
        });
        
        // Add Z-axis reference line for visual reference
        const zAxisStart = { x: start[0], y: start[1], z: start[2] };
        const zAxisEnd = { x: start[0], y: start[1], z: start[2] + 15 };
        
        viewer.addArrow({
            start: zAxisStart,
            end: zAxisEnd,
            radius: 0.4,
            radiusRatio: 1.3,
            mid: 0.85,
            color: 'blue',
            alpha: 0.6
        });
        
        // Add Z-axis label
        viewer.addLabel('Eje Z (referencia)', {
            position: { x: zAxisEnd.x, y: zAxisEnd.y, z: zAxisEnd.z + 2 },
            backgroundColor: 'rgba(0, 123, 255, 0.8)',
            fontColor: 'white',
            fontSize: 8,
            showBackground: true,
            alignment: 'center'
        });
    }

    /**
     * Create py3Dmol container if it doesn't exist
     */
    getOrCreatePy3DmolDiv() {
        let py3dmolDiv = document.getElementById('py3dmol-dipole-viewer');
        if (!py3dmolDiv) {
            // Find the structure view container
            const structureView = document.getElementById('structure-view');
            if (structureView) {
                py3dmolDiv = document.createElement('div');
                py3dmolDiv.id = 'py3dmol-dipole-viewer';
                py3dmolDiv.style.cssText = 'width: 100%; height: 600px; display: none; border: 1px solid #ccc; background: white; position: relative;';
                py3dmolDiv.innerHTML = `
                    <div id="py3dmol-container" style="width: 100%; height: 100%;"></div>
                    <div style="position: absolute; top: 10px; right: 10px; background: rgba(255,255,255,0.9); padding: 10px; border-radius: 5px; font-size: 12px;">
                        <strong>🧬 py3Dmol Visualization</strong><br>
                        🔴 Red Arrow: Dipole Vector<br>
                        🔵 Protein: Cartoon representation
                    </div>
                `;
                structureView.appendChild(py3dmolDiv);
            }
        }
        return py3dmolDiv;
    }

    /**
     * Switch from Mol* to py3Dmol view
     */
    switchToPy3DmolView() {
        const molstarViewer = document.getElementById('viewer');
        const plotlyViewer = document.getElementById('plotly-dipole-viewer');
        const py3dmolViewer = document.getElementById('py3dmol-dipole-viewer');
        
        // Hide other viewers
        if (molstarViewer) molstarViewer.style.display = 'none';
        if (plotlyViewer) plotlyViewer.style.display = 'none';
        
        // Show py3Dmol viewer
        if (py3dmolViewer) py3dmolViewer.style.display = 'block';
        
        // Update button to show "Back to Mol*" option
        const toggleBtn = document.getElementById('toggle-dipole');
        if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fas fa-undo"></i> Volver a Mol*';
            toggleBtn.onclick = () => this.switchBackToMolstar();
        }
    }

    /**
     * Switch back to Mol* viewer
     */
    switchBackToMolstar() {
        const molstarViewer = document.getElementById('viewer');
        const plotlyViewer = document.getElementById('plotly-dipole-viewer');
        const py3dmolViewer = document.getElementById('py3dmol-dipole-viewer');
        
        // Show Mol* viewer
        if (molstarViewer) molstarViewer.style.display = 'block';
        
        // Hide other viewers
        if (plotlyViewer) plotlyViewer.style.display = 'none';
        if (py3dmolViewer) py3dmolViewer.style.display = 'none';
        
        // Reset dipole shape reference
        this.dipoleShape = null;
        this.py3dmolViewer = null;
        
        // Hide dipole info
        const dipoleInfo = document.getElementById('dipole-info');
        if (dipoleInfo) dipoleInfo.style.display = 'none';
        
        // Reset button
        const toggleBtn = document.getElementById('toggle-dipole');
        if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fas fa-arrow-up"></i> Mostrar Dipolo';
            toggleBtn.onclick = null; 
        }
    }
}


    /**
     * VER PARA AGRUPAR
     */
function agruparPorResiduo(atoms) {
    const segmentos = {};
    for (const atom of atoms) {
        const clave = `${atom.chainId}:${atom.residueName}:${atom.residueNumber}`;
        if (!segmentos[clave]) segmentos[clave] = [];
        segmentos[clave].push(atom.label); // A:ALA:15:CB
    }
    return segmentos;
}

window.MolstarProteinAnalyzer = MolstarProteinAnalyzer;