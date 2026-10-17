"""Add voice session features/results without altering existing C1 records."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("voice_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("participant_id", sa.String(64), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_session_id", sa.String(64), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False), sa.Column("recorded_at", sa.String(40)),
        sa.Column("data_source", sa.String(24), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("audio_sha256", sa.String(64), nullable=False), sa.Column("model_id", sa.String(80)),
        sa.Column("metadata_json", sa.JSON(), nullable=False), sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "client_session_id", name="uq_voice_client_session"))
    op.create_index("ix_voice_participant_created", "voice_sessions", ["participant_id", "created_at"])


def downgrade():
    op.drop_table("voice_sessions")
