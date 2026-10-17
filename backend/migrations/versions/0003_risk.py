"""Longitudinal observations and immutable prediction snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    for kind in ("daily", "weekly"):
        name = f"risk_{kind}"
        op.create_table(name,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("participant_id", sa.String(64), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("client_record_id", sa.String(64), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("data_source", sa.String(24), nullable=False), sa.Column("observed_on", sa.String(10), nullable=False),
            sa.Column("reported_at", sa.String(40), nullable=False), sa.Column("ingested_at", sa.String(40), nullable=False), sa.Column("payload", sa.JSON(), nullable=False),
            sa.UniqueConstraint("participant_id", "observed_on", name=f"uq_risk_{kind}_date"), sa.UniqueConstraint("participant_id", "client_record_id", name=f"uq_risk_{kind}_client"))
        op.create_index(f"ix_risk_{kind}_time", name, ["participant_id", "observed_on"])
    op.create_table("risk_predictions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("participant_id", sa.String(64), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_prediction_id", sa.String(64), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False), sa.Column("as_of", sa.String(40), nullable=False), sa.Column("data_source", sa.String(24), nullable=False),
        sa.Column("model_id", sa.String(80)), sa.Column("status", sa.String(40), nullable=False), sa.Column("snapshot_hash", sa.String(64), nullable=False), sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "client_prediction_id", name="uq_risk_prediction_client"))
    op.create_index("ix_risk_prediction_time", "risk_predictions", ["participant_id", "created_at"])


def downgrade():
    for name in ("risk_predictions", "risk_weekly", "risk_daily"):
        op.drop_table(name)
