"""Preference versions, frozen recommendations, sessions and immutable feedback."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def owner():
    return sa.Column("participant_id", sa.String(64), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)


def common(client_field):
    return [sa.Column("id", sa.String(36), primary_key=True), owner(), sa.Column(client_field, sa.String(64), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False)]


def upgrade():
    op.create_table("intervention_preferences", *common("client_update_id"),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("created_at", sa.String(40), nullable=False), sa.Column("data_source", sa.String(24), nullable=False), sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "client_update_id", name="uq_intervention_preference_client"), sa.UniqueConstraint("participant_id", "version", name="uq_intervention_preference_version"))
    op.create_table("intervention_recommendations", *common("client_request_id"),
        sa.Column("created_at", sa.String(40), nullable=False), sa.Column("data_source", sa.String(24), nullable=False), sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "client_request_id", name="uq_intervention_recommendation_client"))
    op.create_index("ix_intervention_recommendation_time", "intervention_recommendations", ["participant_id", "created_at"])
    op.create_table("intervention_sessions", *common("client_session_id"),
        sa.Column("recommendation_id", sa.String(36), sa.ForeignKey("intervention_recommendations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", sa.String(64), nullable=False), sa.Column("data_source", sa.String(24), nullable=False),
        sa.Column("started_at", sa.String(40), nullable=False), sa.Column("ended_at", sa.String(40)), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False), sa.Column("start_result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "client_session_id", name="uq_intervention_session_client"), sa.UniqueConstraint("recommendation_id", name="uq_intervention_session_recommendation"))
    op.create_index("ix_intervention_session_time", "intervention_sessions", ["participant_id", "started_at"])
    op.create_table("intervention_events", *common("client_event_id"),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("intervention_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False), sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "client_event_id", name="uq_intervention_event_client"), sa.UniqueConstraint("session_id", name="uq_intervention_event_terminal"))
    op.create_table("intervention_feedback", *common("client_feedback_id"),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("intervention_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False), sa.Column("data_source", sa.String(24), nullable=False), sa.Column("activity_id", sa.String(64), nullable=False),
        sa.Column("helpfulness", sa.Integer(), nullable=False), sa.Column("would_repeat", sa.Integer(), nullable=False), sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "client_feedback_id", name="uq_intervention_feedback_client"), sa.UniqueConstraint("session_id", name="uq_intervention_feedback_session"))
    op.create_index("ix_intervention_feedback_time", "intervention_feedback", ["participant_id", "created_at"])


def downgrade():
    for name in ("intervention_feedback", "intervention_events", "intervention_sessions", "intervention_recommendations", "intervention_preferences"):
        op.drop_table(name)
