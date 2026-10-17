from datetime import date, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from app.schemas import Id, StrictModel

STUDY_TIMEZONE = "Asia/Colombo"
RiskSource = Literal["synthetic_demo", "local_research"]


def aware_utc(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Use a timezone-aware timestamp")
    return value.astimezone(timezone.utc)


class Observation(StrictModel):
    participant_id: Id
    client_record_id: Id
    data_source: RiskSource
    consent: bool
    observed_on: date
    reported_at: datetime

    @field_validator("reported_at")
    @classmethod
    def report_time(cls, value):
        value = aware_utc(value)
        if value > datetime.now(timezone.utc):
            raise ValueError("reported_at cannot be in the future")
        return value

    @model_validator(mode="after")
    def date_order(self):
        if self.observed_on > self.reported_at.astimezone(ZoneInfo(STUDY_TIMEZONE)).date():
            raise ValueError("observed_on cannot be after the local date of reported_at")
        return self


class DailyInput(Observation):
    sleep_hours: float | None = Field(default=None, ge=0, le=16)
    study_minutes: int | None = Field(default=None, ge=0, le=960, strict=True)
    break_minutes: int | None = Field(default=None, ge=0, le=480, strict=True)
    late_study_minutes: int | None = Field(default=None, ge=0, le=960, strict=True)
    planned_tasks: int | None = Field(default=None, ge=0, le=50, strict=True)
    completed_tasks: int | None = Field(default=None, ge=0, le=50, strict=True)
    fatigue: int | None = Field(default=None, ge=1, le=5, strict=True)
    mental_strain: int | None = Field(default=None, ge=1, le=5, strict=True)
    concentration_readiness: int | None = Field(default=None, ge=1, le=5, strict=True)

    @model_validator(mode="after")
    def coherent(self):
        if (self.planned_tasks is None) != (self.completed_tasks is None):
            raise ValueError("Provide both planned_tasks and completed_tasks, or neither")
        if self.planned_tasks is not None and self.completed_tasks > self.planned_tasks:
            raise ValueError("completed_tasks cannot exceed planned_tasks in this task protocol")
        if self.late_study_minutes is not None and (self.study_minutes is None or self.late_study_minutes > self.study_minutes):
            raise ValueError("late_study_minutes requires study_minutes and cannot exceed it")
        fields = ("sleep_hours", "study_minutes", "break_minutes", "planned_tasks", "fatigue", "mental_strain", "concentration_readiness")
        if all(getattr(self, field) is None for field in fields):
            raise ValueError("At least one observed daily field is required; missing is not zero")
        return self


class WeeklyInput(Observation):
    instrument_version: Literal["exploratory-exhaustion-item-v1"] = "exploratory-exhaustion-item-v1"
    exhaustion: int = Field(ge=1, le=5, strict=True)
    disengagement: int | None = Field(default=None, ge=1, le=5, strict=True)
    academic_efficacy: int | None = Field(default=None, ge=1, le=5, strict=True)


class DailyBatch(StrictModel):
    records: list[DailyInput] = Field(min_length=1, max_length=90)

    @model_validator(mode="after")
    def one_participant_and_unique(self):
        if len({(r.participant_id, r.data_source) for r in self.records}) != 1:
            raise ValueError("A batch must have one participant and one data source")
        if len({r.observed_on for r in self.records}) != len(self.records) or len({r.client_record_id for r in self.records}) != len(self.records):
            raise ValueError("A batch cannot contain duplicate days or client IDs")
        return self


class RiskRequest(StrictModel):
    participant_id: Id
    client_prediction_id: Id
    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def cutoff(cls, value):
        if value is not None:
            value = aware_utc(value)
            if value > datetime.now(timezone.utc):
                raise ValueError("as_of cannot be in the future")
        return value
