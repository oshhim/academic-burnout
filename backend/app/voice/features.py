"""The same bounded audio decoder and feature extractor serve training and API."""
import io
import math
import threading
from importlib.metadata import version

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

FEATURE_SCHEMA = "egemaps-v02-functionals-88-16k-v1"
SAMPLE_RATE = 16000
MAX_AUDIO_BYTES = 8 * 1024 * 1024
_local = threading.local()


class AudioError(ValueError):
    pass


def extractor_version():
    return f"{FEATURE_SCHEMA}-opensmile-{version("opensmile")}"


def smile():
    if not hasattr(_local, "smile"):
        import opensmile
        _local.smile = opensmile.Smile(feature_set=opensmile.FeatureSet.eGeMAPSv02, feature_level=opensmile.FeatureLevel.Functionals)
    return _local.smile


def feature_names():
    return list(smile().feature_names)


def decode_audio(raw):
    if not raw or len(raw) > MAX_AUDIO_BYTES:
        raise AudioError("Supply a WAV file of at most 8 MiB.")
    try:
        with sf.SoundFile(io.BytesIO(raw)) as audio:
            if audio.format not in {"WAV", "WAVEX"}:
                raise AudioError("Only WAV is supported; convert WebM/MP3/M4A to PCM WAV before upload.")
            if not 8000 <= audio.samplerate <= 96000 or audio.channels not in (1, 2):
                raise AudioError("Use mono/stereo audio at 8–96 kHz.")
            if not 1 <= audio.frames / audio.samplerate <= 30:
                raise AudioError("Recording duration must be 1–30 seconds; audio is not silently truncated.")
            original_rate, channels = audio.samplerate, audio.channels
            values = audio.read(dtype="float32", always_2d=True)
    except (sf.LibsndfileError, RuntimeError, OSError) as exc:
        raise AudioError("Audio could not be decoded as a supported WAV file.") from exc
    if not np.isfinite(values).all() or np.max(np.abs(values)) > 1.001:
        raise AudioError("WAV contains nonfinite or out-of-range sample values.")
    clipping = float(np.mean(np.abs(values) >= 0.999))
    channel_rms = float(np.sqrt(np.mean(values.astype(np.float64) ** 2)))
    mono = values.mean(axis=1)
    cancellation = channels == 2 and channel_rms > 0.001 and np.sqrt(np.mean(mono ** 2)) < channel_rms * 0.1
    if original_rate != SAMPLE_RATE:
        divisor = math.gcd(original_rate, SAMPLE_RATE)
        mono = resample_poly(mono, SAMPLE_RATE // divisor, original_rate // divisor)
    mono = np.asarray(mono, dtype=np.float32)
    frame_len = 320
    frames = mono[:len(mono) // frame_len * frame_len].reshape(-1, frame_len)
    energy = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
    dbfs = 20 * np.log10(np.maximum(energy, 1e-10))
    threshold = max(-55, float(np.max(dbfs)) - 35)
    activity = energy > 10 ** (threshold / 20)
    active_seconds = float(activity.sum() * frame_len / SAMPLE_RATE)
    rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
    reasons = []
    if active_seconds < 0.5 or activity.mean() < 0.1 or rms < 10 ** (-55 / 20):
        reasons.append("too_little_signal_activity")
    if clipping > 0.01:
        reasons.append("excessive_clipping")
    if cancellation:
        reasons.append("stereo_phase_cancellation")
    quality = {"status": "accepted" if not reasons else "insufficient_quality", "reasons": reasons,
               "duration_sec": round(len(mono) / SAMPLE_RATE, 6), "original_sample_rate": original_rate,
               "sample_rate": SAMPLE_RATE, "original_channels": channels,
               "rms_dbfs": round(20 * np.log10(max(rms, 1e-10)), 4),
               "active_duration_sec": round(active_seconds, 4), "active_fraction": round(float(activity.mean()), 6),
               "clipping_fraction": round(clipping, 6), "gate_status": "provisional_signal_activity_heuristic_not_speech_or_snr_detector"}
    return mono, quality


def extract_features(raw):
    samples, quality = decode_audio(raw)
    if quality["status"] != "accepted":
        return quality, None
    frame = smile().process_signal(samples, SAMPLE_RATE)
    vector = frame.iloc[0].to_numpy(dtype=np.float64)
    if len(vector) != 88 or not np.isfinite(vector).all():
        quality["status"] = "insufficient_quality"
        quality["reasons"].append("unusable_acoustic_features")
        return quality, None
    return quality, dict(zip(frame.columns, vector.tolist()))
