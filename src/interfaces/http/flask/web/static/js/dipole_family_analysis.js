// filepath: app/static/js/dipole_family_analysis.js
class DipoleFamilyAnalyzer {
    constructor() {
        console.log('🚀 DipoleFamilyAnalyzer iniciado');
        console.log('🔍 Elementos encontrados:', {
            familySelector: !!document.getElementById('familySelector'),
            visualizeFamilyBtn: !!document.getElementById('visualizeFamilyBtn'),
            loadFamilyDataBtn: !!document.getElementById('loadFamilyDataBtn'),
            familyInfo: !!document.getElementById('familyInfo'),
            familyInfoText: !!document.getElementById('familyInfoText'),
            visualizationArea: !!document.getElementById('visualizationArea'),
            statisticsArea: !!document.getElementById('statisticsArea'),
            selectedFamilyTitle: !!document.getElementById('selectedFamilyTitle'),
            loadingSpinner: !!document.getElementById('loadingSpinner'),
            visualizationPlaceholder: !!document.getElementById('visualizationPlaceholder'),
            peptideList: !!document.getElementById('peptideList'),
            visualizationGrid: !!document.getElementById('visualizationGrid'),
        });
        
        this.familySelector = document.getElementById('familySelector');
        this.visualizeFamilyBtn = document.getElementById('visualizeFamilyBtn');
        this.loadFamilyDataBtn = document.getElementById('loadFamilyDataBtn');
        this.familyInfo = document.getElementById('familyInfo');
        this.familyInfoText = document.getElementById('familyInfoText');
        this.visualizationArea = document.getElementById('visualizationArea');
        this.statisticsArea = document.getElementById('statisticsArea');
        this.selectedFamilyTitle = document.getElementById('selectedFamilyTitle');
        this.loadingSpinner = document.getElementById('loadingSpinner');
        this.visualizationPlaceholder = document.getElementById('visualizationPlaceholder');
        
        // Nuevo elemento para mostrar péptidos
        this.peptideList = document.getElementById('peptideList');
        this.visualizationGrid = document.getElementById('visualizationGrid');
        
        this.currentFamilyData = null;
        
        this.loadFamilyOptions();
        this.initializeEventListeners();
        
    }

    initializeEventListeners() {
        this.familySelector.addEventListener('change', () => {
            this.onFamilySelected();
        });
        
        this.visualizeFamilyBtn.addEventListener('click', () => {
            this.visualizeFamily();
        });
    }
    

    async loadFamilyOptions() {
        try {
            console.log('🔄 Iniciando carga de familias...');
            
            // Usar únicamente el endpoint v2
            const response = await fetch('/v2/families');
            console.log('📡 Response status:', response.status);
            console.log('📡 Response headers:', response.headers);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('📦 Response data:', data);
            
            if (data.success) {
                console.log('✅ Familias encontradas:', data.families.length);
                
                if (data.families.length === 0) {
                    console.warn('⚠️ No se encontraron familias en la respuesta');
                    return;
                }
                
                data.families.forEach((family, index) => {
                    console.log(`👨‍👩‍👧‍👦 Procesando familia ${index + 1}:`, family);
                    const option = document.createElement('option');
                    option.value = family.value;
                    option.textContent = `${family.text} (${family.count} péptidos)`;
                    option.dataset.count = family.count;
                    this.familySelector.appendChild(option);
                });
                
                console.log('✅ Todas las familias procesadas correctamente');
            } else {
                console.error('❌ Error en response:', data.error);
                alert(`Error cargando familias: ${data.error}`);
            }
        } catch (error) {
            console.error('💥 Error cargando familias:', error);
            alert(`Error de conexión: ${error.message}`);
        }
    }

    async onFamilySelected() {
        const selectedFamily = this.familySelector.value;
        const selectedText = this.familySelector.selectedOptions[0].textContent;
        
        if (selectedFamily) {
            // Mostrar información de la familia
            this.familyInfoText.textContent = `Familia seleccionada: ${selectedText}`;
            this.familyInfo.style.display = 'block';
            
            // Cargar péptidos de la familia
            await this.loadFamilyPeptides(selectedFamily);
            
            // Solo habilitar el botón de visualización
            this.visualizeFamilyBtn.disabled = false;
            
            // Actualizar título
            this.selectedFamilyTitle.textContent = selectedText;
        } else {
            this.familyInfo.style.display = 'none';
            this.peptideList.style.display = 'none';
            this.visualizeFamilyBtn.disabled = true;
        }
    }

    async loadFamilyPeptides(familyName) {
        try {
            this.showLoading(true, 'Cargando péptidos de la familia...');
            
            const response = await fetch(`/v2/family-peptides/${familyName}`);
            const data = await response.json();
            
            if (data.success) {
                this.displayPeptideList(data.data);
            }
        } catch (error) {
            console.error('Error cargando péptidos:', error);
        } finally {
            this.showLoading(false);
        }
    }

    displayPeptideList(familyData) {
        const { family_name, family_type, total_count } = familyData;
        
        let listHTML = `
            <div class="peptide-info-container">
                <div class="peptide-info-header">
                    <h6 class="peptide-info-title">
                        <i class="fas fa-list me-2"></i>Péptidos de la Familia
                    </h6>
                    <span class="peptide-count-badge">${total_count} péptidos</span>
                </div>
                
                <div class="peptide-info-content">
        `;
        
        // Manejar familia β-TRTX (múltiples originales)
        if (family_type === 'multiple_originals') {
            const { all_peptides } = familyData;
            
            listHTML += `
                <div class="peptide-section">
                    <div class="section-header">
                        <i class="fas fa-dna me-2"></i>
                        <strong>Todos los Péptidos de la Familia</strong>
                    </div>
                    <div class="table-container">
                        <table class="peptide-table">
                            <thead>
                                <tr>
                                    <th>Código</th>
                                    <th>Secuencia</th>
                                    <th>IC50</th>
                                </tr>
                            </thead>
                            <tbody>
            `;
            
            all_peptides.forEach(peptide => {
                listHTML += `
                    <tr>
                        <td>
                            <span class="peptide-code">${peptide.peptide_code}</span>
                        </td>
                        <td>
                            <div class="sequence-container">
                                <code class="sequence-text-readonly">${peptide.sequence}</code>
                            </div>
                        </td>
                        <td>
                            <span class="ic50-value">
                                ${peptide.ic50_value} ${peptide.ic50_unit}
                            </span>
                        </td>
                    </tr>
                `;
            });
            
            listHTML += `
                    </tbody>
                </table>
            </div>
        </div>
        `;
        } 
        // Manejar familias con original + modificados
        else if (family_type === 'original_plus_modified') {
            const { original_peptide, modified_peptides, modified_count } = familyData;
            
            // Péptido original - AHORA EN FORMATO TABLA
            if (original_peptide) {
                listHTML += `
                    <div class="peptide-section original-section">
                        <div class="section-header original-header">
                            <i class="fas fa-star me-2"></i>
                            <strong>Péptido Original</strong>
                        </div>
                        <div class="table-container">
                            <table class="peptide-table original-table">
                                <thead>
                                    <tr>
                                        <th>Código</th>
                                        <th>Secuencia</th>
                                        <th>IC50</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr class="original-row">
                                        <td>
                                            <span class="peptide-code original-code">${original_peptide.peptide_code}</span>
                                        </td>
                                        <td>
                                            <div class="sequence-container">
                                                <code class="sequence-text-readonly original-sequence">${original_peptide.sequence}</code>
                                            </div>
                                        </td>
                                        <td>
                                            <span class="ic50-value">
                                                ${original_peptide.ic50_value} ${original_peptide.ic50_unit}
                                            </span>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }
            
            // Péptidos modificados
            if (modified_peptides.length > 0) {
                listHTML += `
                    <div class="peptide-section modified-section">
                        <div class="section-header modified-header">
                            <i class="fas fa-flask me-2"></i>
                            <strong>Péptidos Modificados</strong>
                            <span class="modified-count">(${modified_count})</span>
                        </div>
                        <div class="table-container">
                            <table class="peptide-table modified-table">
                                <thead>
                                    <tr>
                                        <th>Código</th>
                                        <th>Secuencia</th>
                                        <th>IC50</th>
                                        <th>Diferencias</th>
                                    </tr>
                                </thead>
                                <tbody>
                `;
                
                modified_peptides.forEach(peptide => {
                    const differences = this.findSequenceDifferences(original_peptide.sequence, peptide.sequence);
                    
                    listHTML += `
                        <tr>
                            <td>
                                <span class="peptide-code">${peptide.peptide_code}</span>
                            </td>
                            <td>
                                <code class="sequence-text-readonly">${peptide.sequence}</code>
                            </td>
                            <td>
                                <span class="ic50-value">
                                    ${peptide.ic50_value} ${peptide.ic50_unit}
                                </span>
                            </td>
                            <td>
                                ${differences ? `<span class="difference-badge">${differences}</span>` : '<span class="text-muted">-</span>'}
                            </td>
                        </tr>
                    `;
                });
                
                listHTML += `
                            </tbody>
                        </table>
                    </div>
                </div>
                `;
            }
        }
        
        listHTML += `
                </div>
            </div>
        `;
        
        this.peptideList.innerHTML = listHTML;
        this.peptideList.style.display = 'block';
    }

    // ✨ NUEVO: Método para encontrar diferencias entre secuencias
    findSequenceDifferences(originalSeq, modifiedSeq) {
        if (!originalSeq || !modifiedSeq) return null;
        
        // Buscar el patrón de modificación en el nombre del péptido
        // Por ejemplo: μ-TRTX-Hh2a_Y33W indica una sustitución Y→W en posición 33
        const modifications = [];
        
        for (let i = 0; i < Math.min(originalSeq.length, modifiedSeq.length); i++) {
            if (originalSeq[i] !== modifiedSeq[i]) {
                modifications.push(`${originalSeq[i]}${i+1}${modifiedSeq[i]}`);
            }
        }
        
        if (originalSeq.length !== modifiedSeq.length) {
            modifications.push(`Δ${Math.abs(originalSeq.length - modifiedSeq.length)}`);
        }
        
        return modifications.length > 0 ? modifications.join(', ') : null;
    }

    async loadFamilyData() {
        const selectedFamily = this.familySelector.value;
        
        if (!selectedFamily) return;
        
        try {
            this.showLoading(true, 'Cargando datos de dipolo...');
            
            const response = await fetch(`/v2/family-dipoles/${selectedFamily}`);
            const data = await response.json();
            
            if (data.success) {
                this.currentFamilyData = data.data;
                this.displayFamilyStats();
                this.visualizeFamilyBtn.innerHTML = '<i class="fas fa-eye me-2"></i>Actualizar Visualización';
            }
        } catch (error) {
            console.error('Error cargando datos de familia:', error);
        } finally {
            this.showLoading(false);
        }
    }

    async visualizeFamily() {

        const selectedFamily = this.familySelector.value;
        
        if (!selectedFamily) return;
        
        console.log('🔍 DEBUG: Iniciando visualización familiar');
        console.log('🔍 Familia seleccionada:', selectedFamily);
        
        try {
            this.showLoading(true, 'Calculando dipolos de la familia...');
            
            // Cargar datos con dipolos calculados (v2 con fallback a legacy)
            const response = await fetch(`/v2/family-dipoles/${selectedFamily}`);
            const data = await response.json();
            
            if (data.success) {
                console.log('🔍 Response completa:', data);
                console.log('🔍 Número de resultados dipolo:', data.data?.dipole_results?.length || 0);
                console.log('🔍 Número de errores:', data.data?.errors?.length || 0);
                console.log('🔍 Primer resultado (si existe):', data.data?.dipole_results?.[0]);
                
                this.currentFamilyData = data.data;
                this.createDipoleGrid(data.data.dipole_results);
                this.displayFamilyStats();
                
                // Mostrar áreas de visualización y estadísticas
                this.visualizationArea.style.display = 'block';
                this.statisticsArea.style.display = 'block';
                
                // Auto-scroll hacia la sección de visualización
                this.scrollToVisualization();
            } else {
                console.error('Error loading family dipoles:', data.error);
            }
        } catch (error) {
            console.error('Error visualizing family:', error);
        } finally {
            this.showLoading(false);
        }
    }

    scrollToVisualization() {
        // Scroll suave hacia la sección de visualización
        if (this.visualizationArea) {
            const element = this.visualizationArea;
            const offset = 100; // Espacio adicional desde la parte superior
            
            // Calcular la posición del elemento
            const elementPosition = element.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - offset;
            
            // Scroll suave hacia la posición
            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        }
    }

    createDipoleGrid(dipoleResults) {
        if (!dipoleResults || dipoleResults.length === 0) {
            this.visualizationGrid.innerHTML = '<p class="text-center">No hay datos de dipolo disponibles.</p>';
            return;
        }

        // ✅ CAMBIO: CSS Grid puro sin Bootstrap
        let gridHTML = '';

        dipoleResults.forEach((result, index) => {
            const dipoleData = result.dipole_data;
            const peptideCode = result.peptide_code;
            
            gridHTML += `
                <div class="dipole-visualization-card">
                    <div class="dipole-card-header">
                        <h6 class="dipole-card-title">
                            <i class="fas fa-dna"></i>${peptideCode}
                        </h6>
                        <small class="dipole-card-subtitle">
                            IC50: ${result.ic50_value} ${result.ic50_unit}
                        </small>
                    </div>
                    <div class="card-body">
                        <!-- Visualización 3D del dipolo -->
                        <div id="dipole-viewer-${index}" class="dipole-viewer">
                            <div class="loading-placeholder">
                                <div class="spinner-border spinner-border-sm" role="status"></div>
                                <span class="ms-2">Cargando estructura...</span>
                            </div>
                        </div>
                        
                        <!-- Información del dipolo -->
                        <div class="dipole-info-compact">
                            <div class="dipole-stats">
                                <div class="dipole-stat">
                                    <div class="stat-label">Magnitud</div>
                                    <div class="stat-value">${dipoleData.magnitude.toFixed(3)} D</div>
                                </div>
                                <div class="dipole-stat">
                                    <div class="stat-label">Ángulo Z</div>
                                    <div class="stat-value">${dipoleData.angle_with_z_axis.degrees.toFixed(1)}°</div>
                                </div>
                                <div class="dipole-stat">
                                    <div class="stat-label">Componentes</div>
                                    <div class="stat-value">X,Y,Z</div>
                                </div>
                            </div>
                            <div class="dipole-vector-info">
                                <code class="vector-code">[${dipoleData.vector.map(x => x.toFixed(2)).join(', ')}]</code>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        // ✅ Insertar directamente en visualizationGrid
        const dipoleVisualization = document.getElementById('dipoleVisualization');
        const visualizationGrid = document.getElementById('visualizationGrid');
        
        // Limpiar el área de carga
        dipoleVisualization.innerHTML = '';
        
        // Insertar grid en visualizationGrid
        visualizationGrid.innerHTML = gridHTML;

        // Inicializar visualizadores py3Dmol para cada toxina
        this.initializeDipoleViewers(dipoleResults);
    }

    async initializeDipoleViewers(dipoleResults) {
        for (let i = 0; i < dipoleResults.length; i++) {
            const result = dipoleResults[i];
            const viewerId = `dipole-viewer-${i}`;
            
            try {
                await this.createPy3DmolViewer(viewerId, result.pdb_data, result.dipole_data);
            } catch (error) {
                console.error(`Error initializing viewer for ${result.peptide_code}:`, error);
                document.getElementById(viewerId).innerHTML = `
                    <div class="alert alert-warning">
                        Error cargando visualización para ${result.peptide_code}
                    </div>
                `;
            }
        }
    }

    async createPy3DmolViewer(containerId, pdbData, dipoleData) {
        const container = document.getElementById(containerId);
        
        // Limpiar contenedor
        container.innerHTML = '';
        
        // Crear visualizador py3Dmol
        const viewer = $3Dmol.createViewer(container, {
            defaultcolors: $3Dmol.rasmolElementColors
        });

        // Añadir estructura PDB
        viewer.addModel(pdbData, "pdb");
        
        // Estilo de la proteína
        viewer.setStyle({}, {
            cartoon: {
                color: 'spectrum',
                opacity: 0.8
            },
            stick: {
                radius: 0.2,
                opacity: 0.6
            }
        });

        // Añadir vector dipolar
        this.addDipoleArrowToViewer(viewer, dipoleData);

        // Renderizar
        viewer.zoomTo();
        viewer.render();

        return viewer;
    }

    addDipoleArrowToViewer(viewer, dipoleData) {
        const start = dipoleData.center_of_mass;
        const end = dipoleData.end_point;

        // Flecha del dipolo (roja)
        viewer.addArrow({
            start: { x: start[0], y: start[1], z: start[2] },
            end: { x: end[0], y: end[1], z: end[2] },
            radius: 1.0,
            color: 'red',
            opacity: 0.9
        });

        // Esfera en centro de masa
        viewer.addSphere({
            center: { x: start[0], y: start[1], z: start[2] },
            radius: 1.5,
            color: 'red',
            opacity: 0.8
        });

        // Eje Z de referencia (azul)
        const zAxisEnd = [start[0], start[1], start[2] + 20];
        viewer.addArrow({
            start: { x: start[0], y: start[1], z: start[2] },
            end: { x: zAxisEnd[0], y: zAxisEnd[1], z: zAxisEnd[2] },
            radius: 0.5,
            color: 'blue',
            opacity: 0.6
        });
    }

    displayFamilyStats() {
        if (!this.currentFamilyData) return;
        
        const summary = this.currentFamilyData.summary;
        const errors = this.currentFamilyData.errors || [];
        
        document.getElementById('magnitudeStats').innerHTML = `
            <div class="row text-center">
                <div class="col-4">
                    <h6 class="text-muted">Péptidos</h6>
                    <h5 class="text-info">${summary.total_proteins}</h5>
                </div>
                <div class="col-4">
                    <h6 class="text-muted">Dipolo Promedio</h6>
                    <h5 class="text-primary">${summary.avg_magnitude.toFixed(3)} D</h5>
                </div>
                <div class="col-4">
                    <h6 class="text-muted">Rango</h6>
                    <h5 class="text-success">${summary.min_magnitude.toFixed(2)} - ${summary.max_magnitude.toFixed(2)} D</h5>
                </div>
            </div>
            ${errors.length > 0 ? `
                <div class="alert alert-warning mt-3">
                    <small><strong>Errores de cálculo:</strong> ${errors.length} péptidos</small>
                </div>
            ` : ''}
        `;
        
        document.getElementById('orientationStats').innerHTML = `
            <div class="text-center">
                <h6 class="text-muted">Análisis de Orientación</h6>
                <p class="text-muted">Comparación de ángulos con eje Z</p>
                <div class="mt-2">
                    <small class="text-info">
                        Los vectores dipolar se muestran en rojo<br>
                        El eje Z de referencia en azul
                    </small>
                </div>
            </div>
        `;
    }

    showLoading(show, message = 'Procesando datos...') {
        if (show) {
            this.loadingSpinner.style.display = 'block';
            this.visualizationPlaceholder.textContent = message;
        } else {
            this.loadingSpinner.style.display = 'none';
            this.visualizationPlaceholder.textContent = 'La visualización se mostrará aquí...';
        }
    }
}

// Inicializar cuando se carga la página
document.addEventListener('DOMContentLoaded', () => {
    new DipoleFamilyAnalyzer();
});