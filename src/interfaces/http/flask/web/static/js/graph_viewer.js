document.addEventListener("DOMContentLoaded", async () => {
    
    // Initialize fallback renderer - WebGL renderer removed to improve stability
    let graphRenderer = null;
    
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    const propertiesContainer = document.querySelector('.graph-properties-container');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            tabContents.forEach(content => content.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            
            if (tabId === 'graph-view') {
                propertiesContainer.style.display = 'block';
                document.body.classList.add('graph-tab-active');

                if (window.molstarAnalyzer) {
                    analyzeMolstarStructure();
                }
            } else {
                propertiesContainer.style.display = 'none';
                document.body.classList.remove('graph-tab-active');
            }
        });
    });

    // Inicializar la primera pestaña como activa
    if (propertiesContainer) {
        propertiesContainer.style.display = 'none';
    }
    
    const graphPlotElement = document.getElementById('graph-plot');
    const longInput = document.getElementById('long-input');
    const distInput = document.getElementById('dist-input');
    const granularityToggle = document.getElementById('granularity-toggle');
    const granularityToggleWrapper = document.getElementById('granularity-toggle-wrapper');
    
    let currentProteinGroup = null;
    let currentProteinId = null;
    
    // Initialize WebGL graph renderer with safety check
    if (typeof MolstarGraphRenderer !== 'undefined') {
        graphRenderer = new MolstarGraphRenderer(graphPlotElement);
    } else {
        // Fallback if renderer not loaded yet
        console.warn('MolstarGraphRenderer not loaded yet, will retry...');
        graphRenderer = {
            loadGraph: () => console.log('Waiting for MolstarGraphRenderer...'),
            clear: () => {}
        };
        // Retry after a short delay
        setTimeout(() => {
            if (typeof MolstarGraphRenderer !== 'undefined') {
                graphRenderer = new MolstarGraphRenderer(graphPlotElement);
                window.graphRenderer = graphRenderer;
                console.log('MolstarGraphRenderer loaded successfully');
            }
        }, 500);
    }
    
    // Exponer globalmente para debugging
    window.graphRenderer = graphRenderer;
    
    // Función para sincronizar el estado visual del toggle con el checkbox
    function syncGranularityToggleVisual() {
        if (granularityToggleWrapper && granularityToggle) {
            if (granularityToggle.checked) {
                granularityToggleWrapper.classList.remove('active');
            } else {
                granularityToggleWrapper.classList.add('active');
            }
        }
    }
    
    // Inicializar estado visual del toggle
    syncGranularityToggleVisual();
    
    // Show initial message
    const initialMsg = document.createElement('div');
    initialMsg.style.cssText = 'position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; font-size: 18px; text-align: center;';
    initialMsg.innerHTML = '<i class="fas fa-project-diagram" style="font-size: 48px; margin-bottom: 16px;"></i><br>Seleccione una proteína para ver su grafo';
    graphPlotElement.style.position = 'relative';
    graphPlotElement.appendChild(initialMsg);
    
    // Eventos para actualizar automaticamente el grafo
    longInput.addEventListener('change', updateGraphVisualization);
    distInput.addEventListener('change', updateGraphVisualization);
    granularityToggle.addEventListener('change', () => {
        syncGranularityToggleVisual();
        updateGraphVisualization();
    });
    
    // Event listener para el toggle visual
    if (granularityToggleWrapper) {
        granularityToggleWrapper.addEventListener('click', () => {
            granularityToggle.checked = !granularityToggle.checked;
            syncGranularityToggleVisual();
            updateGraphVisualization();
        });
    }
    
    const groupSelect = document.getElementById('groupSelect');
    const proteinSelect = document.getElementById('proteinSelect');
    
    groupSelect.addEventListener('change', () => {
        currentProteinGroup = groupSelect.value;
        setTimeout(() => {
            currentProteinId = proteinSelect.value;
            updateGraphVisualization();
        }, 300);
    });
    
    proteinSelect.addEventListener('change', () => {
        currentProteinGroup = groupSelect.value;
        currentProteinId = proteinSelect.value;
        updateGraphVisualization();
    });
    
    currentProteinGroup = groupSelect.value;
    
    // Esperamos a que los selectores estén llenos
    setTimeout(async () => {
        currentProteinId = proteinSelect.value;
        
        // Inicializar grafo automáticamente si tenemos una proteína seleccionada
        if (currentProteinGroup && currentProteinId) {
            await updateGraphVisualization();
        }
    }, 800);
    
    // Función para actualizar la visualización del grafo
    async function updateGraphVisualization() {
        if (!currentProteinGroup || !currentProteinId) {
            clearAnalysisPanel();
            return;
        }

        try {
            const longValue = longInput.value;
            const distValue = distInput.value;
            const granularity = granularityToggle.checked ? 'atom' : 'CA';
            
            // Evitar aristas por defecto en atómico
            const edgesParam = (granularity === 'atom') ? '0' : '1';
            
            showLoading(graphPlotElement);
            
            const url = `/v2/proteins/${currentProteinGroup}/${currentProteinId}/graph?long=${longValue}&threshold=${distValue}&granularity=${granularity}&edges=${edgesParam}`;
            console.time('fetch-graph');
            const response = await fetch(url);
            console.timeEnd('fetch-graph');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            console.time('parse-json');
            const data = await response.json();
            console.timeEnd('parse-json');
            
            if (data.error) {
                clearAnalysisPanel();
                return;
            }

    

            // Render with WebGL-optimized renderer (replaces Plotly)
            console.time('webgl-render');
            if (graphRenderer) {
                // Clear any initial message
                const msgs = graphPlotElement.querySelectorAll('div');
                msgs.forEach(msg => {
                    if (msg.textContent.includes('Seleccione una proteína')) {
                        msg.remove();
                    }
                });
                
                graphRenderer.loadGraph(data);
            }
            console.timeEnd('webgl-render');
            
            updateBasicStructuralInfo(data.properties, granularity);
            updateAdvancedMetrics(data); 
            analyzeMolstarStructure();

            // Notificar al dual view manager que el grafo se cargó
            if (window.dualViewManager) {
                window.dualViewManager.markGraphLoaded();
            }

        } catch (error) {
            clearAnalysisPanel();
            
            // Show error message in renderer
            if (graphRenderer) {
                graphRenderer.clear();
            }
            
            const errorMsg = document.createElement('div');
            errorMsg.className = 'graph-error-message';
            errorMsg.style.cssText = 'position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #ff6b6b; font-size: 16px; text-align: center;';
            errorMsg.innerHTML = '<i class="fas fa-exclamation-triangle" style="font-size: 48px; margin-bottom: 16px;"></i><br>Error al cargar el grafo:<br>' + error.message;
            graphPlotElement.appendChild(errorMsg);
            
            // Notificar error de carga del grafo
            if (window.dualViewManager) {
                window.dualViewManager.markGraphLoaded(); // Marcar como "cargado" aunque haya error
            }
        } finally {
            hideLoading(graphPlotElement);
        }
    }
    
    function updateBasicStructuralInfo(properties, granularity) {
        if (!properties) return;
        
        // Get the actual toxin name from the metadata endpoint
        getToxinName(currentProteinGroup, currentProteinId).then(toxinName => {
            updateElementText('toxin-name', toxinName);
        }).catch(() => {
            // Fallback to the old format if API fails
            const fallbackName = `${currentProteinGroup.toUpperCase()}_${currentProteinId}`;
            updateElementText('toxin-name', fallbackName);
        });
        
        // Actualizar datos básicos del grafo
        updateElementText('num-nodes', properties.num_nodes || '-');
        updateElementText('num-edges', properties.num_edges || '-');
        
        // Densidad del grafo
        updateElementText('graph-density', (properties.density || 0).toFixed(4));
        
        // Coeficiente de agrupamiento
        updateElementText('avg-clustering', (properties.avg_clustering || 0).toFixed(4));
        
        // Mostrar tipo de grafo (átomo o CA)
        const granularityText = granularity === 'atom' ? 'Nivel atómico' : 'Nivel de residuos (CA)';
        
        const infoElement = document.getElementById('graph-info');
        if (infoElement) {
            infoElement.textContent = `Grafo visualizado en: ${granularityText}`;
        }
    }

    async function analyzeMolstarStructure() {
        try {
            if (!window.molstarAnalyzer) {
                return;
            }
            
            const analysis = await window.molstarAnalyzer.analyzeCurrentStructure();
            
            if (analysis) {
                // Solo actualizar datos complementarios que no provengan del endpoint del grafo
                // No llamar updateAdvancedMetrics aquí porque ya se hizo con los datos del grafo
                
                // Actualizar puentes disulfuro si no se actualizaron antes
                const disulfideBridgesElement = document.getElementById('disulfide-bridges');
                if (disulfideBridgesElement && disulfideBridgesElement.textContent === '-') {
                    updateElementText('disulfide-bridges', analysis.graph_properties?.disulfide_bridges || '0');
                }
            }
        } catch (error) {
            // No mostramos el error para mantener la interfaz limpia
        }
    }
    
    function updateAdvancedMetrics(analysis) {
        // Métricas de centralidad 
        const metrics = analysis.summary_statistics;
        
        if (metrics) {
            // Degree Centrality
            updateElementText('degree-min', metrics.degree_centrality?.min?.toFixed(4) || '-');
            updateElementText('degree-max', metrics.degree_centrality?.max?.toFixed(4) || '-');
            updateElementText('degree-mean', metrics.degree_centrality?.mean?.toFixed(4) || '-');
            updateElementText('degree-top', metrics.degree_centrality?.top_residues || '-');

            // Betweenness Centrality
            updateElementText('between-min', metrics.betweenness_centrality?.min?.toFixed(4) || '-');
            updateElementText('between-max', metrics.betweenness_centrality?.max?.toFixed(4) || '-');
            updateElementText('between-mean', metrics.betweenness_centrality?.mean?.toFixed(4) || '-');
            updateElementText('between-top', metrics.betweenness_centrality?.top_residues || '-');

            // Closeness Centrality
            updateElementText('closeness-min', metrics.closeness_centrality?.min?.toFixed(4) || '-');
            updateElementText('closeness-max', metrics.closeness_centrality?.max?.toFixed(4) || '-');
            updateElementText('closeness-mean', metrics.closeness_centrality?.mean?.toFixed(4) || '-');
            updateElementText('closeness-top', metrics.closeness_centrality?.top_residues || '-');

            // Clustering Coefficient
            updateElementText('clustering-min', metrics.clustering_coefficient?.min?.toFixed(4) || '-');
            updateElementText('clustering-max', metrics.clustering_coefficient?.max?.toFixed(4) || '-');
            updateElementText('clustering-mean', metrics.clustering_coefficient?.mean?.toFixed(4) || '-');
            updateElementText('clustering-top', metrics.clustering_coefficient?.top_residues || '-');
        } else {
            console.warn('No summary_statistics found in analysis data');
        }

        // Top 5 residuos
        const top5 = analysis.top_5_residues;
        
        if (top5) {
            populateTop5List('top-degree-list', top5.degree_centrality);
            populateTop5List('top-between-list', top5.betweenness_centrality);
            populateTop5List('top-closeness-list', top5.closeness_centrality);
            populateTop5List('top-clustering-list', top5.clustering_coefficient);
            populateTop5List('top-seqdist-list', top5.seq_distance_avg);
            populateTop5List('top-longcontacts-list', top5.long_contacts_prop);
        } else {
            console.warn('No top_5_residues found in analysis data');
        }
    }

    function showLoading(element) {
        if (!element) return;

        const removable = element.querySelectorAll('.graph-loading-indicator, .graph-error-message');
        removable.forEach(node => node.remove());

        const fallback = element.querySelector('.graph-fallback-message');
        if (fallback) {
            fallback.style.opacity = '0.35';
        }

        const loadingMsg = document.createElement('div');
        loadingMsg.className = 'graph-loading-indicator';
        loadingMsg.style.cssText = 'position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; font-size: 16px; text-align: center;';
        loadingMsg.innerHTML = '<div class="spinner" style="width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.3); border-top-color: #4fc3f7; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 16px;"></div>Cargando grafo...';
        element.appendChild(loadingMsg);
    }
    
    function hideLoading(element) {
        if (!element) return;
        const loadingIndicators = element.querySelectorAll('.graph-loading-indicator');
        loadingIndicators.forEach(indicator => indicator.remove());

        const fallback = element.querySelector('.graph-fallback-message');
        if (fallback) {
            fallback.style.opacity = '';
        }
    }

    function setupExportButton() {
        const exportBtn = document.getElementById('export-csv-btn');
        const familySelector = document.getElementById('family-selector');
        const exportFamilyBtn = document.getElementById('export-family-csv-btn');
        const wtFamilySelector = document.getElementById('wt-family-selector');
        const exportWtBtn = document.getElementById('export-wt-comparison-btn');
        const exportTypeSelector = document.getElementById('export-type-selector');
        
        if (!exportBtn) return;
        
        const buttonContent = exportBtn.querySelector('.btn-content-modern span:last-child');
        const loadingContent = exportBtn.querySelector('.btn-loading-modern');
        
        // Function to update button text based on export type
        function updateExportButtonText() {
            if (!exportTypeSelector || !buttonContent) return;
            
            const exportType = exportTypeSelector.value;
            if (exportType === 'segments_atomicos') {
                buttonContent.textContent = 'Segmentos Atómicos';
            } else {
                buttonContent.textContent = 'Descargar Excel';
            }
        }
        
        // Update button text when export type changes
        if (exportTypeSelector) {
            exportTypeSelector.addEventListener('change', updateExportButtonText);
            // Set initial text
            updateExportButtonText();
        }
        
        // INDIVIDUAL EXPORT with visual feedback
        exportBtn.addEventListener('click', async () => {
            if (!currentProteinGroup || !currentProteinId) {
                exportFeedback.showWarning('Please select a toxin first');
                return;
            }
            
            // Disable button and show loading state
            exportBtn.disabled = true;
            if (buttonContent && buttonContent.parentElement) {
                buttonContent.parentElement.style.display = 'none';
            }
            if (loadingContent) {
                loadingContent.style.display = 'inline-flex';
            }
            
            try {
                const longValue = longInput.value;
                const distValue = distInput.value;
                const granularity = granularityToggle.checked ? 'atom' : 'CA';
                
                // Get export type from selector
                const exportTypeSelector = document.getElementById('export-type-selector');
                const exportType = exportTypeSelector ? exportTypeSelector.value : 'residues';
                
                // Validar que la segmentación atómica sea solo para Nav1.7 y granularidad atom
                if (exportType === 'segments_atomicos') {
                    if (currentProteinGroup !== 'nav1_7') {
                        exportFeedback.showError('La segmentación atómica solo está disponible para toxinas Nav1.7');
                        return;
                    }
                    if (granularity !== 'atom') {
                        exportFeedback.showError('La segmentación atómica requiere granularidad "Átomos". Por favor actívela en los controles del grafo.');
                        return;
                    }
                }
                
                // Get toxin name
                const nameResponse = await fetch(`/v2/metadata/toxin_name/${currentProteinGroup}/${currentProteinId}`);
                const nameData = await nameResponse.json();
                const toxinName = nameData.toxin_name || `${currentProteinGroup}_${currentProteinId}`;
                
                // Show export modal
                exportFeedback.startIndividualExport(toxinName);
                
                const cleanName = toxinName.replace(/[^\w\-_]/g, '');
                
                let filename;
                let url;
                
                if (exportType === 'segments_atomicos') {
                    // Segmentación atómica (solo Nav1.7)
                    filename = `Nav1.7-${cleanName}-Segmentos-Atomicos.xlsx`;
                    url = `/v2/export/segments_atomicos/${currentProteinId}?long=${longValue}&threshold=${distValue}&granularity=${granularity}`;
                } else {
                    // Análisis por residuos (normal)
                    const exportTypeText = 'Residuos';
                    if (currentProteinGroup === "nav1_7") {
                        filename = `Nav1.7-${cleanName}-${exportTypeText}.xlsx`;
                    } else {
                        filename = `Toxinas-${cleanName}-${exportTypeText}.xlsx`;
                    }
                    url = `/v2/export/residues/${currentProteinGroup}/${currentProteinId}?long=${longValue}&threshold=${distValue}&granularity=${granularity}&export_type=residues`;
                }
                
                // Simulate delay to show progress
                await new Promise(resolve => setTimeout(resolve, 1500));
                
                // Download the file
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                // Show success toast and reset button
                exportFeedback.completeExport('individual', { toxinName });
            } catch (error) {
                console.error('Export failed:', error);
                exportFeedback.showError('Export failed. Please try again.');
            } finally {
                exportBtn.disabled = false;
                if (buttonContent && buttonContent.parentElement) {
                    buttonContent.parentElement.style.display = 'inline-flex';
                }
                if (loadingContent) {
                    loadingContent.style.display = 'none';
                }
                // Restore original button text
                updateExportButtonText();
            }
        });
        
        // FAMILY EXPORT
        if (familySelector && exportFamilyBtn) {
            const familyExportTypeSelector = document.getElementById('family-export-type-selector');
            const familyButtonContent = exportFamilyBtn.querySelector('.btn-content-modern span:last-child');
            const familyLoadingContent = exportFamilyBtn.querySelector('.btn-loading-modern');
            
            // Update family button text based on export type
            function updateFamilyExportButtonText() {
                if (!familyButtonContent) return;
                const exportType = familyExportTypeSelector ? familyExportTypeSelector.value : 'residues';
                
                if (exportType === 'segments_atomicos') {
                    familyButtonContent.textContent = 'Segmentación Atómica Familia';
                } else {
                    familyButtonContent.textContent = 'Exportar familia';
                }
            }
            
            // Update button text when family export type changes
            if (familyExportTypeSelector) {
                familyExportTypeSelector.addEventListener('change', updateFamilyExportButtonText);
                updateFamilyExportButtonText(); // Set initial text
            }
            
            familySelector.addEventListener('change', () => {
                exportFamilyBtn.disabled = !familySelector.value;
            });
            
            exportFamilyBtn.addEventListener('click', async () => {
                const selectedFamily = familySelector.value;
                if (!selectedFamily) {
                    exportFeedback.showWarning('Por favor selecciona una familia de toxinas');
                    return;
                }
                
                // Get export type for families
                const familyExportType = familyExportTypeSelector ? familyExportTypeSelector.value : 'residues';
                
                // Validate atomic segmentation requirements for families
                if (familyExportType === 'segments_atomicos') {
                    const granularity = granularityToggle.checked ? 'atom' : 'CA';
                    if (granularity !== 'atom') {
                        exportFeedback.showError('La segmentación atómica requiere granularidad "Átomos". Por favor actívela en los controles del grafo.');
                        return;
                    }
                }
                
                exportFamilyBtn.disabled = true;
                if (familyButtonContent && familyButtonContent.parentElement) {
                    familyButtonContent.parentElement.style.display = 'none';
                }
                if (familyLoadingContent) {
                    familyLoadingContent.style.display = 'inline-flex';
                }
                
                try {
                    const longValue = longInput.value;
                    const distValue = distInput.value;
                    const granularity = granularityToggle.checked ? 'atom' : 'CA';
                    
                    // Show family export modal with appropriate text
                    if (familyExportType === 'segments_atomicos') {
                        exportFeedback.showExportModal({
                            icon: '🧩',
                            title: 'Exportando Segmentación Atómica Familiar',
                            subtitle: `Procesando familia: ${selectedFamily}`,
                            details: 'Aplicando segmentación atómica a todas las toxinas de la familia con métricas estructurales completas'
                        });
                    } else {
                        exportFeedback.startFamilyExport(selectedFamily, 'multiple');
                    }
                    
                    const familyNames = {
                        'μ-TRTX-Hh2a': 'Mu_TRTX_Hh2a',
                        'μ-TRTX-Hhn2b': 'Mu_TRTX_Hhn2b',
                        'β-TRTX': 'Beta_TRTX',
                        'ω-TRTX': 'Omega_TRTX'
                    };
                    
                    const familyName = familyNames[selectedFamily] || selectedFamily.replace(/[^\w]/g, '_');
                    
                    let filename;
                    if (familyExportType === 'segments_atomicos') {
                        filename = `Dataset_${familyName}_Segmentacion_Atomica_${granularity}.xlsx`;
                    } else {
                        filename = `Dataset_${familyName}_IC50_Topologia_${granularity}.xlsx`;
                    }
                    
                    // Add export_type parameter to URL
                    const url = `/v2/export/family/${encodeURIComponent(selectedFamily)}?long=${longValue}&threshold=${distValue}&granularity=${granularity}&export_type=${familyExportType}`;
                    
                    // Simulate delay for family processing (longer time for atomic segmentation)
                    const delay = familyExportType === 'segments_atomicos' ? 3500 : 2500;
                    await new Promise(resolve => setTimeout(resolve, delay));
                    
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = filename;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    
                    // Show success toast
                    exportFeedback.completeExport('family', { 
                        familyName: selectedFamily,
                        residueCount: 'multiple'
                    });
                } catch (error) {
                    console.error('Exportación de familia falló:', error);
                    exportFeedback.showError('Exportación de familia falló. Por favor intenta de nuevo.');
                } finally {
                    exportFamilyBtn.disabled = false;
                    if (familyButtonContent && familyButtonContent.parentElement) {
                        familyButtonContent.parentElement.style.display = 'inline-flex';
                    }
                    if (familyLoadingContent) {
                        familyLoadingContent.style.display = 'none';
                    }
                    updateFamilyExportButtonText(); // Restore proper text
                }
            });
        }
        
        // WT COMPARISON
        if (wtFamilySelector && exportWtBtn) {
            const wtExportTypeSelector = document.getElementById('wt-export-type-selector');
            const wtButtonContent = exportWtBtn.querySelector('.btn-content-modern span:last-child');
            const wtLoadingContent = exportWtBtn.querySelector('.btn-loading-modern');
            
            // Update WT button text based on export type
            function updateWtExportButtonText() {
                if (!wtButtonContent) return;
                const exportType = wtExportTypeSelector ? wtExportTypeSelector.value : 'residues';
                
                if (exportType === 'segments_atomicos') {
                    wtButtonContent.textContent = 'Comparar WT (Segmentación)';
                } else {
                    wtButtonContent.textContent = 'Comparar con WT';
                }
            }
            
            // Update button text when WT export type changes
            if (wtExportTypeSelector) {
                wtExportTypeSelector.addEventListener('change', updateWtExportButtonText);
                updateWtExportButtonText(); // Set initial text
            }
            
            wtFamilySelector.addEventListener('change', () => {
                exportWtBtn.disabled = !wtFamilySelector.value;
            });
            
            exportWtBtn.addEventListener('click', async () => {
                const selectedWtFamily = wtFamilySelector.value;
                if (!selectedWtFamily) {
                    exportFeedback.showWarning('Por favor selecciona una familia WT');
                    return;
                }
                
                // Get export type for WT comparison
                const wtExportType = wtExportTypeSelector ? wtExportTypeSelector.value : 'residues';
                
                // Validate atomic segmentation requirements for WT
                if (wtExportType === 'segments_atomicos') {
                    const granularity = granularityToggle.checked ? 'atom' : 'CA';
                    if (granularity !== 'atom') {
                        exportFeedback.showError('La segmentación atómica requiere granularidad "Átomos". Por favor actívela en los controles del grafo.');
                        return;
                    }
                }
                
                exportWtBtn.disabled = true;
                if (wtButtonContent && wtButtonContent.parentElement) {
                    wtButtonContent.parentElement.style.display = 'none';
                }
                if (wtLoadingContent) {
                    wtLoadingContent.style.display = 'inline-flex';
                }
                
                try {
                    const longValue = longInput.value;
                    const distValue = distInput.value;
                    const granularity = granularityToggle.checked ? 'atom' : 'CA';
                    
                    // Show WT comparison modal with appropriate text
                    if (wtExportType === 'segments_atomicos') {
                        exportFeedback.showExportModal({
                            icon: '🧩',
                            title: 'Comparación WT con Segmentación Atómica',
                            subtitle: `Comparando: ${selectedWtFamily} vs hwt4_Hh2a_WT`,
                            details: 'Aplicando segmentación atómica para comparar diferencias estructurales detalladas a nivel de residuos'
                        });
                    } else {
                        exportFeedback.startWTComparison(selectedWtFamily);
                    }
                    
                    const familyClean = selectedWtFamily
                        .replace('μ', 'mu')
                        .replace('β', 'beta')
                        .replace('ω', 'omega')
                        .replace('δ', 'delta');
                    
                    let filename;
                    if (wtExportType === 'segments_atomicos') {
                        filename = `Comparacion_WT_${familyClean}_vs_hwt4_Hh2a_WT_Segmentacion_Atomica_${granularity}.xlsx`;
                    } else {
                        filename = `Comparacion_WT_${familyClean}_vs_hwt4_Hh2a_WT_${granularity}.xlsx`;
                    }
                    
                    // Add export_type parameter to URL
                    const url = `/v2/export/wt_comparison/${encodeURIComponent(selectedWtFamily)}?long=${longValue}&threshold=${distValue}&granularity=${granularity}&export_type=${wtExportType}`;
                    
                    // Simulate delay for WT comparison (longer for atomic segmentation)
                    const delay = wtExportType === 'segments_atomicos' ? 3000 : 2000;
                    await new Promise(resolve => setTimeout(resolve, delay));
                    
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = filename;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    
                    // Show WT-specific success toast
                    exportFeedback.completeExport('wt-comparison', { 
                        wtFamily: selectedWtFamily
                    });
                } catch (error) {
                    console.error('Comparación WT falló:', error);
                    exportFeedback.showError('Comparación WT falló. Por favor intenta de nuevo.');
                } finally {
                    exportWtBtn.disabled = false;
                    if (wtButtonContent && wtButtonContent.parentElement) {
                        wtButtonContent.parentElement.style.display = 'inline-flex';
                    }
                    if (wtLoadingContent) {
                        wtLoadingContent.style.display = 'none';
                    }
                    updateWtExportButtonText(); // Restore proper text
                }
            });
        }
    }
    // Llamar setupExportButton DENTRO del scope donde están definidas las variables
    setupExportButton();

    // Exponer funciones globalmente
    window.updateGraphVisualization = updateGraphVisualization;
    window.analyzeMolstarStructure = analyzeMolstarStructure;
    window.currentProteinGroup = () => currentProteinGroup;
    window.currentProteinId = () => currentProteinId;
    window.setCurrentProtein = (group, id) => {
        currentProteinGroup = group;
        currentProteinId = id;
    };
});

// Función para ser llamada desde la gestión de pestañas
window.triggerGraphUpdate = function(group, id) {
    if (group && id && window.setCurrentProtein) {
        window.setCurrentProtein(group, id);
        window.updateGraphVisualization();
    }
};

// Función para obtener el nombre real de la toxina desde el endpoint de metadata
async function getToxinName(group, id) {
    try {
        const response = await fetch(`/v2/metadata/toxin_name/${group}/${id}`);
        const data = await response.json();
        return data.toxin_name || `${group.toUpperCase()}_${id}`;
    } catch (error) {
        console.warn('Error fetching toxin name:', error);
        return `${group.toUpperCase()}_${id}`;
    }
}

// Funciones auxiliares fuera del scope principal
function updateAnalysisPanel(analysisData) {
    if (!analysisData) {
        return;
    }
    
    const nodesElement = document.getElementById('num-nodes');
    if (nodesElement && nodesElement.textContent === '-') {
        updateElementText('toxin-name', analysisData.toxin || '-');
        updateElementText('num-nodes', analysisData.graph_properties?.nodes || '-');
        updateElementText('num-edges', analysisData.graph_properties?.edges || '-');
        updateElementText('disulfide-bridges', analysisData.graph_properties?.disulfide_bridges || '-');
        updateElementText('graph-density', (analysisData.graph_properties?.density || 0).toFixed(4));
        updateElementText('avg-clustering', (analysisData.graph_properties?.clustering_coefficient_avg || 0).toFixed(4));
    }
}

function updateElementText(elementId, text) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = text;
    }
}

function populateTop5List(listId, items) {
    const list = document.getElementById(listId);
    if (!list) return;
    
    list.innerHTML = '';
    
    if (!items || items.length === 0) {
        const li = document.createElement('li');
        li.textContent = 'No hay datos disponibles';
        li.style.opacity = '0.6';
        li.style.fontStyle = 'italic';
        list.appendChild(li);
        return;
    }
    
    items.forEach((item, index) => {
        const li = document.createElement('li');
        
        // Crear estructura más detallada con el nuevo formato
        const residueInfo = document.createElement('div');
        residueInfo.style.cssText = 'display: flex; flex-direction: column; gap: 0.25rem; flex: 1;';
        
        // Identificador del residuo (formato completo: A:TRP:21 o A:TRP:21:N)
        const residueId = document.createElement('span');
        residueId.style.cssText = 'font-weight: 700; color: var(--gray-900); font-size: var(--text-sm);';
        
        if (item.residueName && item.chain) {
            // Formato nuevo: mostrar cadena, aminoácido y posición
            let idText = `${item.chain}:${item.residueName}:${item.residue}`;
            
            // Si hay información de átomo (granularidad atom), incluirlo
            if (item.atomName) {
                idText += `:${item.atomName}`;
            }
            
            residueId.textContent = idText;
        } else {
            // Fallback al formato anterior
            residueId.textContent = `${item.residueName || ''}${item.residue || ''}`;
        }
        
        // Valor de la métrica
        const metricValue = document.createElement('span');
        metricValue.style.cssText = 'font-size: var(--text-xs); color: var(--primary-600); font-weight: 600;';
        metricValue.textContent = `Valor: ${item.value.toFixed(4)}`;
        
        residueInfo.appendChild(residueId);
        residueInfo.appendChild(metricValue);
        
        // Agregar badge de ranking
        const rankBadge = document.createElement('span');
        rankBadge.style.cssText = 'background: var(--primary-100); color: var(--primary-700); padding: 0.125rem 0.5rem; border-radius: var(--radius-full); font-size: var(--text-xs); font-weight: 700;';
        rankBadge.textContent = `#${index + 1}`;
        
        li.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: var(--space-2);';
        li.appendChild(residueInfo);
        li.appendChild(rankBadge);
        
        list.appendChild(li);
    });
}

function clearAnalysisPanel() {
    // Función para limpiar el panel de análisis
}


