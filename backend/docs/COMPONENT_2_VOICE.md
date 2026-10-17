# Component 2 — Voice: public-audio baseline, features and API

## What is implemented

1. Original RAVDESS speech download with publisher MD5 verification and traversal-safe WAV extraction.
2. Bounded WAV validation, mono conversion, polyphase resampling to 16 kHz and provisional activity/clipping quality gates.
3. Standard openSMILE **eGeMAPSv02 functionals: 88 features**, with an identical implementation for training and API inference.
4. Actual dummy/logistic/linear-SVM/RBF-SVM comparisons with speaker-separated model selection and testing.
5. Supplied trained model, version/checksum/schema checks, model card, per-class metrics, confusion matrix and plots.
6. Multipart features/check-in APIs, immutable self-reports, pagination, retry protection, shared participant export/deletion and a schema migration preserving C1 data.
7. Browser and Python demos using three attributed original public recordings.

There is no ChatGPT/OpenAI/Claude call, voice therapy, transcription, speech-language detector, generative assistant, clinical stress classifier or burnout predictor. Those functions are not simulated by the emotion-style model. Component 2 here is its acoustic/model backend.

## Dataset and labels

RAVDESS original **audio speech** contains 1,440 recordings from 24 professional actors, two fixed English statements and eight acted labels: neutral, calm, happy, sad, angry, fearful, disgust and surprised. Actor IDs come from filenames. Labels are filename metadata used only during training/evaluation; inference takes waveform features, not the filename, provided label or participant ID.

The original download is approximately 209 MB. The script verifies `bc696df654c87fed845eb13823edef8a` (publisher MD5), extracts only speech WAVs and writes provenance. Full training data are not bundled. Three unchanged WAVs from held-out actor 19 are included for a reproducible demo with CC BY-NC-SA 4.0 attribution.

This dataset has **no student wellbeing, stress, therapy-response or burnout ground truth**. Its acted speech and North American English setting do not validate inference on spontaneous Sinhala, Tamil or Sri Lankan English speech. CREMA-D cross-corpus testing and an approved local speech study are later extensions; neither is claimed as completed.

Sources:

- Dataset and terms: <https://zenodo.org/records/1188976>
- Livingstone SR, Russo FA (2018), PLoS ONE 13(5): e0196391. <https://doi.org/10.1371/journal.pone.0196391>
- openSMILE documentation/features/research-use terms: <https://audeering.github.io/opensmile-python/>

## Acoustic pipeline

**Input:** WAV/WAVEX, 1–30 seconds, 8–96 kHz, mono/stereo, ≤8 MiB. SoundFile checks the actual container rather than trusting extension/MIME. Corrupt, nonfinite/out-of-range, unsupported-channel and excessive-duration input is rejected before feature extraction. No silent truncation or unrecorded gain normalization occurs.

**Preprocessing:** convert stereo to mono; detect strong phase cancellation; resample to 16 kHz with `scipy.signal.resample_poly`. Preserve amplitude. The feature schema and openSMILE package version are recorded in each response.

**Quality:** use 20 ms RMS frames. The activity threshold is the greater of −55 dBFS and (maximum frame level −35 dB). Require ≥0.5 seconds activity, ≥10% active frames and overall RMS ≥−55 dBFS; reject clipping fraction >1% or severe stereo phase cancellation. Settings are provisional and are applied identically to training and prediction. Energy activity is **not a reliable speech detector, SNR estimate or emotion-confidence score**. Noise/music can pass; a quiet but valid utterance can be rejected. All rejected training/test records remain in the manifest and coverage report.

**Features:** the standard eGeMAPSv02 set includes pitch, loudness, jitter/shimmer, harmonics/noise measures, spectral/cepstral descriptors, formant-related measures and temporal/voicing functionals. The exact 88 feature names are stored in `model_card.json` and available from `/voice/config`. They are openSMILE functionals, not a custom claim to 88 newly invented features. Nonfinite/unusable features cause abstention. Whole-recording functionals do not recover word meanings or a fine-grained emotion timeline.

No general-purpose waveform augmentation is used. No synthetic audio supplies training emotion labels. Generated tones/silence/noise are used only for decoder/quality software tests.

## Speaker-separated model comparison

- Fixed training speakers: actors **01–18** (1,080 original recordings; 1,031 accepted).
- Fixed test speakers: actors **19–24** (360 original recordings; 346 accepted).
- Cross-validation: three-fold `StratifiedGroupKFold`, seed 42, grouping by actor **inside the training partition only**.
- `StandardScaler` lives inside each sklearn pipeline and is fitted only on the fold's training records.
- Compare most-frequent dummy, balanced logistic regression C=1, balanced linear SVM C=1, and balanced RBF SVM C=1/C=10 with gamma=scale.
- Select the non-dummy model with highest mean training-speaker CV macro F1. Freeze selection before reading test metrics. Train that delivered model on accepted training speakers only; do not refit with held-out actors.
- Report test metrics for every frozen candidate for comparison, without using them to change selection. This is one fixed split with 24 actors, not a generalization guarantee or confidence interval.

Actual results from the supplied model:

| Configuration | CV macro F1 | Test macro F1 | Test accuracy |
|---|---:|---:|---:|
| Most-frequent dummy | 0.0306 | 0.0305 | 13.87% |
| Logistic regression C=1 **selected** | **0.4753** | **0.4905** | **49.42%** |
| Linear SVM C=1 | 0.4413 | 0.5071 | 52.02% |
| RBF SVM C=1 | 0.4382 | 0.4655 | 47.11% |
| RBF SVM C=10 | 0.4378 | 0.4404 | 45.38% |

Why is logistic regression selected when linear SVM's test score is higher? The model-selection rule used CV before the test was inspected. Switching to the largest test score would use the held-out set for model selection and make it no longer an independent final test. Future tuning needs a newly defined untouched evaluation set or a nested evaluation design.

**Coverage must accompany accuracy:** 63/1,440 recordings abstained at the quality gate (49 train, 14 test). Accepted test coverage is 346/360 = **96.11%**. Selected-model correct classifications = 171; accuracy on accepted records = 171/346 = **49.42%**. Counting abstentions as incorrect across the full held-out set gives 171/360 = **47.50%**. Per-label rejected counts, UAR, per-class precision/recall/F1 and every accepted test prediction are supplied in `evaluation.json`. Do not call either accuracy a student stress-detection rate.

The full model is fast and lightweight relative to a transformer. Its approximately half-correct eight-class held-out result is a baseline needing improvement/validation, not sufficient reliability for automatic wellbeing decisions. Log-Mel CNN/wav2vec comparisons remain future work and are not claimed in the results.

## Run and retrain

Use the root README for Python 3.12 setup, pinned dependencies, database migration and server startup. **No full dataset download or training is necessary for the supplied demo.**

```bash
python -m scripts.run_voice_demo --output data/voice_demo_results.json
python -m scripts.verify_http
python -m pytest -q
```

To reproduce training on the original data:

```bash
python -m training.download_ravdess
python -m training.train_voice
python -m training.plot_voice_evaluation
```

The first complete feature extraction took about 158 seconds in the original verification environment; timings on other computers vary. Subsequent training runs can reuse the feature cache keyed by waveform SHA-256 and extractor version. Fit and evaluation metrics remain reproducible. Feature vectors/cache are derived research data; do not mix them with private student records. Restart the API after replacing the locally trained artifacts.

For intentional package upgrades, install `requirements-training.txt`, stop the API, retrain with the new versions and rerun tests, then restart the API. The supplied artifact requires the tested sklearn/NumPy/joblib versions and exact openSMILE/schema version. An incompatible artifact results in explicit model unavailability; no dummy model silently replaces it. Joblib can execute code when loading a malicious pickle: load only this project's trusted/generated local model artifacts, never arbitrary uploaded model files. The API has no model-upload route.

## API contracts

All endpoints below are prefixed `/api/v1` and require `X-API-Key`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /voice/config | Feature names, extractor/version, format limits |
| GET | /voice/model | Actual model status, ID, data source, card and limitations |
| GET | /voice/evaluation | Measured public-data model comparison |
| POST | /voice/features | Stateless audio validation/features only |
| POST | /voice/checkins | Extract, classify where quality permits and persist numerical result |
| GET | /voice/history/{participant_id} | Paginated results; limit 1–100 and offset |
| POST | /voice/self-reports/{session_id} | Attach immutable exploratory 1–5 ratings |
| GET | /participants/{id}/export | Export C1 and C2 numerical data |
| DELETE | /participants/{id} | Delete participant and both components' records |

The upload endpoints use **multipart/form-data**, with `audio` (WAV file) and `metadata` (JSON text). Do not send a JSON body containing a filesystem path: the server cannot access the user's local path. Do not manually set the multipart boundary header in a browser; `FormData` supplies it.

Public demo metadata:

```json
{
  "participant_id": "RAVDEMO-01",
  "client_session_id": "voice-001",
  "data_source": "public_dataset",
  "consent": true,
  "dataset": "RAVDESS",
  "dataset_recording_id": "03-01-01-01-01-01-19"
}
```

Register that participant using `POST /participants` with `data_source=public_dataset` and consent/permission before creating check-ins. `recorded_at` is null for public samples because their exact capture time is unknown; the API independently stores submission time. Provenance fields supplied by API clients are declarations, not an automatic authenticity check of arbitrary uploaded public WAVs. The bundled original clips have recorded SHA-256 hashes in their manifest.

For approved local data use `data_source=local_research`, consent, an actual timezone-aware `recorded_at`, and no public dataset fields. Local collection is blocked unless `ENABLE_RESEARCH_MODE=true`. That configuration change does not itself constitute ethical approval. Use a different participant ID for each source; the server rejects source mixing. For synthetic technical audio use `synthetic_demo`, omit public dataset fields and never report its predictions as research evidence.

Frontend example (after registration):

```javascript
const body = new FormData();
body.append('metadata', JSON.stringify(metadata));
body.append('audio', file, file.name);
const response = await fetch('http://127.0.0.1:8000/api/v1/voice/checkins', {
  method: 'POST', headers: {'X-API-Key': developmentKey}, body
});
const result = await response.json();
if (!response.ok) throw new Error(JSON.stringify(result));
```

Use the browser demo `/voice-demo` or Swagger `/docs` to make a request without writing frontend code. Default browser microphone `MediaRecorder` often produces WebM/Opus; convert/encode into WAV in the frontend before uploading. Browser microphone capture/transcoding is not implemented by this upload demo. Original RAVDESS files can be uploaded directly.

## Response and persistence

Accepted check-ins return the 88 features, waveform hash, preprocessing/quality metadata, predicted acted-emotion style, uncalibrated class decision scores, model ID and data-source/validation evidence. **No probability/confidence percentage is returned**, even though the logistic estimator supports a mathematical softmax: that would not establish calibrated correctness on local speech. Scores must not be treated as stress/burnout probabilities.

Poor-quality audio returns `insufficient_quality`, reasons and no features/prediction. Malformed input returns 422; missing/incompatible model gives 503 for a quality-accepted check-in. A features-only request can still operate without a trained model. Feature requests are not stored. Check-in retries with the same participant/client ID and identical audio/metadata return the same stored session; changed content returns 409. Different filenames alone never affect classification.

Exploratory ratings are fatigue, mental strain and concentration readiness (integer 1–5). They are labels for later study, not a validated burnout scale and not training labels for this public emotion classifier. They are requested for every session rather than only difficult predictions. Stored self-reports are immutable.

The database stores numerical features, audio SHA-256, request metadata, output/model version and optional ratings. The application does not retain raw voice uploads. The framework can temporarily spool a multipart file while processing it; upload handles are closed after requests. Operational hosting/proxy logging and retention must be configured before real collection. Current numeric records persist until deletion; automatic expiry is not implemented. Shared demo-key authorization is for a trusted local progress demo; real student-facing deployment needs participant authentication and access controls.

## Proposal/progress presentation

Show `/voice-demo`, play a public clip, submit it, inspect feature count/model ID and open measured comparisons. Then show `/voice/history/{id}`, participant export, and `pytest`. Use supplied PNG/PDF plots with their axes, speaker split, accepted-recording denominator and coverage stated.

The saved demonstration predicts neutral→neutral, happy→calm and angry→angry. The incorrect happy prediction is retained to show the baseline's limits; do not replace a model output with the dataset label.

Present the contribution as a **low-resource, quality-aware voice measurement pipeline integrated with personal facial references and longitudinal feedback**, whose benefit still requires a study. eGeMAPS and logistic regression themselves are established methods, not inventions. The component's research extension can compare personal longitudinal changes and local self-report validation against this public emotion baseline. Do not claim therapy effectiveness, clinical detection, an original emotion-recognition architecture, real-time continuous monitoring, or local student accuracy based on this corpus.

Next: verify the actual frontend WAV capture path, collect approved natural-speech/local labels, evaluate domain shift and rejection rates, and add a genuinely independent corpus/local test before tuning further. Keep source/quality/model-version fields when C3 later consumes these outputs.
