"""Add billing customers table

Revision ID: 9c3f5b2b7d1a
Revises: 405427add0df
Create Date: 2026-05-22 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c3f5b2b7d1a"
down_revision: Union[str, Sequence[str], None] = "405427add0df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("plan", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_customer_id"),
    )
    op.create_index(op.f("ix_billing_customers_user_id"), "billing_customers", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_billing_customers_stripe_customer_id"),
        "billing_customers",
        ["stripe_customer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_billing_customers_stripe_customer_id"), table_name="billing_customers")
    op.drop_index(op.f("ix_billing_customers_user_id"), table_name="billing_customers")
    op.drop_table("billing_customers")
