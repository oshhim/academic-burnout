// Plain-JS port of backend/app/facial/extraction.py, injected into the capture
// WebView. Kept as a string so the exact same code can be checked against the
// Python implementation in Node (see scripts/check-face-math.mjs).
// Any change here needs a new FACE_EXTRACTOR_VERSION and a new baseline.

export const FACE_EXTRACTOR_VERSION = 'webview-mp-0.10.35-facelandmarker-f16v1-adapter-v1';

export const FACE_MATH_JS = String.raw`
const LEFT_EYE = [33, 160, 158, 133, 153, 144];
const RIGHT_EYE = [362, 385, 387, 263, 373, 380];
const DEG = 180 / Math.PI;

function eyeRatio(landmarks, idx, width, height) {
  const p = idx.map((i) => [landmarks[i].x * width, landmarks[i].y * height]);
  const d = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const horizontal = d(p[0], p[3]);
  if (horizontal < 1e-6) throw new Error('degenerate eye');
  return (d(p[1], p[5]) + d(p[2], p[4])) / (2 * horizontal);
}

// MediaPipe JS returns the raw packed matrix; MatrixData defaults to column-major.
// Detect the layout from where the translation sits (it is never ~0 on a face).
function matrixAt(m) {
  const data = m.data;
  const columnMajor = Math.abs(data[14]) > Math.abs(data[11]);
  return (r, c) => (columnMajor ? data[c * 4 + r] : data[r * 4 + c]);
}

function headAngles(m) {
  const at = matrixAt(m);
  const R = [0, 1, 2].map((r) => [0, 1, 2].map((c) => at(r, c)));
  for (let c = 0; c < 3; c++) {
    const n = Math.max(Math.hypot(R[0][c], R[1][c], R[2][c]), 1e-9);
    for (let r = 0; r < 3; r++) R[r][c] /= n;
  }
  const pitch = Math.atan2(R[2][1], R[2][2]) * DEG;
  const yaw = Math.atan2(-R[2][0], Math.hypot(R[0][0], R[1][0])) * DEG;
  const roll = Math.atan2(R[1][0], R[0][0]) * DEG;
  return [pitch, yaw, roll];
}

// Grayscale as OpenCV COLOR_RGB2GRAY; sharpness = variance of the 4-neighbour Laplacian.
function grayStats(rgba, width, height) {
  const g = new Float32Array(width * height);
  let sum = 0;
  for (let i = 0, j = 0; i < g.length; i++, j += 4) {
    g[i] = 0.299 * rgba[j] + 0.587 * rgba[j + 1] + 0.114 * rgba[j + 2];
    sum += g[i];
  }
  let s1 = 0, s2 = 0, n = 0;
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const i = y * width + x;
      const lap = g[i - width] + g[i + width] + g[i - 1] + g[i + 1] - 4 * g[i];
      s1 += lap; s2 += lap * lap; n++;
    }
  }
  const variance = n ? s2 / n - (s1 / n) ** 2 : 0;
  return { brightness: sum / g.length / 255, sharpness: Math.min(Math.max(variance / 150, 0), 1) };
}

function frameMeasurement(result, width, height, stats) {
  const count = result.faceLandmarks.length;
  const empty = { face_count: count, brightness: stats.brightness, sharpness: stats.sharpness, features: null, pose: null };
  if (count !== 1 || !result.faceBlendshapes?.length || !result.facialTransformationMatrixes?.length) return empty;
  try {
    const ear = (eyeRatio(result.faceLandmarks[0], LEFT_EYE, width, height) + eyeRatio(result.faceLandmarks[0], RIGHT_EYE, width, height)) / 2;
    const k = {};
    for (const c of result.faceBlendshapes[0].categories) k[c.categoryName] = c.score;
    const required = ['browDownLeft', 'browDownRight', 'mouthPressLeft', 'mouthPressRight', 'jawOpen'];
    if (required.some((r) => !(r in k)) || !Number.isFinite(ear) || ear < 0.02 || ear > 1) return empty;
    const features = { eye_aspect_ratio: ear, brow_lowering: (k.browDownLeft + k.browDownRight) / 2, lip_press: (k.mouthPressLeft + k.mouthPressRight) / 2, jaw_open: k.jawOpen };
    const pose = headAngles(result.facialTransformationMatrixes[0]);
    if (!pose.every(Number.isFinite) || !Object.values(features).every(Number.isFinite)) return empty;
    return { ...empty, features, pose };
  } catch (e) {
    return empty;
  }
}

// numpy.unwrap on one axis (radians), same algorithm as NumPy.
function unwrap(values) {
  const out = [values[0]];
  const period = 2 * Math.PI;
  let correction = 0;
  for (let i = 1; i < values.length; i++) {
    const dd = values[i] - values[i - 1];
    const shifted = dd + Math.PI;
    let ddmod = shifted - period * Math.floor(shifted / period) - Math.PI;
    if (ddmod === -Math.PI && dd > 0) ddmod = Math.PI;
    correction += Math.abs(dd) < Math.PI ? 0 : ddmod - dd;
    out.push(values[i] + correction);
  }
  return out;
}

function mean(xs) { return xs.reduce((a, b) => a + b, 0) / xs.length; }

function summarizeWindow(frames, start, duration, phase) {
  const valid = frames.filter((f) => f.face_count === 1 && f.features);
  const tracking = frames.length ? valid.length / frames.length : 0;
  const count = frames.reduce((m, f) => Math.max(m, f.face_count), 0);
  const features = { eye_aspect_ratio: 0.3, brow_lowering: 0, lip_press: 0, jaw_open: 0, head_motion_deg: 0 };
  let yaw = 0, pitch = 0;
  if (valid.length) {
    for (const key of ['eye_aspect_ratio', 'brow_lowering', 'lip_press', 'jaw_open']) features[key] = mean(valid.map((f) => f.features[key]));
    const axes = [0, 1, 2].map((a) => unwrap(valid.map((f) => f.pose[a] / DEG)).map((v) => v * DEG));
    const centres = axes.map(mean);
    const sq = valid.map((_, i) => axes.reduce((s, axis, a) => s + (axis[i] - centres[a]) ** 2, 0));
    features.head_motion_deg = Math.min(Math.sqrt(mean(sq)), 180);
    const worst = (a) => valid.map((f) => f.pose[a]).reduce((m, v) => (Math.abs(v) > Math.abs(m) ? v : m), 0);
    pitch = worst(0);
    yaw = worst(1);
  }
  return {
    t_start_sec: start, duration_sec: duration, phase, features,
    quality: {
      face_count: count, tracking_score: tracking,
      brightness: frames.length ? mean(frames.map((f) => f.brightness)) : 0,
      sharpness: frames.length ? mean(frames.map((f) => f.sharpness)) : 0,
      yaw_deg: yaw, pitch_deg: pitch,
    },
  };
}

// Same windowing as backend/scripts/extract_video.py: 2.5 s windows, 15 s phases.
function buildWindows(framesByWindow, actualDuration, protocol) {
  const windows = [];
  for (const i of Object.keys(framesByWindow).map(Number).sort((a, b) => a - b)) {
    const start = i * 2.5;
    const duration = Math.min(2.5, actualDuration - start);
    if (duration < 0.1) continue;
    const phase = protocol === 'neutral_only' ? 'neutral' : ['neutral', 'task', 'recovery'][Math.min(Math.floor(start / 15), 2)];
    windows.push(summarizeWindow(framesByWindow[i], start, duration, phase));
  }
  return windows;
}
`;
