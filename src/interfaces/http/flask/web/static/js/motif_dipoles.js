document.addEventListener('DOMContentLoaded', () => {
  const refContainer = document.getElementById('reference-viewer');
  const grid = document.getElementById('filtered-grid');
  const prevBtn = document.getElementById('prev-page');
  const nextBtn = document.getElementById('next-page');
  const pageLbl = document.getElementById('page-indicator');

  if (!refContainer || !grid) return; // not on this page

  let page = 1, pageSize = 6;
  let lastCount = 0, lastParams = { gap_min: 3, gap_max: 6, require_pair: 0 };

  function addDipoleArrow(viewer, dipole) {
    const dir = (dipole && dipole.normalized) ? dipole.normalized : [0,0,1];
    const start = (dipole && dipole.center_of_mass) ? dipole.center_of_mass : [0,0,0];
    const scale = 15.0;
    const end = [ start[0] + dir[0]*scale, start[1] + dir[1]*scale, start[2] + dir[2]*scale ];

    viewer.addArrow({
      start: {x:start[0], y:start[1], z:start[2]},
      end: {x:end[0], y:end[1], z:end[2]},
      radius: 0.4, radiusRatio: 1.3, mid: 0.85,
      color: '#8e44ad', alpha: 0.95 // morado para distinguir del eje X rojo
    });
  }

  function addAxes(viewer, center, scale=8.0) {
    const c = center || [0,0,0];
    // X (rojo)
    viewer.addArrow({ start: {x:c[0], y:c[1], z:c[2]}, end: {x:c[0]+scale, y:c[1], z:c[2]}, color: '#e74c3c', radius: 0.25, radiusRatio: 1.4 });
    // Y (verde)
    viewer.addArrow({ start: {x:c[0], y:c[1], z:c[2]}, end: {x:c[0], y:c[1]+scale, z:c[2]}, color: '#27ae60', radius: 0.25, radiusRatio: 1.4 });
    // Z (azul)
    viewer.addArrow({ start: {x:c[0], y:c[1], z:c[2]}, end: {x:c[0], y:c[1], z:c[2]+scale}, color: '#3498db', radius: 0.25, radiusRatio: 1.4 });
  }

  function overlayLegend(container, dipole) {
    try { container.style.position = container.style.position || 'relative'; } catch(e) {}
    const mag = (dipole && dipole.magnitude && dipole.magnitude.toFixed) ? dipole.magnitude.toFixed(2) : '-';
    const ang = (dipole && dipole.angle_with_z_axis && dipole.angle_with_z_axis.degrees && dipole.angle_with_z_axis.degrees.toFixed) ? dipole.angle_with_z_axis.degrees.toFixed(1) : '-';
    let legend = container.querySelector('.dipole-legend');
    if (!legend) {
      legend = document.createElement('div');
      legend.className = 'dipole-legend';
      legend.style.position = 'absolute';
      legend.style.left = '8px';
      legend.style.bottom = '8px';
      legend.style.background = 'rgba(255,255,255,0.88)';
      legend.style.border = '1px solid #ddd';
      legend.style.borderRadius = '6px';
      legend.style.padding = '6px 8px';
      legend.style.fontSize = '12px';
      legend.style.color = '#222';
      legend.style.boxShadow = '0 1px 2px rgba(0,0,0,0.08)';
      container.appendChild(legend);
    }
    legend.innerHTML = `<strong>Dipolo</strong><br>Mag: ${mag} D<br>&angle;Z: ${ang}&deg;`;
  }

  async function loadReference() {
    try {
      const res = await fetch('/v2/motif_dipoles/reference');
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      refContainer.innerHTML = '';
  const viewer = $3Dmol.createViewer(refContainer, { backgroundColor: 'white' });
  viewer.addModel(data.pdb_text, 'pdb');
  viewer.setStyle({}, { cartoon: { color: 'spectrum', opacity: 0.9 } });
  // Centro aproximado para ejes: usa center_of_mass si viene, sino origen
  const com = (data.dipole && data.dipole.center_of_mass) ? data.dipole.center_of_mass : [0,0,0];
  addAxes(viewer, com, 10.0);
  addDipoleArrow(viewer, data.dipole);
  viewer.zoomTo(); viewer.render();
  overlayLegend(refContainer, data.dipole);
    } catch (e) {
      refContainer.innerHTML = `<div class="alert alert-warning">Referencia no disponible: ${e.message}</div>`;
    }
  }

  function cardHTML(idx, item) {
    const id = `motif-v-${idx}`;
    const title = `${item.name || ''} (${item.accession_number})`;
    const mag = (item.dipole && item.dipole.magnitude && item.dipole.magnitude.toFixed) ? item.dipole.magnitude.toFixed(2) : '-';
    const ang = (item.dipole && item.dipole.angle_with_z_axis && item.dipole.angle_with_z_axis.degrees && item.dipole.angle_with_z_axis.degrees.toFixed) ? item.dipole.angle_with_z_axis.degrees.toFixed(1) : '-';
    return `
      <div class="dipole-visualization-card">
        <div class="dipole-card-header">
          <h6 class="dipole-card-title"><i class="fas fa-dna"></i>${title}</h6>
          <small class="dipole-card-subtitle">Mag=${mag} D · ∠Z=${ang}°</small>
        </div>
        <div id="${id}" class="dipole-viewer" style="position:relative;"></div>
      </div>
    `;
  }

  async function renderPage() {
    pageLbl.textContent = `Página ${page}`;
    const url = `/v2/motif_dipoles/page?page=${page}&page_size=${pageSize}&gap_min=${lastParams.gap_min}&gap_max=${lastParams.gap_max}&require_pair=${lastParams.require_pair ? 1 : 0}`;
    grid.innerHTML = `<div class="loading-state" style="grid-column:1/-1;"><div class="spinner"></div><p class="loading-text">Cargando página...</p></div>`;
    try {
      const res = await fetch(url);
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      lastCount = data.count || 0;
      const items = data.items || [];
      if (!items.length) {
        grid.innerHTML = `<div class="alert alert-info" style="grid-column:1/-1;">No hay elementos en esta página.</div>`;
        return;
      }
      grid.innerHTML = items.map((it, i) => cardHTML(i, it)).join('');
      items.forEach((it, i) => {
        const el = document.getElementById(`motif-v-${i}`);
        el.style.position = 'relative';
        const viewer = $3Dmol.createViewer(el, { backgroundColor: 'white' });
        viewer.addModel(it.pdb_text, 'pdb');
        viewer.setStyle({}, { cartoon: { color: 'spectrum', opacity: 0.9 } });
        const com = (it.dipole && it.dipole.center_of_mass) ? it.dipole.center_of_mass : [0,0,0];
        addAxes(viewer, com, 8.0);
        addDipoleArrow(viewer, it.dipole);
        viewer.zoomTo(); viewer.render();
        overlayLegend(el, it.dipole);
      });
    } catch (e) {
      grid.innerHTML = `<div class="alert alert-danger" style="grid-column:1/-1;">Error: ${e.message}</div>`;
    }
  }

  // Navegación
  prevBtn && prevBtn.addEventListener('click', () => { if (page > 1) { page--; renderPage(); } });
  nextBtn && nextBtn.addEventListener('click', () => {
    const maxPage = Math.max(1, Math.ceil(lastCount / pageSize));
    if (page < maxPage) { page++; renderPage(); }
  });

  // Sincronizar con filtros inferiores si existen
  const gapMinEl = document.getElementById('gap-min');
  const gapMaxEl = document.getElementById('gap-max');
  const reqPairEl = document.getElementById('require-pair');
  const runBtn = document.getElementById('run-filter');
  if (runBtn && gapMinEl && gapMaxEl && reqPairEl) {
    runBtn.addEventListener('click', () => {
      lastParams = {
        gap_min: parseInt(gapMinEl.value || 3, 10),
        gap_max: parseInt(gapMaxEl.value || 6, 10),
        require_pair: !!reqPairEl.checked,
      };
      page = 1;
      renderPage();
    });
  }

  loadReference();
  renderPage();
});
