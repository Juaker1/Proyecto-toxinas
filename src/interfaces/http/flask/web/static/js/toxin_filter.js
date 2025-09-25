document.addEventListener('DOMContentLoaded', () => {
  const gapMinEl = document.getElementById('gap-min');
  const gapMaxEl = document.getElementById('gap-max');
  const requirePairEl = document.getElementById('require-pair');
  const runBtn = document.getElementById('run-filter');
  const exportBtn = document.getElementById('export-xlsx');
  const bodyEl = document.getElementById('motif-body');
  const hitCountEl = document.getElementById('hit-count');
  const statusEl = document.getElementById('status-line');

  async function fetchtoxin_filter() {
    const gapMin = gapMinEl.value || 3;
    const gapMax = gapMaxEl.value || 6;
    const requirePair = requirePairEl.checked ? 1 : 0;
    const url = `/v2/toxin_filter?gap_min=${gapMin}&gap_max=${gapMax}&require_pair=${requirePair}`;
    statusEl.querySelector('span').textContent = 'Buscando...';
    bodyEl.innerHTML = '<tr><td colspan="8">Cargando...</td></tr>';
    try {
      const res = await fetch(url);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      hitCountEl.textContent = data.count;
      exportBtn.disabled = data.count === 0;
      bodyEl.innerHTML = data.results.map(r => {
        const seqHtml = highlightSequence(r.sequence, r);
        return `<tr>
          <td>${r.peptide_id}</td>
          <td>${r.name || ''}</td>
            <td>${r.score}</td>
            <td>${r.gap}</td>
            <td>${r.X3 || ''}</td>
            <td>${r.has_hydrophobic_pair ? '✔' : ''}</td>
            <td>${r.length}</td>
            <td><code>${seqHtml}</code></td>
        </tr>`;
      }).join('');
      statusEl.querySelector('span').textContent = 'Listo.';
      // store for export
  exportBtn.dataset.rows = JSON.stringify(data.results);
    } catch (e) {
      bodyEl.innerHTML = `<tr><td colspan="8">Error: ${e.message}</td></tr>`;
      statusEl.querySelector('span').textContent = 'Error al cargar.';
    }
  }

  function highlightSequence(seq, meta) {
    const s = seq.split('');
    const marks = new Map();
    ['iC5','iS','iW','iK','iX3'].forEach(k => {
      if (meta[k] !== null && meta[k] !== undefined) marks.set(meta[k], k);
    });
    return s.map((ch,i) => {
      if (!marks.has(i)) return ch;
      const cls = marks.get(i);
      const color = ({iC5:'#d9534f', iS:'#0275d8', iW:'#5cb85c', iK:'#f0ad4e', iX3:'#6f42c1'})[cls] || '#222';
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
  fetchtoxin_filter();
});
