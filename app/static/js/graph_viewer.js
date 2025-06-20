document.addEventListener("DOMContentLoaded", async () => {
    
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
    
    let currentProteinGroup = null;
    let currentProteinId = null;
    
    // Inicializamos el grafico vacio con plotly
    Plotly.newPlot(graphPlotElement, [], {
        title: 'Seleccione una proteína para ver su grafo',
        height: 500,
        scene: {
            xaxis: { title: 'x' },
            yaxis: { title: 'y' },
            zaxis: { title: 'z' }
        }
    });
    
    // Eventos para actualizar automaticamente el grafo
    longInput.addEventListener('change', updateGraphVisualization);
    distInput.addEventListener('change', updateGraphVisualization);
    granularityToggle.addEventListener('change', updateGraphVisualization);
    
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
            
            showLoading(graphPlotElement);
            
            const response = await fetch(`/get_protein_graph/${currentProteinGroup}/${currentProteinId}?long=${longValue}&threshold=${distValue}&granularity=${granularity}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                clearAnalysisPanel();
                return;
            }

            Plotly.react(graphPlotElement, data.plotData, data.layout);
            
            updateBasicStructuralInfo(data.properties, granularity);
            updateAdvancedMetrics(data); 
            analyzeMolstarStructure();

        } catch (error) {
            clearAnalysisPanel();
            Plotly.react(graphPlotElement, [], {
                title: 'Error al cargar el grafo: ' + error.message,
                height: 500
            });
        } finally {
            hideLoading(graphPlotElement);
        }
    }
    
    function updateBasicStructuralInfo(properties, granularity) {
        if (!properties) return;
        
        const toxinName = `${currentProteinGroup.toUpperCase()}_${currentProteinId}`;
        updateElementText('toxin-name', toxinName);
        
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
                // Actualizar datos complementarios y métricas avanzadas
                updateAdvancedMetrics(analysis);
                
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
        }

        // Top 5 residuos
        const top5 = analysis.top_5_residues;
        if (top5) {
            populateTop5List('top-degree-list', top5.degree_centrality);
            populateTop5List('top-between-list', top5.betweenness_centrality);
            populateTop5List('top-closeness-list', top5.closeness_centrality);
            populateTop5List('top-clustering-list', top5.clustering_coefficient);
        }
    }

    function showLoading(element) {
        Plotly.react(element, [], {
            title: 'Cargando grafo...',
            height: 500
        });
    }
    
    function hideLoading(element) {
    }

    function setupExportButton() {
        const exportBtn = document.getElementById('export-csv-btn');
        const familySelector = document.getElementById('family-selector');
        const exportFamilyBtn = document.getElementById('export-family-csv-btn');
        const wtFamilySelector = document.getElementById('wt-family-selector');
        const exportWtBtn = document.getElementById('export-wt-comparison-btn');
        
        if (!exportBtn) return;
        
        const buttonText = exportBtn.querySelector('.button-text');
        const loadingText = exportBtn.querySelector('.loading-text');
        
        // INDIVIDUAL EXPORT with visual feedback
        exportBtn.addEventListener('click', async () => {
            if (!currentProteinGroup || !currentProteinId) {
                exportFeedback.showWarning('Please select a toxin first');
                return;
            }
            
            // Disable button and show loading state
            exportBtn.disabled = true;
            buttonText.style.display = 'none';
            loadingText.style.display = 'inline';
            
            try {
                const longValue = longInput.value;
                const distValue = distInput.value;
                const granularity = granularityToggle.checked ? 'atom' : 'CA';
                
                // Get toxin name
                const nameResponse = await fetch(`/get_toxin_name/${currentProteinGroup}/${currentProteinId}`);
                const nameData = await nameResponse.json();
                const toxinName = nameData.toxin_name || `${currentProteinGroup}_${currentProteinId}`;
                
                // Show export modal
                exportFeedback.startIndividualExport(toxinName);
                
                const cleanName = toxinName.replace(/[^\w\-_]/g, '');
                
                let filename;
                if (currentProteinGroup === "nav1_7") {
                    filename = `Nav1.7-${cleanName}.xlsx`; // Changed from .csv to .xlsx
                } else {
                    filename = `Toxinas-${cleanName}.xlsx`; // Changed from .csv to .xlsx
                }
                
                // Use the new Excel endpoint
                const url = `/export_residues_xlsx/${currentProteinGroup}/${currentProteinId}?long=${longValue}&threshold=${distValue}&granularity=${granularity}`;
                
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
                buttonText.style.display = 'inline';
                loadingText.style.display = 'none';
            }
        });
        
        // FAMILY EXPORT
        if (familySelector && exportFamilyBtn) {
            familySelector.addEventListener('change', () => {
                exportFamilyBtn.disabled = !familySelector.value;
            });
            
            exportFamilyBtn.addEventListener('click', async () => {
                const selectedFamily = familySelector.value;
                if (!selectedFamily) {
                    exportFeedback.showWarning('Please select a toxin family');
                    return;
                }
                
                const familyButtonText = exportFamilyBtn.querySelector('.button-text');
                const familyLoadingText = exportFamilyBtn.querySelector('.loading-text');
                
                exportFamilyBtn.disabled = true;
                familyButtonText.style.display = 'none';
                familyLoadingText.style.display = 'inline';
                
                try {
                    const longValue = longInput.value;
                    const distValue = distInput.value;
                    const granularity = granularityToggle.checked ? 'atom' : 'CA';
                    
                    // Show family export modal
                    exportFeedback.startFamilyExport(selectedFamily, 'multiple');
                    
                    const familyNames = {
                        'μ-TRTX-Hh2a': 'Mu_TRTX_Hh2a',
                        'μ-TRTX-Hhn2b': 'Mu_TRTX_Hhn2b',
                        'β-TRTX': 'Beta_TRTX',
                        'ω-TRTX': 'Omega_TRTX'
                    };
                    
                    const familyName = familyNames[selectedFamily] || selectedFamily.replace(/[^\w]/g, '_');
                    const filename = `Dataset_${familyName}_IC50_Topologia_${granularity}.xlsx`; // Changed from .csv to .xlsx
                    
                    // Use the new Excel endpoint
                    const url = `/export_family_xlsx/${encodeURIComponent(selectedFamily)}?long=${longValue}&threshold=${distValue}&granularity=${granularity}`;
                    
                    // Simulate delay for family processing (longer time)
                    await new Promise(resolve => setTimeout(resolve, 2500));
                    
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
                    console.error('Family export failed:', error);
                    exportFeedback.showError('Family export failed. Please try again.');
                } finally {
                    exportFamilyBtn.disabled = false;
                    familyButtonText.style.display = 'inline';
                    familyLoadingText.style.display = 'none';
                }
            });
        }
        
        // WT COMPARISON
        if (wtFamilySelector && exportWtBtn) {
            wtFamilySelector.addEventListener('change', () => {
                exportWtBtn.disabled = !wtFamilySelector.value;
            });
            
            exportWtBtn.addEventListener('click', async () => {
                const selectedWtFamily = wtFamilySelector.value;
                if (!selectedWtFamily) {
                    exportFeedback.showWarning('Please select a WT family');
                    return;
                }
                
                const wtButtonText = exportWtBtn.querySelector('.button-text');
                const wtLoadingText = exportWtBtn.querySelector('.loading-text');
                
                exportWtBtn.disabled = true;
                wtButtonText.style.display = 'none';
                wtLoadingText.style.display = 'inline';
                
                try {
                    const longValue = longInput.value;
                    const distValue = distInput.value;
                    const granularity = granularityToggle.checked ? 'atom' : 'CA';
                    
                    // Show WT comparison modal
                    exportFeedback.startWTComparison(selectedWtFamily);
                    
                    const familyClean = selectedWtFamily
                        .replace('μ', 'mu')
                        .replace('β', 'beta')
                        .replace('ω', 'omega')
                        .replace('δ', 'delta');
                    
                    const filename = `Comparacion_WT_${familyClean}_vs_hwt4_Hh2a_WT_${granularity}.xlsx`; // Changed from .csv to .xlsx
                    
                    // Use the new Excel endpoint
                    const url = `/export_wt_comparison_xlsx/${encodeURIComponent(selectedWtFamily)}?long=${longValue}&threshold=${distValue}&granularity=${granularity}`;
                    
                    // Simulate delay for WT comparison
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    
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
                    console.error('WT comparison export failed:', error);
                    exportFeedback.showError('WT comparison export failed. Please try again.');
                } finally {
                    exportWtBtn.disabled = false;
                    wtButtonText.style.display = 'inline';
                    wtLoadingText.style.display = 'none';
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
        list.appendChild(li);
        return;
    }
    
    items.forEach((item, index) => {
        const li = document.createElement('li');
        // Verificar si tenemos la información completa del residuo
        if (item.residueName && item.chain) {
            // Formato deseado: "VAL21 (Cadena A): 0.1122"
            li.textContent = `${item.residueName}${item.residue} (Cadena ${item.chain}): ${item.value.toFixed(4)}`;
        } else {
            // Fallback al formato anterior si no tenemos toda la información
            li.textContent = `${item.residueName}${item.residue}: ${item.value.toFixed(4)}`;
        }
        list.appendChild(li);
    });
}

function clearAnalysisPanel() {
    // Función para limpiar el panel de análisis
}


