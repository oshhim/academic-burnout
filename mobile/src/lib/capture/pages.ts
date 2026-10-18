// HTML pages that run inside a WebView: the phone's browser engine provides camera
// and microphone access plus WebAssembly for MediaPipe, without a custom native build.
// Only numbers (face) or a WAV file (voice) are posted back; video never leaves the page.

import { FACE_MATH_JS } from './face-math';

const MEDIAPIPE = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35';
const FACE_MODEL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';

export type FaceProtocol = 'neutral_only' | 'neutral_task_recovery';

export const TASK_PROMPT = 'Silently count backwards from 300 in steps of 7.';

const BASE_STYLE = `
  * { box-sizing: border-box; -webkit-user-select: none; user-select: none; }
  html, body { margin: 0; height: 100%; background: #0B0E14; color: #E1E2EB; font-family: -apple-system, system-ui, sans-serif; }
  .wrap { position: relative; height: 100%; overflow: hidden; border-radius: 16px; background: #12161F; }
  .overlay { position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: space-between; padding: 16px; pointer-events: none; }
  .phase { font: 600 13px/18px ui-monospace, monospace; letter-spacing: .08em; color: #4CD7F6; text-transform: uppercase; }
  .prompt { font: 600 20px/27px -apple-system, system-ui; margin-top: 4px; text-shadow: 0 1px 6px #000; }
  .status { font: 13px/18px -apple-system, system-ui; color: #C7C4D7; text-shadow: 0 1px 4px #000; }
  .ok { color: #4CD7F6; } .bad { color: #FFB4AB; }
  button { pointer-events: auto; width: 100%; min-height: 48px; border: 0; border-radius: 12px; color: #fff; font: 600 16px -apple-system, system-ui;
           background: linear-gradient(135deg, #6366F1, #A855F7); margin-top: 10px; }
  button:disabled { opacity: .45; }
  .ghost { background: transparent; border: 1px solid rgba(255,255,255,.15); }
`;

const BRIDGE = `const post = (m) => window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify(m));
window.onerror = (msg) => post({ type: 'error', message: String(msg) });`;

export function facePage(protocol: FaceProtocol) {
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
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<style>${BASE_STYLE}
  /* Stacked layout: instruction, camera panel, progress, controls. Nothing overlaps the controls. */
  .page { height: 100%; display: flex; flex-direction: column; gap: 12px; padding: 4px 0 0; }
  .head { display: flex; flex-direction: column; gap: 6px; min-height: 76px; }
  .chips { display: flex; justify-content: space-between; align-items: center; }
  .chip { font: 600 12px/16px ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; color: #4CD7F6;
          background: rgba(76,215,246,.12); border-radius: 999px; padding: 5px 10px; }
  .count { color: #E1E2EB; background: #272A31; min-width: 48px; text-align: center; }
  .prompt { font: 600 18px/25px -apple-system, system-ui; color: #E1E2EB; }
  .stage { position: relative; flex: 1; min-height: 220px; border-radius: 16px; overflow: hidden; background: #12161F; border: 1px solid rgba(255,255,255,.08); }
  video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1); }
  /* Corner-bracket face guide, as in the check-in design. */
  .guide { position: absolute; left: 50%; top: 50%; width: 56%; aspect-ratio: 3 / 4; max-height: 70%; transform: translate(-50%, -56%); }
  .guide i { position: absolute; width: 28px; height: 28px; border: 3px solid #C0C1FF; }
  .guide i:nth-child(1) { left: 0; top: 0; border-right: 0; border-bottom: 0; border-top-left-radius: 14px; }
  .guide i:nth-child(2) { right: 0; top: 0; border-left: 0; border-bottom: 0; border-top-right-radius: 14px; }
  .guide i:nth-child(3) { left: 0; bottom: 0; border-right: 0; border-top: 0; border-bottom-left-radius: 14px; }
  .guide i:nth-child(4) { right: 0; bottom: 0; border-left: 0; border-top: 0; border-bottom-right-radius: 14px; }
  .pill { position: absolute; left: 50%; bottom: 12px; transform: translateX(-50%); white-space: nowrap;
          font: 600 13px/18px -apple-system, system-ui; padding: 6px 12px; border-radius: 999px;
          background: rgba(11,14,20,.72); -webkit-backdrop-filter: blur(12px); backdrop-filter: blur(12px); }
  .pill:empty { display: none; }
  .bar { height: 6px; border-radius: 3px; background: #272A31; overflow: hidden; }
  .bar > div { height: 100%; width: 0; background: linear-gradient(90deg, #4CD7F6, #A855F7); transition: width .2s linear; }
  .controls { display: flex; flex-direction: column; gap: 8px; padding-bottom: 4px; }
  .controls button { margin-top: 0; }
  .secondary { background: #272A31; }
</style></head><body><div class="page">
  <div class="head">
    <div class="chips"><span class="chip" id="phase">Preparing</span><span class="chip count" id="count"></span></div>
    <div class="prompt" id="prompt">Loading the face model…</div>
  </div>
  <div class="stage">
    <video id="video" playsinline muted autoplay></video>
    <div class="guide"><i></i><i></i><i></i><i></i></div>
    <div class="pill" id="status"></div>
  </div>
  <div class="bar"><div id="progress"></div></div>
  <div class="controls" id="controls">
    <button id="start" disabled>Start recording</button>
    <button id="cancel" class="secondary">Cancel</button>
  </div>
</div>
<script type="module">
${BRIDGE}
const CONFIG = ${JSON.stringify(config)};
${FACE_MATH_JS}
const $ = (id) => document.getElementById(id);
const video = $('video');
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d', { willReadFrequently: true });
let landmarker, stream, recording = false, cancelled = false;

function stopCamera() { if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null; }
$('cancel').onclick = () => { cancelled = true; recording = false; stopCamera(); post({ type: 'cancel' }); };

function measure(now) {
  const w = video.videoWidth, h = video.videoHeight;
  const scale = Math.min(1, 640 / w);
  canvas.width = Math.round(w * scale); canvas.height = Math.round(h * scale);
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const stats = grayStats(ctx.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height);
  const result = landmarker.detectForVideo(video, now);
  return frameMeasurement(result, w, h, stats);
}

function faceText(m) {
  if (m.face_count === 0) return '<span class="bad">No face detected</span>';
  if (m.face_count > 1) return '<span class="bad">More than one face</span>';
  if (!m.features) return '<span class="bad">Face unclear: improve lighting</span>';
  if (Math.abs(m.pose[1]) > 35 || Math.abs(m.pose[0]) > 30) return '<span class="bad">Face the camera</span>';
  if (m.brightness < 0.15) return '<span class="bad">Too dark</span>';
  return '<span class="ok">Face detected</span>';
}

let lastTs = -1;
function timestamp() { const t = Math.max(lastTs + 1, Math.round(performance.now())); lastTs = t; return t; }

function preview() {
  if (recording || cancelled || !stream) return;
  if (video.readyState >= 2) $('status').innerHTML = faceText(measure(timestamp()));
  setTimeout(preview, 300);
}

function record() {
  recording = true;
  $('start').style.display = 'none';
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
      $('status').innerHTML = faceText(m);
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function finish(recordedAt, framesByWindow, frames) {
  recording = false;
  stopCamera();
  $('phase').textContent = 'Done'; $('count').textContent = ''; $('status').textContent = '';
  $('prompt').textContent = 'Sending numerical features…'; $('progress').style.width = '100%';
  $('controls').style.display = 'none';
  post({ type: 'face', recordedAt, frames, windows: buildWindows(framesByWindow, CONFIG.duration, CONFIG.protocol) });
}

$('start').onclick = () => record();

(async () => {
  try {
    const { FilesetResolver, FaceLandmarker } = await import('${MEDIAPIPE}/vision_bundle.mjs');
    const files = await FilesetResolver.forVisionTasks('${MEDIAPIPE}/wasm');
    const options = (delegate) => ({ baseOptions: { modelAssetPath: '${FACE_MODEL}', delegate }, runningMode: 'VIDEO', numFaces: 2,
      outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true,
      minFaceDetectionConfidence: 0.6, minFacePresenceConfidence: 0.6, minTrackingConfidence: 0.6 });
    try { landmarker = await FaceLandmarker.createFromOptions(files, options('GPU')); }
    catch (e) { landmarker = await FaceLandmarker.createFromOptions(files, options('CPU')); }
    $('prompt').textContent = 'Allow camera access…';
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
    video.srcObject = stream;
    await video.play();
    $('phase').textContent = CONFIG.protocol === 'neutral_only' ? 'Reference' : 'Check-in';
    $('count').textContent = CONFIG.duration + 's';
    $('prompt').textContent = 'Fit your face inside the corners, then start.';
    $('start').disabled = false;
    post({ type: 'ready' });
    preview();
  } catch (e) {
    post({ type: 'error', message: (e && e.message) || String(e) });
    $('prompt').textContent = 'Camera or model failed: ' + ((e && e.message) || e);
  }
})();
</script></body></html>`;
}

export function voicePage() {
  return `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<style>${BASE_STYLE}
  .wrap { padding: 16px; display: flex; flex-direction: column; gap: 10px; }
  .time { font: 600 34px/40px ui-monospace, monospace; }
  .meter { height: 8px; border-radius: 4px; background: rgba(255,255,255,.12); overflow: hidden; }
  .meter > div { height: 100%; width: 0; background: linear-gradient(90deg, #4CD7F6, #A855F7); transition: width .08s; }
</style></head><body><div class="wrap">
<div class="phase" id="phase">Microphone</div>
<div class="time" id="time">0.0 s</div>
<div class="meter"><div id="level"></div></div>
<div class="status" id="status">Speak for 3–30 seconds in a quiet room. Recording stops automatically at 30 s.</div>
<button id="toggle">Start recording</button>
</div>
<script>
${BRIDGE}
const $ = (id) => document.getElementById(id);
const MAX_SEC = 30;
let stream, audioCtx, node, chunks = [], recording = false, startedAt, recordedAt, timer;

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

async function start() {
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
      $('level').style.width = Math.min(100, peak * 140) + '%';
    };
    source.connect(node); node.connect(audioCtx.destination);
    recording = true; startedAt = performance.now(); recordedAt = new Date().toISOString();
    $('toggle').textContent = 'Stop and analyze'; $('phase').textContent = 'Recording';
    timer = setInterval(() => {
      const t = (performance.now() - startedAt) / 1000;
      $('time').textContent = t.toFixed(1) + ' s';
      if (t >= MAX_SEC) stop();
    }, 100);
  } catch (e) {
    post({ type: 'error', message: 'Microphone unavailable: ' + ((e && e.message) || e) });
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
  $('toggle').textContent = 'Start recording'; $('phase').textContent = 'Microphone'; $('level').style.width = '0';
  if (seconds < 1) { post({ type: 'error', message: 'Recording too short: speak for at least 1 second.' }); return; }
  post({ type: 'audio', base64: toBase64(encodeWav(samples, rate)), sampleRate: rate, durationSec: seconds, recordedAt });
}

$('toggle').onclick = () => (recording ? stop() : start());
post({ type: 'ready' });
</script></body></html>`;
}
