from typing import Literal
from pydantic import Field, field_validator, model_validator
from app.schemas import Id, StrictModel
from app.interventions.catalog import BY_ID, CATEGORIES

Category = Literal["pause", "movement", "planning", "reflection", "audio"]
Strategy = Literal["generic", "preference", "adaptive", "multimodal_weighted"]
ContextMode = Literal["latest_eligible", "explicit_refs", "none"]


class Mutation(StrictModel):
    participant_id: Id
    data_source: Literal["synthetic_demo", "local_research"]
    consent: bool = Field(strict=True)


class PreferenceInput(Mutation):
    client_update_id: Id
    category_ratings: dict[Category, int] = Field(default_factory=dict)
    excluded_activity_ids: list[str] = Field(default_factory=list, max_length=len(BY_ID))
    allow_movement: bool = Field(default=True, strict=True)
    allow_audio: bool = Field(default=True, strict=True)
    max_duration_seconds: int = Field(default=600, ge=60, le=1800, strict=True)

    @field_validator("category_ratings", mode="before")
    @classmethod
    def exact_ratings(cls, value):
        if not isinstance(value, dict) or any(type(r) is not int or not 1 <= r <= 5 for r in value.values()):
            raise ValueError("Category ratings must be integers from 1 to 5")
        return value

    @field_validator("excluded_activity_ids")
    @classmethod
    def known_unique(cls, value):
        if len(set(value)) != len(value) or any(a not in BY_ID for a in value):
            raise ValueError("Excluded activities must be unique known catalog IDs")
        return sorted(value)


class RecommendationInput(Mutation):
    client_request_id: Id
    strategy: Strategy = "adaptive"
    goal: Literal["rest", "refocus", "organize", "reflect"]
    available_seconds: int = Field(ge=60, le=1800, strict=True)
    limit: int = Field(default=3, ge=1, le=len(BY_ID), strict=True)
    facial_session_id: Id | None = None
    voice_session_id: Id | None = None
    risk_prediction_id: Id | None = None
    context_mode: ContextMode = "latest_eligible"
    demo_context_id: Id | None = None

    @model_validator(mode="after")
    def explicit_context(self):
        if self.demo_context_id and (self.strategy != "multimodal_weighted" or self.context_mode == "none"):
            raise ValueError("A demo context requires multimodal_weighted with context enabled")
        if self.demo_context_id and any((self.facial_session_id, self.voice_session_id, self.risk_prediction_id)):
            raise ValueError("Use a synthetic context OR stored assessment references, not both")
        return self


class DemoContextInput(Mutation):
    client_update_id: Id
    components: list[Literal["facial", "voice", "risk"]] = Field(default_factory=list, max_length=3)
    facial_scenario: Literal["persistent", "returned", "poor_quality"] = "persistent"
    voice_scenario: Literal["sad", "neutral", "poor_quality"] = "sad"
    risk_scenario: Literal["higher", "lower", "insufficient_history"] = "higher"

    @field_validator("components")
    @classmethod
    def unique_components(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Choose each component at most once")
        return sorted(value)


class StartInput(Mutation):
    client_session_id: Id
    recommendation_id: Id
    activity_id: str = Field(min_length=1, max_length=64)


class EventInput(Mutation):
    client_event_id: Id
    session_id: Id
    outcome: Literal["completed", "abandoned"]


class FeedbackInput(Mutation):
    client_feedback_id: Id
    session_id: Id
    helpfulness: int = Field(ge=1, le=5, strict=True)
    would_repeat: bool = Field(strict=True)


def default_preferences():
    return {"category_ratings": {c: 3 for c in CATEGORIES}, "excluded_activity_ids": [], "allow_movement": True, "allow_audio": True, "max_duration_seconds": 600}
