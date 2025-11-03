/* Web Worker para construir datasets de gráficos sin bloquear el hilo principal */

self.onmessage = (ev) => {
  try {
    const { type, items, referenceAngles, referenceAngleDeg } = ev.data || {};
    if (type !== 'build-datasets' || !Array.isArray(items)) {
      self.postMessage({ ic50: { data: [], layout: {} }, ori: { data: [], layout: {} } });
      return;
    }

    // Utilidades locales
    const toNum = (v) => (typeof v === 'number' && isFinite(v)) ? v : (typeof v === 'string' && v.trim() ? Number(v) : null);
    const buildLabel = (it, ori) => {
      const acc = it.accession_number || it.accession || it.name || it.peptide_id || 'NA';
      const suffix = (typeof ori === 'number' && isFinite(ori)) ? ` (ori=${ori.toFixed(1)}°)` : '';
      return `${acc}${suffix}`;
    };

    // ========== IC50 (AI vs DB) ==========
    const hasIc50 = (it) => (
      (it.ai_ic50_avg_nm != null) || (it.ai_ic50_value_nm != null) ||
      (it.ai_ic50_min_nm != null && it.ai_ic50_max_nm != null) || (it.nav1_7_ic50_value_nm != null)
    );
    const rows = items.filter(hasIc50);
    const aiRows = []; const dbRows = [];
    for (const r of rows) {
      const hasAI = (r.ai_ic50_avg_nm != null) || (r.ai_ic50_value_nm != null) || (r.ai_ic50_min_nm != null && r.ai_ic50_max_nm != null);
      if (hasAI) aiRows.push(r); else dbRows.push(r);
    }
    const centerVal = (r) => toNum(r.ai_ic50_avg_nm ?? r.ai_ic50_value_nm ?? r.nav1_7_ic50_value_nm);

    const centersAI = aiRows.map(centerVal);
    const errPlusAI = aiRows.map((r, idx) => (r.ai_ic50_max_nm != null && centersAI[idx] != null) ? Math.max(0, Number(r.ai_ic50_max_nm) - centersAI[idx]) : 0);
    const errMinusAI = aiRows.map((r, idx) => (r.ai_ic50_min_nm != null && centersAI[idx] != null) ? Math.max(0, centersAI[idx] - Number(r.ai_ic50_min_nm)) : 0);

    // Orientación aproximada solo para etiquetas (usar orientation_score_deg si existe, de lo contrario ΔZ básico)
    const pickOrientation = (it) => {
      if (typeof it.orientation_score_deg === 'number' && isFinite(it.orientation_score_deg)) return it.orientation_score_deg;
      const diffs = it.angle_diff_vs_reference;
      if (diffs && typeof diffs === 'object' && diffs.z != null) {
        const z = toNum(diffs.z);
        if (z != null) return z;
      }
      const angles = it.angles_deg;
      if (angles && referenceAngles && angles.z != null && referenceAngles.z != null) {
        const a = toNum(angles.z); const b = toNum(referenceAngles.z);
        if (a != null && b != null) return Math.abs(a - b);
      }
      if (angles && angles.z != null && referenceAngleDeg != null) {
        const a = toNum(angles.z); const b = toNum(referenceAngleDeg);
        if (a != null && b != null) return Math.abs(a - b);
      }
      return null;
    };

    const labelsAI = aiRows.map((r) => buildLabel(r, pickOrientation(r)));
    const centersDB = dbRows.map(centerVal);
    const labelsDB = dbRows.map((r) => buildLabel(r, pickOrientation(r)));

    const ic50 = {
      data: [
        { x: labelsAI, y: centersAI, name: 'AI (prom/valor)', type: 'scatter', mode: 'markers', marker: { color: '#2563eb', size: 8, opacity: 0.9 },
          error_y: { type: 'data', array: errPlusAI, arrayminus: errMinusAI, visible: true, thickness: 1.2, width: 2, color: '#2563eb' } },
        { x: labelsDB, y: centersDB, name: 'DB', type: 'scatter', mode: 'markers', marker: { color: '#10b981', size: 8, opacity: 0.9 } }
      ],
      layout: { title: 'IC50 (nM) - Accession (ori=Δori°)', xaxis: { title: 'Accession (con Δori)', automargin: true, tickangle: -45, type: 'category' }, yaxis: { title: 'IC50 (nM)', type: 'log' }, margin: { t: 40, l: 60, r: 20, b: 160 }, legend: { orientation: 'h', y: -0.2 } }
    };

    // ========== ORI sin IC50 ==========
    const noIc50 = items.filter(it => {
      const hasDb = (it.nav1_7_ic50_value_nm != null);
      const hasAi = (it.ai_ic50_avg_nm != null) || (it.ai_ic50_value_nm != null) || (it.ai_ic50_min_nm != null) || (it.ai_ic50_max_nm != null);
      return !hasDb && !hasAi;
    });
    const xOri = []; const yOri = [];
    for (const it of noIc50) {
      let ori = pickOrientation(it);
      if (typeof ori === 'number' && isFinite(ori)) {
        xOri.push(String(it.accession_number || it.accession || it.name || it.peptide_id || 'NA'));
        yOri.push(ori);
      }
    }

    const ori = {
      data: [{ x: xOri, y: yOri, name: 'Δori (°) sin IC50', type: 'scatter', mode: 'markers', marker: { color: '#ef6c00', size: 8, opacity: 0.9 } }],
      layout: { title: 'Orientación Δori (°) - Solo accesiones sin IC50', xaxis: { title: 'Accession (con Δori)', automargin: true, tickangle: -45, type: 'category' }, yaxis: { title: 'Δori (°)', type: 'linear', rangemode: 'tozero', range: [0, 180] }, margin: { t: 40, l: 60, r: 20, b: 160 }, legend: { orientation: 'h', y: -0.2 } }
    };

    self.postMessage({ ic50, ori });
  } catch (e) {
    try {
      self.postMessage({ ic50: { data: [], layout: {} }, ori: { data: [], layout: {} }, error: String(e && e.message || e) });
    } catch (_) {}
  }
};
