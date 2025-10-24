document.addEventListener('DOMContentLoaded', () => {
  const gapMinEl = document.getElementById('gap-min');
  const gapMaxEl = document.getElementById('gap-max');
  const requirePairEl = document.getElementById('require-pair');
  const runBtn = document.getElementById('run-filter');
  const exportBtn = document.getElementById('export-xlsx');
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
  const tblPageSize = 10;
  let tblRows = [];
  let tableSearchQuery = '';

  async function fetchtoxin_filter() {
    const gapMin = gapMinEl.value || 3;
    const gapMax = gapMaxEl.value || 6;
    const requirePair = requirePairEl.checked ? 1 : 0;
    const url = `/v2/toxin_filter?gap_min=${gapMin}&gap_max=${gapMax}&require_pair=${requirePair}`;
    statusEl.querySelector('span').textContent = 'Buscando...';
  bodyEl.innerHTML = '<tr><td colspan="10">Cargando...</td></tr>';
    try {
      const res = await fetch(url);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      hitCountEl.textContent = data.count;
      exportBtn.disabled = data.count === 0;
      tblRows = data.results || [];
      tblPageNum = 1;
      renderTablePage();
      statusEl.querySelector('span').textContent = 'Listo.';
      // store for export
      exportBtn.dataset.rows = JSON.stringify(data.results);
    } catch (e) {
  bodyEl.innerHTML = `<tr><td colspan="10">Error: ${e.message}</td></tr>`;
      statusEl.querySelector('span').textContent = 'Error al cargar.';
    }
  }

  function renderTablePage() {
    // Apply accession search filter (client-side). Matches accession_number, peptide_id or name.
    const q = (tableSearchQuery || '').toString().trim().toLowerCase();
    const filtered = q ? tblRows.filter(r => {
      const acc = (r.accession_number || '').toString().toLowerCase();
      const pid = (r.peptide_id || '').toString().toLowerCase();
      const name = (r.name || '').toString().toLowerCase();
      return acc.includes(q) || pid.includes(q) || name.includes(q);
    }) : tblRows.slice();

    const total = filtered.length;
    const maxPage = Math.max(1, Math.ceil(total / tblPageSize));
    tblPageNum = Math.min(Math.max(1, tblPageNum), maxPage);
    const start = (tblPageNum - 1) * tblPageSize;
    const pageRows = filtered.slice(start, start + tblPageSize);
    bodyEl.innerHTML = pageRows.map(r => {
      const seqHtml = highlightSequence(r.sequence, r);
      return `<tr>
          <td>${r.peptide_id}</td>
          <td>${r.name || ''}</td>
          <td>${r.score}</td>
          <td>${r.gap}</td>
          <td>${r.X3 || ''}</td>
          <td>${r.has_hydrophobic_pair ? '✔' : ''}</td>
          <td>${r.hydrophobic_pair || ''}</td>
          <td>${r.hydrophobic_pair_score != null ? r.hydrophobic_pair_score.toFixed(2) : ''}</td>
          <td>${r.length}</td>
          <td><code>${seqHtml}</code></td>
        </tr>`;
    }).join('');
    if (tblPage) tblPage.textContent = `Página ${tblPageNum}`;
    if (tblPrev) tblPrev.disabled = tblPageNum <= 1;
    if (tblNext) tblNext.disabled = tblPageNum >= maxPage;

    // Update visible hit count to reflect filtered rows
    const hitCountEl = document.getElementById('hit-count');
    if (hitCountEl) hitCountEl.textContent = total;
  }

  function highlightSequence(seq, meta) {
    const s = seq.split('');
    const marks = new Map();
    ['iC5','iS','iW','iK','iX3','iHP1','iHP2'].forEach(k => {
      if (meta[k] !== null && meta[k] !== undefined) marks.set(meta[k], k);
    });
    return s.map((ch,i) => {
      if (!marks.has(i)) return ch;
      const cls = marks.get(i);
      const color = ({
        iC5:'#d9534f',
        iS:'#0275d8',
        iW:'#5cb85c',
        iK:'#f0ad4e',
        iX3:'#6f42c1',
        iHP1:'#20c997',
        iHP2:'#20c997'
      })[cls] || '#222';
      return `<span style="color:${color};font-weight:bold;">${ch}</span>`;
    }).join('');
  }

  function exportXlsx() {
    try {
      const rows = JSON.parse(exportBtn.dataset.rows || '[]');
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
    }
  }

  runBtn.addEventListener('click', fetchtoxin_filter);
  exportBtn.addEventListener('click', exportXlsx);
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
      if (expanded) {
        resultsBody.style.display = 'none';
        toggleBtn.textContent = 'Expandir';
        toggleBtn.setAttribute('aria-expanded', 'false');
      } else {
        resultsBody.style.display = '';
        toggleBtn.textContent = 'Colapsar';
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

  // Initial load
  fetchtoxin_filter();
});
