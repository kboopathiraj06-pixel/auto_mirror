/**
 * AutoMirror – Main Application Logic  (MediaPipe AI edition)
 */

const POLL_INTERVAL = 150;   // ms
const MANUAL_STEP = 2.5;   // degrees per button press
const MAX_H = 25, MAX_V = 20;

let autoMode = true;
let currentState = { left: { h: 0, v: 0 }, right: { h: 0, v: 0 }, servo: { left_h: 90, left_v: 90, right_h: 90, right_v: 90 } };

// ─────────────────────────────────────────────
//  Clock
// ─────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const el = document.getElementById('clock');
  const de = document.getElementById('date-display');
  if (el) el.textContent = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  if (de) de.textContent = now.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
}
updateClock();
setInterval(updateClock, 1000);

// ─────────────────────────────────────────────
//  Toast
// ─────────────────────────────────────────────
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

// ─────────────────────────────────────────────
//  Mirror animation (3-D perspective rotation)
// ─────────────────────────────────────────────
function animateMirror(side, h, v) {
  const el = document.getElementById(`${side}-mirror-frame`);
  if (!el) return;
  h = Math.max(-MAX_H, Math.min(MAX_H, h));
  v = Math.max(-MAX_V, Math.min(MAX_V, v));
  el.style.transform = `perspective(300px) rotateY(${h}deg) rotateX(${-v}deg)`;
  const mag = (Math.abs(h) + Math.abs(v)) / (MAX_H + MAX_V);
  const g = Math.round(120 + mag * 135);
  el.style.borderColor = `rgba(0,${g},255,0.8)`;
  el.style.boxShadow = `0 0 ${12 + mag * 20}px rgba(0,${g},255,0.3), inset 0 0 30px rgba(0,0,0,0.6)`;
}

// ─────────────────────────────────────────────
//  Gauge bars
// ─────────────────────────────────────────────
function updateGauge(id, value, maxVal) {
  const el = document.getElementById(id);
  if (!el) return;
  const pct = (value / maxVal) * 50;
  if (value >= 0) {
    el.style.left = '50%'; el.style.width = pct + '%'; el.style.transform = 'none';
  } else {
    el.style.left = (50 + pct) + '%'; el.style.width = (-pct) + '%'; el.style.transform = 'none';
  }
}

// ─────────────────────────────────────────────
//  Readouts
// ─────────────────────────────────────────────
function setReadout(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = (val >= 0 ? '+' : '') + val.toFixed(1);
  el.style.color = Math.abs(val) > 15 ? 'var(--accent-amber)' : 'var(--accent)';
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ─────────────────────────────────────────────
//  Status bar + AI HUD update
// ─────────────────────────────────────────────
function updateStatusBar(s) {
  const fd = document.getElementById('face-dot');
  const fl = document.getElementById('face-label');
  if (fd) fd.className = 'status-dot ' + (s.face_detected ? 'active' : 'error');
  if (fl) fl.textContent = s.face_detected ? 'Face Detected' : 'No Face';

  const cd = document.getElementById('cal-dot');
  const cl = document.getElementById('cal-label');
  if (cd) cd.className = 'status-dot ' + (s.calibrated ? 'active' : 'warning');
  if (cl) cl.textContent = s.calibrated ? 'Calibrated' : 'Uncalibrated';

  // Eye position chips
  setText('eye-x-chip', `EX: ${(s.eye_x * 100).toFixed(0)}%`);
  setText('eye-y-chip', `EY: ${(s.eye_y * 100).toFixed(0)}%`);

  // Head pose HUD
  setText('hud-yaw', `Yaw ${s.head_yaw >= 0 ? '+' : ''}${s.head_yaw.toFixed(1)}°`);
  setText('hud-pitch', `Pitch ${s.head_pitch >= 0 ? '+' : ''}${s.head_pitch.toFixed(1)}°`);
  setText('hud-lm', `LM: ${s.landmarks_count}`);

  // AI angle chips (left panel)
  setText('ai-yaw', `${s.head_yaw >= 0 ? '+' : ''}${s.head_yaw.toFixed(1)}°`);
  setText('ai-pitch', `${s.head_pitch >= 0 ? '+' : ''}${s.head_pitch.toFixed(1)}°`);
  setText('ai-roll', `${s.head_roll >= 0 ? '+' : ''}${s.head_roll.toFixed(1)}°`);

  // Landmarks count (right panel)
  setText('ai-lm-count', s.landmarks_count || '--');
  setText('ai-mode-chip', autoMode ? 'AUTO' : 'MANUAL');

  // Servo badges
  if (s.servo) {
    setText('sv-left-h', s.servo.left_h + '°');
    setText('sv-left-v', s.servo.left_v + '°');
    setText('sv-right-h', s.servo.right_h + '°');
    setText('sv-right-v', s.servo.right_v + '°');
  }
}

// ─────────────────────────────────────────────
//  Stats bar
// ─────────────────────────────────────────────
function updateStats(latMs) {
  const fps = Math.min(Math.round(1000 / latMs), 60);
  setText('stat-fps', fps);
  setText('stat-lat', Math.round(latMs));
  setText('stat-lm', currentState.landmarks_count || '--');
}

// ─────────────────────────────────────────────
//  Main poll
// ─────────────────────────────────────────────
async function pollMirrorState() {
  const t0 = performance.now();
  try {
    const res = await fetch('/api/mirror_state');
    const state = await res.json();
    const latMs = performance.now() - t0;
    currentState = state;

    if (autoMode) {
      animateMirror('left', state.left.h, state.left.v);
      animateMirror('right', state.right.h, state.right.v);
      setReadout('left-h', state.left.h);
      setReadout('left-v', state.left.v);
      setReadout('right-h', state.right.h);
      setReadout('right-v', state.right.v);
      updateGauge('left-h-gauge', state.left.h, MAX_H);
      updateGauge('left-v-gauge', state.left.v, MAX_V);
      updateGauge('right-h-gauge', state.right.h, MAX_H);
      updateGauge('right-v-gauge', state.right.v, MAX_V);
    }

    updateStatusBar(state);
    updateStats(latMs);
  } catch {
    setText('stat-det', 'ERR');
  }
}

// ─────────────────────────────────────────────
//  Auto/manual toggle
// ─────────────────────────────────────────────
function toggleAuto() {
  autoMode = !autoMode;
  const btn = document.getElementById('btn-auto');
  if (btn) { btn.textContent = autoMode ? '🤖 Auto: ON' : '👋 Manual'; btn.className = autoMode ? 'btn btn-secondary' : 'btn btn-primary'; }
  setText('ai-mode-chip', autoMode ? 'AUTO' : 'MANUAL');
  toast(autoMode ? 'AI auto-adjustment enabled' : 'Manual mode activated', 'info');
}

function goCal() { window.location.href = '/calibration'; }

// ─────────────────────────────────────────────
//  Reset helpers
// ─────────────────────────────────────────────
async function resetAll() {
  await fetch('/api/reset_mirrors', { method: 'POST' });
  toast('All mirrors centred & calibration cleared', 'info');
}

async function resetSingle(side) {
  const cur = currentState[side] || { h: 0, v: 0 };
  if (cur.h !== 0) await manualAdjust(side, 'h', -cur.h);
  if (cur.v !== 0) await manualAdjust(side, 'v', -cur.v);
}

async function emergencyCenter() {
  await fetch('/api/reset_mirrors', { method: 'POST' });
  toast('⚠ Emergency centre activated', 'error');
}

// ─────────────────────────────────────────────
//  Manual adjustment
// ─────────────────────────────────────────────
async function manualAdjust(side, axis, delta) {
  const body = JSON.stringify({ side, axis, delta });
  const res = await fetch('/api/manual_adjust', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
  const data = await res.json();
  if (data.mirror) {
    const h = data.mirror.h, v = data.mirror.v;
    animateMirror(side, h, v);
    setReadout(`${side}-h`, h);
    setReadout(`${side}-v`, v);
    updateGauge(`${side}-h-gauge`, h, MAX_H);
    updateGauge(`${side}-v-gauge`, v, MAX_V);
    if (!currentState[side]) currentState[side] = {};
    currentState[side].h = h; currentState[side].v = v;
  }
}

// ─────────────────────────────────────────────
//  Button bindings with hold-to-repeat
// ─────────────────────────────────────────────
function bindManualButtons() {
  const map = [
    ['lbtn-up', 'left', 'v', +MANUAL_STEP],
    ['lbtn-down', 'left', 'v', -MANUAL_STEP],
    ['lbtn-left', 'left', 'h', -MANUAL_STEP],
    ['lbtn-right', 'left', 'h', +MANUAL_STEP],
    ['rbtn-up', 'right', 'v', +MANUAL_STEP],
    ['rbtn-down', 'right', 'v', -MANUAL_STEP],
    ['rbtn-left', 'right', 'h', -MANUAL_STEP],
    ['rbtn-right', 'right', 'h', +MANUAL_STEP],
  ];
  map.forEach(([id, side, axis, delta]) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.addEventListener('click', () => {
      autoMode = false;
      const ab = document.getElementById('btn-auto');
      if (ab) { ab.textContent = '👋 Manual'; ab.className = 'btn btn-primary'; }
      setText('ai-mode-chip', 'MANUAL');
      manualAdjust(side, axis, delta);
    });
    let iv = null;
    btn.addEventListener('mousedown', () => { iv = setInterval(() => manualAdjust(side, axis, delta), 120); });
    btn.addEventListener('mouseup', () => clearInterval(iv));
    btn.addEventListener('mouseleave', () => clearInterval(iv));
  });
}

// ─────────────────────────────────────────────
//  Driver profiles
// ─────────────────────────────────────────────
async function refreshProfiles() {
  const res = await fetch('/api/profiles');
  const data = await res.json();
  const sel = document.getElementById('profile-select');
  if (!sel) return;
  const cur = sel.value;
  sel.innerHTML = '<option value="">— Select Profile —</option>';
  Object.keys(data).forEach(n => {
    const o = document.createElement('option');
    o.value = n; o.textContent = n;
    sel.appendChild(o);
  });
  if (cur && data[cur]) sel.value = cur;
}

async function saveProfile() {
  const name = document.getElementById('profile-name')?.value?.trim();
  if (!name) { toast('Enter a profile name', 'error'); return; }
  const res = await fetch('/api/profiles/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
  const d = await res.json();
  if (d.status === 'saved') { toast(`✅ "${name}" saved`, 'success'); document.getElementById('profile-name').value = ''; refreshProfiles(); }
}

async function loadProfile() {
  const name = document.getElementById('profile-select')?.value;
  if (!name) { toast('Select a profile first', 'error'); return; }
  const res = await fetch('/api/profiles/load', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
  const d = await res.json();
  if (d.status === 'loaded') {
    toast(`✅ Profile "${name}" loaded`, 'success');
    const m = d.mirror;
    animateMirror('left', m.left.h, m.left.v);
    animateMirror('right', m.right.h, m.right.v);
    setReadout('left-h', m.left.h); setReadout('left-v', m.left.v);
    setReadout('right-h', m.right.h); setReadout('right-v', m.right.v);
  } else { toast('Profile not found', 'error'); }
}

async function deleteProfile() {
  const name = document.getElementById('profile-select')?.value;
  if (!name) { toast('Select a profile to delete', 'error'); return; }
  if (!confirm(`Delete profile "${name}"?`)) return;
  await fetch('/api/profiles/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
  toast(`Profile "${name}" deleted`, 'info');
  refreshProfiles();
}

// ─────────────────────────────────────────────
//  Startup
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  bindManualButtons();
  refreshProfiles();
  setInterval(pollMirrorState, POLL_INTERVAL);
  pollMirrorState();
});
