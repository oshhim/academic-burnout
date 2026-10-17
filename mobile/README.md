# EMPath+ mobile

Expo (React Native) app for testing the four backend components from a phone, with real camera and microphone capture. It follows the minimal screen set in the frontend integration guide and uses the EMPath+ design tokens. It is not the full product UI.

| Tab | Component | Demo data mode | Real capture mode |
|---|---|---|---|
| Setup | Shared | Backend URL, key, consent, registration | Separate consent; registers a `local_research` participant |
| Facial | C1 | Synthetic numerical windows | Front camera, measured on the phone with MediaPipe; only numbers are sent |
| Voice | C2 | Bundled public RAVDESS WAVs | Microphone, encoded as 16-bit PCM WAV |
| Risk | C3 | Your entries + 14-day sample histories | Your entries; the synthetic-only model deliberately gives no score |
| Activities | C4 | Preferences → offers → start → finish → feedback | Same, under your real participant |

Each data source has its own participant (`synthetic_demo`, `public_dataset`, `local_research`), because the guide forbids mixing them under one ID. All records live in the backend database; the phone stores only the connection settings and participant IDs.

## How real capture works

Camera and microphone run inside a WebView (`react-native-webview`, included in Expo Go), so no custom native build is needed.

- **Facial (C1):** MediaPipe Face Landmarker `@mediapipe/tasks-vision@0.10.35` (the same MediaPipe version as `backend/scripts/extract_video.py`) runs at about 10 Hz. The page computes the backend's features per 2.5 s window: eye aspect ratio, brow lowering, lip press, jaw open, head motion, and quality (face count, tracking, brightness, sharpness, yaw, pitch). The math in `src/lib/capture/face-math.ts` is a line-by-line port of `backend/app/facial/extraction.py`; on randomized inputs it matches the Python to within 1e-14. Sessions are sent with extractor version `webview-mp-0.10.35-facelandmarker-f16v1-adapter-v1`, so they need their own baseline. The video never leaves the page.
- **Voice (C2):** Web Audio captures mono samples, which are encoded to PCM16 WAV at the device sample rate (the backend resamples to 16 kHz). The encoder round-trips 16-bit audio exactly: re-encoded RAVDESS files give identical features and predictions.

The phone needs internet access the first time, to download MediaPipe (~10 MB WASM plus model) from jsDelivr and Google's model storage.

**Check-in task:** the 15-second task phase currently shows a placeholder ("Silently count backwards from 300 in steps of 7"). Agree the standardized task with your supervisor before any study; change `TASK_PROMPT` in `src/lib/capture/pages.ts`.

**Thresholds:** the C1 quality gate and deviation levels are provisional engineering settings that have not been validated on phone capture.

## Run it

You need Node 20+ and **Expo Go** (supporting SDK 57) on your phone. Phone and laptop must be on the same Wi-Fi.

1. For Real capture mode, set `ENABLE_RESEARCH_MODE=true` in `backend/.env`. Only test with your own face and voice: the setting is not ethics approval for collecting data from others.
2. Start the backend on all network interfaces (from `backend/`):

   ```bash
   .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. Start the app (from `mobile/`):

   ```bash
   npm install
   npx expo start -c
   ```

4. Scan the QR code with the iPhone Camera app (or Expo Go on Android).
5. On **Setup**: check the backend URL (it defaults to your laptop's Wi-Fi IP on port 8000), give consent, tap **Connect and register**. To use the camera and microphone, give the second consent and tap **Enable real capture**. Allow camera and microphone access when asked.

The default API key is `local-demo-key-change-me`. It is an administrator key for the whole database, so use it only on a trusted local network.

If the phone can't connect: confirm both devices are on the same Wi-Fi, the backend was started with `--host 0.0.0.0`, and the macOS firewall allows incoming connections for Python.

## Project layout

```text
src/
  app/
    _layout.tsx            Fonts, session provider, root stack
    (tabs)/_layout.tsx     Bottom tabs
    (tabs)/index.tsx       Setup and data mode
    (tabs)/facial.tsx      C1
    (tabs)/voice.tsx       C2
    (tabs)/risk.tsx        C3
    (tabs)/activities.tsx  C4
  components/
    ui.tsx                 Themed building blocks (Screen, Card, Button, Chips, Rating, ...)
    capture-view.tsx       WebView host for camera/microphone pages
  lib/
    api.ts                 HTTP client and error mapping
    session.tsx            Connection, participants, data mode, retry-safe operation IDs
    fixtures.ts            Synthetic C1 windows and C3 sample diary (ported from backend scripts)
    capture/face-math.ts   Port of backend/app/facial/extraction.py
    capture/pages.ts       Camera (MediaPipe) and microphone (WAV) capture pages
  theme.ts                 Colours, spacing and type from the design system
```

## Checks

```bash
npx tsc --noEmit
npx expo lint
```
