"""Initial participant and Component 1 tables. Frozen migration definition."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("participants", sa.Column("id", sa.String(64), primary_key=True), sa.Column("data_source", sa.String(24), nullable=False), sa.Column("created_at", sa.String(40), nullable=False), sa.Column("consent_version", sa.String(64)))
    op.create_table("facial_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("participant_id", sa.String(64), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_session_id", sa.String(64), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.String(40), nullable=False), sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False), sa.Column("data_source", sa.String(24), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("baseline_id", sa.String(36)), sa.Column("features", sa.JSON(), nullable=False), sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "client_session_id", name="uq_facial_client_session"))
    op.create_index("ix_facial_participant_time", "facial_sessions", ["participant_id", "recorded_at"])
    op.create_table("facial_baselines",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("participant_id", sa.String(64), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False), sa.Column("effective_at", sa.String(40), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data_source", sa.String(24), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False), sa.Column("summary", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "version", name="uq_baseline_version"),
        sa.UniqueConstraint("participant_id", "request_hash", name="uq_baseline_selection"))
    op.create_index("ix_baseline_participant_created", "facial_baselines", ["participant_id", "created_at"])
    op.create_table("facial_self_reports", sa.Column("session_id", sa.String(36), sa.ForeignKey("facial_sessions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("participant_id", sa.String(64), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False), sa.Column("created_at", sa.String(40), nullable=False), sa.Column("ratings", sa.JSON(), nullable=False))


def downgrade():
    # Only use deliberately on disposable demo databases: this deletes tables.
    for table in ("facial_self_reports", "facial_baselines", "facial_sessions", "participants"):
        op.drop_table(table)
