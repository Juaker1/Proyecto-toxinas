class DualViewManager {
    constructor() {
        this.currentStructureView = 'molstar';
        this.isShowingLoadedStructure = false;
        this.dipoleVisible = false;
        this.currentDatabaseProtein = null;
        this.loadedStructureInfo = null;
        
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // View switching for structure panel
        document.getElementById('switch-to-molstar').addEventListener('click', () => {
            this.switchStructureView('molstar');
        });
        
        document.getElementById('switch-to-py3dmol').addEventListener('click', () => {
            this.switchStructureView('py3dmol');
        });
        
        // Sync structure button
        document.getElementById('sync-structure-btn').addEventListener('click', () => {
            this.syncWithDatabaseProtein();
        });

        // Analysis toggle functionality
        const toggleAnalysisBtn = document.getElementById('toggle-analysis');
        const detailedAnalysis = document.getElementById('detailed-analysis');
        
        if (toggleAnalysisBtn && detailedAnalysis) {
            toggleAnalysisBtn.addEventListener('click', () => {
                const isVisible = detailedAnalysis.style.display !== 'none';
                
                if (isVisible) {
                    detailedAnalysis.style.display = 'none';
                    toggleAnalysisBtn.innerHTML = '📈 Mostrar Análisis Detallado <span class="toggle-icon">▼</span>';
                    toggleAnalysisBtn.classList.remove('expanded');
                } else {
                    detailedAnalysis.style.display = 'block';
                    detailedAnalysis.classList.add('show');
                    toggleAnalysisBtn.innerHTML = '📊 Ocultar Análisis Detallado <span class="toggle-icon">▲</span>';
                    toggleAnalysisBtn.classList.add('expanded');
                }
            });
        }
    }

    switchStructureView(viewType) {
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
                break;
        }

        if (targetViewer) {
            targetViewer.classList.add('active');
            targetViewer.style.display = 'block';
        }

        this.currentStructureView = viewType;
        console.log(`Switched to ${viewType} view`);
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
        
        // Update graph analysis label
        this.updateGraphAnalysisLabel(name || `${group}_${id}`);
        
        // If not showing loaded structure, sync the 3D view
        if (!this.isShowingLoadedStructure) {
            this.updateStructureLabel(`Base de datos: ${name || `${group}_${id}`}`);
        }
    }

    // Called when a local PDB is loaded
    onLocalStructureLoaded(filename) {
        this.loadedStructureInfo = { filename };
        this.isShowingLoadedStructure = true;
        
        // Update structure label
        this.updateStructureLabel(`Archivo local: ${filename}`);
        
        // Enable PSF and dipole buttons
        document.getElementById('load-psf-btn').disabled = false;
        
        console.log(`Local structure loaded: ${filename}`);
    }

    // Called when PSF is loaded
    onPSFLoaded(filename) {
        document.getElementById('toggle-dipole').disabled = false;
        console.log(`PSF loaded: ${filename}`);
    }

    // Sync 3D view with currently selected database protein
    async syncWithDatabaseProtein() {
        if (!this.currentDatabaseProtein) {
            alert('No hay proteína seleccionada en la base de datos');
            return;
        }

        try {
            // Load the database protein in the 3D viewer
            await this.loadDatabaseProteinIn3D(
                this.currentDatabaseProtein.group, 
                this.currentDatabaseProtein.id
            );
            
            this.isShowingLoadedStructure = false;
            this.updateStructureLabel(`Base de datos: ${this.currentDatabaseProtein.name || `${this.currentDatabaseProtein.group}_${this.currentDatabaseProtein.id}`}`);
            
            // Reset dipole and local file controls
            this.resetDipoleControls();
            
        } catch (error) {
            console.error('Error syncing with database protein:', error);
            alert('Error al sincronizar con la proteína de la base de datos');
        }
    }

    async loadDatabaseProteinIn3D(group, id) {
        // Use the same loading logic as in viewer.js
        try {
            await window.molstarAnalyzer.plugin.plugin?.clear?.();
            await window.molstarAnalyzer.plugin.resetCamera?.();
            await window.molstarAnalyzer.plugin.resetStructure?.();
        } catch (clearError) {
            // Ignore clearing errors
        }

        const res = await fetch(`/get_pdb/${group}/${id}`);
        if (!res.ok) {
            throw new Error(`Error HTTP: ${res.status}`);
        }
        
        const pdbText = await res.text();
        if (!pdbText || !pdbText.includes("ATOM")) {
            throw new Error("PDB inválido o vacío");
        }

        const blob = new Blob([pdbText], { type: 'chemical/x-pdb' });
        const blobUrl = URL.createObjectURL(blob);
        
        try {
            await window.molstarAnalyzer.plugin.loadStructureFromUrl(blobUrl, 'pdb');
        } finally {
            URL.revokeObjectURL(blobUrl);
        }
    }

    // Handle dipole visualization
    async showDipole(dipoleData) {
        try {
            // Try py3Dmol first (best for molecular visualization)
            if (this.currentStructureView === 'py3dmol') {
                await window.molstarAnalyzer.showDipoleInPy3Dmol(dipoleData);
            } else {
                // Mol* view - try to visualize dipole
                await window.molstarAnalyzer.visualizeDipoleVector(dipoleData);
            }
            
            this.dipoleVisible = true;
            this.updateDipoleButton(true);
            
        } catch (error) {
            console.error("Error showing dipole:", error);
            throw error;
        }
    }

    async hideDipole() {
        try {
            await window.molstarAnalyzer.removeDipoleVector();
            this.dipoleVisible = false;
            this.updateDipoleButton(false);
        } catch (error) {
            console.error("Error hiding dipole:", error);
            throw error;
        }
    }

    updateDipoleButton(visible) {
        const toggleBtn = document.getElementById('toggle-dipole');
        if (toggleBtn) {
            if (visible) {
                toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i> Ocultar Dipolo';
            } else {
                toggleBtn.innerHTML = '<i class="fas fa-arrow-up"></i> Mostrar Dipolo';
            }
        }
    }

    resetDipoleControls() {
        // Reset dipole button
        document.getElementById('toggle-dipole').disabled = true;
        this.updateDipoleButton(false);
        
        // Hide dipole info
        document.getElementById('dipole-info').style.display = 'none';
        
        // Reset file upload buttons
        const loadPdbBtn = document.getElementById('load-pdb-btn');
        const loadPsfBtn = document.getElementById('load-psf-btn');
        
        loadPdbBtn.innerHTML = '<i class="fas fa-upload"></i> Cargar PDB';
        loadPdbBtn.style.background = '';
        loadPdbBtn.disabled = false;
        
        loadPsfBtn.innerHTML = '<i class="fas fa-upload"></i> Cargar PSF';
        loadPsfBtn.style.background = '';
        loadPsfBtn.disabled = true;
        
        this.dipoleVisible = false;
        this.loadedStructureInfo = null;
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