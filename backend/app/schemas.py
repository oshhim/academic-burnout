from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Id = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]
Source = Literal["synthetic_demo", "local_research", "public_dataset"]
Phase = Literal["neutral", "task", "recovery"]
Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ParticipantCreate(StrictModel):
    participant_id: Id
    data_source: Source = "synthetic_demo"
    consent: bool
    consent_version: str = Field(default="demo-v1", min_length=1, max_length=64)


class Features(StrictModel):
    # Window means, not diagnoses or model probability estimates.
    eye_aspect_ratio: float = Field(ge=0.02, le=1)
    brow_lowering: Unit
    lip_press: Unit
    jaw_open: Unit
    head_motion_deg: float = Field(ge=0, le=180)


class Quality(StrictModel):
    face_count: int = Field(ge=0, le=10)
    tracking_score: Unit
    brightness: Unit
    sharpness: Unit
    yaw_deg: float = Field(ge=-180, le=180)
    pitch_deg: float = Field(ge=-180, le=180)


class Window(StrictModel):
    t_start_sec: float = Field(ge=0, le=180)
    duration_sec: float = Field(ge=0.1, le=5)
    phase: Phase
    features: Features
    quality: Quality


class Ratings(StrictModel):
    fatigue: int = Field(ge=1, le=5, strict=True)
    mental_strain: int = Field(ge=1, le=5, strict=True)
    concentration_readiness: int = Field(ge=1, le=5, strict=True)


class SessionInput(StrictModel):
    participant_id: Id
    client_session_id: Id
    data_source: Source
    feature_schema_version: Literal["facial-window-v1"] = "facial-window-v1"
    extractor_version: str = Field(default="synthetic-v1", min_length=1, max_length=100)
    recorded_at: datetime
    consent: bool
    baseline_condition_confirmed: bool = False
    protocol: Literal["neutral_only", "neutral_task_recovery"]
    windows: list[Window] = Field(min_length=3, max_length=180)
    ratings: Ratings | None = None

    @field_validator("recorded_at")
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recorded_at must include timezone, for example +00:00")
        value = value.astimezone(timezone.utc)
        if (value - datetime.now(timezone.utc)).total_seconds() > 300:
            raise ValueError("recorded_at cannot be more than five minutes in the future")
        return value

    @model_validator(mode="after")
    def chronological(self):
        phase_order = {"neutral": 0, "task": 1, "recovery": 2}
        last_end = 0.0
        last_phase = -1
        for window in self.windows:
            if window.t_start_sec < last_end - 1e-6:
                raise ValueError("Windows must be chronological and non-overlapping")
            if phase_order[window.phase] < last_phase:
                raise ValueError("Phases must follow neutral, task, recovery order")
            last_end = window.t_start_sec + window.duration_sec
            last_phase = phase_order[window.phase]
        if last_end > 180 or last_end < 10:
            raise ValueError("Session elapsed duration must be between 10 and 180 seconds")
        phases = {w.phase for w in self.windows}
        if self.protocol == "neutral_only" and phases != {"neutral"}:
            raise ValueError("neutral_only protocol must contain only neutral windows")
        return self


class BaselineCreate(StrictModel):
    participant_id: Id
    session_ids: list[str] = Field(min_length=3, max_length=10)

    @field_validator("session_ids")
    @classmethod
    def unique_ids(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Provide different calibration session IDs")
        return values


class CheckinInput(SessionInput):
    baseline_id: str | None = Field(default=None, max_length=36)


class Evidence(StrictModel):
    model_version: str = "c1-statistical-v1.0.0"
    method: str = "robust_personal_baseline_deviation"
    training_data_source: str = "not_applicable_no_trained_wellbeing_classifier"
    validation_status: str = "software_verified_not_wellbeing_validated"
    feature_schema_version: str = "facial-window-v1"


class QualityResult(StrictModel):
    status: Literal["accepted", "insufficient_quality"]
    usable_duration_sec: float
    elapsed_duration_sec: float
    usable_fraction: float
    quality_score: float
    rejected_window_count: int
    reasons: list[str]


class DeviationResult(StrictModel):
    mean_absolute_standardized_deviation: float
    level: Literal["within_reference_range", "moderate_visual_change", "large_visual_change"]
    per_feature_signed_z: dict[str, float]
    top_changed_features: list[str]
    # No confidence/probability: reference-scale change has no clinical calibration.


class TemporalResult(StrictModel):
    status: Literal["measured", "not_measurable"]
    reason: str | None
    phase_deviations: dict[str, float]
    task_to_recovery_change: float | None
    return_fraction: float | None
    return_rate_z_per_sec: float | None
    interpretation: str


class SessionOutput(StrictModel):
    session_id: str
    participant_id: str
    client_session_id: str
    data_source: Source
    recorded_at: str
    extractor_version: str
    protocol: str
    baseline_condition_confirmed: bool
    status: Literal["accepted", "insufficient_quality"]
    quality: QualityResult
    session_features: dict[str, float] | None
    baseline_id: str | None
    deviation: DeviationResult | None
    temporal: TemporalResult | None
    request_self_report: bool
    self_report_reason: str
    evidence: Evidence
    warnings: list[str]


class BaselineOutput(StrictModel):
    baseline_id: str
    participant_id: str
    data_source: Source
    version: int
    created_at: str
    effective_at: str
    session_ids: list[str]
    center: dict[str, float]
    scale: dict[str, float]
    scale_floors: dict[str, float]
    extractor_version: str
    evidence: Evidence
    warnings: list[str]


class HistoryOutput(StrictModel):
    participant_id: str
    total: int
    offset: int
    limit: int
    sessions: list[SessionOutput]
