from sqlalchemy import JSON, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data_source: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[str] = mapped_column(String(40))
    consent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FacialSession(Base):
    __tablename__ = "facial_sessions"
    __table_args__ = (
        UniqueConstraint("participant_id", "client_session_id", name="uq_facial_client_session"),
        Index("ix_facial_participant_time", "participant_id", "recorded_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    client_session_id: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    recorded_at: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(16))
    data_source: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    baseline_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    features: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class FacialBaseline(Base):
    __tablename__ = "facial_baselines"
    __table_args__ = (
        Index("ix_baseline_participant_created", "participant_id", "created_at"),
        UniqueConstraint("participant_id", "version", name="uq_baseline_version"),
        UniqueConstraint("participant_id", "request_hash", name="uq_baseline_selection"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    created_at: Mapped[str] = mapped_column(String(40))
    effective_at: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer)
    data_source: Mapped[str] = mapped_column(String(24))
    request_hash: Mapped[str] = mapped_column(String(64))
    summary: Mapped[dict] = mapped_column(JSON)


class SelfReport(Base):
    __tablename__ = "facial_self_reports"
    session_id: Mapped[str] = mapped_column(ForeignKey("facial_sessions.id", ondelete="CASCADE"), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    created_at: Mapped[str] = mapped_column(String(40))
    ratings: Mapped[dict] = mapped_column(JSON)


class VoiceSession(Base):
    __tablename__ = "voice_sessions"
    __table_args__ = (
        UniqueConstraint("participant_id", "client_session_id", name="uq_voice_client_session"),
        Index("ix_voice_participant_created", "participant_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    client_session_id: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    recorded_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_source: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    audio_sha256: Mapped[str] = mapped_column(String(64))
    model_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class RiskDaily(Base):
    __tablename__ = "risk_daily"
    __table_args__ = (UniqueConstraint("participant_id", "observed_on", name="uq_risk_daily_date"), UniqueConstraint("participant_id", "client_record_id", name="uq_risk_daily_client"), Index("ix_risk_daily_time", "participant_id", "observed_on"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    client_record_id: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    data_source: Mapped[str] = mapped_column(String(24))
    observed_on: Mapped[str] = mapped_column(String(10))
    reported_at: Mapped[str] = mapped_column(String(40))
    ingested_at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)


class RiskWeekly(Base):
    __tablename__ = "risk_weekly"
    __table_args__ = (UniqueConstraint("participant_id", "observed_on", name="uq_risk_weekly_date"), UniqueConstraint("participant_id", "client_record_id", name="uq_risk_weekly_client"), Index("ix_risk_weekly_time", "participant_id", "observed_on"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    client_record_id: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    data_source: Mapped[str] = mapped_column(String(24))
    observed_on: Mapped[str] = mapped_column(String(10))
    reported_at: Mapped[str] = mapped_column(String(40))
    ingested_at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"
    __table_args__ = (UniqueConstraint("participant_id", "client_prediction_id", name="uq_risk_prediction_client"), Index("ix_risk_prediction_time", "participant_id", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    client_prediction_id: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    as_of: Mapped[str] = mapped_column(String(40))
    data_source: Mapped[str] = mapped_column(String(24))
    model_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)


class InterventionPreference(Base):
    __tablename__ = "intervention_preferences"
    __table_args__ = (UniqueConstraint("participant_id", "client_update_id", name="uq_intervention_preference_client"), UniqueConstraint("participant_id", "version", name="uq_intervention_preference_version"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    client_update_id: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(40))
    data_source: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict] = mapped_column(JSON)


class InterventionRecommendation(Base):
    __tablename__ = "intervention_recommendations"
    __table_args__ = (UniqueConstraint("participant_id", "client_request_id", name="uq_intervention_recommendation_client"), Index("ix_intervention_recommendation_time", "participant_id", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    client_request_id: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    data_source: Mapped[str] = mapped_column(String(24))
    result: Mapped[dict] = mapped_column(JSON)


class InterventionSession(Base):
    __tablename__ = "intervention_sessions"
    __table_args__ = (UniqueConstraint("participant_id", "client_session_id", name="uq_intervention_session_client"), UniqueConstraint("recommendation_id", name="uq_intervention_session_recommendation"), Index("ix_intervention_session_time", "participant_id", "started_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("intervention_recommendations.id", ondelete="CASCADE"))
    client_session_id: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    activity_id: Mapped[str] = mapped_column(String(64))
    data_source: Mapped[str] = mapped_column(String(24))
    started_at: Mapped[str] = mapped_column(String(40))
    ended_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict] = mapped_column(JSON)
    start_result: Mapped[dict] = mapped_column(JSON)


class InterventionEvent(Base):
    __tablename__ = "intervention_events"
    __table_args__ = (UniqueConstraint("participant_id", "client_event_id", name="uq_intervention_event_client"), UniqueConstraint("session_id", name="uq_intervention_event_terminal"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    session_id: Mapped[str] = mapped_column(ForeignKey("intervention_sessions.id", ondelete="CASCADE"))
    client_event_id: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    result: Mapped[dict] = mapped_column(JSON)


class InterventionFeedback(Base):
    __tablename__ = "intervention_feedback"
    __table_args__ = (UniqueConstraint("participant_id", "client_feedback_id", name="uq_intervention_feedback_client"), UniqueConstraint("session_id", name="uq_intervention_feedback_session"), Index("ix_intervention_feedback_time", "participant_id", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    session_id: Mapped[str] = mapped_column(ForeignKey("intervention_sessions.id", ondelete="CASCADE"))
    client_feedback_id: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    data_source: Mapped[str] = mapped_column(String(24))
    activity_id: Mapped[str] = mapped_column(String(64))
    helpfulness: Mapped[int] = mapped_column(Integer)
    would_repeat: Mapped[bool] = mapped_column(Integer)
    result: Mapped[dict] = mapped_column(JSON)
