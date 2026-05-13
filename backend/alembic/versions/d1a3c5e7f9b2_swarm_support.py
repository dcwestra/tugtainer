"""swarm support

Revision ID: d1a3c5e7f9b2
Revises: b9034fe596ee
Create Date: 2026-05-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1a3c5e7f9b2"
down_revision: str | Sequence[str] | None = "b9034fe596ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("hosts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "host_type",
                sa.String(),
                nullable=False,
                default="standalone",
                server_default=sa.text("'standalone'"),
            )
        )
        batch_op.add_column(
            sa.Column("swarm_cluster_id", sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("swarm_cluster_name", sa.String(), nullable=True)
        )

    op.create_table(
        "swarm_services",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("swarm_cluster_id", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False, index=True),
        sa.Column(
            "check_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("(FALSE)"),
        ),
        sa.Column(
            "update_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("(FALSE)"),
        ),
        sa.Column(
            "update_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("(FALSE)"),
        ),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column(
            "modified_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            server_onupdate=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column("image_id", sa.String(), nullable=True),
        sa.Column("local_digests", sa.JSON(), nullable=True),
        sa.Column("remote_digests", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("swarm_services")
    with op.batch_alter_table("hosts", schema=None) as batch_op:
        batch_op.drop_column("swarm_cluster_name")
        batch_op.drop_column("swarm_cluster_id")
        batch_op.drop_column("host_type")
