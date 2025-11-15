// filepath: app/static/js/dipole_family_analysis.js
class DipoleFamilyAnalyzer {
    constructor() {
        // Constantes de clasificación de zonas funcionales
        this.GENERAL_ZONES = {
            X: {
                optimal: [28, 32],
                acceptable: [[20, 28], [32, 35]],
                unfavorable: [0, 20, 35, 180]
            },
            Y: {
                optimal: [110, 122],
                acceptable: [[100, 110], [122, 125]],
                unfavorable: [0, 100, 125, 180]
            },
            Z: {
                optimalA: [70, 90],
                optimalB: [100, 112],
                acceptable: [[90, 100]],
                unfavorable: [0, 70, 112, 180]
            }
        };

        this.FAMILY_ZONES = {
            'μ-TRTX-Hh2a': {
                X: [10, 35],
                Y: [100, 115],
                Z: [70, 90]
            },
            'μ-TRTX-Hhn2b': {
                X: [28, 35],
                Y: [110, 115],
                Z: [100, 110]
            },
            'β-TRTX': {
                X: null,
                Y: null,
                Z: [108, 112]
            },
            'ω-TRTX-Gr2a': {
                X: [28, 32],
                Y: [118, 122],
                Z: [87, 90]
            }
        };

        this.ZONE_COLORS = {
            optimal: '#4CAF50',
            acceptable: '#FFC107',
            unfavorable: '#F44336'
        };
      
        
        this.familySelector = document.getElementById('familySelector');
        this.visualizeFamilyBtn = document.getElementById('visualizeFamilyBtn');
        this.loadFamilyDataBtn = document.getElementById('loadFamilyDataBtn');
        this.familyInfo = document.getElementById('familyInfo');
        this.familyInfoText = document.getElementById('familyInfoText');
    this.familyHint = document.getElementById('familyHint');
        this.visualizationArea = document.getElementById('visualizationArea');
    this.statisticsArea = document.getElementById('statisticsArea'); // puede no existir
        this.selectedFamilyTitle = document.getElementById('selectedFamilyTitle');
        this.loadingSpinner = document.getElementById('loadingSpinner');
        this.visualizationPlaceholder = document.getElementById('visualizationPlaceholder');
        
        // Nuevo elemento para mostrar péptidos
        this.peptideList = document.getElementById('peptideList');
        this.visualizationGrid = document.getElementById('visualizationGrid');
        this.visualizationActions = document.getElementById('visualizationActions');
        this.toggleFilterBtn = document.getElementById('toggleFilterBtn');
        this.toggleFilterText = document.getElementById('toggleFilterText');
        this.toggleFilterIcon = document.getElementById('toggleFilterIcon');
        this.highlightedCountBadge = document.getElementById('highlightedCountBadge');
        
        // Elementos de análisis de ángulos
        this.angleAnalysisSection = document.getElementById('angleAnalysisSection');
        this.angleChartX = document.getElementById('angleChartX');
        this.angleChartY = document.getElementById('angleChartY');
        this.angleChartZ = document.getElementById('angleChartZ');
        
        // Elementos de análisis de zonas funcionales
        this.zonesAnalysisSection = document.getElementById('zonesAnalysisSection');
        this.zoneChartX = document.getElementById('zoneChartX');
        this.zoneChartY = document.getElementById('zoneChartY');
        this.zoneChartZ = document.getElementById('zoneChartZ');
        this.zonesModeToggle = document.getElementById('zonesModeToggle');
        this.zonesLegend = document.getElementById('zonesLegend');
        this.currentZonesMode = 'general';
        
        // Elementos de Rose Plot
        this.rosePlotModeToggle = document.getElementById('rosePlotModeToggle');
        this.currentRosePlotMode = 'frequency'; // 'frequency' o 'affinity'
        this.rosePlotBinSize = 10; // grados por bin
        this.rosePlotUpdateTimer = null; // Para debouncing
        
    this.currentFamilyData = null;
    // Cache por familia para restaurar estado (datos y resaltados)
    this.familyCache = {}; // { [familyName]: { dipoleData, highlights: Set<string> } }
        this.cardIndexByCode = {}; // mapa peptide_code -> índice de tarjeta
        this.visualizationReady = false;
        this.showingHighlightsOnly = false;
        
        this.loadFamilyOptions();
        this.initializeEventListeners();
        
    }

    syncHighlightToggleVisuals() {
        if (!this.peptideList) return;
        const toggles = this.peptideList.querySelectorAll('.highlight-toggle');
        toggles.forEach(input => {
            this.updateToggleControlVisual(input, input.checked);
        });
    }

    updateToggleControlVisual(input, isActive) {
        if (!input) return;
        const control = input.closest('.highlight-toggle-control');
        if (!control) return;
        control.classList.toggle('is-active', !!isActive);
        control.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    }

    onToggleFilterClicked() {
        if (!this.visualizationReady) return;
        const highlightCount = this.getCurrentHighlights().size;
        if (highlightCount === 0 && !this.showingHighlightsOnly) return;
        
        // Toggle entre mostrar solo resaltados y mostrar todo
        this.showingHighlightsOnly = !this.showingHighlightsOnly;
        this.applyVisualizationFilter();
        this.updateFilterButtonsState();
        
        const fname = this.familySelector.value;
        if (this.familyCache[fname]) {
            this.familyCache[fname].filterMode = this.showingHighlightsOnly ? 'highlights' : 'all';
        }
    }

    applyVisualizationFilter() {
        if (!this.visualizationGrid) return;
        const cards = Array.from(this.visualizationGrid.querySelectorAll('.dipole-visualization-card'));
        if (!cards.length) return;
        const hasHighlightedCards = cards.some(card => card.classList.contains('highlighted-card'));
        if (!hasHighlightedCards) {
            this.showingHighlightsOnly = false;
        }
        cards.forEach(card => {
            const shouldHide = this.showingHighlightsOnly && !card.classList.contains('highlighted-card');
            card.classList.toggle('is-hidden', shouldHide);
        });
    }

    setVisualizationActionsVisible(visible) {
        if (!this.visualizationActions) return;
        this.visualizationActions.style.display = visible ? 'flex' : 'none';
    }

    updateFilterButtonsState() {
        const highlightCount = this.getCurrentHighlights().size;
        
        if (this.toggleFilterBtn) {
            // Deshabilitar solo si no hay visualización o no hay resaltados y está en modo "mostrar todo"
            this.toggleFilterBtn.disabled = !this.visualizationReady || (highlightCount === 0 && !this.showingHighlightsOnly);
            this.toggleFilterBtn.setAttribute('aria-pressed', this.showingHighlightsOnly ? 'true' : 'false');
        }
        
        // Actualizar texto e icono del botón según el estado
        if (this.toggleFilterText && this.toggleFilterIcon) {
            if (this.showingHighlightsOnly) {
                this.toggleFilterText.textContent = 'Mostrar todas';
                this.toggleFilterIcon.className = 'fas fa-th-large';
            } else {
                this.toggleFilterText.textContent = 'Resaltar vistas';
                this.toggleFilterIcon.className = 'fas fa-filter';
            }
        }
        
        // Actualizar badge de contador
        if (this.highlightedCountBadge) {
            this.highlightedCountBadge.textContent = highlightCount;
            this.highlightedCountBadge.hidden = highlightCount === 0;
        }
    }

    initializeEventListeners() {
        this.familySelector.addEventListener('change', () => {
            this.onFamilySelected();
        });
        
        this.visualizeFamilyBtn.addEventListener('click', () => {
            // Ocultar señal/aviso al iniciar la visualización
            if (this.familyHint) {
                this.familyHint.style.display = 'none';
            }
            this.visualizeFamily();
        });

        if (this.toggleFilterBtn) {
            this.toggleFilterBtn.addEventListener('click', () => this.onToggleFilterClicked());
        }
        
        if (this.zonesModeToggle) {
            this.zonesModeToggle.addEventListener('change', (e) => {
                this.currentZonesMode = e.target.checked ? 'family' : 'general';
                if (this.currentFamilyData && this.currentFamilyData.dipole_results) {
                    this.updateZonesLegend();
                    this.createZonesCharts(this.currentFamilyData.dipole_results);
                }
            });
        }
        
        // Event listener para el toggle del Rose Plot
        if (this.rosePlotModeToggle) {
            console.log('✅ Rose Plot toggle encontrado, agregando listener');
            
            // Guardar referencia para evitar múltiples listeners
            let isUpdating = false;
            
            this.rosePlotModeToggle.addEventListener('change', () => {
                // Prevenir ejecuciones simultáneas
                if (isUpdating) {
                    console.log('⏸️ Actualización en progreso, ignorando');
                    return;
                }
                
                isUpdating = true;
                
                // Cancelar cualquier actualización pendiente
                if (this.rosePlotUpdateTimer) {
                    clearTimeout(this.rosePlotUpdateTimer);
                }
                
                // Pequeño delay para asegurar que el checkbox se actualizó
                this.rosePlotUpdateTimer = setTimeout(() => {
                    // Leer el estado actual del checkbox directamente
                    const isChecked = this.rosePlotModeToggle.checked;
                    const newMode = isChecked ? 'affinity' : 'frequency';
                    
                    console.log('🔄 Toggle estado:', isChecked, '→ modo:', newMode);
                    console.log('📋 Modo actual antes del cambio:', this.currentRosePlotMode);
                    
                    // Verificar si realmente cambió
                    if (this.currentRosePlotMode === newMode) {
                        console.log('⚠️ Modo ya es', newMode, '- esto no debería pasar');
                        isUpdating = false;
                        return;
                    }
                    
                    // Actualizar el modo
                    this.currentRosePlotMode = newMode;
                    console.log('✅ Modo actualizado a:', this.currentRosePlotMode);
                    
                    // Actualizar Rose Plots
                    if (this.currentFamilyData && this.currentFamilyData.dipole_results) {
                        console.log('🔨 Actualizando gráficos...');
                        this.updateRosePlots(this.currentFamilyData.dipole_results);
                    } else {
                        console.warn('⚠️ No hay datos disponibles');
                    }
                    
                    // Resetear el flag después de un pequeño delay
                    setTimeout(() => {
                        isUpdating = false;
                    }, 200);
                }, 50);
            });
        } else {
            console.warn('⚠️ Rose Plot toggle NO encontrado en el DOM');
        }
    }
    

    async loadFamilyOptions() {
        try {
            
            // Usar únicamente el endpoint v2
            const response = await fetch('/v2/families');
   
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
      
            
            if (data.success) {
                
                if (data.families.length === 0) {
                    console.warn('⚠️ No se encontraron familias en la respuesta');
                    return;
                }
                
                data.families.forEach((family, index) => {
                    const option = document.createElement('option');
                    option.value = family.value;
                    option.textContent = `${family.text} (${family.count} péptidos)`;
                    option.dataset.count = family.count;
                    this.familySelector.appendChild(option);
                });
                
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
            this.showingHighlightsOnly = false;
            this.setVisualizationActionsVisible(false);
            // Mostrar información de la familia
            this.familyInfoText.textContent = `Familia seleccionada: ${selectedText}`;
            this.familyInfo.style.display = 'block';
            if (this.familyHint) {
                this.familyHint.style.display = 'block';
            }
            // Resetear estado de visualización y ocultar controles de resaltado
            this.visualizationReady = false;
            this.cardIndexByCode = {};
            this.setHighlightControlsVisible(false);
            this.updateFilterButtonsState();
            
            // Cargar péptidos de la familia
            await this.loadFamilyPeptides(selectedFamily);
            
            // Si la familia ya fue visualizada antes, restaurar su estado
            const cached = this.familyCache[selectedFamily];
            if (cached && cached.dipoleData && Array.isArray(cached.dipoleData.dipole_results)) {
                this.currentFamilyData = cached.dipoleData;
                this.createDipoleGrid(cached.dipoleData.dipole_results);
                this.visualizationArea.style.display = 'block';
                if (this.statisticsArea) {
                    this.statisticsArea.style.display = 'none';
                }
                this.visualizationReady = true;
                this.enableHighlightControls();
                // Reaplicar resaltados guardados
                if (cached.highlights && cached.highlights.size) {
                    const toggles = this.peptideList ? Array.from(this.peptideList.querySelectorAll('.highlight-toggle')) : [];
                    const toggleMap = new Map(toggles.map(input => [input.dataset.peptideCode, input]));
                    cached.highlights.forEach(code => {
                        this.toggleCardHighlight(code, true, { skipFilterUpdate: true });
                        const checkbox = toggleMap.get(code);
                        if (checkbox) {
                            checkbox.checked = true;
                        }
                    });
                    this.syncHighlightToggleVisuals();
                }
                this.showingHighlightsOnly = cached.filterMode === 'highlights';
                this.setVisualizationActionsVisible(true);
                this.applyVisualizationFilter();
                this.updateFilterButtonsState();
                // Como ya hay visualización, ocultar el hint
                if (this.familyHint) {
                    this.familyHint.style.display = 'none';
                }
            }
            
            // Solo habilitar el botón de visualización
            this.visualizeFamilyBtn.disabled = false;
            
            // Actualizar título
            this.selectedFamilyTitle.textContent = selectedText;
        } else {
            this.familyInfo.style.display = 'none';
            this.peptideList.style.display = 'none';
            this.visualizeFamilyBtn.disabled = true;
            if (this.familyHint) {
                this.familyHint.style.display = 'none';
            }
            this.visualizationReady = false;
            this.cardIndexByCode = {};
            this.setHighlightControlsVisible(false);
            this.setVisualizationActionsVisible(false);
            this.showingHighlightsOnly = false;
            this.updateFilterButtonsState();
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
        const buildHighlightCell = (code) => `
            <td class="highlight-cell" style="display:none">
                <label class="highlight-toggle-control" aria-pressed="false">
                    <input type="checkbox" class="highlight-toggle highlight-toggle-input" data-peptide-code="${code}">
                    <span class="highlight-toggle-chip" role="button">
                        <i class="fas fa-highlighter"></i>
                        <span>Resaltar</span>
                    </span>
                </label>
            </td>
        `;
        
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
                                    <th class="highlight-header" style="display:none">Resaltar</th>
                                </tr>
                            </thead>
                            <tbody>
            `;
            
            all_peptides.forEach(peptide => {
                const mods = this.parseModificationsFromCode(peptide.peptide_code);
                const highlightedSeq = (mods && mods.length)
                    ? this.highlightSequence(peptide.sequence, mods)
                    : (peptide.sequence || '');
                listHTML += `
                    <tr>
                        <td>
                            <span class="peptide-code">${peptide.peptide_code}</span>
                        </td>
                        <td>
                            <div class="sequence-container">
                                <code class="sequence-text-readonly">${highlightedSeq}</code>
                            </div>
                        </td>
                        <td>
                            <span class="ic50-value">
                                ${peptide.ic50_value} ${peptide.ic50_unit}
                            </span>
                        </td>
                        ${buildHighlightCell(peptide.peptide_code)}
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
                                        <th class="highlight-header" style="display:none">Resaltar</th>
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
                                        ${buildHighlightCell(original_peptide.peptide_code)}
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
                                        <th class="highlight-header" style="display:none">Resaltar</th>
                                    </tr>
                                </thead>
                                <tbody>
                `;
                
                modified_peptides.forEach(peptide => {
                    const mods = this.parseModificationsFromCode(peptide.peptide_code);
                    // Preferimos tokens; si no hay tokens, resaltamos diferencias contra el original
                    let highlightedSeq = '';
                    if (mods && mods.length) {
                        highlightedSeq = this.highlightSequence(peptide.sequence, mods);
                    } else if (original_peptide && original_peptide.sequence) {
                        highlightedSeq = this.highlightDiffs(original_peptide.sequence, peptide.sequence);
                    } else {
                        highlightedSeq = peptide.sequence || '';
                    }

                    const differences = (mods && mods.length)
                        ? mods.map(m => m.token).join(', ')
                        : this.findSequenceDifferences(original_peptide?.sequence, peptide.sequence);
                    
                    listHTML += `
                        <tr>
                            <td>
                                <span class="peptide-code">${peptide.peptide_code}</span>
                            </td>
                            <td>
                                <div class="sequence-container">
                                  <code class="sequence-text-readonly">${highlightedSeq}</code>
                                </div>
                            </td>
                            <td>
                                <span class="ic50-value">
                                    ${peptide.ic50_value} ${peptide.ic50_unit}
                                </span>
                            </td>
                            <td>
                                ${differences ? `<span class="difference-badge">${differences}</span>` : '<span class="text-muted">-</span>'}
                            </td>
                            ${buildHighlightCell(peptide.peptide_code)}
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
        // Si la visualización ya está lista, mostrar controles y enlazar eventos
        if (this.visualizationReady) {
            this.enableHighlightControls();
        }
        // Permitir que un clic en la secuencia dispare el resaltado correspondiente
        this.attachSequenceToggleHandlers();
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

    // ✨ NUEVO: Parsear modificaciones a partir del código del péptido
    // Formato esperado en el código: base + _T1X + _E4A + ... (uno o varios)
    // Donde cada token es [A-Z][0-9]+[A-Z] con posiciones basadas en 1
    parseModificationsFromCode(peptideCode) {
        if (!peptideCode || typeof peptideCode !== 'string') return [];
        const idx = peptideCode.indexOf('_');
        if (idx === -1) return [];
        const after = peptideCode.slice(idx + 1);
        const tokens = after.split('_').filter(Boolean);
        const mods = [];
        const re = /^([A-Za-z])(\d+)([A-Za-z])$/;
        for (const t of tokens) {
            const m = t.match(re);
            if (!m) continue;
            const from = m[1].toUpperCase();
            const pos = parseInt(m[2], 10);
            const to = m[3].toUpperCase();
            if (Number.isFinite(pos) && pos > 0) mods.push({ from, pos, to, token: `${from}${pos}${to}` });
        }
        return mods;
    }

    // ✨ NUEVO: Resaltar en la secuencia modificada los cambios indicados por mods
    // Se toma la posición (1-based) y se envuelve el carácter en <span class="seq-change">…</span>
    highlightSequence(sequence, mods) {
        if (!sequence || !mods || mods.length === 0) return sequence || '';
        const chars = Array.from(sequence);
        // Crear un set de posiciones a resaltar para acceso O(1)
        const byPos = new Map();
        for (const m of mods) {
            if (m.pos >= 1 && m.pos <= chars.length) {
                byPos.set(m.pos, m);
            }
        }
        const out = chars.map((ch, i) => {
            const pos = i + 1; // 1-based
            const mod = byPos.get(pos);
            if (mod) {
                const title = `${mod.from}${mod.pos}${mod.to}: ${mod.from}→${mod.to}`;
                return `<span class="seq-change" data-pos="${pos}" title="${title}">${ch}</span>`;
            }
            return ch;
        });
        return out.join('');
    }

    // ✨ NUEVO: Resaltar diferencias entre dos secuencias (fallback cuando no hay tokens)
    // Resalta en la secuencia modificada los caracteres que difieren del original
    highlightDiffs(originalSeq, modifiedSeq) {
        if (!modifiedSeq) return '';
        if (!originalSeq) return modifiedSeq;
        const a = Array.from(originalSeq);
        const b = Array.from(modifiedSeq);
        const L = Math.max(a.length, b.length);
        const out = [];
        for (let i = 0; i < L; i++) {
            const ch = b[i] ?? '';
            const base = a[i] ?? '';
            if (!ch) continue;
            if (base && ch === base) {
                out.push(ch);
            } else {
                const pos = i + 1;
                const title = base ? `${base}${pos}${ch}: ${base}→${ch}` : `+${ch} @${pos}`;
                out.push(`<span class="seq-change" data-pos="${pos}" title="${title}">${ch}</span>`);
            }
        }
        return out.join('');
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
        

        
        try {
            this.showLoading(true, 'Calculando dipolos de la familia...');
            
            // Cargar datos con dipolos calculados (v2 con fallback a legacy)
            const response = await fetch(`/v2/family-dipoles/${selectedFamily}`);
            const data = await response.json();
            
            if (data.success) {

                this.currentFamilyData = data.data;
                this.showingHighlightsOnly = false;
                this.createDipoleGrid(data.data.dipole_results);
                // Crear gráficos de análisis de ángulos
                this.createAngleCharts(data.data.dipole_results);
                // Crear gráficos de análisis de zonas funcionales
                this.createZonesCharts(data.data.dipole_results);
                // Cachear datos de la familia y estado de resaltado
                this.cacheFamilyVisualization(selectedFamily, data.data);
                
                // Mostrar área de visualización (estadísticas eliminadas)
                this.visualizationArea.style.display = 'block';
                if (this.statisticsArea) {
                    this.statisticsArea.style.display = 'none';
                }
                // Asegurar que la señal quede oculta después de visualizar
                if (this.familyHint) {
                    this.familyHint.style.display = 'none';
                }
                // Visualización lista: habilitar controles de resaltado en tablas
                this.visualizationReady = true;
                this.enableHighlightControls();
                this.setVisualizationActionsVisible(true);
                this.applyVisualizationFilter();
                this.updateFilterButtonsState();
                
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

    cacheFamilyVisualization(familyName, dipoleData) {
        const highlights = this.getCurrentHighlights();
        this.familyCache[familyName] = {
            dipoleData,
            highlights,
            filterMode: this.showingHighlightsOnly ? 'highlights' : 'all'
        };
    }

    getCurrentHighlights() {
        const set = new Set();
        const toggles = this.peptideList ? this.peptideList.querySelectorAll('.highlight-toggle') : [];
        toggles.forEach(inp => {
            if (inp.checked && inp.dataset.peptideCode) set.add(inp.dataset.peptideCode);
        });
        return set;
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

        // Priorizar el péptido original (sin "_") al inicio
        try {
            dipoleResults = [...dipoleResults].sort((a, b) => {
                const aOrig = !String(a.peptide_code || '').includes('_');
                const bOrig = !String(b.peptide_code || '').includes('_');
                if (aOrig && !bOrig) return -1;
                if (!aOrig && bOrig) return 1;
                return String(a.peptide_code || '').localeCompare(String(b.peptide_code || ''), 'es');
            });
        } catch (e) { /* si falla, se usa el orden original */ }

        // ✅ CAMBIO: CSS Grid puro sin Bootstrap
        let gridHTML = '';
        this.cardIndexByCode = {};

        dipoleResults.forEach((result, index) => {
            const dipoleData = result.dipole_data;
            const peptideCode = result.peptide_code;
            this.cardIndexByCode[peptideCode] = index;
            
            const angles = this.computeAxisAngles(dipoleData);

            gridHTML += `
                <div class="dipole-visualization-card" data-peptide-code="${peptideCode}">
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
                                    <div class="stat-label">Ángulo X</div>
                                    <div class="stat-value">${angles.x}°</div>
                                </div>
                                <div class="dipole-stat">
                                    <div class="stat-label">Ángulo Y</div>
                                    <div class="stat-value">${angles.y}°</div>
                                </div>
                                <div class="dipole-stat">
                                    <div class="stat-label">Ángulo Z</div>
                                    <div class="stat-value">${angles.z}°</div>
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
        
    // Reemplazar el área superior por una leyenda compacta
    dipoleVisualization.innerHTML = this.buildLegendHTML();
        
        // Insertar grid en visualizationGrid
        visualizationGrid.innerHTML = gridHTML;

        // Inicializar visualizadores py3Dmol para cada toxina
        this.initializeDipoleViewers(dipoleResults);
    }

    buildLegendHTML() {
        return `
            <div class="dipole-legend" role="note" aria-label="Leyenda de colores de flechas">
                <span class="legend-item"><span class="legend-swatch" style="--legend-color: red"></span> Dipolo</span>
                <span class="legend-item"><span class="legend-swatch" style="--legend-color: green"></span> Eje X</span>
                <span class="legend-item"><span class="legend-swatch" style="--legend-color: orange"></span> Eje Y</span>
                <span class="legend-item"><span class="legend-swatch" style="--legend-color: blue"></span> Eje Z</span>
            </div>
        `;
    }

    // Mostrar columna "Resaltar" y enlazar eventos
    enableHighlightControls() {
        if (!this.peptideList) return;
        this.setHighlightControlsVisible(true);
        const toggles = this.peptideList.querySelectorAll('.highlight-toggle');
        toggles.forEach(input => {
            input.removeEventListener('change', this._onHighlightToggle);
        });
        this._onHighlightToggle = (e) => {
            const code = e.target.dataset.peptideCode;
            const on = e.target.checked;
            this.updateToggleControlVisual(e.target, on);
            this.toggleCardHighlight(code, on, { skipFilterUpdate: true });
            // Actualizar cache de resaltados para la familia actual
            const fname = this.familySelector.value;
            if (!this.familyCache[fname]) this.familyCache[fname] = { dipoleData: this.currentFamilyData, highlights: new Set(), filterMode: 'all' };
            if (on) {
                this.familyCache[fname].highlights.add(code);
            } else {
                this.familyCache[fname].highlights.delete(code);
            }
            this.applyVisualizationFilter();
            this.updateFilterButtonsState();
            if (this.familyCache[fname]) {
                this.familyCache[fname].filterMode = this.showingHighlightsOnly ? 'highlights' : 'all';
            }
        };
        toggles.forEach(input => input.addEventListener('change', this._onHighlightToggle));
        this.syncHighlightToggleVisuals();
        if (this.visualizationReady) {
            this.setVisualizationActionsVisible(true);
        }
        this.updateFilterButtonsState();
    }

    setHighlightControlsVisible(visible) {
        if (!this.peptideList) return;
        const display = visible ? 'table-cell' : 'none';
        this.peptideList.querySelectorAll('.highlight-header, .highlight-cell').forEach(el => {
            el.style.display = display;
        });
    }

    toggleCardHighlight(peptideCode, on, options = {}) {
        const { skipFilterUpdate = false } = options;
        const index = this.cardIndexByCode[peptideCode];
    if (!this.visualizationGrid) return;
    const cards = Array.from(this.visualizationGrid.querySelectorAll('.dipole-visualization-card'));
    const card = (index != null) ? cards[index] : cards.find(c => (c.dataset.peptideCode||'') === peptideCode);
        if (!card) return;
        card.classList.toggle('highlighted-card', !!on);
        // No auto-scroll al activar, para permitir seleccionar múltiples a la vez
        if (!skipFilterUpdate) {
            this.applyVisualizationFilter();
            this.updateFilterButtonsState();
        }
    }

    // Permite hacer clic en la secuencia para alternar el resaltado de su visualización
    attachSequenceToggleHandlers() {
        // Limpia handler previo si existiese para evitar duplicados
        if (this._sequenceClickHandler) {
            this.peptideList.removeEventListener('click', this._sequenceClickHandler);
        }
        this._sequenceClickHandler = (e) => {
            const target = e.target;
            // Solo reaccionar si se hace clic dentro de la celda de secuencia
            if (!(target.closest('.sequence-container') || target.closest('.sequence-text-readonly'))) return;
            const row = target.closest('tr');
            if (!row) return;
            const codeEl = row.querySelector('.peptide-code');
            const peptideCode = codeEl ? codeEl.textContent.trim() : null;
            if (!peptideCode) return;
            const checkbox = row.querySelector('.highlight-toggle');
            // Si aún no se ha generado la visualización, no hay nada que resaltar
            if (!this.visualizationReady) return;
            // Asegurar columna visible tras visualizar
            this.setHighlightControlsVisible(true);
            if (checkbox) {
                checkbox.checked = !checkbox.checked;
                // Disparar el evento change para mantener cache sincronizada
                checkbox.dispatchEvent(new Event('change', { bubbles: true }));
            } else {
                // Fallback: alternar por código aunque no exista checkbox en la fila
                const cards = this.visualizationGrid ? Array.from(this.visualizationGrid.querySelectorAll('.dipole-visualization-card')) : [];
                const card = cards.find(c => (c.dataset.peptideCode||'') === peptideCode);
                if (card) {
                    const newState = !card.classList.contains('highlighted-card');
                    this.toggleCardHighlight(peptideCode, newState, { skipFilterUpdate: true });
                    // Actualizar cache manualmente si no hay checkbox
                    const fname = this.familySelector.value;
                    if (!this.familyCache[fname]) this.familyCache[fname] = { dipoleData: this.currentFamilyData, highlights: new Set(), filterMode: 'all' };
                    if (newState) this.familyCache[fname].highlights.add(peptideCode);
                    else this.familyCache[fname].highlights.delete(peptideCode);
                    this.applyVisualizationFilter();
                    this.updateFilterButtonsState();
                    if (this.familyCache[fname]) {
                        this.familyCache[fname].filterMode = this.showingHighlightsOnly ? 'highlights' : 'all';
                    }
                }
            }
        };
        this.peptideList.addEventListener('click', this._sequenceClickHandler);
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

        // Eje X (verde), Y (naranja) y Z (azul) desde el centro de masa
        const axisLen = 20;
        const xAxisEnd = [start[0] + axisLen, start[1], start[2]];
        const yAxisEnd = [start[0], start[1] + axisLen, start[2]];
        const zAxisEnd = [start[0], start[1], start[2] + axisLen];

        viewer.addArrow({
            start: { x: start[0], y: start[1], z: start[2] },
            end: { x: xAxisEnd[0], y: xAxisEnd[1], z: xAxisEnd[2] },
            radius: 0.5,
            color: 'green',
            opacity: 0.6
        });

        viewer.addArrow({
            start: { x: start[0], y: start[1], z: start[2] },
            end: { x: yAxisEnd[0], y: yAxisEnd[1], z: yAxisEnd[2] },
            radius: 0.5,
            color: 'orange',
            opacity: 0.6
        });

        // Eje Z de referencia (azul)
        viewer.addArrow({
            start: { x: start[0], y: start[1], z: start[2] },
            end: { x: zAxisEnd[0], y: zAxisEnd[1], z: zAxisEnd[2] },
            radius: 0.5,
            color: 'blue',
            opacity: 0.6
        });
    }

    // Cálculo de ángulos con respecto a ejes X/Y/Z a partir del vector
    computeAxisAngles(dipoleData) {
        const v = dipoleData?.vector || [0,0,1];
        const mag = Math.max(1e-8, dipoleData?.magnitude || Math.hypot(v[0], v[1], v[2]));
        const clamp = (x) => Math.max(-1, Math.min(1, x));
        const toDeg = (r) => (r * 180 / Math.PI);
        const ax = toDeg(Math.acos(clamp(v[0] / mag)));
        const ay = toDeg(Math.acos(clamp(v[1] / mag)));
        const az = toDeg(Math.acos(clamp(v[2] / mag)));
        return { x: ax.toFixed(1), y: ay.toFixed(1), z: az.toFixed(1) };
    }

    classifyAngleZone(angle, axis, family = null) {
        const useFamily = this.currentZonesMode === 'family' && family && this.FAMILY_ZONES[family];
        
        if (useFamily) {
            const familyZone = this.FAMILY_ZONES[family][axis];
            if (familyZone === null) {
                // Si la familia no tiene criterio para este eje, usar general
                return this.classifyAngleZoneGeneral(angle, axis);
            }
            const [min, max] = familyZone;
            if (angle >= min && angle <= max) {
                return 'optimal';
            }
            // Para familias, todo lo que no es óptimo es desfavorable
            return 'unfavorable';
        }
        
        return this.classifyAngleZoneGeneral(angle, axis);
    }

    classifyAngleZoneGeneral(angle, axis) {
        const zones = this.GENERAL_ZONES[axis];
        
        if (axis === 'Z') {
            // Eje Z tiene dos rangos óptimos
            if (angle >= zones.optimalA[0] && angle <= zones.optimalA[1]) {
                return 'optimal';
            }
            if (angle >= zones.optimalB[0] && angle <= zones.optimalB[1]) {
                return 'optimal';
            }
            // Revisar zona aceptable
            for (const [min, max] of zones.acceptable) {
                if (angle >= min && angle <= max) {
                    return 'acceptable';
                }
            }
            return 'unfavorable';
        }
        
        // Ejes X e Y
        if (angle >= zones.optimal[0] && angle <= zones.optimal[1]) {
            return 'optimal';
        }
        
        for (const [min, max] of zones.acceptable) {
            if (angle >= min && angle <= max) {
                return 'acceptable';
            }
        }
        
        return 'unfavorable';
    }

    updateZonesLegend() {
        if (!this.zonesLegend) return;

        const currentFamily = this.familySelector.value;
        let legendHTML = '';

        if (this.currentZonesMode === 'general') {
            // Modo General: mostrar rangos generales por eje
            legendHTML = `
                <div class="legend-section">
                    <h4 class="legend-axis-title"><i class="fas fa-arrows-alt-h"></i> Eje X</h4>
                    <div class="legend-items">
                        <div class="legend-item">
                            <span class="legend-color" style="background: #4CAF50;"></span>
                            <span class="legend-text">Óptimo (28-32°)</span>
                        </div>
                        <div class="legend-item">
                            <span class="legend-color" style="background: #FFC107;"></span>
                            <span class="legend-text">Aceptable (20-28°, 32-35°)</span>
                        </div>
                        <div class="legend-item">
                            <span class="legend-color" style="background: #F44336;"></span>
                            <span class="legend-text">Desfavorable (<20°, >35°)</span>
                        </div>
                    </div>
                </div>
                <div class="legend-section">
                    <h4 class="legend-axis-title"><i class="fas fa-arrows-alt-v"></i> Eje Y</h4>
                    <div class="legend-items">
                        <div class="legend-item">
                            <span class="legend-color" style="background: #4CAF50;"></span>
                            <span class="legend-text">Óptimo (110-122°)</span>
                        </div>
                        <div class="legend-item">
                            <span class="legend-color" style="background: #FFC107;"></span>
                            <span class="legend-text">Aceptable (100-110°, 122-125°)</span>
                        </div>
                        <div class="legend-item">
                            <span class="legend-color" style="background: #F44336;"></span>
                            <span class="legend-text">Desfavorable (<100°, >125°)</span>
                        </div>
                    </div>
                </div>
                <div class="legend-section">
                    <h4 class="legend-axis-title"><i class="fas fa-expand-arrows-alt"></i> Eje Z</h4>
                    <div class="legend-items">
                        <div class="legend-item">
                            <span class="legend-color" style="background: #4CAF50;"></span>
                            <span class="legend-text">Óptimo (70-90°, 100-112°)</span>
                        </div>
                        <div class="legend-item">
                            <span class="legend-color" style="background: #FFC107;"></span>
                            <span class="legend-text">Aceptable (90-100°)</span>
                        </div>
                        <div class="legend-item">
                            <span class="legend-color" style="background: #F44336;"></span>
                            <span class="legend-text">Desfavorable (<70°, >112°)</span>
                        </div>
                    </div>
                </div>
            `;
        } else {
            // Modo Por Familia: mostrar rangos específicos de la familia
            const familyZones = this.FAMILY_ZONES[currentFamily];
            if (familyZones) {
                legendHTML = '<div class="legend-family-info"><i class="fas fa-dna"></i> Criterios para ' + currentFamily + '</div>';
                
                ['X', 'Y', 'Z'].forEach(axis => {
                    const axisIcon = axis === 'X' ? 'fa-arrows-alt-h' : (axis === 'Y' ? 'fa-arrows-alt-v' : 'fa-expand-arrows-alt');
                    const range = familyZones[axis];
                    
                    if (range === null) {
                        legendHTML += `
                            <div class="legend-section">
                                <h4 class="legend-axis-title"><i class="fas ${axisIcon}"></i> Eje ${axis}</h4>
                                <div class="legend-items">
                                    <div class="legend-item legend-item-muted">
                                        <span class="legend-text">Sin criterio específico (usa General)</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    } else {
                        legendHTML += `
                            <div class="legend-section">
                                <h4 class="legend-axis-title"><i class="fas ${axisIcon}"></i> Eje ${axis}</h4>
                                <div class="legend-items">
                                    <div class="legend-item">
                                        <span class="legend-color" style="background: #4CAF50;"></span>
                                        <span class="legend-text">Óptimo (${range[0]}-${range[1]}°)</span>
                                    </div>
                                    <div class="legend-item">
                                        <span class="legend-color" style="background: #F44336;"></span>
                                        <span class="legend-text">Desfavorable (<${range[0]}°, >${range[1]}°)</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                });
            }
        }

        this.zonesLegend.innerHTML = legendHTML;
    }

    createAngleCharts(dipoleResults) {
        if (!dipoleResults || dipoleResults.length === 0 || !this.angleAnalysisSection) {
            return;
        }

        console.log('📊 Creando Rose Plots en modo:', this.currentRosePlotMode);

        // Verificar que Plotly esté disponible
        if (typeof Plotly === 'undefined') {
            console.warn('Plotly no está disponible aún. Reintentando en 500ms...');
            setTimeout(() => this.createAngleCharts(dipoleResults), 500);
            return;
        }

        // Mostrar la sección de análisis
        this.angleAnalysisSection.style.display = 'block';

        // Crear Rose Plots para cada eje
        const createRosePlotData = (axis) => {
            // Crear bins para el rango 0-180°
            const numBins = Math.ceil(180 / this.rosePlotBinSize);
            const bins = [];
            
            // Inicializar bins
            for (let i = 0; i < numBins; i++) {
                const binStart = i * this.rosePlotBinSize;
                const binEnd = Math.min((i + 1) * this.rosePlotBinSize, 180);
                bins.push({
                    start: binStart,
                    end: binEnd,
                    center: (binStart + binEnd) / 2,
                    peptides: [],
                    angles: [],
                    ic50_values: []
                });
            }
            
            // Clasificar péptidos en bins
            dipoleResults.forEach(result => {
                const angles = this.computeAxisAngles(result.dipole_data);
                let angle;
                
                if (axis === 'X') angle = parseFloat(angles.x);
                else if (axis === 'Y') angle = parseFloat(angles.y);
                else angle = parseFloat(angles.z);
                
                // Encontrar el bin correspondiente
                const binIndex = Math.min(Math.floor(angle / this.rosePlotBinSize), numBins - 1);
                
                bins[binIndex].peptides.push(result.peptide_code);
                bins[binIndex].angles.push(angle);
                
                // Extraer valor numérico de IC50
                const ic50Value = parseFloat(result.ic50_value);
                if (!isNaN(ic50Value) && ic50Value > 0) {
                    bins[binIndex].ic50_values.push(ic50Value);
                }
            });
            
            // Calcular valores según el modo
            const theta = []; // ángulos en grados
            const r = []; // valores radiales
            const customdata = [];
            const colors = [];
            const hovertext = [];
            
            bins.forEach(bin => {
                if (bin.peptides.length > 0) {
                    theta.push(bin.center);
                    
                    let radialValue;
                    let medianIC50 = 0;
                    let affinitySum = 0;
                    
                    if (this.currentRosePlotMode === 'frequency') {
                        radialValue = bin.peptides.length;
                    } else {
                        // Modo afinidad: suma de 1/IC50
                        bin.ic50_values.forEach(ic50 => {
                            affinitySum += 1 / ic50;
                        });
                        radialValue = affinitySum;
                    }
                    
                    r.push(radialValue);
                    
                    // Calcular mediana de IC50
                    if (bin.ic50_values.length > 0) {
                        const sortedIC50 = [...bin.ic50_values].sort((a, b) => a - b);
                        const mid = Math.floor(sortedIC50.length / 2);
                        medianIC50 = sortedIC50.length % 2 === 0 
                            ? (sortedIC50[mid - 1] + sortedIC50[mid]) / 2 
                            : sortedIC50[mid];
                    }
                    
                    // Color basado en afinidad (verde = alta afinidad/bajo IC50, rojo = baja afinidad/alto IC50)
                    const color = medianIC50 > 0 ? this.getAffinityColor(medianIC50) : '#808080';
                    colors.push(color);
                    
                    // Formatear lista de péptidos
                    const peptideList = '• ' + bin.peptides.join('<br>• ');
                    
                    // Información para tooltip
                    const info = {
                        peptideList: peptideList,
                        count: bin.peptides.length,
                        range: `${bin.start.toFixed(0)}°-${bin.end.toFixed(0)}°`,
                        medianIC50: medianIC50.toFixed(2),
                        value: radialValue.toFixed(3)
                    };
                    customdata.push(info);
                    
                    // Texto para hover
                    const modeLabel = this.currentRosePlotMode === 'frequency' ? 'Frecuencia' : 'Afinidad Σ(1/IC50)';
                    hovertext.push(
                        `<b>Rango: ${info.range}</b><br>` +
                        `Péptidos: ${info.count}<br>` +
                        `${modeLabel}: ${info.value}<br>` +
                        `IC50 Mediana: ${info.medianIC50} nM<br>` +
                        `<br><b>Lista de péptidos:</b><br>${peptideList}`
                    );
                }
            });
            
            return {
                type: 'barpolar',
                r: r,
                theta: theta,
                marker: {
                    color: colors,
                    line: {
                        color: 'white',
                        width: 1
                    }
                },
                hovertext: hovertext,
                hoverinfo: 'text',
                hoverlabel: {
                    align: 'left',
                    bgcolor: 'white',
                    font: { size: 12, family: 'monospace' }
                }
            };
        };
        
        // Calcular dirección promedio para cada eje
        const calculateMeanDirection = (axis) => {
            let sumX = 0, sumY = 0;
            
            dipoleResults.forEach(result => {
                const angles = this.computeAxisAngles(result.dipole_data);
                let angle;
                
                if (axis === 'X') angle = parseFloat(angles.x);
                else if (axis === 'Y') angle = parseFloat(angles.y);
                else angle = parseFloat(angles.z);
                
                const rad = angle * Math.PI / 180;
                sumX += Math.cos(rad);
                sumY += Math.sin(rad);
            });
            
            const meanAngle = Math.atan2(sumY, sumX) * 180 / Math.PI;
            return meanAngle >= 0 ? meanAngle : meanAngle + 360;
        };

        const layout = {
            polar: {
                radialaxis: {
                    visible: true,
                    showline: true,
                    showticklabels: true,
                    tickfont: { size: 10 },
                    title: this.currentRosePlotMode === 'frequency' ? 'Frecuencia' : 'Σ(1/IC50)'
                },
                angularaxis: {
                    direction: 'clockwise',
                    rotation: 90,
                    thetaunit: 'degrees',
                    range: [0, 180],
                    showline: true,
                    showticklabels: true,
                    tickmode: 'linear',
                    tick0: 0,
                    dtick: 30
                }
            },
            showlegend: false,
            margin: { t: 40, b: 40, l: 60, r: 60 },
            height: 400,
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)'
        };

        const config = {
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
            toImageButtonOptions: {
                format: 'svg',
                filename: 'rose_plot_dipole'
            }
        };

        // Crear los 3 Rose Plots
        if (this.angleChartX) {
            const data = [createRosePlotData('X')];
            Plotly.newPlot(this.angleChartX, data, layout, config);
        }

        if (this.angleChartY) {
            const data = [createRosePlotData('Y')];
            Plotly.newPlot(this.angleChartY, data, layout, config);
        }

        if (this.angleChartZ) {
            const data = [createRosePlotData('Z')];
            Plotly.newPlot(this.angleChartZ, data, layout, config);
        }
    }
    
    getAffinityColor(ic50Value) {
        // Escala de colores: verde (alta afinidad/bajo IC50) → amarillo → rojo (baja afinidad/alto IC50)
        // Rango típico de IC50: 1-1000 nM
        // Usamos escala logarítmica para mejor distribución
        const logIC50 = Math.log10(Math.max(ic50Value, 1));
        const logMin = 0; // log10(1) = 0
        const logMax = 3; // log10(1000) = 3
        
        // Normalizar entre 0 y 1
        let normalized = (logIC50 - logMin) / (logMax - logMin);
        normalized = Math.max(0, Math.min(1, normalized)); // Clamp entre 0-1
        
        // Interpolar color
        if (normalized < 0.5) {
            // Verde a Amarillo
            const t = normalized * 2;
            const r = Math.round(76 + (255 - 76) * t);
            const g = Math.round(175 + (235 - 175) * t);
            const b = Math.round(80 + (59 - 80) * t);
            return `rgb(${r}, ${g}, ${b})`;
        } else {
            // Amarillo a Rojo
            const t = (normalized - 0.5) * 2;
            const r = Math.round(255);
            const g = Math.round(235 - (235 - 87) * t);
            const b = Math.round(59 - (59 - 34) * t);
            return `rgb(${r}, ${g}, ${b})`;
        }
    }

    updateRosePlots(dipoleResults) {
        // Función optimizada que solo actualiza los datos sin recrear los gráficos
        console.log('🔄 Actualizando Rose Plots (sin recrear DOM)');
        
        if (!dipoleResults || dipoleResults.length === 0) {
            console.warn('⚠️ No hay datos para actualizar');
            return;
        }

        // Helper para generar datos de un eje
        const generateAxisData = (axis) => {
            const numBins = Math.ceil(180 / this.rosePlotBinSize);
            const bins = [];
            
            for (let i = 0; i < numBins; i++) {
                const binStart = i * this.rosePlotBinSize;
                const binEnd = Math.min((i + 1) * this.rosePlotBinSize, 180);
                bins.push({
                    start: binStart,
                    end: binEnd,
                    center: (binStart + binEnd) / 2,
                    peptides: [],
                    angles: [],
                    ic50_values: []
                });
            }
            
            dipoleResults.forEach(result => {
                const angles = this.computeAxisAngles(result.dipole_data);
                let angle;
                
                if (axis === 'X') angle = parseFloat(angles.x);
                else if (axis === 'Y') angle = parseFloat(angles.y);
                else angle = parseFloat(angles.z);
                
                const binIndex = Math.min(Math.floor(angle / this.rosePlotBinSize), numBins - 1);
                
                bins[binIndex].peptides.push(result.peptide_code);
                bins[binIndex].angles.push(angle);
                
                const ic50Value = parseFloat(result.ic50_value);
                if (!isNaN(ic50Value) && ic50Value > 0) {
                    bins[binIndex].ic50_values.push(ic50Value);
                }
            });
            
            const theta = [];
            const r = [];
            const colors = [];
            const hovertext = [];
            
            bins.forEach(bin => {
                if (bin.peptides.length > 0) {
                    theta.push(bin.center);
                    
                    let radialValue;
                    let medianIC50 = 0;
                    
                    if (this.currentRosePlotMode === 'frequency') {
                        radialValue = bin.peptides.length;
                    } else {
                        let affinitySum = 0;
                        bin.ic50_values.forEach(ic50 => {
                            affinitySum += 1 / ic50;
                        });
                        radialValue = affinitySum;
                    }
                    
                    r.push(radialValue);
                    
                    if (bin.ic50_values.length > 0) {
                        const sortedIC50 = [...bin.ic50_values].sort((a, b) => a - b);
                        const mid = Math.floor(sortedIC50.length / 2);
                        medianIC50 = sortedIC50.length % 2 === 0 
                            ? (sortedIC50[mid - 1] + sortedIC50[mid]) / 2 
                            : sortedIC50[mid];
                    }
                    
                    const color = medianIC50 > 0 ? this.getAffinityColor(medianIC50) : '#808080';
                    colors.push(color);
                    
                    const peptideList = '• ' + bin.peptides.join('<br>• ');
                    const modeLabel = this.currentRosePlotMode === 'frequency' ? 'Frecuencia' : 'Afinidad Σ(1/IC50)';
                    
                    hovertext.push(
                        `<b>Rango: ${bin.start.toFixed(0)}°-${bin.end.toFixed(0)}°</b><br>` +
                        `Péptidos: ${bin.peptides.length}<br>` +
                        `${modeLabel}: ${radialValue.toFixed(3)}<br>` +
                        `IC50 Mediana: ${medianIC50.toFixed(2)} nM<br>` +
                        `<br><b>Lista de péptidos:</b><br>${peptideList}`
                    );
                }
            });
            
            return { theta, r, colors, hovertext };
        };

        // Actualizar cada gráfico usando Plotly.update
        const updateChart = (chartElement, axisName) => {
            if (!chartElement) return;
            
            const data = generateAxisData(axisName);
            const modeLabel = this.currentRosePlotMode === 'frequency' ? 'Frecuencia' : 'Σ(1/IC50)';
            
            Plotly.update(chartElement, {
                r: [data.r],
                theta: [data.theta],
                'marker.color': [data.colors],
                hovertext: [data.hovertext]
            }, {
                'polar.radialaxis.title': modeLabel
            });
        };

        updateChart(this.angleChartX, 'X');
        updateChart(this.angleChartY, 'Y');
        updateChart(this.angleChartZ, 'Z');
        
        console.log('✅ Rose Plots actualizados en modo:', this.currentRosePlotMode);
    }

    createZonesCharts(dipoleResults) {
        if (!dipoleResults || dipoleResults.length === 0 || !this.zonesAnalysisSection) {
            return;
        }

        // Verificar que Plotly esté disponible
        if (typeof Plotly === 'undefined') {
            console.warn('Plotly no está disponible para zonas. Reintentando en 500ms...');
            setTimeout(() => this.createZonesCharts(dipoleResults), 500);
            return;
        }

        // Mostrar la sección de análisis
        this.zonesAnalysisSection.style.display = 'block';

        // Actualizar leyenda con rangos
        this.updateZonesLegend();

        // Obtener familia actual
        const currentFamily = this.familySelector.value;

        // Recolectar clasificaciones por eje
        const classifications = { X: {}, Y: {}, Z: {} };
        
        ['X', 'Y', 'Z'].forEach(axis => {
            classifications[axis] = {
                optimal: [],
                acceptable: [],
                unfavorable: []
            };
        });

        dipoleResults.forEach(result => {
            const angles = this.computeAxisAngles(result.dipole_data);
            const peptideCode = result.peptide_code;
            
            ['X', 'Y', 'Z'].forEach(axis => {
                const angle = parseFloat(angles[axis.toLowerCase()]);
                const zone = this.classifyAngleZone(angle, axis, currentFamily);
                classifications[axis][zone].push(peptideCode);
            });
        });

        // Crear datos para gráfico de torta
        const createZonePieData = (axisData) => {
            const labels = [];
            const values = [];
            const colors = [];
            const customdata = [];

            if (axisData.optimal.length > 0) {
                labels.push('Óptimo');
                values.push(axisData.optimal.length);
                colors.push(this.ZONE_COLORS.optimal);
                const formattedList = axisData.optimal.join('<br>• ');
                customdata.push('• ' + formattedList);
            }
            if (axisData.acceptable.length > 0) {
                labels.push('Aceptable');
                values.push(axisData.acceptable.length);
                colors.push(this.ZONE_COLORS.acceptable);
                const formattedList = axisData.acceptable.join('<br>• ');
                customdata.push('• ' + formattedList);
            }
            if (axisData.unfavorable.length > 0) {
                labels.push('Desfavorable');
                values.push(axisData.unfavorable.length);
                colors.push(this.ZONE_COLORS.unfavorable);
                const formattedList = axisData.unfavorable.join('<br>• ');
                customdata.push('• ' + formattedList);
            }

            return [{
                type: 'pie',
                labels: labels,
                values: values,
                customdata: customdata,
                marker: {
                    colors: colors,
                    line: {
                        color: 'white',
                        width: 2
                    }
                },
                textinfo: 'label+percent',
                textposition: 'auto',
                textfont: {
                    size: 14,
                    color: 'white',
                    family: 'Arial, sans-serif'
                },
                hovertemplate: '<b>%{label}</b><br>' +
                              'Total: %{value} péptidos<br>' +
                              'Porcentaje: %{percent}<br>' +
                              '<br><b>Péptidos en esta zona:</b><br>%{customdata}<br>' +
                              '<extra></extra>',
                hoverlabel: {
                    align: 'left',
                    bgcolor: 'white',
                    font: { size: 12, family: 'monospace' },
                    bordercolor: colors
                }
            }];
        };

        const layout = {
            showlegend: true,
            legend: {
                orientation: 'h',
                y: -0.15,
                x: 0.5,
                xanchor: 'center',
                font: {
                    size: 12
                }
            },
            margin: { t: 20, b: 60, l: 20, r: 20 },
            height: 350,
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)'
        };

        const config = {
            responsive: true,
            displayModeBar: false
        };

        // Renderizar los 3 gráficos
        if (this.zoneChartX) {
            Plotly.newPlot(this.zoneChartX, createZonePieData(classifications.X), layout, config);
        }

        if (this.zoneChartY) {
            Plotly.newPlot(this.zoneChartY, createZonePieData(classifications.Y), layout, config);
        }

        if (this.zoneChartZ) {
            Plotly.newPlot(this.zoneChartZ, createZonePieData(classifications.Z), layout, config);
        }
    }

    displayFamilyStats() {
        // Eliminado en la UI. Se conserva el método como no-op por compatibilidad.
        return;
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