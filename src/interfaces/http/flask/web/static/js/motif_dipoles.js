document.addEventListener('DOMContentLoaded', () => {
  const refContainer = document.getElementById('reference-viewer');
  const grid = document.getElementById('filtered-grid');
  const prevBtn = document.getElementById('prev-page');
  const nextBtn = document.getElementById('next-page');
  const pageLbl = document.getElementById('page-indicator');
  const referenceSelector = document.getElementById('reference-selector');

  if (!refContainer || !grid) return; // not on this page

  let page = 1;
  let pageSize = 6;
  let lastCount = 0;
  let lastParams = { gap_min: 3, gap_max: 6, require_pair: 0 };
  let viewMode = 'dipole'; // Estado global: 'dipole', 'disulfide', 'both'
  let currentPageItems = []; // Guardar items actuales para re-renderizar
  let ic50Filter = 'all'; // 'all' | 'with_ic50' | 'without_ic50'
  let referenceAngleDeg = null;
  let referenceAngles = null;
  let referenceVector = null;
  let referenceSource = null;
  let referencePaths = { pdb: null, psf: null };
  let selectedReferenceCode = 'WT';
  let referenceOptions = [];
  let referenceDisplayName = 'Proteína WT';

  // ========== OVERLAY DE CARGA PARA FILTRADO IC50 ==========
  function getIc50Overlay() {
    const cardBody = document.querySelector('#filtered-dipoles-card .card-body');
    if (!cardBody) return null;
    let overlay = document.getElementById('ic50-loading-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'ic50-loading-overlay';
      overlay.className = 'ic50-loading-overlay';
      overlay.innerHTML = `
        <div class="ic50-loading-box">
          <div class="ic50-spinner"></div>
          <span id="ic50-loading-text">Filtrando…</span>
        </div>
      `;
      cardBody.appendChild(overlay);
    }
    return overlay;
  }
  function showIc50Loading(text = 'Filtrando…') {
    const overlay = getIc50Overlay();
    if (!overlay) return;
    const label = overlay.querySelector('#ic50-loading-text');
    if (label) label.textContent = text;
    overlay.style.display = 'flex';
  }
  function hideIc50Loading() {
    const overlay = getIc50Overlay();
    if (!overlay) return;
    overlay.style.display = 'none';
  }

  // ========== FUNCIONES DE DETECCIÓN DE PUENTES DISULFURO ==========
  
  function findDisulfideBonds(sequence = '') {
    if (!sequence || typeof sequence !== 'string') {
      return { bonds: [], positions: [] };
    }

    const positions = [];
    for (let i = 0; i < sequence.length; i += 1) {
      if (sequence[i] === 'C') {
        positions.push(i);
      }
    }

    const bonds = [];
    const n = positions.length;

    // Patrón típico ICK (Inhibitor Cystine Knot)
    if (n >= 6) {
      bonds.push([positions[0], positions[3]]);
      bonds.push([positions[1], positions[4]]);
      bonds.push([positions[2], positions[5]]);
      if (n >= 8) {
        bonds.push([positions[6], positions[7]]);
      }
    } else {
      for (let i = 0; i + 1 < n; i += 2) {
        bonds.push([positions[i], positions[i + 1]]);
      }
    }

    return { bonds, positions };
  }

  async function renderPage() {
    // Mostrar overlay de carga y deshabilitar navegación de página mientras se renderiza
    try { showIc50Loading('Cargando página…'); } catch(e) {}
    if (prevBtn) prevBtn.disabled = true;
    if (nextBtn) nextBtn.disabled = true;
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        gap_min: String(lastParams.gap_min),
        gap_max: String(lastParams.gap_max),
        require_pair: lastParams.require_pair ? '1' : '0',
      });
      if (selectedReferenceCode && selectedReferenceCode !== 'WT') {
        params.set('peptide_code', selectedReferenceCode);
      }
      const res = await fetch(`/v2/motif_dipoles/page?${params.toString()}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      // Reference metadata
      if (data.reference) {
        if (data.reference.peptide_code) {
          selectedReferenceCode = data.reference.peptide_code;
          if (referenceSelector) referenceSelector.value = selectedReferenceCode;
        }
        referenceDisplayName = data.reference.display_name || referenceDisplayName;
      }
      const referenceOptionList = data.reference_options;
      if (referenceOptionList) {
        updateReferenceSelector(referenceOptionList, selectedReferenceCode);
      }

      if (typeof data.page === 'number' && data.page > 0) {
        page = data.page;
      }
  pageLbl.textContent = `Página ${page}`;

      const rawItems = data.items || [];
      // Frontend exclusion set to ensure excluded accessions are never shown
      const EXCLUDED_ACCESSIONS = new Set(["P83303","P84507","P0DL84","P84508","D2Y1X8","P0DL72","P0CH54"]);
      let items = [];
      if (ic50Filter !== 'all') {
        // Cliente: obtener todos los ítems, filtrar por IC50 y paginar desde la página 1
        const allItems = await fetchAllItemsWithCurrentParams();
        const hasIc50 = (it) => (
          Boolean(it.nav1_7_has_ic50) ||
          it.nav1_7_ic50_value != null ||
          it.nav1_7_ic50_value_nm != null ||
          it.ai_ic50_value_nm != null ||
          (it.ai_ic50_min_nm != null && it.ai_ic50_max_nm != null)
        );
        const filtered = allItems.filter(it => {
          if (ic50Filter === 'with_ic50') return hasIc50(it);
          if (ic50Filter === 'without_ic50') return !hasIc50(it);
          return true;
        });
        lastCount = filtered.length;
        const maxPage = Math.max(1, Math.ceil(lastCount / pageSize));
        if (page > maxPage) page = maxPage;
        const start = (page - 1) * pageSize;
        const end = Math.min(lastCount, start + pageSize);
        items = filtered.slice(start, end);
      } else {
        // Comportamiento base del servidor: por página
        lastCount = data.count || 0;
        items = rawItems
          .filter(it => {
            const acc = (it.accession_number || it.accession || '');
            if (acc && EXCLUDED_ACCESSIONS.has(acc)) return false;
            return true;
          })
          .map((it) => prepareItem(it));
      }
      currentPageItems = items; // Guardar para re-renderizar
  // Actualizar indicador de página tras posible ajuste de paginación
  pageLbl.textContent = `Página ${page}`;

      // Ensure view-mode-controls exists and inject IC50 controls to the left of the view buttons
      const viewControls = document.querySelector('.view-mode-controls');
  if (viewControls && !viewControls._ic50Injected) {
        // create left group for IC50 filter buttons
        const leftGroup = document.createElement('div');
        leftGroup.className = 'ic50-filter-group';
        leftGroup.style.display = 'flex';
        leftGroup.style.gap = '0.4rem';
        leftGroup.style.alignItems = 'center';
        leftGroup.innerHTML = `
          <button class="ic50-filter-btn active" data-mode="all" title="Mostrar todos">Todos</button>
          <button class="ic50-filter-btn" data-mode="with_ic50" title="Mostrar solo con IC50">Con IC50</button>
          <button class="ic50-filter-btn" data-mode="without_ic50" title="Mostrar sin IC50">Sin IC50</button>
        `;
    // insert leftGroup before existing first child to keep it on the left
        viewControls.insertBefore(leftGroup, viewControls.firstChild);

        // Wire filter buttons
        leftGroup.addEventListener('click', async (ev) => {
          const btn = ev.target.closest('.ic50-filter-btn');
          if (!btn) return;
          leftGroup.querySelectorAll('.ic50-filter-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const mode = btn.dataset.mode || 'all';
          ic50Filter = mode;
          page = 1; // resetear a la primera página al cambiar el filtro
          // Mostrar overlay y deshabilitar botones mientras se recalcula
          const label = mode === 'with_ic50' ? 'Filtrando: Con IC50…'
                      : mode === 'without_ic50' ? 'Filtrando: Sin IC50…'
                      : 'Cargando todos…';
          showIc50Loading(label);
          leftGroup.querySelectorAll('.ic50-filter-btn').forEach(b => { b.disabled = true; });
          try {
            await renderPage();
            // Actualizar gráficos tras recalcular
            await updateChartsWithAllItems();
          } finally {
            hideIc50Loading();
            leftGroup.querySelectorAll('.ic50-filter-btn').forEach(b => { b.disabled = false; });
          }
        });

        viewControls._ic50Injected = true;
      }

      if (!items.length) {
        grid.innerHTML = `<div class="alert alert-info" style="grid-column:1/-1;">No hay elementos en esta página.</div>`;
        return;
      }

      // Aplicar animación de cambio
      grid.classList.add('mode-changing');
      setTimeout(() => grid.classList.remove('mode-changing'), 300);

      grid.innerHTML = items.map((it, i) => cardHTML(i, it)).join('');

      items.forEach((it, i) => {
        const el = document.getElementById(`motif-v-${i}`);
        el.style.position = 'relative';
        const viewer = $3Dmol.createViewer(el, { backgroundColor: 'white' });

        // Renderizar según el modo actual
        if (viewMode === 'dipole') {
          renderDipoleView(viewer, it.pdb_text, it, el);
        } else if (viewMode === 'disulfide') {
          // Necesitamos la secuencia - asumimos que viene en it.sequence
          const sequence = it.sequence || '';
          renderDisulfideView(viewer, it.pdb_text, sequence, el);
        }
      });

      // Adjuntar listeners de descarga para cada tarjeta renderizada
      (function attachDownloadHandlers() {
        const downloadButtons = grid.querySelectorAll('.card-download-btn');
        downloadButtons.forEach((btn) => {
          if (btn._hasHandler) return; // evitar doble bind
          btn._hasHandler = true;
          btn.addEventListener('click', async (ev) => {
            ev.preventDefault();
            const accession = btn.dataset.accession;
            if (!accession) return alert('Accession no disponible');
            const original = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Descargando...';
            try {
              const url = `/v2/motif_dipoles/item/download?accession=${encodeURIComponent(accession)}`;
              const res = await fetch(url);
              if (!res.ok) {
                let msg = `HTTP ${res.status}`;
                try { const txt = await res.text(); if (txt) msg += ` - ${txt}`; } catch(e) {}
                throw new Error(msg);
              }
              const blob = await res.blob();
              const disposition = res.headers.get('Content-Disposition') || '';
              let filename = `${accession}_files.zip`;
              const m = /filename="?([^";]+)"?/.exec(disposition);
              if (m && m[1]) filename = m[1];
              const urlBlob = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = urlBlob;
              a.download = filename;
              document.body.appendChild(a);
              a.click();
              a.remove();
              URL.revokeObjectURL(urlBlob);
            } catch (err) {
              console.error('Error descargando archivo de item:', err);
              alert('No se pudo descargar: ' + (err && err.message ? err.message : 'error desconocido'));
            } finally {
              btn.disabled = false;
              btn.innerHTML = original;
            }
          });
        });
      })();
    } catch (e) {
      grid.innerHTML = `<div class=\"alert alert-danger\" style=\"grid-column:1/-1;\">Error: ${e.message}</div>`;
    } finally {
      // Ocultar overlay y re-habilitar navegación
      try { hideIc50Loading(); } catch(e) {}
      if (prevBtn) prevBtn.disabled = false;
      if (nextBtn) nextBtn.disabled = false;
      // Refrescar los gráficos fijos
      try { await updateChartsWithAllItems(); } catch(e) { console.warn('Charts update failed:', e); }
    }
  }

  function formatNumber(value, digits = 2) {
    const numeric = toFiniteNumber(value);
    return numeric !== null ? numeric.toFixed(digits) : '-';
  }

  function formatDegWithSuffix(value, digits = 2) {
    const numeric = toFiniteNumber(value);
    if (numeric === null) return '-';
    return `${numeric.toFixed(digits)}°`;
  }

  function formatReferenceOption(option) {
    if (!option) return '';
    if (option.value === 'WT') {
      return option.label || 'Proteína WT';
    }
    const base = option.label || option.peptide_code || option.value;
    const norm = (typeof option.normalized_ic50 === 'number' && Number.isFinite(option.normalized_ic50))
      ? option.normalized_ic50.toFixed(3)
      : '-';
    const ic50Numeric = toFiniteNumber(option.ic50_value);
    const unitText = option.ic50_unit ? ` ${option.ic50_unit}` : '';
    const ic50Text = ic50Numeric !== null ? `${ic50Numeric.toFixed(3)}${unitText}` : '-';
    return `${base} · IC50=${ic50Text} · Norm=${norm}`;
  }

  function updateReferenceSelector(options, selectedValue = selectedReferenceCode) {
    if (!referenceSelector || !Array.isArray(options)) return;
    referenceOptions = options.slice();
    referenceSelector.innerHTML = '';
    referenceOptions.forEach((opt) => {
      const optionEl = document.createElement('option');
      optionEl.value = opt.value;
      optionEl.textContent = formatReferenceOption(opt);
      referenceSelector.appendChild(optionEl);
    });
    if (selectedValue) {
      referenceSelector.value = selectedValue;
    }
  }

  function toFiniteNumber(value) {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string' && value.trim().length) {
      const parsed = parseFloat(value);
      if (Number.isFinite(parsed)) return parsed;
    }
    return null;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function computeAxisAnglesFromVector(vec) {
    if (!Array.isArray(vec) || vec.length < 3) return null;
    const norm = Math.hypot(vec[0], vec[1], vec[2]);
    if (!Number.isFinite(norm) || norm === 0) return null;
    const nx = vec[0] / norm;
    const ny = vec[1] / norm;
    const nz = vec[2] / norm;
    return {
      x: Math.acos(clamp(nx, -1, 1)) * RAD2DEG,
      y: Math.acos(clamp(ny, -1, 1)) * RAD2DEG,
      z: Math.acos(clamp(nz, -1, 1)) * RAD2DEG,
    };
  }

  function computeAxisAnglesFromDipole(dipole) {
    if (!dipole) return null;
    if (dipole.angles_deg) return dipole.angles_deg;
    const vec = dipole.normalized || dipole.normalized_vector || dipole.vector;
    if (Array.isArray(vec)) {
      return computeAxisAnglesFromVector(vec);
    }
    if (vec && typeof vec === 'object') {
      const components = [vec.x, vec.y, vec.z];
      if (components.every((num) => typeof num === 'number' && Number.isFinite(num))) {
        return computeAxisAnglesFromVector(components);
      }
    }
    return null;
  }

  function normalizeAngleDiffs(diffObj) {
    if (!diffObj || typeof diffObj !== 'object') return null;
    const result = {};
    let count = 0;
    ['x', 'y', 'z'].forEach((axis) => {
      if (Object.prototype.hasOwnProperty.call(diffObj, axis)) {
        const num = toFiniteNumber(diffObj[axis]);
        if (num !== null) {
          result[axis] = num;
          count += 1;
        }
      }
    });
    return count ? result : null;
  }

  function normalizeAngles(anglesObj) {
    if (!anglesObj || typeof anglesObj !== 'object') return null;
    const result = {};
    let count = 0;
    ['x', 'y', 'z'].forEach((axis) => {
      if (Object.prototype.hasOwnProperty.call(anglesObj, axis)) {
        const num = toFiniteNumber(anglesObj[axis]);
        if (num !== null) {
          result[axis] = num;
          count += 1;
        }
      }
    });
    return count ? result : null;
  }

  function getNormalizedVector(subject) {
    if (!subject) return null;
    if (Array.isArray(subject.normalized_vector)) return subject.normalized_vector;
    const dipole = subject.dipole || subject;
    if (!dipole) return null;
    if (Array.isArray(dipole.normalized)) return dipole.normalized;
    if (Array.isArray(dipole.vector)) return dipole.vector;
    const vec = dipole.normalized || dipole.vector;
    if (vec && typeof vec === 'object') {
      const components = [vec.x, vec.y, vec.z];
      if (components.every((num) => typeof num === 'number' && Number.isFinite(num))) {
        return components;
      }
      const values = Object.values(vec).map((v) => toFiniteNumber(v)).filter((v) => v !== null);
      if (values.length >= 3) return values.slice(0, 3);
    }
    return null;
  }

  function getOrientationMetrics(subject) {
    const dipole = subject && subject.dipole ? subject.dipole : subject;
    const normalizedVector = getNormalizedVector(subject) || getNormalizedVector(dipole);
    let angles = (subject && subject.angles_deg)
      || computeAxisAnglesFromDipole(subject)
      || computeAxisAnglesFromDipole(dipole);
    if (!angles && normalizedVector) {
      angles = computeAxisAnglesFromVector(normalizedVector);
    }
    let diffs = normalizeAngleDiffs(subject && subject.angle_diff_vs_reference);
    if (!diffs && angles && referenceAngles) {
      const computed = {};
      let count = 0;
      ['x', 'y', 'z'].forEach((axis) => {
        const a = toFiniteNumber(angles[axis]);
        const b = referenceAngles ? toFiniteNumber(referenceAngles[axis]) : null;
        if (a !== null && b !== null) {
          computed[axis] = Math.abs(a - b);
          count += 1;
        }
      });
      diffs = count ? computed : null;
    }

    const angleZ = angles && Object.prototype.hasOwnProperty.call(angles, 'z')
      ? toFiniteNumber(angles.z)
      : getAngleDegrees(dipole);
    const deltaZ = diffs && Object.prototype.hasOwnProperty.call(diffs, 'z')
      ? diffs.z
      : (() => {
          const refZ = referenceAngles ? toFiniteNumber(referenceAngles.z) : referenceAngleDeg;
          if (angleZ !== null && refZ !== null) {
            return Math.abs(angleZ - refZ);
          }
          return null;
        })();

    const orientationScore = toFiniteNumber(subject && subject.orientation_score_deg)
      ?? toFiniteNumber(subject && subject.vector_angle_vs_reference_deg)
      ?? toFiniteNumber(subject && subject.angle_diff_l2_deg)
      ?? (diffs
        ? Math.sqrt(
            ['x', 'y', 'z']
              .map((axis) => (Object.prototype.hasOwnProperty.call(diffs, axis) ? diffs[axis] ** 2 : 0))
              .reduce((acc, val) => acc + val, 0)
          )
        : null);

    const vectorAngle = toFiniteNumber(subject && subject.vector_angle_vs_reference_deg) ?? orientationScore;

    return {
      angles,
      normalizedVector,
      angleZ,
      diffs,
      deltaZ,
      orientationScore,
      vectorAngle,
    };
  }

  // Construye etiqueta X: accession + (ori=..°)
  function buildLabelWithOri(item) {
    const acc = item.accession_number || item.accession || item.name || item.peptide_id || 'NA';
    let ori = null;
    // Preferimos un campo directo si existe
    if (typeof item.orientation_score_deg === 'number' && Number.isFinite(item.orientation_score_deg)) {
      ori = item.orientation_score_deg;
    } else {
      const m = getOrientationMetrics(item);
      if (m && typeof m.orientationScore === 'number' && Number.isFinite(m.orientationScore)) {
        ori = m.orientationScore;
      } else if (m && typeof m.deltaZ === 'number' && Number.isFinite(m.deltaZ)) {
        // Fallback si no hay score L2: usar ΔZ
        ori = m.deltaZ;
      }
    }
    const oriText = (ori !== null) ? ` (ori=${ori.toFixed(1)}°)` : '';
    return `${acc}${oriText}`;
  }

  function buildDipoleInfoHTML(subject, options = {}) {
    const { includeTitle = true, isReference = false, extraLines = [] } = options;
    const dipole = subject && subject.dipole ? subject.dipole : subject;
    const metrics = getOrientationMetrics(subject);
    const magnitude = toFiniteNumber(dipole && dipole.magnitude);
    const lines = [];
    if (includeTitle) {
      lines.push('<strong>Dipolo</strong>');
    }
    lines.push(`Mag: ${magnitude !== null ? magnitude.toFixed(2) : '-'} D`);
    if (metrics.angles) {
      lines.push(
        `∠X: ${formatDegWithSuffix(metrics.angles.x)} · ∠Y: ${formatDegWithSuffix(metrics.angles.y)} · ∠Z: ${formatDegWithSuffix(metrics.angles.z)}`
      );
    } else {
      lines.push(`∠Z: ${formatDegWithSuffix(metrics.angleZ)}`);
    }
    if (!isReference) {
      if (metrics.diffs) {
        lines.push(
          `ΔX: ${formatDegWithSuffix(metrics.diffs.x)} · ΔY: ${formatDegWithSuffix(metrics.diffs.y)} · ΔZ: ${formatDegWithSuffix(metrics.diffs.z)}`
        );
      } else if (metrics.deltaZ !== null) {
        lines.push(`ΔZ: ${formatDegWithSuffix(metrics.deltaZ)}`);
      }
      if (metrics.orientationScore !== null) {
        lines.push(`Δori: ${formatDegWithSuffix(metrics.orientationScore)}`);
      }
      if (metrics.vectorAngle !== null && metrics.vectorAngle !== metrics.orientationScore) {
        lines.push(`∠Vec: ${formatDegWithSuffix(metrics.vectorAngle)}`);
      }
    }
    if (extraLines && extraLines.length) {
      extraLines.forEach((line) => {
        if (line) lines.push(line);
      });
    }
    return lines.join('<br>');
  }

  function renderIc50Chart() {
    const container = document.getElementById('ic50-chart-container');
    if (!container) return;
    // Use currentPageItems (already filtered by exclusions and ic50Filter)
    const rows = (currentPageItems || []).filter(it => {
      const hasRange = (it.ai_ic50_min_nm != null && it.ai_ic50_max_nm != null);
      const hasSingle = (it.ai_ic50_value_nm != null) || (it.nav1_7_ic50_value_nm != null);
      return hasRange || hasSingle;
    });
    if (!rows.length) {
      container.innerHTML = '<div class="alert alert-info">No hay valores de IC50 para graficar en la vista actual.</div>';
      return;
    }
    // X labels: "1. ACCESSION"
    const x = rows.map((r, i) => `${i + 1}. ${r.accession_number || r.accession || r.name || r.peptide_id}`);
    const yMin = rows.map(r => (r.ai_ic50_min_nm != null ? Number(r.ai_ic50_min_nm) : null));
    const yMax = rows.map(r => (r.ai_ic50_max_nm != null ? Number(r.ai_ic50_max_nm) : null));
    const yAvg = rows.map(r => {
      if (r.ai_ic50_avg_nm != null) return Number(r.ai_ic50_avg_nm);
      if (r.ai_ic50_value_nm != null) return Number(r.ai_ic50_value_nm);
      if (r.nav1_7_ic50_value_nm != null) return Number(r.nav1_7_ic50_value_nm);
      return null;
    });

    const traceMin = {
      x, y: yMin,
      name: 'Min (AI)',
      type: 'bar',
      marker: { color: '#22c55e' },
    };
    const traceAvg = {
      x, y: yAvg,
      name: 'Promedio / Valor',
      type: 'bar',
      marker: { color: '#667eea' },
    };
    const traceMax = {
      x, y: yMax,
      name: 'Max (AI)',
      type: 'bar',
      marker: { color: '#ef4444' },
    };
    const layout = {
      title: 'IC50 de péptidos filtrados (nM)',
      barmode: 'group',
      xaxis: { title: 'Orden de péptidos (index. accession)', automargin: true },
      yaxis: { title: 'IC50 (nM)', type: 'log' },
      margin: { t: 40, l: 60, r: 20, b: 140 },
      legend: { orientation: 'h', y: -0.2 },
    };
    try {
      Plotly.newPlot(container, [traceMin, traceAvg, traceMax], layout, {responsive: true});
    } catch (e) {
      container.innerHTML = `<div class="alert alert-danger">Error al renderizar gráfico: ${e.message}</div>`;
    }
  }

  // Fetch all pages with current params to include all accessions with IC50
  async function fetchAllItemsWithCurrentParams() {
    const all = [];
    let localPage = 1;
    let total = null;
    const paramsBase = new URLSearchParams({
      page_size: String(24), // server max
      gap_min: String(lastParams.gap_min),
      gap_max: String(lastParams.gap_max),
      require_pair: lastParams.require_pair ? '1' : '0',
    });
    if (selectedReferenceCode && selectedReferenceCode !== 'WT') {
      paramsBase.set('peptide_code', selectedReferenceCode);
    }
    // Loop pages until we collect all items
    while (true) {
      const params = new URLSearchParams(paramsBase);
      params.set('page', String(localPage));
      const res = await fetch(`/v2/motif_dipoles/page?${params.toString()}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      const rawItems = data.items || [];
      // Apply same exclusions here
      const EXCLUDED_ACCESSIONS = new Set(["P83303","P84507","P0DL84","P84508","D2Y1X8","P0DL72","P0CH54"]);
      for (const it of rawItems) {
        const acc = (it.accession_number || it.accession || '');
        if (acc && EXCLUDED_ACCESSIONS.has(acc)) continue;
        all.push(prepareItem(it));
      }
      if (typeof data.count === 'number' && typeof data.page_size === 'number') {
        total = data.count;
        const maxPage = Math.max(1, Math.ceil(total / data.page_size));
        if (localPage >= maxPage) break;
      } else {
        // If no pagination metadata, stop to avoid infinite loop
        break;
      }
      localPage += 1;
    }
    return all;
  }

  // Render scatter plot with all accessions that have IC50 (AI or DB), log scale, always-visible container
  async function renderIc50ScatterAll(prefetchedItems) {
    const container = document.getElementById('ic50-scatter-all');
    if (!container) return;
    if (!prefetchedItems) {
      container.innerHTML = '<div class="alert alert-info">Cargando datos de IC50...</div>';
    }
    try {
      const allItems = Array.isArray(prefetchedItems) ? prefetchedItems : await fetchAllItemsWithCurrentParams();
      // Pick those with any IC50 available
      const hasIc50 = (it) => {
        return (
          (it.ai_ic50_avg_nm != null) ||
          (it.ai_ic50_value_nm != null) ||
          (it.ai_ic50_min_nm != null && it.ai_ic50_max_nm != null) ||
          (it.nav1_7_ic50_value_nm != null)
        );
      };
      const rows = allItems.filter(hasIc50);
      if (!rows.length) {
        container.innerHTML = '<div class="alert alert-info">No hay valores de IC50 para graficar.</div>';
        return;
      }
      // Build AI vs DB buckets
      const aiRows = [];
      const dbRows = [];
      for (const r of rows) {
        const hasAI = (r.ai_ic50_avg_nm != null) || (r.ai_ic50_value_nm != null) || (r.ai_ic50_min_nm != null && r.ai_ic50_max_nm != null);
        if (hasAI) aiRows.push(r); else dbRows.push(r);
      }
      // Compose axis and data arrays
      const makeCenterValue = (r) => {
        if (r.ai_ic50_avg_nm != null) return Number(r.ai_ic50_avg_nm);
        if (r.ai_ic50_value_nm != null) return Number(r.ai_ic50_value_nm);
        if (r.nav1_7_ic50_value_nm != null) return Number(r.nav1_7_ic50_value_nm);
        return null;
      };
      const makeErrPlus = (r, center) => {
        if (r.ai_ic50_max_nm != null && center != null) return Math.max(0, Number(r.ai_ic50_max_nm) - center);
        return 0;
      };
      const makeErrMinus = (r, center) => {
        if (r.ai_ic50_min_nm != null && center != null) return Math.max(0, center - Number(r.ai_ic50_min_nm));
        return 0;
      };

      const labelsAI = aiRows.map((r) => buildLabelWithOri(r));
      const centersAI = aiRows.map(r => makeCenterValue(r));
      const errPlusAI = aiRows.map((r, idx) => makeErrPlus(r, centersAI[idx]));
      const errMinusAI = aiRows.map((r, idx) => makeErrMinus(r, centersAI[idx]));

      const labelsDB = dbRows.map((r) => buildLabelWithOri(r));
      const centersDB = dbRows.map(r => makeCenterValue(r));

      // Build traces: AI with error bars, DB without
      const traceAI = {
        x: labelsAI,
        y: centersAI,
        name: 'AI (promedio/valor)',
        type: 'scatter',
        mode: 'markers',
        marker: { color: '#2563eb', size: 8, opacity: 0.9 },
        error_y: {
          type: 'data',
          array: errPlusAI,
          arrayminus: errMinusAI,
          visible: true,
          thickness: 1.2,
          width: 2,
          color: '#2563eb',
        },
      };
      const traceDB = {
        x: labelsDB,
        y: centersDB,
        name: 'DB',
        type: 'scatter',
        mode: 'markers',
        marker: { color: '#10b981', size: 8, opacity: 0.9 },
      };

      const layout = {
        title: 'IC50 (nM) - Accession (ori=Δori°)',
        xaxis: { title: 'Accession (con Δori)', automargin: true, tickangle: -45, type: 'category' },
        yaxis: { title: 'IC50 (nM)', type: 'log' },
        margin: { t: 40, l: 60, r: 20, b: 160 },
        legend: { orientation: 'h', y: -0.2 },
      };

      Plotly.newPlot(container, [traceAI, traceDB], layout, { responsive: true });
    } catch (e) {
      container.innerHTML = `<div class="alert alert-danger">Error al renderizar gráfico: ${e.message}</div>`;
    }
  }

  // Renderiza gráfico de orientación (solo items sin IC50), Y lineal en grados
  async function renderOriNoIc50Chart(prefetchedItems) {
    const container = document.getElementById('ori-no-ic50-chart');
    if (!container) return;
    if (!prefetchedItems) {
      container.innerHTML = '<div class="alert alert-info">Cargando datos…</div>';
    }
    try {
      const allItems = Array.isArray(prefetchedItems) ? prefetchedItems : await fetchAllItemsWithCurrentParams();
      const noIc50 = allItems.filter(it => {
        const hasDb = (it.nav1_7_ic50_value_nm != null);
        const hasAi = (it.ai_ic50_avg_nm != null) || (it.ai_ic50_value_nm != null) || (it.ai_ic50_min_nm != null) || (it.ai_ic50_max_nm != null);
        return !hasDb && !hasAi;
      });
      if (!noIc50.length) {
        container.innerHTML = '<div class="alert alert-info">No hay accesiones sin IC50.</div>';
        return;
      }
      const labels = [];
      const values = [];
      for (const it of noIc50) {
        const m = getOrientationMetrics(it);
        let ori = null;
        if (m && typeof m.orientationScore === 'number' && Number.isFinite(m.orientationScore)) {
          ori = m.orientationScore;
        } else if (m && typeof m.deltaZ === 'number' && Number.isFinite(m.deltaZ)) {
          ori = m.deltaZ;
        }
        if (ori !== null) {
          const acc = it.accession_number || it.accession || it.name || it.peptide_id || 'NA';
          labels.push(String(acc));
          values.push(ori);
        }
      }
      if (!values.length) {
        container.innerHTML = '<div class="alert alert-info">No hay valores de orientación para mostrar.</div>';
        return;
      }
      const trace = {
        x: labels,
        y: values,
        name: 'Δori (°) sin IC50',
        type: 'scatter',
        mode: 'markers',
        marker: { color: '#ef6c00', size: 8, opacity: 0.9 },
      };
      const layout = {
        title: 'Orientación Δori (°) - Solo accesiones sin IC50',
        xaxis: { title: 'Accession (con Δori)', automargin: true, tickangle: -45, type: 'category' },
        yaxis: { title: 'Δori (°)', type: 'linear', rangemode: 'tozero', range: [0, 180] },
        margin: { t: 40, l: 60, r: 20, b: 160 },
        legend: { orientation: 'h', y: -0.2 },
      };
      Plotly.newPlot(container, [trace], layout, { responsive: true });
    } catch (e) {
      container.innerHTML = `<div class="alert alert-danger">Error al renderizar gráfico: ${e.message}</div>`;
    }
  }

  // Actualiza ambos gráficos usando los parámetros actuales, reutilizando datos si es posible
  async function updateChartsWithAllItems() {
    try {
      const items = await fetchAllItemsWithCurrentParams();
      await Promise.all([
        renderIc50ScatterAll(items),
        renderOriNoIc50Chart(items)
      ]);
    } catch (e) {
      console.error('Error actualizando gráficos:', e);
    }
  }

  function prepareItem(item) {
    if (!item || typeof item !== 'object') return item;
    const prepared = { ...item };
    const normalizedAngles = normalizeAngles(prepared.angles_deg);
    if (normalizedAngles) {
      prepared.angles_deg = normalizedAngles;
    }
    const normalizedDiffs = normalizeAngleDiffs(prepared.angle_diff_vs_reference);
    if (normalizedDiffs) {
      prepared.angle_diff_vs_reference = normalizedDiffs;
    }
    const fieldsToNormalize = [
      'angle_with_z_deg',
      'orientation_score_deg',
      'vector_angle_vs_reference_deg',
      'angle_diff_l2_deg',
      'angle_diff_l1_deg',
    ];
    fieldsToNormalize.forEach((field) => {
      if (Object.prototype.hasOwnProperty.call(prepared, field)) {
        const num = toFiniteNumber(prepared[field]);
        if (num !== null) prepared[field] = num;
      }
    });
    const vector = Array.isArray(prepared.normalized_vector)
      ? prepared.normalized_vector
      : getNormalizedVector(prepared);
    if (vector) {
      prepared.normalized_vector = vector;
    }
    return prepared;
  }

  function getAngleDegrees(dipole) {
    if (!dipole) return null;
    const raw = dipole.angle_with_z_axis ? dipole.angle_with_z_axis.degrees : null;
    const parsed = toFiniteNumber(raw);
    if (parsed !== null) return parsed;
    return toFiniteNumber(dipole.angle_with_z_deg);
  }

  // ========== FUNCIONES DE RENDERIZADO POR MODO ==========
  
  function renderDipoleView(viewer, pdbText, subject, container, options = {}) {
    const dipole = subject && subject.dipole ? subject.dipole : subject;
    viewer.clear();
    viewer.addModel(pdbText, 'pdb');
    viewer.setStyle({}, { cartoon: { color: 'spectrum', opacity: 0.9 } });
    
    const com = (dipole && dipole.center_of_mass) ? dipole.center_of_mass : [0,0,0];
    addAxes(viewer, com, 8.0);
    addDipoleArrow(viewer, dipole);
    
    viewer.zoomTo();
    viewer.render();
    overlayLegend(container, subject || dipole, options);
  }

  function renderDisulfideView(viewer, pdbText, sequence, container) {
    viewer.clear();
    const model = viewer.addModel(pdbText, 'pdb');
    
    // Proteína en cartoon semi-transparente
    viewer.setStyle({}, { 
      cartoon: { 
        color: 'lightgray', 
        opacity: 0.4 
      } 
    });
    
    // Resaltar cisteínas en stick
    viewer.setStyle({ resn: 'CYS' }, {
      stick: { 
        colorscheme: 'yellowCarbon',
        radius: 0.3 
      }
    });
    
    // Detectar puentes disulfuro desde el PDB
    const bonds = detectDisulfideBondsFromPDB(model);
    
    // Dibujar cilindros representando los puentes
    bonds.forEach(bond => {
      viewer.addCylinder({
        start: bond.atom1,
        end: bond.atom2,
        radius: 0.15,
        color: 'gold',
        fromCap: 1,
        toCap: 1
      });
    });
    
    viewer.zoomTo();
    viewer.render();
    
    // Overlay con info de puentes
    overlayDisulfideInfo(container, bonds, sequence);
  }

  // Detectar puentes disulfuro a partir del modelo 3D (busca átomos SG en residuos CYS)
  function detectDisulfideBondsFromPDB(model) {
    try {
      // Obtener todos los átomos del modelo
      const atoms = typeof model.selectedAtoms === 'function' ? model.selectedAtoms({}) : (model.atoms || []);
      if (!Array.isArray(atoms)) return [];

      // Filtrar átomos SG de CYS
      const sgAtoms = atoms.filter(a => {
        try {
          const resn = (a.resn || '').toString().toUpperCase();
          const atomName = (a.atom || '').toString().trim().toUpperCase();
          const elem = (a.elem || '').toString().toUpperCase();
          return resn === 'CYS' && (atomName === 'SG' || elem === 'S');
        } catch (e) {
          return false;
        }
      });

      const bonds = [];
      const thresholdMax = 2.6; // Å - umbral generoso
      const thresholdMin = 1.6; // Å - evitar coincidencias triviales

      for (let i = 0; i < sgAtoms.length; i++) {
        for (let j = i + 1; j < sgAtoms.length; j++) {
          const a = sgAtoms[i];
          const b = sgAtoms[j];
          if (a.x == null || a.y == null || a.z == null || b.x == null || b.y == null || b.z == null) continue;
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dz = a.z - b.z;
          const d = Math.sqrt(dx*dx + dy*dy + dz*dz);
          if (d >= thresholdMin && d <= thresholdMax) {
            bonds.push({
              atom1: { x: a.x, y: a.y, z: a.z },
              atom2: { x: b.x, y: b.y, z: b.z },
              resi1: a.resi, chain1: a.chain, resn1: a.resn,
              resi2: b.resi, chain2: b.chain, resn2: b.resn,
              distance: d,
            });
          }
        }
      }
      return bonds;
    } catch (e) {
      console.error('detectDisulfideBondsFromPDB error', e);
      return [];
    }
  }

  function renderBothView(viewer, pdbText, subject, sequence, container, options = {}) {
    const dipole = subject && subject.dipole ? subject.dipole : subject;
    viewer.clear();
    const model = viewer.addModel(pdbText, 'pdb');
    
    // Proteína en cartoon con opacidad media
    viewer.setStyle({}, { 
      cartoon: { 
        color: 'spectrum', 
        opacity: 0.6 
      } 
    });
    
    // Cisteínas destacadas
    viewer.setStyle({ resn: 'CYS' }, {
      stick: { 
        colorscheme: 'yellowCarbon', 
        radius: 0.25 
      }
    });
    
    // Puentes disulfuro
    const bonds = detectDisulfideBondsFromPDB(model);
    bonds.forEach(bond => {
      viewer.addCylinder({
        start: bond.atom1,
        end: bond.atom2,
        radius: 0.12,
        color: 'gold',
        fromCap: 1,
        toCap: 1,
        dashed: true
      });
    });
    
    // Ejes y vector dipolar
    const com = (dipole && dipole.center_of_mass) ? dipole.center_of_mass : [0,0,0];
    addAxes(viewer, com, 8.0);
    addDipoleArrow(viewer, dipole);
    
    viewer.zoomTo();
    viewer.render();
    
    // Overlay combinado
    overlayBothInfo(container, subject || dipole, bonds, options);
  }

  function overlayDisulfideInfo(container, bonds, sequence) {
    try { container.style.position = container.style.position || 'relative'; } catch(e) {}
    
    const { positions } = findDisulfideBonds(sequence);
    let legend = container.querySelector('.dipole-legend');
    
    if (!legend) {
      legend = document.createElement('div');
      legend.className = 'dipole-legend';
      legend.style.position = 'absolute';
      legend.style.left = '8px';
      legend.style.bottom = '8px';
      legend.style.background = 'rgba(255,255,255,0.92)';
      legend.style.border = '1px solid #ddd';
      legend.style.borderRadius = '6px';
      legend.style.padding = '6px 8px';
      legend.style.fontSize = '12px';
      legend.style.color = '#222';
      legend.style.boxShadow = '0 1px 2px rgba(0,0,0,0.08)';
      container.appendChild(legend);
    }
    
    legend.innerHTML = `
      <strong>Puentes Disulfuro</strong><br>
      Cisteínas: ${positions.length}<br>
      Puentes: ${bonds.length}<br>
      Pos: ${positions.map(p => p+1).join(', ')}
    `;
  }

  function overlayBothInfo(container, subject, bonds, options = {}) {
    try { container.style.position = container.style.position || 'relative'; } catch(e) {}

    let legend = container.querySelector('.dipole-legend');

    if (!legend) {
      legend = document.createElement('div');
      legend.className = 'dipole-legend';
      legend.style.position = 'absolute';
      legend.style.left = '8px';
      legend.style.bottom = '8px';
      legend.style.background = 'rgba(255,255,255,0.92)';
      legend.style.border = '1px solid #ddd';
      legend.style.borderRadius = '6px';
      legend.style.padding = '6px 8px';
      legend.style.fontSize = '11px';
      legend.style.color = '#222';
      legend.style.boxShadow = '0 1px 2px rgba(0,0,0,0.08)';
      container.appendChild(legend);
    }

    const extra = (options.extraLines && options.extraLines.length) ? [...options.extraLines] : [];
    extra.push(`<strong>Puentes S-S:</strong> ${bonds.length}`);
    legend.innerHTML = buildDipoleInfoHTML(subject, { ...options, extraLines: extra });
  }

  // ========== FUNCIONES AUXILIARES EXISTENTES ==========


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

  function overlayLegend(container, subject, options = {}) {
    try { container.style.position = container.style.position || 'relative'; } catch(e) {}
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
    legend.innerHTML = buildDipoleInfoHTML(subject, options);
  }

  async function loadReference(peptideCode = selectedReferenceCode) {
    const desiredCode = peptideCode || 'WT';
    const params = new URLSearchParams();
    if (desiredCode && desiredCode !== 'WT') {
      params.set('peptide_code', desiredCode);
    }
    const url = params.toString() ? `/v2/motif_dipoles/reference?${params.toString()}` : '/v2/motif_dipoles/reference';
    try {
      refContainer.innerHTML = `
        <div class="loading-state">
          <div class="spinner" id="refSpinner"></div>
          <p class="loading-text">Cargando referencia...</p>
        </div>
      `;
      const res = await fetch(url);
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      selectedReferenceCode = data.selected_reference_code || desiredCode || 'WT';
      referenceDisplayName = data.display_name || (selectedReferenceCode === 'WT' ? 'Proteína WT' : selectedReferenceCode);

      // Mostrar la secuencia de la referencia junto al selector si existe el elemento
      try {
        const seqEl = document.getElementById('reference-sequence');
        if (seqEl) {
          const seqText = (data && data.sequence) ? String(data.sequence) : '-';
          seqEl.textContent = seqText || '-';
          seqEl.title = (data && data.sequence) ? String(data.sequence) : '';
        }
      } catch (e) {
        // no crítico
      }

      const candidateAngles = data.angles_deg || computeAxisAnglesFromDipole(data) || computeAxisAnglesFromDipole(data.dipole);
      const normalizedAngles = normalizeAngles(candidateAngles);
      if (normalizedAngles) {
        referenceAngles = normalizedAngles;
      }
      const refAngleCandidate = toFiniteNumber(data.angle_with_z_deg)
        ?? (referenceAngles && Object.prototype.hasOwnProperty.call(referenceAngles, 'z') ? referenceAngles.z : null)
        ?? getAngleDegrees(data.dipole);
      if (refAngleCandidate !== null) {
        referenceAngleDeg = refAngleCandidate;
      }
      referenceSource = data.source || null;
      referenceVector = Array.isArray(data.normalized_vector)
        ? data.normalized_vector
        : getNormalizedVector(data) || getNormalizedVector(data.dipole) || referenceVector;
      referencePaths = {
        pdb: data.pdb_path || referencePaths.pdb,
        psf: data.psf_path || referencePaths.psf,
      };
      if (Array.isArray(data.reference_options)) {
        updateReferenceSelector(data.reference_options, selectedReferenceCode);
      } else if (referenceSelector) {
        referenceSelector.value = selectedReferenceCode;
      }

      const extraLines = [];
      const ic50Value = toFiniteNumber(data.ic50_value);
      if (ic50Value !== null) {
        const unitText = data.ic50_unit ? ` ${data.ic50_unit}` : '';
        extraLines.push(`IC50: ${ic50Value.toFixed(3)}${unitText}`);
      }
      if (typeof data.normalized_ic50 === 'number' && Number.isFinite(data.normalized_ic50)) {
        extraLines.push(`IC50 norm: ${data.normalized_ic50.toFixed(3)}`);
      }

      refContainer.innerHTML = '';
      const viewer = $3Dmol.createViewer(refContainer, { backgroundColor: 'white' });
      renderDipoleView(viewer, data.pdb_text, data, refContainer, { isReference: true, extraLines });
      return data;
    } catch (e) {
      refContainer.innerHTML = `<div class="alert alert-warning">Referencia no disponible: ${e.message}</div>`;
      throw e;
    }
  }

  function cardHTML(idx, item) {
    const id = `motif-v-${idx}`;
    const title = `${item.name || ''} (${item.accession_number})`;
    const magnitude = toFiniteNumber(item && item.dipole && item.dipole.magnitude);
    const metrics = getOrientationMetrics(item);
    const angleZ = formatDegWithSuffix(metrics.angleZ);
    const deltaOrient = formatDegWithSuffix(metrics.orientationScore);
    const deltaZ = formatDegWithSuffix(metrics.deltaZ);
    return `
      <div class="dipole-visualization-card">
        <div class="dipole-card-header" style="display:flex;align-items:center;justify-content:space-between;gap:0.5rem;">
          <div style="display:flex;flex-direction:column;align-items:flex-start;gap:4px;">
            <h6 class="dipole-card-title" style="margin:0;font-size:16px;line-height:1.1;">
              <i class="fas fa-dna"></i>
              <span class="title-text" style="font-size:16px;font-weight:600;">${item.name || ''}</span>
              <a class="accession-link" href="https://www.uniprot.org/uniprotkb/${item.accession_number}/entry" target="_blank" rel="noopener noreferrer" style="margin-left:6px;color:var(--link-color,#1e88e5);font-weight:600;font-size:16px;">(${item.accession_number})</a>
            </h6>
            <span class="dipole-sequence" style="color:#374151;font-family:monospace;font-size:16px;line-height:1.2;">${item.sequence || '-'}</span>
          </div>
          <div>
            <button class="card-download-btn btn btn-sm btn-secondary" data-accession="${item.accession_number}" style="z-index:1000;">
              <i class="fas fa-download"></i>
              <span class="btn-label">Descargar</span>
            </button>
          </div>
        </div>
        <div id="${id}" class="dipole-viewer" style="position:relative;"></div>
      </div>
    `;
  }

  if (referenceSelector) {
    referenceSelector.addEventListener('change', async (event) => {
      const newValue = event.target.value || 'WT';
      if (newValue === selectedReferenceCode) return;
      const previousValue = selectedReferenceCode;
      selectedReferenceCode = newValue;
      try {
        await loadReference(newValue);
      } catch (err) {
        selectedReferenceCode = previousValue;
        if (referenceSelector) referenceSelector.value = previousValue;
        console.error('No se pudo cargar la referencia seleccionada:', err);
        return;
      }
      await renderPage();
      await updateChartsWithAllItems();
        });

        
  }

  // Botón para descargar PDB y PSF de la referencia seleccionada (zip)
  const downloadRefBtn = document.getElementById('download-reference-btn');
  if (downloadRefBtn) {
    downloadRefBtn.addEventListener('click', async (ev) => {
      ev.preventDefault();
      const code = selectedReferenceCode || 'WT';
      downloadRefBtn.disabled = true;
      const originalHtml = downloadRefBtn.innerHTML;
      downloadRefBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Descargando...';
      try {
        const url = `/v2/motif_dipoles/reference/download?peptide_code=${encodeURIComponent(code)}`;
        const res = await fetch(url);
        if (!res.ok) {
          let msg = `HTTP ${res.status}`;
          try { const txt = await res.text(); if (txt) msg += ` - ${txt}`; } catch(e) {}
          throw new Error(msg);
        }
        const blob = await res.blob();
        const disposition = res.headers.get('Content-Disposition') || '';
        let filename = `${code}_reference_files.zip`;
        const m = /filename="?([^";]+)"?/.exec(disposition);
        if (m && m[1]) filename = m[1];
        const urlBlob = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = urlBlob;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(urlBlob);
      } catch (err) {
        console.error('Error descargando referencia:', err);
        alert('No se pudo descargar la referencia: ' + (err && err.message ? err.message : 'error desconocido'));
      } finally {
        downloadRefBtn.disabled = false;
        downloadRefBtn.innerHTML = originalHtml;
      }
    });
  }

  // Función para re-renderizar la página actual con un modo diferente
  function reRenderCurrentPage() {
    if (!currentPageItems.length) return;
    
    // Aplicar animación
    grid.classList.add('mode-changing');
    setTimeout(() => grid.classList.remove('mode-changing'), 300);
    
    currentPageItems.forEach((it, i) => {
      const el = document.getElementById(`motif-v-${i}`);
      if (!el) return;
      
      // Limpiar viewer existente
      el.innerHTML = '';
      el.style.position = 'relative';
      
      const viewer = $3Dmol.createViewer(el, { backgroundColor: 'white' });
      
      // Renderizar según modo
      if (viewMode === 'dipole') {
        renderDipoleView(viewer, it.pdb_text, it, el);
      } else if (viewMode === 'disulfide') {
        const sequence = it.sequence || '';
        renderDisulfideView(viewer, it.pdb_text, sequence, el);
      }
    });
  }

  // Navegación
  prevBtn && prevBtn.addEventListener('click', () => { if (page > 1) { page--; renderPage(); } });
  nextBtn && nextBtn.addEventListener('click', () => {
    const maxPage = Math.max(1, Math.ceil(lastCount / pageSize));
    if (page < maxPage) { page++; renderPage(); }
  });

  // ========== EVENT LISTENERS PARA BOTONES DE MODO DE VISUALIZACIÓN ==========
  
  const dipoleBtn = document.getElementById('showDipoleBtn');
  const disulfideBtn = document.getElementById('showDisulfideBtn');
  
  function setActiveButton(activeBtn) {
    [dipoleBtn, disulfideBtn].forEach(btn => {
      if (btn) btn.classList.remove('active');
    });
    if (activeBtn) activeBtn.classList.add('active');
  }
  
  if (dipoleBtn) {
    dipoleBtn.addEventListener('click', () => {
      viewMode = 'dipole';
      setActiveButton(dipoleBtn);
      reRenderCurrentPage();
    });
  }
  
  if (disulfideBtn) {
    disulfideBtn.addEventListener('click', () => {
      viewMode = 'disulfide';
      setActiveButton(disulfideBtn);
      reRenderCurrentPage();
    });
  }
  
  // 'Both' mode removed - no handler

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

  loadReference()
    .catch((err) => {
      console.error('No se pudo inicializar la referencia:', err);
    })
    .then(() => {
      renderPage();
    });
});
