/* ============================================================
   main.js – SurveyCAD
   ============================================================ */

// ── Named constants (Rule 6) ────────────────────────────────────
const MAX_PREVIEW_ROWS = 10;
const API_UPLOAD   = '/api/upload';
const API_GENERATE = '/api/generate';
const API_DOWNLOAD = '/api/download/';
const ALLOWED_EXTENSIONS = ['csv', 'txt'];

// ── AbortControllers for in-flight requests (Rule 5) ────────────
let _uploadController = null;
let _generateController = null;

// ── Application state ───────────────────────────────────────────
const state = {
  rows: [], uniqueCodes: [], hasElevation: false, hasDesc: false,
  showAll: false, selectedModes: new Set(), polylineCodes: new Set(),
};

// ── DOM refs ────────────────────────────────────────────────────
const uploadZone       = document.getElementById('upload-zone');
const fileInput        = document.getElementById('file-input');
const uploadResult     = document.getElementById('upload-result');
const previewSection   = document.getElementById('preview-section');
const tableBody        = document.getElementById('table-body');
const pointCount       = document.getElementById('point-count');
const codesWrap        = document.getElementById('codes-wrap');
const btnShowAll       = document.getElementById('btn-show-all');
const modeScr          = document.getElementById('mode-scr');
const modeDxf          = document.getElementById('mode-dxf');
const settingsToggle   = document.getElementById('settings-toggle');
const settingsPanel    = document.getElementById('settings-panel');
const sliderHeight     = document.getElementById('slider-height');
const heightInput      = document.getElementById('height-input');
const selectUnits      = document.getElementById('select-units');
const toggleOffset     = document.getElementById('toggle-offset');
const polylineList     = document.getElementById('polyline-list');
const instrToggle      = document.getElementById('instructions-toggle');
const instrBody        = document.getElementById('instructions-body');
const btnGenerate      = document.getElementById('btn-generate');
const logBox           = document.getElementById('log-box');
const downloadSection  = document.getElementById('download-section');
const downloadGrid     = document.getElementById('download-grid');
const steps            = document.querySelectorAll('.step');

// ── Background Canvas ───────────────────────────────────────────
(function initCanvas() {
  const canvas = document.getElementById('bg-canvas');
  const ctx = canvas.getContext('2d');
  let W, H, dots = [], lines = [], gridOffset = 0, frame = 0;

  /**
   * Resizes the canvas to match the window dimensions.
   * @returns {void}
   */
  function resize() { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; }

  /**
   * Generates a random number between a and b.
   * @param {number} a - The minimum value.
   * @param {number} b - The maximum value.
   * @returns {number} The random number.
   */
  function rand(a, b) { return a + Math.random() * (b - a); }

  /**
   * Initializes the dots and lines for the background animation.
   * @returns {void}
   */
  function initDots() {
    dots = [];
    const count = Math.min(35, Math.floor(W * H / 25000));
    for (let i = 0; i < count; i++) {
      dots.push({ x: rand(0, W), y: rand(0, H), vx: rand(-0.15, 0.15), vy: rand(-0.1, 0.1), r: rand(1.5, 3.5), phase: rand(0, Math.PI * 2) });
    }
    lines = [];
    for (let i = 0; i < dots.length; i++) {
      for (let j = i + 1; j < dots.length; j++) {
        if (Math.hypot(dots[i].x - dots[j].x, dots[i].y - dots[j].y) < W * 0.16) lines.push([i, j]);
      }
    }
  }

  /**
   * Draws a single frame of the background animation.
   * @returns {void}
   */
  function draw() {
    frame++;
    ctx.clearRect(0, 0, W, H);
    const spacing = 80;
    gridOffset = (gridOffset + 0.25) % spacing;

    // Grid — orange only
    ctx.strokeStyle = 'rgba(255,107,0,0.04)';
    ctx.lineWidth = 1;
    for (let y = -spacing + gridOffset; y < H + spacing; y += spacing) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    for (let x = 0; x < W + spacing; x += spacing) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }

    // Radial glow - slowly moving center for 3D animated wash effect
    const cx = W / 2 + (W * 0.15 * Math.sin(frame * 0.005));
    const cy = H / 3 + (H * 0.1 * Math.cos(frame * 0.007));
    const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, W * 0.55);
    grd.addColorStop(0, 'rgba(255,107,0,0.035)');
    grd.addColorStop(1, 'transparent');
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, W, H);

    // Lines — orange only
    for (const [a, b] of lines) {
      const alpha = 0.06 + 0.04 * Math.sin(frame * 0.01 + a);
      ctx.strokeStyle = `rgba(255,107,0,${alpha})`;
      ctx.lineWidth = 0.7;
      ctx.beginPath(); ctx.moveTo(dots[a].x, dots[a].y); ctx.lineTo(dots[b].x, dots[b].y); ctx.stroke();
    }

    // Dots — orange only
    for (const d of dots) {
      const pulse = 1 + 0.3 * Math.sin(frame * 0.02 + d.phase);
      ctx.beginPath(); ctx.arc(d.x, d.y, d.r * pulse, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,107,0,0.5)';
      ctx.fill();
      ctx.beginPath(); ctx.arc(d.x, d.y, d.r * 4 * pulse, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,107,0,0.02)';
      ctx.fill();
      d.x += d.vx; d.y += d.vy;
      if (d.x < -30) d.x = W + 30; if (d.x > W + 30) d.x = -30;
      if (d.y < -30) d.y = H + 30; if (d.y > H + 30) d.y = -30;
    }
    requestAnimationFrame(draw);
  }

  window.addEventListener('resize', () => { resize(); initDots(); });
  resize(); initDots(); draw();
})();

// ── Height slider / input sync ──────────────────────────────────

/**
 * Synchronizes the visual slider and number input fields based on interaction.
 * @param {string} source - The source of the change event ('slider' or 'input').
 * @returns {void}
 */
function syncHeight(source) {
  let val;
  if (source === 'slider') {
    val = parseFloat(sliderHeight.value);
    heightInput.value = val;
  } else {
    val = parseFloat(heightInput.value);
    if (isNaN(val) || val < 0.1) val = 0.1;
    sliderHeight.value = Math.min(val, parseFloat(sliderHeight.max));
  }
  const min = parseFloat(sliderHeight.min), max = parseFloat(sliderHeight.max);
  const pct = ((Math.min(Math.max(val, min), max) - min) / (max - min) * 100).toFixed(1);
  sliderHeight.style.setProperty('--pct', pct + '%');
}
sliderHeight.addEventListener('input', () => syncHeight('slider'));
heightInput.addEventListener('input', () => syncHeight('input'));
heightInput.addEventListener('change', () => syncHeight('input'));
syncHeight('slider');

// ── Settings toggle ─────────────────────────────────────────────
settingsToggle.addEventListener('click', () => {
  const open = settingsPanel.classList.toggle('open');
  settingsToggle.classList.toggle('open', open);
  settingsToggle.querySelector('span').textContent = open ? 'Hide Settings' : 'Show Settings';
});

// ── Instructions toggle ─────────────────────────────────────────
instrToggle.addEventListener('click', () => {
  const open = instrBody.classList.toggle('open');
  instrToggle.classList.toggle('open', open);
});

/**
 * Toggles a generation mode (SCR or DXF) and updates the generate button.
 * @param {HTMLElement} el - The DOM element representing the mode card.
 * @param {string} mode - The string name of the mode.
 * @returns {void}
 */
function toggleMode(el, mode) {
  if (state.selectedModes.has(mode)) { state.selectedModes.delete(mode); el.classList.remove('selected'); }
  else { state.selectedModes.add(mode); el.classList.add('selected'); }
  updateGenerateBtn();
}
modeScr.addEventListener('click', () => toggleMode(modeScr, 'scr'));
modeDxf.addEventListener('click', () => toggleMode(modeDxf, 'dxf'));

/**
 * Sets the active step indicator in the UI.
 * @param {number} n - The step number to set as active.
 * @returns {void}
 */
function setStep(n) {
  steps.forEach((s, i) => {
    s.classList.remove('active', 'done');
    if (i + 1 < n) s.classList.add('done');
    if (i + 1 === n) s.classList.add('active');
  });
}
setStep(1);

// Make steps clickable to scroll
document.getElementById('step-1').addEventListener('click', () => { window.scrollTo({ top: 0, behavior: 'smooth' }); });
document.getElementById('step-2').addEventListener('click', () => { document.querySelector('section:nth-of-type(2)').scrollIntoView({ behavior: 'smooth' }); });
document.getElementById('step-3').addEventListener('click', () => { btnGenerate.scrollIntoView({ behavior: 'smooth', block: 'center' }); });

/**
 * Displays a temporary toast notification message to the user.
 * @param {string} msg - The message text to display.
 * @param {string} [type='error'] - The type/style of the toast.
 * @returns {void}
 */
function showToast(msg, type = 'error') {
  const tc = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  tc.appendChild(t);
  setTimeout(() => t.remove(), 4100);
}

/**
 * Appends a log line to the log output box.
 * @param {string} msg - The message to log.
 * @param {boolean} [isErr=false] - Whether this line represents an error.
 * @returns {void}
 */
function addLog(msg, isErr = false) {
  const line = document.createElement('span');
  line.className = 'log-line' + (isErr ? ' err' : '');
  line.textContent = '> ' + msg;
  logBox.appendChild(line);
  logBox.scrollTop = logBox.scrollHeight;
}

/**
 * Clears all existing log messages from the log box.
 * @returns {void}
 */
function clearLog() {
  while (logBox.firstChild) {
    logBox.removeChild(logBox.firstChild);
  }
}

// ── Upload ──────────────────────────────────────────────────────
uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => { e.preventDefault(); uploadZone.classList.remove('drag-over'); if (e.dataTransfer.files[0]) doUpload(e.dataTransfer.files[0]); });
fileInput.addEventListener('change', () => { if (fileInput.files[0]) doUpload(fileInput.files[0]); });

/**
 * Handles uploading a survey file to the backend API.
 * @param {File} file - The file object to upload.
 * @returns {Promise<void>}
 */
async function doUpload(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) { showUploadResult(false, 'Only .csv and .txt files are accepted.'); return; }
  showUploadResult(null, 'Uploading…');

  if (_uploadController) _uploadController.abort();
  _uploadController = new AbortController();

  const fd = new FormData(); fd.append('file', file);
  try {
    const res = await fetch(API_UPLOAD, { method: 'POST', body: fd, signal: _uploadController.signal });
    const data = await res.json();
    if (!res.ok || !data.success) { showUploadResult(false, (data.errors || ['Upload failed.']).join(' ')); return; }
    state.rows = data.rows; state.uniqueCodes = data.unique_codes || [];
    state.hasElevation = data.has_elevation; state.hasDesc = data.has_description; state.showAll = false;
    showUploadResult(true, `${file.name}  —  ${data.row_count} survey points loaded`);
    renderPreview(); renderPolylinesUI(); setStep(2); updateGenerateBtn();
  } catch (e) {
    if (e.name !== 'AbortError') {
      showUploadResult(false, 'Network error: ' + e.message); showToast('Upload failed — ' + e.message);
    }
  }
}

/**
 * Updates the UI with the result message of a file upload.
 * @param {boolean|null} ok - True if successful, false if error, null if loading.
 * @param {string} msg - The status message to display.
 * @returns {void}
 */
function showUploadResult(ok, msg) {
  uploadResult.className = 'upload-result';
  uploadResult.textContent = msg;
  if (ok === true) uploadResult.classList.add('success');
  if (ok === false) uploadResult.classList.add('error');
  if (ok === null) { uploadResult.style.display = 'flex'; uploadResult.style.color = '#7777AA'; }
}

/**
 * Creates a table cell element. If the value is empty or null, shows a
 * styled em-dash placeholder; otherwise sets textContent to the value.
 * @param {string|null} value - The cell text, or null/empty for a placeholder.
 * @returns {HTMLTableCellElement} The constructed <td> element.
 */
function createCell(value) {
  const td = document.createElement('td');
  if (value === null || value === undefined || value === '') {
    const placeholder = document.createElement('span');
    placeholder.className = 'cell-empty';
    placeholder.textContent = '—';
    td.appendChild(placeholder);
  } else {
    td.textContent = value;
  }
  return td;
}

/**
 * Renders the preview table and point count based on the current state.
 * @returns {void}
 */
function renderPreview() {
  previewSection.style.display = 'block';
  const rows = state.showAll ? state.rows : state.rows.slice(0, MAX_PREVIEW_ROWS);

  while (tableBody.firstChild) {
    tableBody.removeChild(tableBody.firstChild);
  }

  rows.forEach(r => {
    const tr = document.createElement('tr');
    tr.appendChild(createCell(r.sr_no));
    tr.appendChild(createCell(r.northing !== null && r.northing !== undefined ? r.northing.toFixed(4) : null));
    tr.appendChild(createCell(r.easting  !== null && r.easting  !== undefined ? r.easting.toFixed(4)  : null));
    tr.appendChild(createCell(r.elevation !== null && r.elevation !== undefined ? r.elevation.toFixed(3) : null));
    tr.appendChild(createCell(r.description || null));
    tableBody.appendChild(tr);
  });

  pointCount.textContent = `${state.rows.length} total survey point${state.rows.length !== 1 ? 's' : ''}`;

  // Unique code badges
  while (codesWrap.firstChild) {
    codesWrap.removeChild(codesWrap.firstChild);
  }
  if (state.uniqueCodes.length) {
    state.uniqueCodes.forEach(c => {
      const span = document.createElement('span');
      span.className = 'code-badge';
      span.textContent = c;
      codesWrap.appendChild(span);
    });
  } else {
    const noCodesSpan = document.createElement('span');
    noCodesSpan.style.fontSize = '0.78rem';
    noCodesSpan.style.color = 'var(--muted)';
    noCodesSpan.textContent = 'No codes';
    codesWrap.appendChild(noCodesSpan);
  }

  btnShowAll.textContent = state.showAll ? 'Show Less' : `Show All ${state.rows.length} Points`;
  btnShowAll.style.display = state.rows.length > MAX_PREVIEW_ROWS ? 'block' : 'none';
}
btnShowAll.addEventListener('click', () => { state.showAll = !state.showAll; renderPreview(); });

/**
 * Escapes special characters to HTML entities for safe attribute insertion.
 * Used only for data-* attribute values — never in innerHTML contexts.
 * @param {string} s - The string to escape.
 * @returns {string} The escaped string.
 */
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Renders the polylines toggle UI based on unique description codes.
 * @returns {void}
 */
function renderPolylinesUI() {
  state.polylineCodes.clear();

  while (polylineList.firstChild) {
    polylineList.removeChild(polylineList.firstChild);
  }

  if (!state.uniqueCodes.length) {
    const placeholder = document.createElement('p');
    placeholder.className = 'polyline-placeholder';
    placeholder.textContent = 'No description codes in this file.';
    polylineList.appendChild(placeholder);
    return;
  }

  state.uniqueCodes.forEach((code, i) => {
    const row = document.createElement('div');
    row.className = 'polyline-row';

    const spanName = document.createElement('span');
    spanName.textContent = code;
    row.appendChild(spanName);

    const label = document.createElement('label');
    label.className = 'toggle';

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.id = `pline-${i}`;
    cb.dataset.code = esc(code);
    cb.addEventListener('change', () => {
      if (cb.checked) state.polylineCodes.add(code);
      else state.polylineCodes.delete(code);
    });

    const slider = document.createElement('span');
    slider.className = 'toggle-slider';

    label.appendChild(cb);
    label.appendChild(slider);

    row.appendChild(label);
    polylineList.appendChild(row);
  });
}

/**
 * Evaluates state to enable or disable the Generate files button.
 * @returns {void}
 */
function updateGenerateBtn() { btnGenerate.disabled = !(state.rows.length > 0 && state.selectedModes.size > 0); }
updateGenerateBtn();

// ── Generate handler ────────────────────────────────────────────
btnGenerate.addEventListener('click', async () => {
  if (btnGenerate.disabled) return;
  clearLog(); setStep(3);
  downloadSection.style.display = 'none';

  while (downloadGrid.firstChild) {
    downloadGrid.removeChild(downloadGrid.firstChild);
  }

  btnGenerate.disabled = true;
  btnGenerate.innerHTML = '<span class="spinner"></span> GENERATING\u2026';
  addLog(`Prepared ${state.rows.length} survey points.`);

  if (_generateController) _generateController.abort();
  _generateController = new AbortController();

  const textHeight = parseFloat(heightInput.value) || parseFloat(sliderHeight.value) || 1.0;
  const body = {
    rows: state.rows, modes: [...state.selectedModes],
    text_height: textHeight, offset: toggleOffset.checked,
    polyline_codes: [...state.polylineCodes], units: selectUnits.value,
  };

  try {
    const res = await fetch(API_GENERATE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: _generateController.signal
    });
    const data = await res.json();
    if (data.errors && data.errors.length) data.errors.forEach(e => addLog(e, true));
    if (!res.ok || !data.success) { addLog('Generation failed.', true); showToast('Generation failed.'); setStep(3); }
    else { if (data.logs && data.logs.length) data.logs.forEach(msg => addLog(msg)); renderDownloads(data.files); setStep(4); }
  } catch (e) {
    if (e.name !== 'AbortError') {
      addLog('Network error: ' + e.message, true); showToast('Network error: ' + e.message);
    }
  }
  finally { btnGenerate.disabled = false; btnGenerate.innerHTML = 'GENERATE CAD FILES'; updateGenerateBtn(); }
});

/**
 * Renders the download buttons for the generated CAD files.
 * All DOM elements are constructed via createElement + textContent.
 * Download is triggered via addEventListener — no onclick attributes.
 * @param {Array<Object>} files - List of generated file objects with name and size_bytes.
 * @returns {void}
 */
function renderDownloads(files) {
  if (!files || !files.length) return;
  downloadSection.style.display = 'block';

  while (downloadGrid.firstChild) {
    downloadGrid.removeChild(downloadGrid.firstChild);
  }

  files.forEach((f, i) => {
    const isScr = f.name.endsWith('.scr');
    const icon = isScr ? '📜' : '📐';
    const kb = (f.size_bytes / 1024).toFixed(1);

    const card = document.createElement('div');
    card.className = 'dl-card pulse-success';
    card.style.animationDelay = `${i * 0.15}s`;

    const info = document.createElement('div');
    info.className = 'dl-info';

    const iconSpan = document.createElement('span');
    iconSpan.className = 'dl-icon';
    iconSpan.textContent = icon;

    const textDiv = document.createElement('div');

    const nameDiv = document.createElement('div');
    nameDiv.className = 'dl-name';
    nameDiv.textContent = f.name;

    const sizeDiv = document.createElement('div');
    sizeDiv.className = 'dl-size';
    sizeDiv.textContent = `${kb} KB`;

    textDiv.appendChild(nameDiv);
    textDiv.appendChild(sizeDiv);

    info.appendChild(iconSpan);
    info.appendChild(textDiv);

    const btn = document.createElement('button');
    btn.className = 'btn-download';
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 3v13M7 12l5 5 5-5"/><path d="M3 21h18"/></svg> Download';

    btn.addEventListener('click', () => {
      window.location.href = API_DOWNLOAD + encodeURIComponent(f.name);
    });

    card.appendChild(info);
    card.appendChild(btn);

    downloadGrid.appendChild(card);
  });
}
