"""Add isolated C4 synthetic-context snapshots; preserve all earlier tables."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("intervention_demo_contexts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("participant_id", sa.String(64), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_update_id", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("data_source", sa.String(24), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.String(40), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "client_update_id", name="uq_intervention_demo_client"))


def downgrade():
    op.drop_table("intervention_demo_contexts")
