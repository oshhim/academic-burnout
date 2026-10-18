# EMPath+ mobile

Expo (React Native, SDK 57) app for testing the four backend components from a phone, with real camera and microphone capture. It follows the minimal screen set in the frontend integration guide and the EMPath+ design system (`design-references/screens/empath/DESIGN.md`: dark "Digital Sanctuary" theme, Inter + Geist). It is a research test app, not the full product UI. Version: see `"version"` in `app.json` (shown at the bottom of Profile).

## Screens

On first open a **launch screen** (four onboarding slides) explains the app; after **Get started** the app opens Profile until it is connected, then Facial.

| Tab | Component | Demo data mode | Real capture mode |
|---|---|---|---|
| Facial | C1 | Synthetic numerical windows and four constructed scenarios | Front camera, measured on the phone with MediaPipe; only numbers are sent |
| Voice | C2 | Bundled public RAVDESS WAVs | Microphone, uploaded as a 16-bit PCM WAV |
| Risk | C3 | Your entries, plus 14-day sample histories | Your entries; the synthetic-only model deliberately gives no score |
| Activities | C4 | Goal/time → options → start → finish → optional rating | Same, under your real participant |
| Profile | Shared | Connection, consent, data mode, data export and delete, reset | Also registers the `local_research` participant |

Every screen header shows a **DEMO / REAL** badge and an avatar that opens Profile.

### Facial flow

1. **Reference** (×3): 15 s of a relaxed, neutral face, recorded when you feel normal and calm. The progress bar counts references recorded since the current baseline.
2. **Create baseline**, or later **Replace baseline with new references** after three new ones. Each replacement is a new baseline version; older versions and references are kept.
3. **Check-in**: 45 s of neutral → task → quiet observation, compared with the newest baseline. Results show the visual-change level, the return toward baseline, and optional 1–5 self-ratings.

### Profile

- Display name and avatar initials, stored **only on the phone** (never sent to the backend). No sign-in.
- Connection status and backend model readiness; Demo/Real data mode with a separate real-capture consent.
- **Export my data** (record counts from `GET /participants/{id}/export`) and **Delete my data** (`DELETE /participants/{id}`, with confirmation), for the current mode's participants.
- **Reset this app** forgets the name, connection and participant IDs on the phone; backend records are kept.
- App version and backend API version.

## Data

Each data source has its own participant (`synthetic_demo`, `public_dataset`, `local_research`), because the guide forbids mixing them under one ID. All records live in the backend database (`backend/data/empath.db`). The phone stores only the connection, participant IDs, data mode, display name and whether the launch screen was seen (AsyncStorage). No Firebase or other cloud service is used.

## How real capture works

Camera and microphone run inside a WebView (`react-native-webview`, included in Expo Go), so no custom native build is needed.

- **Facial (C1):** MediaPipe Face Landmarker `@mediapipe/tasks-vision@0.10.35` (the same MediaPipe version as `backend/scripts/extract_video.py`) runs at about 10 Hz. The page computes the backend's features per 2.5 s window: eye aspect ratio, brow lowering, lip press, jaw open, head motion, and quality (face count, tracking, brightness, sharpness, yaw, pitch). The math in `src/lib/capture/face-math.ts` is a line-by-line port of `backend/app/facial/extraction.py`; on randomized inputs it matches the Python to within 1e-14. Sessions use extractor version `webview-mp-0.10.35-facelandmarker-f16v1-adapter-v1`, so they need their own baseline. The video never leaves the page.
- **Voice (C2):** Web Audio captures mono samples, encoded to PCM16 WAV at the device sample rate (the backend resamples to 16 kHz). The encoder round-trips 16-bit audio exactly: re-encoded RAVDESS files give identical features and predictions. The WAV is uploaded with `expo-file-system`'s native multipart `File.upload()`, because `fetch` with a `FormData` file part failed from Expo Go on iOS.

The phone needs internet the first time the camera opens, to download MediaPipe (~10 MB WASM plus model) from jsDelivr and Google's model storage.

**Check-in task:** the 15-second task phase shows a placeholder ("Silently count backwards from 300 in steps of 7"). Agree the standardized task with your supervisor before any study; change `TASK_PROMPT` in `src/lib/capture/pages.ts`.

**Thresholds:** the C1 quality gate and deviation levels are provisional engineering settings that have not been validated on phone capture.

## Run it

You need Node 20+ and **Expo Go supporting SDK 57** on your phone. Phone and laptop must be on the same Wi-Fi.

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
5. Go through the launch screen, then on **Profile**: check the backend URL (it defaults to your laptop's Wi-Fi IP on port 8000), give consent and tap **Connect and register**. For the camera and microphone, choose **Real capture**, give the second consent, tap **Enable real capture**, and allow camera and microphone access when asked.

The default API key is `local-demo-key-change-me`. It is an administrator key for the whole database, so use it only on a trusted local network.

If the phone can't connect: confirm both devices are on the same Wi-Fi, the backend was started with `--host 0.0.0.0`, and the macOS firewall allows incoming connections for Python. Network errors in the app include the phone's own error message in brackets.

## Project layout

```text
src/
  app/
    _layout.tsx             Fonts, session provider, root stack
    welcome.tsx             Launch screen (onboarding slides)
    (tabs)/_layout.tsx      Bottom tabs
    (tabs)/index.tsx        Entry redirect: welcome, profile or facial (hidden tab)
    (tabs)/facial.tsx       C1
    (tabs)/voice.tsx        C2
    (tabs)/risk.tsx         C3
    (tabs)/activities.tsx   C4
    (tabs)/profile.tsx      Profile, connection, data mode, data controls
  components/
    ui.tsx                  Themed building blocks (Screen, Section, Card, Button, Chips, Rating, Field, ResultHero, ...)
    capture-view.tsx        WebView host for the camera/microphone pages
    mode-badge.tsx          Header DEMO/REAL badge and avatar
    needs-setup.tsx         "Not connected yet" card
  lib/
    api.ts                  HTTP client, error mapping, native file upload
    session.tsx             Connection, participants, data mode, profile name, retry-safe operation IDs
    explain.ts              Plain-language text for backend codes
    fixtures.ts             Synthetic C1 windows and C3 sample diary (ported from backend scripts)
    use-action.ts           Busy/error state for buttons
    capture/face-math.ts    Port of backend/app/facial/extraction.py
    capture/pages.ts        Camera (MediaPipe) and microphone (WAV) capture pages
  theme.ts                  Colours, spacing and type from the design system
assets/images/logo.png      EMPath+ logo used in headers and the launch screen
```

## Notes for iOS

- Text inputs are deliberately stateless (no focus glow) and have no `lineHeight`: re-rendering the input box on focus made the iOS keyboard open and immediately close.
- Labels next to switches have no `lineHeight`, so Inter does not sit low beside the switch.

## Checks

```bash
npx tsc --noEmit
npx expo lint
npx expo-doctor
```
