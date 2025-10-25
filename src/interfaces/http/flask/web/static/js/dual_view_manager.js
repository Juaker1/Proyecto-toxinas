class DualViewManager {
    constructor() {
        this.currentStructureView = 'molstar';
        this.dipoleCalculated = false;
        this.currentDatabaseProtein = null;
        this.currentDipoleData = null;
        this.currentAnalysisView = null; // 'graph' o 'dipole'
        
        // Timer para medir carga de datos
        this.loadingTimer = null;
        this.loadingStartTime = null;
        this.structureLoaded = false;
        this.graphLoaded = false;
        this.loadingReportShown = false;
        this.structureLoadTime = null;
        this.graphLoadTime = null;
        
        this.initializeEventListeners();
        this.updatePy3DmolButtonState();
    }

    initializeEventListeners() {
        // View switching for structure panel
        document.getElementById('switch-to-molstar').addEventListener('click', () => {
            this.switchStructureView('molstar');
        });
        
        const py3dmolBtn = document.getElementById('switch-to-py3dmol');
        py3dmolBtn.addEventListener('click', () => {
            if (this.dipoleCalculated) {
                this.switchStructureView('py3dmol');
            }
        });

        // Analysis toggle functionality - Análisis del grafo
        const toggleAnalysisBtn = document.getElementById('toggle-analysis');
        const detailedAnalysis = document.getElementById('detailed-analysis');
        
        if (toggleAnalysisBtn && detailedAnalysis) {
            toggleAnalysisBtn.addEventListener('click', () => {
                this.toggleAnalysisView('graph');
            });
        }

        // Export toggle functionality - Exportar datos
        const toggleExportBtn = document.getElementById('toggle-export');
        const exportDataSection = document.getElementById('export-data-section');
        
        if (toggleExportBtn && exportDataSection) {
            toggleExportBtn.addEventListener('click', () => {
                this.toggleAnalysisView('export');
            });
        }

        // Dipole analysis toggle functionality
        const toggleDipoleBtn = document.getElementById('toggle-dipole-analysis');
        const dipoleCalculations = document.getElementById('dipole-calculations');
        
        if (toggleDipoleBtn && dipoleCalculations) {
            toggleDipoleBtn.addEventListener('click', () => {
                this.toggleAnalysisView('dipole');
            });
        }
    }

    toggleAnalysisView(viewType) {
        const detailedAnalysis = document.getElementById('detailed-analysis');
        const exportDataSection = document.getElementById('export-data-section');
        const dipoleCalculations = document.getElementById('dipole-calculations');
        const toggleAnalysisBtn = document.getElementById('toggle-analysis');
        const toggleExportBtn = document.getElementById('toggle-export');
        const toggleDipoleBtn = document.getElementById('toggle-dipole-analysis');

        if (this.currentAnalysisView === viewType) {
            // Si es la misma vista, ocultarla
            this.hideAllAnalysisViews();
            this.currentAnalysisView = null;
        } else {
            // Cambiar a nueva vista
            this.hideAllAnalysisViews();
            
            if (viewType === 'graph') {
                detailedAnalysis.style.display = 'block';
                detailedAnalysis.classList.add('show');
                toggleAnalysisBtn.innerHTML = '<i class="fas fa-chart-line"></i> Ocultar Análisis Detallado <i class="fas fa-chevron-up toggle-icon"></i>';
                toggleAnalysisBtn.classList.add('expanded');
                
                // Reset other buttons
                if (toggleExportBtn) {
                    toggleExportBtn.innerHTML = '<i class="fas fa-file-export"></i> Mostrar Exportar Datos Completos <i class="fas fa-chevron-down toggle-icon"></i>';
                    toggleExportBtn.classList.remove('expanded');
                }
                if (toggleDipoleBtn) {
                    toggleDipoleBtn.innerHTML = '<i class="fas fa-bolt"></i> Mostrar Cálculos del Dipolo <i class="fas fa-chevron-down toggle-icon"></i>';
                    toggleDipoleBtn.classList.remove('expanded');
                }
                
            } else if (viewType === 'export') {
                exportDataSection.style.display = 'block';
                exportDataSection.classList.add('show');
                toggleExportBtn.innerHTML = '<i class="fas fa-file-export"></i> Ocultar Exportar Datos Completos <i class="fas fa-chevron-up toggle-icon"></i>';
                toggleExportBtn.classList.add('expanded');
                
                // Reset other buttons
                if (toggleAnalysisBtn) {
                    toggleAnalysisBtn.innerHTML = '<i class="fas fa-chart-line"></i> Mostrar Análisis Detallado <i class="fas fa-chevron-down toggle-icon"></i>';
                    toggleAnalysisBtn.classList.remove('expanded');
                }
                if (toggleDipoleBtn) {
                    toggleDipoleBtn.innerHTML = '<i class="fas fa-bolt"></i> Mostrar Cálculos del Dipolo <i class="fas fa-chevron-down toggle-icon"></i>';
                    toggleDipoleBtn.classList.remove('expanded');
                }
                
            } else if (viewType === 'dipole') {
                dipoleCalculations.style.display = 'block';
                dipoleCalculations.classList.add('show');
                toggleDipoleBtn.innerHTML = '<i class="fas fa-bolt"></i> Ocultar Cálculos del Dipolo <i class="fas fa-chevron-up toggle-icon"></i>';
                toggleDipoleBtn.classList.add('expanded');
                
                // Reset other buttons
                if (toggleAnalysisBtn) {
                    toggleAnalysisBtn.innerHTML = '<i class="fas fa-chart-line"></i> Mostrar Análisis Detallado <i class="fas fa-chevron-down toggle-icon"></i>';
                    toggleAnalysisBtn.classList.remove('expanded');
                }
                if (toggleExportBtn) {
                    toggleExportBtn.innerHTML = '<i class="fas fa-file-export"></i> Mostrar Exportar Datos Completos <i class="fas fa-chevron-down toggle-icon"></i>';
                    toggleExportBtn.classList.remove('expanded');
                }
            }
            
            this.currentAnalysisView = viewType;
        }
    }

    hideAllAnalysisViews() {
        const detailedAnalysis = document.getElementById('detailed-analysis');
        const exportDataSection = document.getElementById('export-data-section');
        const dipoleCalculations = document.getElementById('dipole-calculations');
        const toggleAnalysisBtn = document.getElementById('toggle-analysis');
        const toggleExportBtn = document.getElementById('toggle-export');
        const toggleDipoleBtn = document.getElementById('toggle-dipole-analysis');

        // Hide all analysis views
        if (detailedAnalysis) {
            detailedAnalysis.style.display = 'none';
            detailedAnalysis.classList.remove('show');
        }
        
        if (exportDataSection) {
            exportDataSection.style.display = 'none';
            exportDataSection.classList.remove('show');
        }
        
        if (dipoleCalculations) {
            dipoleCalculations.style.display = 'none';
            dipoleCalculations.classList.remove('show');
        }

        // Reset all buttons
        if (toggleAnalysisBtn) {
            toggleAnalysisBtn.innerHTML = '<i class="fas fa-chart-line"></i> Mostrar Análisis Detallado <i class="fas fa-chevron-down toggle-icon"></i>';
            toggleAnalysisBtn.classList.remove('expanded');
        }
        
        if (toggleExportBtn) {
            toggleExportBtn.innerHTML = '<i class="fas fa-file-export"></i> Mostrar Exportar Datos Completos <i class="fas fa-chevron-down toggle-icon"></i>';
            toggleExportBtn.classList.remove('expanded');
        }
        
        if (toggleDipoleBtn) {
            toggleDipoleBtn.innerHTML = '<i class="fas fa-bolt"></i> Mostrar Cálculos del Dipolo <i class="fas fa-chevron-down toggle-icon"></i>';
            toggleDipoleBtn.classList.remove('expanded');
        }
    }

    switchStructureView(viewType) {
        // Solo permitir cambio a py3Dmol si el dipolo está calculado
        if (viewType === 'py3dmol' && !this.dipoleCalculated) {
            console.log("Cannot switch to py3Dmol: dipole not calculated");
            return;
        }

        // Update active button
        document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
        document.getElementById(`switch-to-${viewType}`).classList.add('active');

        // Hide all viewers
        document.querySelectorAll('.structure-viewer').forEach(viewer => {
            viewer.classList.remove('active');
            viewer.style.display = 'none';
        });

        // Show selected viewer
        let targetViewer;
        switch(viewType) {
            case 'molstar':
                targetViewer = document.getElementById('viewer');
                break;
            case 'py3dmol':
                targetViewer = document.getElementById('py3dmol-dipole-viewer');
                // Si cambiamos a py3Dmol y el dipolo está calculado, asegurarse de que se muestre
                if (this.dipoleCalculated && this.currentDipoleData) {
                    setTimeout(() => this.ensureDipoleVisible(), 100);
                }
                break;
        }

        if (targetViewer) {
            targetViewer.classList.add('active');
            targetViewer.style.display = 'block';
        }

        this.currentStructureView = viewType;
        console.log(`Switched to ${viewType} view`);
    }

    updatePy3DmolButtonState() {
        const py3dmolBtn = document.getElementById('switch-to-py3dmol');
        if (py3dmolBtn) {
            if (this.dipoleCalculated) {
                py3dmolBtn.disabled = false;
                py3dmolBtn.style.opacity = '1';
                py3dmolBtn.style.cursor = 'pointer';
                py3dmolBtn.title = 'Ver estructura con dipolo en py3Dmol';
            } else {
                py3dmolBtn.disabled = true;
                py3dmolBtn.style.opacity = '0.5';
                py3dmolBtn.style.cursor = 'not-allowed';
                py3dmolBtn.title = 'Calcule el dipolo primero para habilitar esta vista';
            }
        }
    }

    updateStructureLabel(text) {
        const label = document.getElementById('current-structure-label');
        if (label) {
            label.textContent = text;
        }
    }

    updateGraphAnalysisLabel(proteinName) {
        const label = document.getElementById('graph-analysis-protein');
        if (label) {
            label.textContent = proteinName;
        }
    }

    // Called when a protein is selected from the database
    onDatabaseProteinSelected(group, id, name) {
        this.currentDatabaseProtein = { group, id, name };
        
        // Reset dipole state when changing protein
        this.resetDipoleState();
        
        // Update graph analysis label
        this.updateGraphAnalysisLabel(name || `${group}_${id}`);
        
        // Update structure label
        this.updateStructureLabel(`Base de datos: ${name || `${group}_${id}`}`);
        
        // Show/hide dipole button based on group
        const dipoleToggleBtn = document.getElementById('toggle-dipole-analysis');
        const dipoleStatusContainer = document.getElementById('dipole-status-container');
        
        if (group === 'nav1_7') {
            if (dipoleToggleBtn) dipoleToggleBtn.style.display = 'block';
            if (dipoleStatusContainer) dipoleStatusContainer.style.display = 'flex';
        } else {
            if (dipoleToggleBtn) dipoleToggleBtn.style.display = 'none';
            if (dipoleStatusContainer) dipoleStatusContainer.style.display = 'none';
            // Hide dipole analysis if it's currently shown
            if (this.currentAnalysisView === 'dipole') {
                this.hideAllAnalysisViews();
                this.currentAnalysisView = null;
            }
        }
        
        // Iniciar timer de carga
        this.startLoadingTimer(name || `${group}_${id}`);
    }

    // Called when a local structure file is loaded
    onLocalStructureLoaded(fileName) {
        // Reset dipole state when changing to local file
        this.resetDipoleState();
        
        // Update labels
        this.updateGraphAnalysisLabel(`Archivo local: ${fileName}`);
        this.updateStructureLabel(`Archivo local: ${fileName}`);
        
        // Iniciar timer para archivo local
        this.startLoadingTimer(`Archivo local: ${fileName}`);
        
        // Hide dipole controls for local files (unless PSF is also loaded)
        const dipoleToggleBtn = document.getElementById('toggle-dipole-analysis');
        const dipoleStatusContainer = document.getElementById('dipole-status-container');
        
        if (dipoleToggleBtn) dipoleToggleBtn.style.display = 'none';
        if (dipoleStatusContainer) dipoleStatusContainer.style.display = 'none';
    }
    
    // Called when a PSF file is loaded
    onPSFLoaded(fileName) {
        // Enable dipole controls when PSF is loaded
        const dipoleToggleBtn = document.getElementById('toggle-dipole-analysis');
        const dipoleStatusContainer = document.getElementById('dipole-status-container');
        
        if (dipoleToggleBtn) dipoleToggleBtn.style.display = 'block';
        if (dipoleStatusContainer) dipoleStatusContainer.style.display = 'flex';
    }

    // Update dipole details in the analysis panel
    updateDipoleDetails(dipoleData) {
        // Update detailed dipole information
        document.getElementById('dipole-magnitude-detail').textContent = 
            dipoleData.magnitude.toFixed(3);
        
        document.getElementById('dipole-angle-z-detail').textContent = 
            dipoleData.angle_with_z_axis.degrees.toFixed(1);
        
        document.getElementById('dipole-direction-detail').textContent = 
            `[${dipoleData.normalized.map(x => x.toFixed(3)).join(', ')}]`;
        
        document.getElementById('dipole-center-detail').textContent = 
            `[${dipoleData.center_of_mass.map(x => x.toFixed(2)).join(', ')}]`;
        
        document.getElementById('dipole-endpoint-detail').textContent = 
            `[${dipoleData.end_point.map(x => x.toFixed(2)).join(', ')}]`;

        // Update technical information
        document.getElementById('dipole-method').textContent = 
            dipoleData.method || 'Cálculo PSF/BioPython';
        
        document.getElementById('dipole-vector-raw').textContent = 
            `[${dipoleData.vector.map(x => x.toFixed(3)).join(', ')}]`;
        
        document.getElementById('dipole-angle-radians').textContent = 
            dipoleData.angle_with_z_axis.radians.toFixed(4);
        
        document.getElementById('dipole-protein-name').textContent = 
            this.currentDatabaseProtein ? this.currentDatabaseProtein.name : 'Proteína actual';
    }

    // Reset dipole state when changing proteins
    resetDipoleState() {
        this.dipoleCalculated = false;
        this.currentDipoleData = null;
        this.updatePy3DmolButtonState();
        
        // Switch back to Mol* if currently on py3Dmol
        if (this.currentStructureView === 'py3dmol') {
            this.switchStructureView('molstar');
        }

        // Hide dipole analysis if it's currently shown
        if (this.currentAnalysisView === 'dipole') {
            this.hideAllAnalysisViews();
            this.currentAnalysisView = null;
        }
    }

    // Método llamado cuando se calcula el dipolo
    onDipoleCalculated(dipoleData) {
        this.dipoleCalculated = true;
        this.currentDipoleData = dipoleData;
        
        // Actualizar el estado del botón py3Dmol
        this.updatePy3DmolButtonState();
        
        // Actualizar los detalles del dipolo en la interfaz
        this.updateDipoleDetails(dipoleData);
        
        // Mostrar la vista de análisis del dipolo si no está visible
        if (this.currentAnalysisView !== 'dipole') {
            this.toggleAnalysisView('dipole');
        }
        
        console.log('Dipole calculated and UI updated:', dipoleData);
    }

    // Create py3Dmol visualization with dipole automatically
    async createPy3DmolWithDipole() {
        try {
            if (!this.currentDipoleData || !this.currentDatabaseProtein) {
                throw new Error("Missing dipole data or protein information");
            }

            // Get PDB text for py3Dmol
            const pdbResponse = await fetch(`/v2/structures/${this.currentDatabaseProtein.group}/${this.currentDatabaseProtein.id}/pdb`);
            const pdbText = await pdbResponse.text();
            
            // Create py3Dmol visualization with dipole
            await window.molstarAnalyzer.showDipoleInPy3Dmol(this.currentDipoleData, pdbText);
            
            console.log("py3Dmol visualization with dipole created automatically");
            
        } catch (error) {
            console.error("Error creating py3Dmol visualization:", error);
        }
    }

    // Ensure dipole is visible when switching to py3Dmol
    async ensureDipoleVisible() {
        if (this.currentDipoleData && this.currentDatabaseProtein) {
            try {
                const pdbResponse = await fetch(`/v2/structures/${this.currentDatabaseProtein.group}/${this.currentDatabaseProtein.id}/pdb`);
                const pdbText = await pdbResponse.text();
                
                await window.molstarAnalyzer.showDipoleInPy3Dmol(this.currentDipoleData, pdbText);
                
                // También actualizar la información mostrada
                if (this.currentDipoleData.angle_with_z_axis) {
                    console.log(`Dipole angle with Z-axis: ${this.currentDipoleData.angle_with_z_axis.degrees.toFixed(1)}°`);
                }
                
            } catch (error) {
                console.error("Error ensuring dipole visibility:", error);
            }
        }
    }

    // Auto-update graph when database protein changes
    setupAutoGraphUpdate() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' && mutation.target.id === 'graph-plot') {
                    // Graph has been updated
                    console.log('Graph visualization updated');
                }
            });
        });
        
        const graphElement = document.getElementById('graph-plot');
        if (graphElement) {
            observer.observe(graphElement, {
                childList: true,
                subtree: true
            });
        }
    }

    // ===== MÉTODOS DEL TIMER DE CARGA =====
    
    // Iniciar el timer de carga cuando se selecciona una proteína
    startLoadingTimer(proteinName) {
        // Limpiar timer anterior si existe
        if (this.loadingTimer) {
            clearTimeout(this.loadingTimer);
        }
        
        // Reset timer state antes de iniciar uno nuevo
        this.loadingStartTime = performance.now();
        this.structureLoaded = false;
        this.graphLoaded = false;
        this.loadingReportShown = false;
        this.structureLoadTime = null;
        this.graphLoadTime = null;
        
        console.log(`⏱️ INICIANDO CARGA DE DATOS PARA: ${proteinName}`);
        console.log(`📊 Componentes a cargar: [Vista 3D Mol*, Análisis de Grafo]`);
        
        // Obtener estadísticas del caché
        this.logCacheStats();
        
        // Timeout de seguridad (30 segundos máximo)
        this.loadingTimer = setTimeout(() => {
            this.showLoadingResults(true);
        }, 30000);
    }
    
    // Marcar cuando la estructura 3D se ha cargado
    markStructureLoaded() {
        this.structureLoaded = true;
        this.structureLoadTime = performance.now() - this.loadingStartTime;
        console.log(`✅ Vista 3D Mol* CARGADA (${this.structureLoadTime.toFixed(2)}ms)`);
        this.checkLoadingComplete();
    }
    
    // Marcar cuando el grafo se ha cargado
    markGraphLoaded() {
        this.graphLoaded = true;
        this.graphLoadTime = performance.now() - this.loadingStartTime;
        console.log(`✅ Análisis de Grafo CARGADO (${this.graphLoadTime.toFixed(2)}ms)`);
        this.checkLoadingComplete();
    }
    
    // Verificar si ambos componentes han terminado de cargar
    checkLoadingComplete() {
        if (this.structureLoaded && this.graphLoaded) {
            this.showLoadingResults(false);
        }
    }
    
    // Mostrar resultados finales del timer
    showLoadingResults(timeout = false) {
        if (!this.loadingStartTime || this.loadingReportShown) {
            return;
        }
        
        // Marcar que ya se mostró el reporte
        this.loadingReportShown = true;
        
        const endTime = performance.now();
        const totalTime = endTime - this.loadingStartTime;
        const proteinName = this.currentDatabaseProtein ? 
            (this.currentDatabaseProtein.name || `${this.currentDatabaseProtein.group}_${this.currentDatabaseProtein.id}`) : 
            'Proteína desconocida';
        
        // Limpiar timer
        if (this.loadingTimer) {
            clearTimeout(this.loadingTimer);
            this.loadingTimer = null;
        }
        
        // Mostrar resultados en consola de manera simple y profesional
        console.log(`TIMER DE CARGA COMPLETADO
Proteína: ${proteinName}
Tiempo Total: ${totalTime.toFixed(2)} ms${timeout ? ' (TIMEOUT)' : ''}

COMPONENTES CARGADOS:
• Vista 3D Mol*: ${this.structureLoaded ? `${this.structureLoadTime?.toFixed(2)}ms` : 'PENDIENTE'}
• Análisis de Grafo: ${this.graphLoaded ? `${this.graphLoadTime?.toFixed(2)}ms` : 'PENDIENTE'}

Estado: ${this.structureLoaded && this.graphLoaded ? 'TODOS LOS DATOS CARGADOS' : 'CARGA INCOMPLETA'}`);
        
        // Log adicional para análisis
        console.log(`📈 Resumen de carga - ${proteinName}:`, {
            proteina: proteinName,
            tiempoTotal: `${totalTime.toFixed(2)}ms`,
            componentes: {
                vista3D: {
                    cargado: this.structureLoaded,
                    tiempo: this.structureLoadTime ? `${this.structureLoadTime.toFixed(2)}ms` : null
                },
                grafo: {
                    cargado: this.graphLoaded,
                    tiempo: this.graphLoadTime ? `${this.graphLoadTime.toFixed(2)}ms` : null
                }
            },
            completo: this.structureLoaded && this.graphLoaded,
            timeout: timeout
        });
        
        // NO resetear el estado aquí - se resetea cuando se inicia un nuevo timer
    }
    
    // ===== MÉTODOS DE ESTADÍSTICAS DE CACHÉ =====
    
    // Mostrar estadísticas del caché en consola
    async logCacheStats() {
        try {
            const response = await fetch('/v2/cache/stats');
            const data = await response.json();
            
            if (data.cache_stats) {
                const stats = data.cache_stats;
                console.log(`💾 ESTADÍSTICAS DEL CACHÉ:
• Grafos almacenados: ${stats.graphs}
• Estructuras 3D: ${stats.structures}
• Vistas previas: ${stats.previews}
• Tamaño total: ${stats.total_size_mb} MB

📈 Sistema de caché: ${data.cache_enabled ? 'ACTIVADO' : 'DESACTIVADO'}`);
            }
        } catch (error) {
            console.log('💾 Sistema de caché: No disponible');
        }
    }
}

function initializeDualViewManager() {
    if (window.dualViewManager) {
        return;
    }
    window.dualViewManager = new DualViewManager();
    window.dualViewManager.setupAutoGraphUpdate();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeDualViewManager, { once: true });
} else {
    initializeDualViewManager();
}