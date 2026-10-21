// HTML pages that run inside a WebView: the phone's browser engine provides camera
// and microphone access plus WebAssembly for MediaPipe, without a custom native build.
// Only numbers (face) or a WAV file (voice) are posted back; video never leaves the page.

import { FACE_MATH_JS } from './face-math';

const MEDIAPIPE = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35';
const FACE_MODEL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';

export type FaceProtocol = 'neutral_only' | 'neutral_task_recovery';

export const TASK_PROMPT = 'Silently count backwards from 300 in steps of 7.';

const BRIDGE = `const post = (m) => window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify(m));
window.onerror = (msg) => post({ type: 'error', message: String(msg) });`;

/**
 * Full-screen face capture: the camera fills the screen behind a dashed face oval,
 * with a glass close button, phase chips, a status pill and a gradient pill button.
 * `insets` are the device safe areas (status bar, home indicator) in CSS pixels.
 */
export function facePage(protocol: FaceProtocol, insets: { top: number; bottom: number } = { top: 0, bottom: 0 }) {
  const config = {
    protocol,
    duration: protocol === 'neutral_only' ? 15 : 45,
    phases:
      protocol === 'neutral_only'
        ? [{ until: 15, name: 'Reference', prompt: 'Relax and look at the screen with your normal, neutral face.' }]
        : [
            { until: 15, name: 'Neutral', prompt: 'Relax and look at the screen with a neutral face.' },
            { until: 30, name: 'Task', prompt: TASK_PROMPT },
            { until: 45, name: 'Quiet observation', prompt: 'Stop the task. Rest quietly and keep looking at the screen.' },
          ],
  };
  return `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<style>
  * { box-sizing: border-box; -webkit-user-select: none; user-select: none; -webkit-tap-highlight-color: transparent; }
  html, body { margin: 0; height: 100%; overflow: hidden; background: #000; color: #F4F5FA; font-family: -apple-system, system-ui, sans-serif; }
  :root { --ow: min(68vw, 300px); --top: ${Math.round(insets.top)}px; --bottom: ${Math.round(insets.bottom)}px; }
  /* The <video> is only the frame source and stays invisible: iOS WebKit scales a live camera
     video late (it shows zoomed, then fits), so the preview is drawn onto #view instead, with the
     same cover maths as the face dots. #view is revealed once the camera has settled. */
  video, #view, #mesh { position: fixed; inset: 0; width: 100%; height: 100%; pointer-events: none; }
  video { opacity: 0; }
  #view, #mesh { transform: scaleX(-1); }
  #view { opacity: 0; transition: opacity .25s; }
  #view.live { opacity: 1; }
  /* Darken outside the oval and behind the top and bottom controls, for legibility. */
  .shade { position: fixed; inset: 0; pointer-events: none;
    background:
      linear-gradient(rgba(0,0,0,.6), rgba(0,0,0,0) calc(var(--top) + 190px)),
      linear-gradient(0deg, rgba(0,0,0,.75), rgba(0,0,0,0) calc(var(--bottom) + 260px)),
      radial-gradient(ellipse calc(var(--ow) / 2) calc(var(--ow) * 2 / 3) at 50% calc(50% - var(--ow) * .0667), rgba(0,0,0,0) 98%, rgba(11,14,20,.4) 100%); }
  .oval { position: fixed; left: 50%; top: 50%; width: var(--ow); aspect-ratio: 3 / 4; transform: translate(-50%, -55%); pointer-events: none; }
  .oval ellipse { fill: none; stroke: rgba(255,255,255,.9); stroke-width: 2.5; stroke-dasharray: 7 8; vector-effect: non-scaling-stroke; transition: stroke .3s; }
  .oval.ok ellipse { stroke: #4CD7F6; }
  .oval.bad ellipse { stroke: #FFB4AB; }
  .top { position: fixed; left: 0; right: 0; top: 0; padding: calc(var(--top) + 12px) 16px 0; display: flex; flex-direction: column; gap: 14px; }
  .bar1 { display: flex; align-items: center; justify-content: space-between; }
  .close { width: 44px; height: 44px; border-radius: 22px; border: 0; padding: 0; display: grid; place-items: center;
           background: rgba(255,255,255,.18); -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px); }
  .chips { display: flex; gap: 8px; }
  .chip { font: 600 12px/16px ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; padding: 7px 11px; border-radius: 999px;
          color: #4CD7F6; background: rgba(11,14,20,.55); -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px); }
  .chip:empty { display: none; }
  .count { color: #F4F5FA; min-width: 46px; text-align: center; }
  .prompt { font: 600 20px/27px -apple-system, system-ui; text-align: center; margin: 0 auto; max-width: 92%; text-shadow: 0 1px 8px rgba(0,0,0,.6); }
  .bottom { position: fixed; left: 0; right: 0; bottom: 0; padding: 0 16px calc(var(--bottom) + 14px); display: flex; flex-direction: column; align-items: center; gap: 12px; }
  .pill { font: 500 14px/18px -apple-system, system-ui; padding: 8px 14px; border-radius: 999px; white-space: nowrap;
          background: rgba(11,14,20,.6); -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px); }
  .pill.ok { color: #4CD7F6; } .pill.bad { color: #FFB4AB; }
  .pill:empty { display: none; }
  .progress { width: 100%; height: 4px; border-radius: 2px; background: rgba(255,255,255,.18); overflow: hidden; }
  .progress > div { height: 100%; width: 0; background: linear-gradient(90deg, #6366F1, #A855F7); transition: width .2s linear; }
  .cta { position: relative; width: 100%; height: 58px; border: 0; border-radius: 29px; color: #fff; font: 600 17px -apple-system, system-ui;
         display: flex; align-items: center; justify-content: center; gap: 10px;
         background: linear-gradient(90deg, #6366F1, #A855F7); box-shadow: 0 8px 28px rgba(99,102,241,.45); }
  .cta:disabled { opacity: 1; }
  .cta.idle:disabled { opacity: .5; box-shadow: none; }
  .spin { position: absolute; right: 20px; width: 22px; height: 22px; border-radius: 50%; border: 2.5px solid rgba(255,255,255,.35); border-top-color: #fff;
          animation: spin .8s linear infinite; display: none; }
  .cta.busy .spin { display: block; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .note { font: 12px/16px -apple-system, system-ui; color: rgba(244,245,250,.7); }
</style></head><body>
<video id="video" playsinline muted autoplay></video>
<canvas id="view"></canvas>
<canvas id="mesh"></canvas>
<div class="shade"></div>
<svg class="oval" id="oval" viewBox="0 0 300 400"><ellipse cx="150" cy="200" rx="147" ry="197"/></svg>
<div class="top">
  <div class="bar1">
    <button class="close" id="cancel" aria-label="Cancel">
      <svg width="16" height="16" viewBox="0 0 16 16"><path d="M2 2l12 12M14 2L2 14" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></svg>
    </button>
    <div class="chips"><span class="chip" id="phase"></span><span class="chip count" id="count"></span></div>
  </div>
  <div class="prompt" id="prompt">Fit your face inside the oval, then start.</div>
</div>
<div class="bottom">
  <div class="pill" id="status">Loading the face model…</div>
  <div class="progress"><div id="progress"></div></div>
  <button class="cta idle" id="start" disabled>
    <svg width="20" height="20" viewBox="0 0 24 24"><path d="M12 2l2.2 6.8L21 11l-6.8 2.2L12 20l-2.2-6.8L3 11l6.8-2.2z" fill="#fff"/></svg>
    <span id="startLabel">Start recording</span><span class="spin"></span>
  </button>
  <div class="note">The camera image stays on this phone. Only numbers are sent.</div>
</div>
<script type="module">
${BRIDGE}
const CONFIG = ${JSON.stringify(config)};
${FACE_MATH_JS}
const $ = (id) => document.getElementById(id);
const video = $('video');
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d', { willReadFrequently: true });
const view = $('view'), viewCtx = view.getContext('2d');
const mesh = $('mesh'), meshCtx = mesh.getContext('2d');
let landmarker, stream, recording = false, cancelled = false;

// Screen size and "object-fit: cover" placement of the camera frame, shared by the preview and the dots.
function cover() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2), W = innerWidth, H = innerHeight;
  const vw = video.videoWidth, vh = video.videoHeight, s = Math.max(W / vw, H / vh);
  return { dpr, W, H, vw, vh, s, ox: (W - vw * s) / 2, oy: (H - vh * s) / 2 };
}

function sizeCanvas(c, g, f) {
  if (c.width !== Math.round(f.W * f.dpr) || c.height !== Math.round(f.H * f.dpr)) { c.width = Math.round(f.W * f.dpr); c.height = Math.round(f.H * f.dpr); }
  g.setTransform(f.dpr, 0, 0, f.dpr, 0, 0);
}

function render() {
  if (!stream) return;
  if (video.readyState >= 2 && video.videoWidth) {
    const f = cover();
    sizeCanvas(view, viewCtx, f);
    viewCtx.drawImage(video, f.ox, f.oy, f.vw * f.s, f.vh * f.s);
  }
  requestAnimationFrame(render);
}

function stopCamera() { if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null; }
$('cancel').onclick = () => { cancelled = true; recording = false; stopCamera(); post({ type: 'cancel' }); };

// Landmark dots over the face, mapped like the video's object-fit: cover (mirrored by CSS too).
function drawMesh(result) {
  const f = cover();
  sizeCanvas(mesh, meshCtx, f);
  meshCtx.clearRect(0, 0, f.W, f.H);
  const points = result && result.faceLandmarks && result.faceLandmarks.length === 1 ? result.faceLandmarks[0] : null;
  if (!points || !view.classList.contains('live')) return;
  meshCtx.fillStyle = 'rgba(255,255,255,.55)';
  for (let i = 0; i < points.length; i += 2) {
    meshCtx.beginPath();
    meshCtx.arc(f.ox + points[i].x * f.vw * f.s, f.oy + points[i].y * f.vh * f.s, 1.1, 0, 6.2832);
    meshCtx.fill();
  }
}

function measure(now) {
  const w = video.videoWidth, h = video.videoHeight;
  const scale = Math.min(1, 640 / w);
  canvas.width = Math.round(w * scale); canvas.height = Math.round(h * scale);
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const stats = grayStats(ctx.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height);
  const result = landmarker.detectForVideo(video, now);
  drawMesh(result);
  return frameMeasurement(result, w, h, stats);
}

function faceState(m) {
  if (m.face_count === 0) return [false, 'No face detected'];
  if (m.face_count > 1) return [false, 'More than one face'];
  if (!m.features) return [false, 'Face unclear: improve lighting'];
  if (Math.abs(m.pose[1]) > 35 || Math.abs(m.pose[0]) > 30) return [false, 'Face the camera'];
  if (m.brightness < 0.15) return [false, 'Too dark'];
  return [true, 'Face detected'];
}

function showState(m) {
  const [ok, text] = faceState(m);
  $('status').textContent = text;
  $('status').className = 'pill ' + (ok ? 'ok' : 'bad');
  $('oval').setAttribute('class', 'oval ' + (ok ? 'ok' : 'bad'));
}

let lastTs = -1;
function timestamp() { const t = Math.max(lastTs + 1, Math.round(performance.now())); lastTs = t; return t; }

function preview() {
  if (recording || cancelled || !stream) return;
  if (video.readyState >= 2) showState(measure(timestamp()));
  setTimeout(preview, 150);
}

function setButton(label, busy) {
  $('startLabel').textContent = label;
  $('start').className = 'cta' + (busy ? ' busy' : '');
  $('start').disabled = busy;
}

function record() {
  recording = true;
  setButton('Recording…', true);
  const recordedAt = new Date().toISOString();
  const t0 = performance.now();
  const framesByWindow = {};
  let lastSample = -1000, frames = 0;
  const tick = () => {
    if (!recording) return;
    const now = performance.now();
    const t = (now - t0) / 1000;
    if (t >= CONFIG.duration) return finish(recordedAt, framesByWindow, frames);
    const phase = CONFIG.phases.find((p) => t < p.until);
    $('phase').textContent = phase.name;
    $('count').textContent = Math.ceil(phase.until - t) + 's';
    $('prompt').textContent = phase.prompt;
    $('progress').style.width = (100 * t / CONFIG.duration) + '%';
    if (now - lastSample >= 100 && video.readyState >= 2) { // ~10 Hz, as in the Python adapter
      lastSample = now;
      const m = measure(timestamp());
      (framesByWindow[Math.floor(t / 2.5)] ??= []).push(m);
      frames++;
      showState(m);
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function finish(recordedAt, framesByWindow, frames) {
  recording = false;
  stopCamera();
  drawMesh(null);
  $('phase').textContent = 'Done'; $('count').textContent = '';
  $('prompt').textContent = 'Recording complete.';
  $('status').textContent = ''; $('progress').style.width = '100%';
  setButton('Sending numbers…', true);
  post({ type: 'face', recordedAt, frames, windows: buildWindows(framesByWindow, CONFIG.duration, CONFIG.protocol) });
}

$('start').onclick = () => record();

// Reveal the preview once the camera has run for at least 1 s (warm-up) and the frame size is
// upright (portrait app) and unchanged for three checks in a row. After 2.5 s it is shown anyway,
// e.g. for cameras that only send landscape.
function showWhenSettled() {
  const t0 = performance.now();
  let last = '', same = 0;
  const check = () => {
    const w = video.videoWidth, h = video.videoHeight, size = w + 'x' + h, elapsed = performance.now() - t0;
    same = w && size === last ? same + 1 : 0;
    last = size;
    if ((elapsed >= 1000 && same >= 2 && h >= w) || elapsed > 2500) return view.classList.add('live');
    setTimeout(check, 100);
  };
  check();
}

(async () => {
  try {
    const { FilesetResolver, FaceLandmarker } = await import('${MEDIAPIPE}/vision_bundle.mjs');
    const files = await FilesetResolver.forVisionTasks('${MEDIAPIPE}/wasm');
    const options = (delegate) => ({ baseOptions: { modelAssetPath: '${FACE_MODEL}', delegate }, runningMode: 'VIDEO', numFaces: 2,
      outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true,
      minFaceDetectionConfidence: 0.6, minFacePresenceConfidence: 0.6, minTrackingConfidence: 0.6 });
    try { landmarker = await FaceLandmarker.createFromOptions(files, options('GPU')); }
    catch (e) { landmarker = await FaceLandmarker.createFromOptions(files, options('CPU')); }
    $('status').textContent = 'Starting the camera…';
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
    video.srcObject = stream;
    await video.play();
    render();
    showWhenSettled();
    $('phase').textContent = CONFIG.protocol === 'neutral_only' ? 'Reference' : 'Check-in';
    $('count').textContent = CONFIG.duration + 's';
    setButton('Start recording', false);
    post({ type: 'ready' });
    preview();
  } catch (e) {
    post({ type: 'error', message: (e && e.message) || String(e) });
    $('status').textContent = 'Camera or model failed: ' + ((e && e.message) || e);
    $('status').className = 'pill bad';
  }
})();
</script></body></html>`;
}

/**
 * Full-screen voice recorder that fills the Voice tab: a glowing orb whose ribbons follow the
 * voice level, a prompt, an "I'm listening" status, a round mic button and a live waveform.
 * After a recording the app sends the result back with window.__result(...): the orb shrinks and
 * the result appears under it; the mic button becomes "Record again".
 * `insets.top` is the status-bar safe area in CSS pixels.
 */
export function voicePage(insets: { top: number } = { top: 0 }) {
  return `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<style>
  * { box-sizing: border-box; -webkit-user-select: none; user-select: none; -webkit-tap-highlight-color: transparent; }
  /* Transparent: the Voice tab draws one aurora background behind its header and this page. */
  html, body { margin: 0; height: 100%; overflow: hidden; color: #F4F5FA; font-family: -apple-system, system-ui, sans-serif; background: transparent; }
  .page { position: fixed; inset: 0; display: flex; flex-direction: column; align-items: center; padding: calc(${Math.round(insets.top)}px + 1vh) 20px 12px; }
  /* Orb and text sit centred in the space above the mic; the orb scales with width and height. */
  .main { flex: 1; width: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 0; padding-bottom: 14px; }
  #orb { width: min(64vw, 40vh, 340px); aspect-ratio: 1; transition: width .45s ease; }
  .done #orb { width: min(34vw, 22vh, 190px); }
  .result { display: none; margin-top: 8px; width: 100%; max-width: 360px; text-align: center; }
  .done .result { display: block; }
  .done .prompt { display: none; }
  .r-label { font: 14px/20px -apple-system, system-ui; color: rgba(244,245,250,.6); }
  .r-style { margin-top: 2px; font: 700 42px/48px -apple-system, system-ui; letter-spacing: -.5px;
             background: linear-gradient(90deg, #4CD7F6, #8083FF, #A855F7); -webkit-background-clip: text; background-clip: text; color: transparent; }
  .r-style.bad { background: none; color: #FFB4AB; font-size: 30px; line-height: 38px; }
  .tiles { display: flex; gap: 8px; margin-top: 16px; }
  .tiles:empty { display: none; }
  .tile { flex: 1; padding: 10px 4px; border-radius: 14px; background: rgba(255,255,255,.07); }
  .tile b { display: block; font: 600 17px/22px -apple-system, system-ui; }
  .tile span { font: 12px/16px -apple-system, system-ui; color: rgba(244,245,250,.6); }
  .r-note { margin-top: 12px; font: 13px/19px -apple-system, system-ui; color: rgba(244,245,250,.6); }
  .r-note a { color: #C0C1FF; font-weight: 600; text-decoration: none; white-space: nowrap; }
  .r-retry { margin-top: 12px; border: 0; padding: 10px 18px; border-radius: 20px; background: rgba(255,255,255,.12); color: #F4F5FA; font: 600 15px -apple-system, system-ui; }
  .prompt { margin-top: 18px; font: 600 21px/28px -apple-system, system-ui; text-align: center; max-width: 340px; }
  .status { display: flex; flex-direction: column; align-items: center; gap: 8px; margin-bottom: 18px; font: 600 17px -apple-system, system-ui; }
  .bars { display: flex; gap: 3px; align-items: center; height: 18px; }
  .bars i { width: 3px; height: 6px; border-radius: 2px; background: #8083FF; }
  .listening .bars i { animation: eq .9s ease-in-out infinite; }
  .bars i:nth-child(2) { animation-delay: -.6s } .bars i:nth-child(3) { animation-delay: -.3s }
  .bars i:nth-child(4) { animation-delay: -.75s } .bars i:nth-child(5) { animation-delay: -.45s }
  @keyframes eq { 0%, 100% { height: 5px } 50% { height: 18px } }
  .dock { position: relative; width: 100%; height: 132px; display: grid; place-items: center; }
  #wave { position: absolute; left: -20px; right: -20px; top: 0; width: calc(100% + 40px); height: 100%; }
  .ring { position: relative; width: 124px; height: 124px; border-radius: 62px; display: grid; place-items: center;
          background: rgba(20,24,36,.9); box-shadow: 0 0 0 1px rgba(255,255,255,.06), 0 10px 40px rgba(0,0,0,.5); }
  .mic { width: 84px; height: 84px; border-radius: 42px; border: 0; padding: 0; display: grid; place-items: center; color: #fff;
         background: linear-gradient(135deg, #6366F1, #A855F7); box-shadow: 0 8px 30px rgba(99,102,241,.55); transition: transform .08s; }
  .mic:disabled { opacity: .5; }
  /* Mid-height screens (most Android phones): the result needs the room, so the restart icon alone
     says "Record again" and the result is a little smaller. */
  @media (max-height: 600px) {
    .done .status { display: none; }
    .done #orb { width: min(28vw, 18vh, 150px); }
    .r-style { font-size: 36px; line-height: 42px; }
  }
  /* Short screens (e.g. iPhone SE): smaller orb, tighter text and dock so the mic button stays visible. */
  @media (max-height: 470px) {
    #orb { width: min(36vw, 30vh, 150px); } .done #orb { width: 64px; }
    .prompt { margin-top: 10px; font-size: 18px; line-height: 24px; }
    .r-style { font-size: 34px; line-height: 40px; } .tiles { margin-top: 10px; } .r-note { margin-top: 8px; }
    .status { margin-bottom: 8px; font-size: 15px; } .dock { height: 104px; }
    .ring { width: 100px; height: 100px; } .mic { width: 70px; height: 70px; }
    .r-label { font-size: 13px; } .tile { padding: 6px 4px; }
  }
  .mic .stop, .mic .again { display: none; } .rec .mic .stop { display: block; } .rec .mic .icon { display: none; }
  .done .mic .icon { display: none; } .done .mic .again { display: block; }
</style></head><body>
<div class="page" id="page">
  <div class="main">
  <canvas id="orb"></canvas>
  <div class="prompt" id="prompt">Speak naturally for 3–30 seconds.</div>
  <div class="result">
    <div class="r-label" id="rLabel"></div>
    <div class="r-style" id="rStyle"></div>
    <div class="tiles" id="rTiles"></div>
    <div class="r-note" id="rNote"></div>
    <button class="r-retry" id="rRetry" style="display: none">Retry upload</button>
  </div>
  </div>
  <div class="status" id="status"><div class="bars"><i></i><i></i><i></i><i></i><i></i></div><span id="statusText">Tap the microphone to start</span></div>
  <div class="dock">
    <canvas id="wave"></canvas>
    <div class="ring"><button class="mic" id="toggle" aria-label="Record">
      <svg class="icon" width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"><rect x="9" y="3" width="6" height="11" rx="3" fill="#fff"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>
      <svg class="stop" width="26" height="26" viewBox="0 0 24 24"><rect x="5" y="5" width="14" height="14" rx="3" fill="#fff"/></svg>
      <svg class="again" width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v4.5h4.5"/></svg>
    </button></div>
  </div>
</div>
<script>
${BRIDGE}
const $ = (id) => document.getElementById(id);
const MAX_SEC = 30;
let stream, audioCtx, node, chunks = [], recording = false, starting = false, startedAt, recordedAt, timer;
let level = 0, peakNow = 0;
const history = [];

function encodeWav(samples, rate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buffer);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); str(8, 'WAVE');
  str(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, 'data'); v.setUint32(40, samples.length * 2, true);
  // Clamp to [-1, 1], scale by 32768 and round: lossless for audio that started as 16-bit.
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, Math.max(-32768, Math.min(32767, Math.round(s * 32768))), true);
  }
  return new Uint8Array(buffer);
}

function toBase64(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

function setStatus(text, listening) {
  $('statusText').textContent = text;
  $('status').className = 'status' + (listening ? ' listening' : '');
}

async function start() {
  // Ignore taps while the microphone is still starting, so two recordings never overlap.
  if (starting) return;
  starting = true;
  $('toggle').disabled = true;
  setStatus('Starting the microphone\u2026', false);
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    await audioCtx.resume();
    const source = audioCtx.createMediaStreamSource(stream);
    node = audioCtx.createScriptProcessor(4096, 1, 1);
    chunks = [];
    node.onaudioprocess = (e) => {
      if (!recording) return;
      const data = new Float32Array(e.inputBuffer.getChannelData(0));
      chunks.push(data);
      let peak = 0; for (let i = 0; i < data.length; i++) peak = Math.max(peak, Math.abs(data[i]));
      peakNow = Math.min(1, peak * 1.6);
    };
    source.connect(node); node.connect(audioCtx.destination);
    recording = true; startedAt = performance.now(); recordedAt = new Date().toISOString();
    $('page').classList.add('rec');
    $('prompt').textContent = 'Keep talking. Tap stop when you’re done.';
    timer = setInterval(() => {
      const t = (performance.now() - startedAt) / 1000;
      setStatus('I\\u2019m listening \\u00b7 ' + t.toFixed(1) + ' s', true);
      if (t >= MAX_SEC) stop();
    }, 100);
    setStatus('I\\u2019m listening \\u00b7 0.0 s', true);
  } catch (e) {
    setStatus('Tap the microphone to start', false);
    post({ type: 'error', message: 'Microphone unavailable: ' + ((e && e.message) || e) });
  } finally {
    starting = false;
    $('toggle').disabled = false;
  }
}

function stop() {
  recording = false; clearInterval(timer);
  if (stream) stream.getTracks().forEach((t) => t.stop());
  const rate = audioCtx.sampleRate;
  if (node) node.disconnect();
  audioCtx.close();
  const length = chunks.reduce((n, c) => n + c.length, 0);
  const samples = new Float32Array(length);
  let offset = 0; for (const c of chunks) { samples.set(c, offset); offset += c.length; }
  const seconds = length / rate;
  $('page').classList.remove('rec'); peakNow = 0;
  if (seconds < 1) {
    setStatus('Tap the microphone to start', false);
    post({ type: 'error', message: 'Recording too short: speak for at least 1 second.' });
    return;
  }
  analysing();
  post({ type: 'audio', base64: toBase64(encodeWav(samples, rate)), sampleRate: rate, durationSec: seconds, recordedAt });
}

function analysing() {
  $('page').classList.remove('done');
  $('toggle').disabled = true;
  $('prompt').textContent = 'Thank you. Analysing…';
  setStatus('Analysing…', false);
}

// Called by the app: { kind: 'ok', style, measures: [[label, value]], note } or
// { kind: 'unusable' | 'error', title, message, canRetry }.
window.__result = (r) => {
  if (recording || starting) return;
  $('page').classList.add('done');
  $('toggle').disabled = false;
  const ok = r.kind === 'ok';
  $('rLabel').textContent = ok ? 'Your voice sounds most like' : r.kind === 'unusable' ? 'Recording not usable' : 'Not analysed';
  $('rStyle').textContent = ok ? r.style : r.title;
  $('rStyle').className = 'r-style' + (ok ? '' : ' bad');
  $('rTiles').replaceChildren(...(ok ? r.measures : []).map(([label, value]) => {
    const tile = document.createElement('div'); tile.className = 'tile';
    const b = document.createElement('b'); b.textContent = value;
    const span = document.createElement('span'); span.textContent = label;
    tile.append(b, span); return tile;
  }));
  $('rNote').textContent = ok ? r.note + ' ' : r.message;
  if (ok) {
    const a = document.createElement('a'); a.href = '#'; a.textContent = 'Details ›';
    a.onclick = (e) => { e.preventDefault(); post({ type: 'details' }); };
    $('rNote').append(a);
  }
  $('rRetry').style.display = r.canRetry ? 'inline-block' : 'none';
  setStatus('Record again', false);
};

$('rRetry').onclick = () => { analysing(); post({ type: 'retry' }); };

// Back to the idle state, ready for another recording.
function reset() {
  if (recording || starting) return;
  $('page').classList.remove('done');
  $('toggle').disabled = false;
  $('prompt').textContent = 'Speak naturally for 3–30 seconds.';
  setStatus('Tap the microphone to start', false);
}

// In the result view the button is "Record again": clear the result and start straight away.
$('toggle').onclick = () => {
  if (recording) return stop();
  if ($('page').classList.contains('done')) { reset(); post({ type: 'reset' }); }
  start();
};

// ---------- Visuals: orb, mic pulse and waveform, driven by the smoothed voice level ----------
const COLORS = ['76,215,246', '128,131,255', '168,85,247'];
function fit(c) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2), r = c.getBoundingClientRect();
  if (c.width !== Math.round(r.width * dpr)) { c.width = Math.round(r.width * dpr); c.height = Math.round(r.height * dpr); }
  const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); return [g, r.width, r.height];
}

function drawOrb(t) {
  const [g, w] = fit($('orb'));
  const c = w / 2, R = w * 0.38;
  g.clearRect(0, 0, w, w);
  // Outer glow, brighter with the voice.
  let grad = g.createRadialGradient(c, c, R * 0.7, c, c, R * 1.3);
  grad.addColorStop(0, 'rgba(99,102,241,' + (0.35 + level * 0.4) + ')'); grad.addColorStop(1, 'rgba(99,102,241,0)');
  g.fillStyle = grad; g.beginPath(); g.arc(c, c, R * 1.3, 0, 6.2832); g.fill();
  // Sphere body.
  grad = g.createRadialGradient(c - R * 0.3, c - R * 0.35, R * 0.1, c, c, R);
  grad.addColorStop(0, '#1B2150'); grad.addColorStop(1, '#05060D');
  g.fillStyle = grad; g.beginPath(); g.arc(c, c, R, 0, 6.2832); g.fill();
  // Flowing light ribbons inside the sphere.
  g.save(); g.beginPath(); g.arc(c, c, R * 0.98, 0, 6.2832); g.clip();
  g.globalCompositeOperation = 'lighter';
  const amp = 0.16 + level * 0.55;
  for (let k = 0; k < 5; k++) {
    const col = COLORS[k % 3], speed = 0.5 + k * 0.17, freq = 1.1 + k * 0.28, tilt = Math.sin(t * 0.2 + k) * 0.35;
    for (let j = 0; j < 7; j++) {
      g.strokeStyle = 'rgba(' + col + ',' + (0.07 + 0.05 * (j === 3)) + ')';
      g.lineWidth = 1.2 + (3 - Math.abs(j - 3)) * 0.8;
      g.beginPath();
      for (let x = -R; x <= R; x += 4) {
        const y = Math.sin((x / R) * Math.PI * freq + t * speed + k * 1.7) * R * amp * Math.cos(k * 0.9 + t * 0.3) + (j - 3) * 3 + x * tilt;
        x === -R ? g.moveTo(c + x, c + y) : g.lineTo(c + x, c + y);
      }
      g.stroke();
    }
  }
  g.restore();
  // Rim light and a soft highlight.
  grad = g.createLinearGradient(c - R, c - R, c + R, c + R);
  grad.addColorStop(0, 'rgba(76,215,246,.9)'); grad.addColorStop(0.5, 'rgba(128,131,255,.6)'); grad.addColorStop(1, 'rgba(168,85,247,.9)');
  g.strokeStyle = grad; g.lineWidth = 2; g.shadowColor = 'rgba(99,102,241,.9)'; g.shadowBlur = 18 + level * 24;
  g.beginPath(); g.arc(c, c, R, 0, 6.2832); g.stroke(); g.shadowBlur = 0;
  grad = g.createRadialGradient(c - R * 0.35, c - R * 0.45, 0, c - R * 0.35, c - R * 0.45, R * 0.5);
  grad.addColorStop(0, 'rgba(255,255,255,.14)'); grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad; g.beginPath(); g.arc(c, c, R, 0, 6.2832); g.fill();
}

function drawWave(t) {
  const [g, w, h] = fit($('wave'));
  g.clearRect(0, 0, w, h);
  const n = Math.floor(w / 7), mid = h / 2;
  for (let i = 0; i < n; i++) {
    // Newest level at both edges moving inward, gentle idle shimmer when quiet.
    const from = Math.min(i, n - 1 - i);
    const v = history[history.length - 1 - from] ?? 0;
    const idle = 0.05 + 0.04 * Math.sin(t * 2 + i * 0.7);
    const bar = 4 + Math.max(v, idle) * h * 0.85;
    const edge = Math.min(1, from / (n * 0.18) + 0.25);
    g.fillStyle = 'rgba(128,131,255,' + (0.18 + 0.32 * edge * (recording ? 1 : 0.5)) + ')';
    g.fillRect(i * 7, mid - bar / 2, 3, bar);
  }
}

let lastPush = 0;
function frame(now) {
  const t = now / 1000;
  level = Math.max(peakNow, level * 0.9);
  peakNow *= 0.85;
  if (now - lastPush > 60) { history.push(recording ? level : 0); if (history.length > 400) history.shift(); lastPush = now; }
  $('toggle').style.transform = 'scale(' + (1 + (recording ? level * 0.12 : 0)) + ')';
  drawOrb(t); drawWave(t);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
post({ type: 'ready' });
</script></body></html>`;
}
