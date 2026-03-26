/* ============================================================
   main.js – SurveyCAD
   ============================================================ */

const MAX_PREVIEW = 10;
const API = { upload: '/api/upload', scr: '/api/generate-scr', dxf: '/api/generate-dxf', dwg: '/api/generate-dwg' };
const ALLOWED_EXT = ['csv', 'txt'];

let _uploadCtrl = null;
const _genCtrl = { scr: null, dxf: null, dwg: null };

const state = {
  rows: [], uniqueCodes: [], hasElevation: false, hasDesc: false,
  showAll: false, polylineCodes: new Set(), uploadedName: 'survey_output',
};

// ── DOM refs ────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const uploadZone   = $('upload-zone'),    fileInput   = $('file-input'),
      uploadResult = $('upload-result'),  previewSec  = $('preview-section'),
      tableBody    = $('table-body'),     pointCount  = $('point-count'),
      codesWrap    = $('codes-wrap'),     btnShowAll  = $('btn-show-all'),
      sliderH      = $('slider-height'),  heightIn    = $('height-input'),
      selUnits     = $('select-units'),   polyList    = $('polyline-list'),
      instrToggle  = $('instructions-toggle'), instrBody = $('instructions-body'),
      btnScr       = $('btn-generate-scr'),   btnDxf   = $('btn-generate-dxf'),
      btnDwg       = $('btn-generate-dwg'),   logBox   = $('log-box');
const steps = document.querySelectorAll('.step');

// ── Background Canvas ───────────────────────────────────────────
(() => {
  const c = $('bg-canvas'), ctx = c.getContext('2d');
  let W, H, dots = [], lines = [], gridOff = 0, frame = 0;
  const rand = (a, b) => a + Math.random() * (b - a);

  function resize() { W = c.width = innerWidth; H = c.height = innerHeight; }

  function initDots() {
    dots = [];
    const n = Math.min(35, Math.floor(W * H / 25000));
    for (let i = 0; i < n; i++)
      dots.push({ x: rand(0, W), y: rand(0, H), vx: rand(-.15, .15), vy: rand(-.1, .1), r: rand(1.5, 3.5), ph: rand(0, Math.PI * 2) });
    lines = [];
    for (let i = 0; i < dots.length; i++)
      for (let j = i + 1; j < dots.length; j++)
        if (Math.hypot(dots[i].x - dots[j].x, dots[i].y - dots[j].y) < W * .16) lines.push([i, j]);
  }

  function draw() {
    frame++;
    ctx.clearRect(0, 0, W, H);
    const sp = 80;
    gridOff = (gridOff + .25) % sp;

    ctx.strokeStyle = 'rgba(255,107,0,0.04)'; ctx.lineWidth = 1;
    for (let y = -sp + gridOff; y < H + sp; y += sp) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    for (let x = 0; x < W + sp; x += sp) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }

    const cx = W / 2 + W * .15 * Math.sin(frame * .005);
    const cy = H / 3 + H * .1 * Math.cos(frame * .007);
    const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, W * .55);
    grd.addColorStop(0, 'rgba(255,107,0,0.035)'); grd.addColorStop(1, 'transparent');
    ctx.fillStyle = grd; ctx.fillRect(0, 0, W, H);

    for (const [a, b] of lines) {
      ctx.strokeStyle = `rgba(255,107,0,${(.06 + .04 * Math.sin(frame * .01 + a))})`;
      ctx.lineWidth = .7; ctx.beginPath(); ctx.moveTo(dots[a].x, dots[a].y); ctx.lineTo(dots[b].x, dots[b].y); ctx.stroke();
    }
    for (const d of dots) {
      const p = 1 + .3 * Math.sin(frame * .02 + d.ph);
      ctx.beginPath(); ctx.arc(d.x, d.y, d.r * p, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,107,0,0.5)'; ctx.fill();
      ctx.beginPath(); ctx.arc(d.x, d.y, d.r * 4 * p, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,107,0,0.02)'; ctx.fill();
      d.x += d.vx; d.y += d.vy;
      if (d.x < -30) d.x = W + 30; if (d.x > W + 30) d.x = -30;
      if (d.y < -30) d.y = H + 30; if (d.y > H + 30) d.y = -30;
    }
    requestAnimationFrame(draw);
  }

  addEventListener('resize', () => { resize(); initDots(); });
  resize(); initDots(); draw();
})();

// ── Height slider / input sync ──────────────────────────────────
function syncHeight(src) {
  let val;
  if (src === 'slider') { val = parseFloat(sliderH.value); heightIn.value = val; }
  else { val = parseFloat(heightIn.value); if (isNaN(val) || val < .1) val = .1; sliderH.value = Math.min(val, parseFloat(sliderH.max)); }
  const mn = parseFloat(sliderH.min), mx = parseFloat(sliderH.max);
  sliderH.style.setProperty('--pct', ((Math.min(Math.max(val, mn), mx) - mn) / (mx - mn) * 100).toFixed(1) + '%');
}
sliderH.addEventListener('input', () => syncHeight('slider'));
heightIn.addEventListener('input', () => syncHeight('input'));
heightIn.addEventListener('change', () => syncHeight('input'));
syncHeight('slider');

// ── Instructions toggle ─────────────────────────────────────────
instrToggle.addEventListener('click', () => {
  const open = instrBody.classList.toggle('open');
  instrToggle.classList.toggle('open', open);
});

// ── Steps navigation ────────────────────────────────────────────
function setStep(n) {
  steps.forEach((s, i) => {
    s.classList.remove('active', 'done');
    if (i + 1 < n) s.classList.add('done');
    if (i + 1 === n) s.classList.add('active');
  });
}
setStep(1);

$('step-1').addEventListener('click', () => scrollTo({ top: 0, behavior: 'smooth' }));
$('step-2').addEventListener('click', () => document.querySelector('section:nth-of-type(2)').scrollIntoView({ behavior: 'smooth' }));
$('step-3').addEventListener('click', () => btnScr.scrollIntoView({ behavior: 'smooth', block: 'center' }));
$('step-4').addEventListener('click', () => document.querySelector('.download-grid').scrollIntoView({ behavior: 'smooth', block: 'center' }));

// ── UI Utilities ────────────────────────────────────────────────
function showToast(msg, type = 'error') {
  const t = document.createElement('div');
  t.className = `toast ${type}`; t.textContent = msg;
  $('toast-container').appendChild(t);
  setTimeout(() => t.remove(), 4100);
}

function addLog(msg, err = false) {
  const el = document.createElement('span');
  el.className = 'log-line' + (err ? ' err' : '');
  el.textContent = '> ' + msg;
  logBox.appendChild(el); logBox.scrollTop = logBox.scrollHeight;
}

function updateBtns() {
  const ok = state.rows.length > 0;
  btnScr.disabled = btnDxf.disabled = btnDwg.disabled = !ok;
}
updateBtns();

// ── Upload ──────────────────────────────────────────────────────
uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); } });
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => { e.preventDefault(); uploadZone.classList.remove('drag-over'); if (e.dataTransfer.files[0]) doUpload(e.dataTransfer.files[0]); });
fileInput.addEventListener('change', () => { if (fileInput.files[0]) doUpload(fileInput.files[0]); });

async function doUpload(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!ALLOWED_EXT.includes(ext)) { showResult(false, 'Only .csv and .txt files are accepted.'); return; }
  showResult(null, 'Uploading…');

  if (_uploadCtrl) _uploadCtrl.abort();
  _uploadCtrl = new AbortController();

  const fd = new FormData(); fd.append('file', file);
  try {
    const res = await fetch(API.upload, { method: 'POST', body: fd, signal: _uploadCtrl.signal });
    const data = await res.json();
    if (!res.ok || !data.success) { showResult(false, (data.errors || ['Upload failed.']).join(' ')); return; }
    Object.assign(state, {
      rows: data.rows, uniqueCodes: data.unique_codes || [],
      hasElevation: data.has_elevation, hasDesc: data.has_description, showAll: false,
      uploadedName: file.name.replace(/\.[^.]+$/, '') || 'survey_output',
    });
    showResult(true, `${file.name}  —  ${data.row_count} survey points loaded`);
    renderPreview(); renderPolylines(); setStep(2); updateBtns();
  } catch (e) {
    if (e.name !== 'AbortError') { showResult(false, 'Network error: ' + e.message); showToast('Upload failed — ' + e.message); }
  }
}

function showResult(ok, msg) {
  uploadResult.className = 'upload-result';
  uploadResult.textContent = msg;
  if (ok === true)  uploadResult.classList.add('success');
  if (ok === false) uploadResult.classList.add('error');
  if (ok === null)  { uploadResult.style.display = 'flex'; uploadResult.style.color = '#7777AA'; }
}

// ── Preview Table ───────────────────────────────────────────────
function cell(v) {
  const td = document.createElement('td');
  if (v == null || v === '') {
    const s = document.createElement('span'); s.className = 'cell-empty'; s.textContent = '—'; td.appendChild(s);
  } else td.textContent = v;
  return td;
}

function renderPreview() {
  previewSec.style.display = 'block';
  const rows = state.showAll ? state.rows : state.rows.slice(0, MAX_PREVIEW);
  tableBody.replaceChildren();

  rows.forEach(r => {
    const tr = document.createElement('tr');
    tr.appendChild(cell(r.sr_no));
    tr.appendChild(cell(r.northing != null ? r.northing.toFixed(4) : null));
    tr.appendChild(cell(r.easting  != null ? r.easting.toFixed(4)  : null));
    tr.appendChild(cell(r.elevation != null ? r.elevation.toFixed(3) : null));
    tr.appendChild(cell(r.description || null));
    tableBody.appendChild(tr);
  });

  pointCount.textContent = `${state.rows.length} total survey point${state.rows.length !== 1 ? 's' : ''}`;
  codesWrap.replaceChildren();

  if (state.uniqueCodes.length) {
    state.uniqueCodes.forEach(c => { const s = document.createElement('span'); s.className = 'code-badge'; s.textContent = c; codesWrap.appendChild(s); });
  } else {
    const s = document.createElement('span'); s.style.cssText = 'font-size:.78rem;color:var(--muted)'; s.textContent = 'No codes'; codesWrap.appendChild(s);
  }

  btnShowAll.textContent = state.showAll ? 'Show Less' : `Show All ${state.rows.length} Points`;
  btnShowAll.style.display = state.rows.length > MAX_PREVIEW ? 'block' : 'none';
}
btnShowAll.addEventListener('click', () => { state.showAll = !state.showAll; renderPreview(); });

// ── Polyline Toggles ────────────────────────────────────────────
function renderPolylines() {
  state.polylineCodes.clear();
  polyList.replaceChildren();

  if (!state.uniqueCodes.length) {
    const p = document.createElement('p'); p.className = 'polyline-placeholder'; p.textContent = 'No description codes in this file.';
    polyList.appendChild(p); return;
  }

  state.uniqueCodes.forEach((code, i) => {
    const row = document.createElement('div'); row.className = 'polyline-row';
    const name = document.createElement('span'); name.textContent = code; row.appendChild(name);
    const lbl = document.createElement('label'); lbl.className = 'toggle';
    const cb = document.createElement('input'); cb.type = 'checkbox'; cb.id = `pline-${i}`;
    cb.addEventListener('change', () => { cb.checked ? state.polylineCodes.add(code) : state.polylineCodes.delete(code); });
    const sl = document.createElement('span'); sl.className = 'toggle-slider';
    lbl.appendChild(cb); lbl.appendChild(sl); row.appendChild(lbl);
    polyList.appendChild(row);
  });
}

// ── Generate & Download ─────────────────────────────────────────
const BTN = { scr: btnScr, dxf: btnDxf, dwg: btnDwg };

async function downloadFile(type) {
  if (!state.rows.length) return;
  const btn = BTN[type];
  const saved = Array.from(btn.childNodes);
  btn.disabled = true; btn.textContent = '';
  const sp = document.createElement('span'); sp.className = 'spinner';
  btn.appendChild(sp); btn.appendChild(document.createTextNode(' Generating...'));

  logBox.replaceChildren(); setStep(3);
  addLog(`Prepared ${state.rows.length} survey points for ${type.toUpperCase()}.`);

  if (_genCtrl[type]) _genCtrl[type].abort();
  _genCtrl[type] = new AbortController();

  const body = {
    rows: state.rows, text_height: parseFloat(heightIn.value) || parseFloat(sliderH.value) || 1.0,
    offset: true, polyline_codes: [...state.polylineCodes], units: selUnits.value,
  };
  const fname = `${state.uploadedName}.${type}`;

  try {
    const res = await fetch(API[type], {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: _genCtrl[type].signal,
    });
    if (!res.ok) {
      let d = {}; try { d = await res.json(); } catch {}
      const msg = d.error || d.errors?.[0] || 'Generation failed.';
      addLog(msg, true); showToast(msg);
    } else {
      addLog(`File generated. Downloading ${fname}…`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = fname;
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
      addLog(`Done! Downloaded ${fname}`);
      steps.forEach(s => { s.classList.remove('active'); s.classList.add('done'); });
    }
  } catch (e) {
    if (e.name !== 'AbortError') { addLog('Network error: ' + e.message, true); showToast('Network error: ' + e.message); }
  } finally {
    btn.textContent = ''; saved.forEach(n => btn.appendChild(n)); updateBtns();
  }
}

btnScr.addEventListener('click', () => downloadFile('scr'));
btnDxf.addEventListener('click', () => downloadFile('dxf'));
btnDwg.addEventListener('click', () => downloadFile('dwg'));
