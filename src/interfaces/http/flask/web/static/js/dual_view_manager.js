class DualViewManager {
    constructor() {
        this.currentStructureView = 'molstar';
        this.dipoleCalculated = false;
        this.currentDatabaseProtein = null;
        this.currentDipoleData = null;
        this.currentAnalysisView = null; // 'graph' o 'dipole'
        
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
    }

    // Called when dipole calculation is completed
    onDipoleCalculated(dipoleData) {
        this.currentDipoleData = dipoleData;
        this.dipoleCalculated = true;
        this.updatePy3DmolButtonState();
        
        // Update dipole details in the analysis panel
        this.updateDipoleDetails(dipoleData);
        
        // Automatically create py3Dmol visualization with dipole
        this.createPy3DmolWithDipole();
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
}

// Initialize dual view manager when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
    window.dualViewManager = new DualViewManager();
    window.dualViewManager.setupAutoGraphUpdate();
});