import io

import numpy as np
import pytest
import soundfile as sf

from app.voice.features import AudioError, decode_audio, extract_features


def wav(values, rate=16000, subtype="PCM_16"):
    output = io.BytesIO()
    sf.write(output, values, rate, format="WAV", subtype=subtype)
    return output.getvalue()


def tone(rate=16000, seconds=2):
    t = np.arange(int(rate * seconds)) / rate
    return 0.2 * np.sin(2 * np.pi * 220 * t)


def test_resampling_duration_activity_and_eighty_eight_finite_features():
    samples, quality = decode_audio(wav(tone(48000), 48000))
    assert len(samples) == 32000 and quality["sample_rate"] == 16000
    assert quality["original_sample_rate"] == 48000 and quality["status"] == "accepted"
    quality, features = extract_features(wav(tone()))
    assert quality["status"] == "accepted" and len(features) == 88
    assert np.isfinite(list(features.values())).all()


@pytest.mark.parametrize("values,reason", [(np.zeros(32000), "too_little_signal_activity"), (np.ones(32000), "excessive_clipping")])
def test_bad_capture_returns_no_features(values, reason):
    quality, features = extract_features(wav(values))
    assert features is None and reason in quality["reasons"]


def test_stereo_cancellation_is_rejected():
    value = tone()
    _, quality = decode_audio(wav(np.column_stack([value, -value])))
    assert "stereo_phase_cancellation" in quality["reasons"]


@pytest.mark.parametrize("data", [b"not audio", wav(np.zeros(100)), wav(np.zeros(31 * 16000)), wav(tone(), 4000), wav(np.full(32000, np.nan), subtype="FLOAT")])
def test_bounded_decoder_rejects_invalid_duration_rate_or_values(data):
    with pytest.raises(AudioError):
        decode_audio(data)


def test_noise_is_not_claimed_to_be_verified_speech():
    rng = np.random.default_rng(42)
    _, quality = decode_audio(wav(rng.normal(0, 0.05, 32000)))
    assert quality["status"] == "accepted"
    assert quality["gate_status"].endswith("not_speech_or_snr_detector")
