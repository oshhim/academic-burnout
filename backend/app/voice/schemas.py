from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas import Id, Ratings, Source, StrictModel


class VoiceMetadata(StrictModel):
    participant_id: Id
    client_session_id: Id
    data_source: Source
    consent: bool
    recorded_at: datetime | None = None
    dataset: Literal["RAVDESS"] | None = None
    dataset_recording_id: str | None = Field(default=None, max_length=100)
    ratings: Ratings | None = None

    @field_validator("recorded_at")
    @classmethod
    def timestamp(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("recorded_at needs a timezone")
            if (value - datetime.now(timezone.utc)).total_seconds() > 300:
                raise ValueError("Recording timestamp is in the future")
            return value.astimezone(timezone.utc)
        return value

    @model_validator(mode="after")
    def provenance(self):
        if self.data_source == "public_dataset" and (self.dataset != "RAVDESS" or not self.dataset_recording_id):
            raise ValueError("Public audio requires dataset=RAVDESS and dataset_recording_id")
        if self.data_source == "local_research" and self.recorded_at is None:
            raise ValueError("Local research recordings require actual recorded_at")
        if self.data_source != "public_dataset" and (self.dataset is not None or self.dataset_recording_id is not None):
            raise ValueError("Do not label local/synthetic audio as a public recording")
        return self


class VoiceQuality(StrictModel):
    status: Literal["accepted", "insufficient_quality"]
    reasons: list[str]
    duration_sec: float
    original_sample_rate: int
    sample_rate: int
    original_channels: int
    rms_dbfs: float
    active_duration_sec: float
    active_fraction: float
    clipping_fraction: float
    gate_status: str


class VoiceOutput(StrictModel):
    session_id: str | None = None
    participant_id: str
    client_session_id: str
    data_source: Source
    submitted_at: str
    recorded_at: str | None
    dataset: str | None
    dataset_recording_id: str | None
    audio_sha256: str
    status: Literal["accepted", "insufficient_quality"]
    feature_schema_version: str
    extractor_version: str
    quality: VoiceQuality
    features: dict[str, float] | None
    prediction: dict | None
    ratings: Ratings | None
    request_self_report: bool
    evidence: dict
    warnings: list[str]
