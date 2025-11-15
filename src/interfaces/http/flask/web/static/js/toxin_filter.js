document.addEventListener('DOMContentLoaded', () => {
  const gapMinEl = document.getElementById('gap-min');
  const gapMaxEl = document.getElementById('gap-max');
  const requirePairEl = document.getElementById('require-pair');
  const runBtn = document.getElementById('run-filter');
  const exportBtn = document.getElementById('export-xlsx');
  const navbarExportBtn = document.getElementById('navbar-export-xlsx');
  const bodyEl = document.getElementById('motif-body');
  const hitCountEl = document.getElementById('hit-count');
  const statusEl = document.getElementById('status-line');
  const toggleBtn = document.getElementById('toggle-results');
  const resultsBody = document.getElementById('results-body');
  // Tabla: paginación local
  const tblPrev = document.getElementById('tbl-prev');
  const tblNext = document.getElementById('tbl-next');
  const tblPage = document.getElementById('tbl-page');
  let tblPageNum = 1;
  const tblPageSize = 10; // keep in sync with CSS --page-size
  let tblRows = [];
  let tableSearchQuery = '';
  // UI and filtering state
  const EXCLUDED_ACCESSIONS = new Set(["P83303","P84507","P0DL84","P84508","D2Y1X8","P0DL72","P0CH54"]);
  let currentMode = 'all'; // modes: all, with_nav, without_nav, with_ic50, without_ic50

  // Glosario toggle functionality
  const glossaryToggle = document.getElementById('glossary-toggle');
  const glossaryContent = document.getElementById('glossary-content');
  if (glossaryToggle && glossaryContent) {
    glossaryToggle.addEventListener('click', () => {
      const isExpanded = glossaryToggle.getAttribute('aria-expanded') === 'true';
      glossaryToggle.setAttribute('aria-expanded', !isExpanded);
      glossaryContent.classList.toggle('collapsed');
    });
  }

  // SheetJS loader (on-demand)
  let _sheetJsLoading = null;
  async function loadSheetJsOnce() {
    if (window.XLSX) return;
    if (_sheetJsLoading) return _sheetJsLoading;
    _sheetJsLoading = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      // Build mínima suficiente para utils y write
      s.src = 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.core.min.js';
      s.defer = true;
      s.onload = () => resolve();
      s.onerror = (e) => reject(e);
      document.head.appendChild(s);
    });
    return _sheetJsLoading;
  }

  // Inject simple tabs for filtering modes without changing header height (use placeholder if present)
  const resultsHeader = document.querySelector('.results-table-header');
  if (resultsHeader) {
    const placeholder = resultsHeader.querySelector('#tabs-placeholder');
    const tabs = document.createElement('div');
    tabs.className = 'filter-mode-tabs';
    tabs.style.display = 'flex';
    tabs.style.gap = '0.5rem';
    tabs.style.margin = '0.5rem 0';
    tabs.innerHTML = `
      <button class="tab-btn active" data-mode="all">Todos</button>
      <button class="tab-btn" data-mode="with_nav">Con Nav1.7</button>
      <button class="tab-btn" data-mode="without_nav">Sin Nav1.7</button>
      <button class="tab-btn" data-mode="with_ic50">Con IC50</button>
      <button class="tab-btn" data-mode="without_ic50">Sin IC50</button>
    `;
    if (placeholder) {
      placeholder.replaceWith(tabs);
    } else {
      const searchArea = resultsHeader.querySelector('div[style]') || resultsHeader;
      resultsHeader.insertBefore(tabs, searchArea.nextSibling);
    }

    tabs.addEventListener('click', (ev) => {
      const btn = ev.target.closest('.tab-btn');
      if (!btn) return;
      tabs.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentMode = btn.dataset.mode || 'all';
      tblPageNum = 1;
      renderTablePage();
    });
  }

  function setStatus(text) {
    if (!statusEl) return;
    const span = statusEl.querySelector('.status-text') || statusEl.querySelector('span') || statusEl;
    span.textContent = text || '';
    statusEl.style.visibility = text ? 'visible' : 'hidden';
  }

  function toggleEmptyState(show) {
    const emptyState = document.getElementById('empty-state');
    const resultsTable = document.querySelector('.results-table');
    if (emptyState && resultsTable) {
      emptyState.style.display = show ? 'block' : 'none';
      resultsTable.style.display = show ? 'none' : 'table';
    }
  }

  function ensureSkeletonRows() {
    if (!bodyEl) return;
    const rows = [];
    for (let i = 0; i < tblPageSize; i++) {
      rows.push('<tr class="skeleton-row">' + '<td></td>'.repeat(9) + '</tr>');
    }
    bodyEl.innerHTML = rows.join('');
  }

  function paintRows(pageRows) {
    if (!bodyEl) return;
    
    // Crear todas las filas de cero para evitar problemas con skeletons
    const rowsHtml = [];
    for (let i = 0; i < tblPageSize; i++) {
      const r = pageRows[i] || null;
      if (!r) {
        // Fila skeleton vacía (9 columnas ahora, sin Score)
        rowsHtml.push('<tr class="skeleton-row">' + '<td></td>'.repeat(9) + '</tr>');
      } else {
        // Fila con datos reales
        const seqHtml = highlightSequence(r.sequence, r);
        rowsHtml.push(`
          <tr>
            <td title="${r.peptide_id || ''}">${r.peptide_id || '—'}</td>
            <td title="${r.name || 'Sin nombre'}">${r.name || '<em class="text-muted">Sin nombre</em>'}</td>
            <td title="Gap: ${r.gap || 0}">${r.gap || 0}</td>
            <td title="Residuo X3: ${r.X3 || 'N/A'}">${r.X3 || '—'}</td>
            <td title="${r.has_hydrophobic_pair ? 'Tiene par hidrofóbico' : 'Sin par hidrofóbico'}">${r.has_hydrophobic_pair ? '<span class="table-cell-badge">✓</span>' : '—'}</td>
            <td title="Par: ${r.hydrophobic_pair || 'N/A'}">${r.hydrophobic_pair || '—'}</td>
            <td title="Score par: ${r.hydrophobic_pair_score != null ? r.hydrophobic_pair_score.toFixed(2) : 'N/A'}">${r.hydrophobic_pair_score != null ? r.hydrophobic_pair_score.toFixed(2) : '—'}</td>
            <td title="Longitud: ${r.length || 0} aminoácidos">${r.length || 0}</td>
            <td title="Secuencia completa con residuos destacados">
              <div class="sequence-container">
                <code class="table-cell-mono">${seqHtml}</code>
              </div>
            </td>
          </tr>
        `);
      }
    }
    
    bodyEl.innerHTML = rowsHtml.join('');
  }

  async function fetchtoxin_filter() {
    const gapMin = gapMinEl.value || 3;
    const gapMax = gapMaxEl.value || 6;
    const requirePair = requirePairEl.checked ? 1 : 0;
    const url = `/v2/toxin_filter?gap_min=${gapMin}&gap_max=${gapMax}&require_pair=${requirePair}`;
    setStatus('🔍 Buscando toxinas...');
    toggleEmptyState(false);
    ensureSkeletonRows();
    
    // Ocultar glosario mientras se busca
    const glossary = document.getElementById('residue-glossary');
    if (glossary) glossary.style.display = 'none';
    
    try {
      const res = await fetch(url);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      hitCountEl.textContent = data.count;
      exportBtn.disabled = data.count === 0;
      tblRows = data.results || [];
      tblPageNum = 1;
      renderTablePage();
      
      if (data.count === 0) {
        setStatus('⚠️ No se encontraron resultados con estos filtros.');
        toggleEmptyState(true);
        if (glossary) glossary.style.display = 'none';
      } else {
        setStatus(`✅ Se encontraron ${data.count} toxina${data.count !== 1 ? 's' : ''}.`);
        // Mostrar glosario cuando hay resultados
        if (glossary) glossary.style.display = 'block';
      }
      
      // store for export
      exportBtn.dataset.rows = JSON.stringify(data.results);
    } catch (e) {
      setStatus('❌ Error al cargar. Por favor, intenta de nuevo.');
      console.error(e);
      toggleEmptyState(true);
      if (glossary) glossary.style.display = 'none';
    }
  }

  function renderTablePage() {
    // Base rows (copy to avoid mutation)
    const q = (tableSearchQuery || '').toString().trim().toLowerCase();
    let base = tblRows.slice();

    // Always omit excluded accessions
    base = base.filter(r => {
      const acc = (r.accession_number || r.accession || '').toString();
      if (!acc) return true; // keep if no accession available
      return !EXCLUDED_ACCESSIONS.has(acc);
    });

    // Apply current mode filter
    if (currentMode === 'with_nav') {
      base = base.filter(r => r.nav1_7_exists === true || r.nav1_7_has_ic50 === true || (r.nav1_7_ic50_db != null));
    } else if (currentMode === 'without_nav') {
      base = base.filter(r => !(r.nav1_7_exists === true || r.nav1_7_has_ic50 === true || (r.nav1_7_ic50_db != null)));
    } else if (currentMode === 'with_ic50') {
      base = base.filter(r => (r.nav1_7_has_ic50 === true) || (r.nav1_7_ic50_db != null) );
    } else if (currentMode === 'without_ic50') {
      base = base.filter(r => !((r.nav1_7_has_ic50 === true) || (r.nav1_7_ic50_db != null)) );
    }

    // Apply accession search filter (client-side). Matches accession_number, peptide_id or name.
    const filtered = q ? base.filter(r => {
      const acc = (r.accession_number || r.accession || '').toString().toLowerCase();
      const pid = (r.peptide_id || '').toString().toLowerCase();
      const name = (r.name || '').toString().toLowerCase();
      return acc.includes(q) || pid.includes(q) || name.includes(q);
    }) : base;

    const total = filtered.length;
    const maxPage = Math.max(1, Math.ceil(total / tblPageSize));
    tblPageNum = Math.min(Math.max(1, tblPageNum), maxPage);
    const start = (tblPageNum - 1) * tblPageSize;
    const pageRows = filtered.slice(start, start + tblPageSize);
    
    // Mostrar/ocultar estado vacío
    if (total === 0 && tblRows.length > 0) {
      toggleEmptyState(true);
    } else {
      toggleEmptyState(false);
      ensureSkeletonRows();
      paintRows(pageRows);
    }
    
    if (tblPage) tblPage.textContent = `Página ${tblPageNum} de ${maxPage}`;
    if (tblPrev) tblPrev.disabled = tblPageNum <= 1;
    if (tblNext) tblNext.disabled = tblPageNum >= maxPage;

    // Update visible hit count to reflect filtered rows
    const hitCountEl = document.getElementById('hit-count');
    if (hitCountEl) hitCountEl.textContent = total;
    
    // Update pagination info
    const paginationInfo = document.getElementById('pagination-info');
    if (paginationInfo && total > 0) {
      const end = Math.min(start + tblPageSize, total);
      paginationInfo.textContent = `Mostrando ${start + 1}-${end} de ${total} resultado${total !== 1 ? 's' : ''}`;
    }
  }

  function highlightSequence(seq, meta) {
    const s = seq.split('');
    
    // Primero, identificar todas las cisteínas y marcarlas según su posición
    let cysCount = 0;
    const cysPositions = new Map();
    s.forEach((ch, i) => {
      if (ch === 'C') {
        cysCount++;
        // 5ta Cys = morado, 6ta Cys = verde, resto = rojo
        if (cysCount === 5) {
          cysPositions.set(i, 'C5');
        } else if (cysCount === 6) {
          cysPositions.set(i, 'C6');
        } else {
          cysPositions.set(i, 'CICK');
        }
      }
    });
    
    // Ahora marcar los residuos del motivo farmacofórico
    const marks = new Map();
    
    // Agregar las cisteínas identificadas
    cysPositions.forEach((type, pos) => {
      marks.set(pos, type);
    });
    
    // Agregar los otros residuos del motivo (pueden sobrescribir cisteínas si es necesario)
    ['iS','iW','iK','iX3','iHP1','iHP2'].forEach(k => {
      if (meta[k] !== null && meta[k] !== undefined) marks.set(meta[k], k);
    });
    
    // Si hay iC5 en meta, asegurarse de usarlo (por si acaso)
    if (meta['iC5'] !== null && meta['iC5'] !== undefined) {
      marks.set(meta['iC5'], 'C5');
    }
    
    return s.map((ch, i) => {
      if (!marks.has(i)) return ch;
      const cls = marks.get(i);
      
      // Colores según el tipo de residuo
      const colorMap = {
        'C5': { bg: '#9333EA', text: '#FFFFFF' },      // Morado - Quinta Cys
        'C6': { bg: '#10B981', text: '#FFFFFF' },      // Verde - Sexta Cys (del motivo WCK)
        'CICK': { bg: '#DC2626', text: '#FFFFFF' },    // Rojo - Otras Cys del ICK
        'iS': { bg: '#2563EB', text: '#FFFFFF' },      // Azul - Serina
        'iW': { bg: '#EA580C', text: '#FFFFFF' },      // Naranja - Triptófano
        'iK': { bg: '#EAB308', text: '#000000' },      // Amarillo - Lisina
        'iX3': { bg: '#84CC16', text: '#000000' },     // Verde claro - X3
        'iHP1': { bg: '#92400E', text: '#FFFFFF' },    // Café - X1
        'iHP2': { bg: '#92400E', text: '#FFFFFF' }     // Café - X2
      };
      
      const colors = colorMap[cls] || { bg: '#6B7280', text: '#FFFFFF' };
      return `<span style="background-color:${colors.bg};color:${colors.text};font-weight:800;padding:2px 4px;border-radius:3px;margin:0 1px;display:inline-block;box-shadow:0 1px 2px rgba(0,0,0,0.2);">${ch}</span>`;
    }).join('');
  }

  async function exportXlsx(triggerBtn) {
    try {
      if (triggerBtn) {
        triggerBtn.disabled = true;
        const original = triggerBtn.innerHTML || triggerBtn.textContent;
        triggerBtn._original = original;
        if (triggerBtn.tagName === 'BUTTON') {
          triggerBtn.innerHTML = '⏳ Exportando...';
        } else {
          triggerBtn.textContent = 'Exportando...';
        }
      }

      await loadSheetJsOnce();

      const dataAttr = (exportBtn && exportBtn.dataset && exportBtn.dataset.rows) ? exportBtn.dataset.rows : '[]';
      let rows = JSON.parse(dataAttr || '[]');
      // Apply same exclusions and mode filtering as table
      rows = rows.filter(r => {
        const acc = (r.accession_number || r.accession || '');
        if (acc && EXCLUDED_ACCESSIONS.has(acc)) return false;
        return true;
      });
      if (currentMode === 'with_nav') rows = rows.filter(r => r.nav1_7_exists || r.nav1_7_has_ic50 || (r.nav1_7_ic50_db != null));
      if (currentMode === 'without_nav') rows = rows.filter(r => !(r.nav1_7_exists || r.nav1_7_has_ic50 || (r.nav1_7_ic50_db != null)));
      if (currentMode === 'with_ic50') rows = rows.filter(r => (r.nav1_7_has_ic50 === true) || (r.nav1_7_ic50_db != null));
      if (currentMode === 'without_ic50') rows = rows.filter(r => !((r.nav1_7_has_ic50 === true) || (r.nav1_7_ic50_db != null)));
      if (!rows.length) return;
      const header = Object.keys(rows[0]);
      const sheetData = [header].concat(rows.map(r => header.map(h => r[h])));
      const ws = XLSX.utils.aoa_to_sheet(sheetData);
      // ancho automático simple
      const colWidths = header.map((h,i)=>({wch: Math.min(40, Math.max(String(h).length, ...rows.map(r => String(r[h]||'').length))+2)}));
      ws['!cols'] = colWidths;
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, 'toxins');
      const wbout = XLSX.write(wb, {bookType:'xlsx', type:'array'});
      const blob = new Blob([wbout], {type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'toxin_filter.xlsx';
      document.body.appendChild(a); a.click(); a.remove();
    } catch (e) {
      alert('Error exportando XLSX: '+ e.message);
    } finally {
      if (triggerBtn) {
        triggerBtn.disabled = false;
        if (triggerBtn._original != null) {
          if (triggerBtn.tagName === 'BUTTON') triggerBtn.innerHTML = triggerBtn._original;
          else triggerBtn.textContent = triggerBtn._original;
          delete triggerBtn._original;
        }
      }
    }
  }

  runBtn.addEventListener('click', fetchtoxin_filter);
  if (exportBtn) exportBtn.addEventListener('click', (e) => { e.preventDefault(); exportXlsx(exportBtn); });
  if (navbarExportBtn) navbarExportBtn.addEventListener('click', (e) => { e.preventDefault(); exportXlsx(navbarExportBtn); });
  // Accession search UI
  const accessionSearchEl = document.getElementById('accession-search');
  const accessionClearBtn = document.getElementById('accession-clear');
  if (accessionSearchEl) {
    accessionSearchEl.addEventListener('input', (ev) => {
      tableSearchQuery = ev.target.value || '';
      tblPageNum = 1;
      renderTablePage();
    });
    accessionSearchEl.addEventListener('keypress', (ev) => {
      if (ev.key === 'Enter') {
        ev.preventDefault();
        tableSearchQuery = accessionSearchEl.value || '';
        tblPageNum = 1;
        renderTablePage();
      }
    });
  }
  if (accessionClearBtn) {
    accessionClearBtn.addEventListener('click', () => {
      tableSearchQuery = '';
      if (accessionSearchEl) accessionSearchEl.value = '';
      tblPageNum = 1;
      renderTablePage();
    });
  }
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const expanded = toggleBtn.getAttribute('aria-expanded') === 'true';
      const icon = toggleBtn.querySelector('i');
      const text = toggleBtn.querySelector('span');
      
      if (expanded) {
        resultsBody.style.display = 'none';
        if (text) text.textContent = 'Mostrar';
        if (icon) icon.className = 'fa-solid fa-eye-slash';
        toggleBtn.setAttribute('aria-expanded', 'false');
      } else {
        resultsBody.style.display = '';
        if (text) text.textContent = 'Ocultar';
        if (icon) icon.className = 'fa-solid fa-eye';
        toggleBtn.setAttribute('aria-expanded', 'true');
      }
    });
  }
  // Wire table pagination
  if (tblPrev) tblPrev.addEventListener('click', () => { if (tblPageNum > 1) { tblPageNum--; renderTablePage(); } });
  if (tblNext) tblNext.addEventListener('click', () => {
    const maxPage = Math.max(1, Math.ceil(tblRows.length / tblPageSize));
    if (tblPageNum < maxPage) { tblPageNum++; renderTablePage(); }
  });

      // Custom checkbox functionality - unified click handling
  const chkBoxWrap = document.getElementById('require-pair-box');
  const chkLabelWrap = chkBoxWrap?.closest('.checkbox-wrapper');
  
  // Function to update checkbox visual state
  function updateCheckboxVisual() {
    if (chkBoxWrap && requirePairEl) {
      if (requirePairEl.checked) {
        chkBoxWrap.classList.add('checked');
      } else {
        chkBoxWrap.classList.remove('checked');
      }
    }
  }
  
  // Initialize checkbox visual state
  updateCheckboxVisual();
  
  // Unified event listener - works for both checkbox and label
  if (chkLabelWrap && requirePairEl) {
    chkLabelWrap.addEventListener('click', () => {
      requirePairEl.checked = !requirePairEl.checked;
      updateCheckboxVisual();
    });
  }

  // Initial load (pre-render skeleton for CLS stability)
  ensureSkeletonRows();
  fetchtoxin_filter();
});
