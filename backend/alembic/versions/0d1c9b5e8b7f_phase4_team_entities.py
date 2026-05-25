"""Phase 4 team entities

Revision ID: 0d1c9b5e8b7f
Revises: 9c3f5b2b7d1a
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0d1c9b5e8b7f"
down_revision = "9c3f5b2b7d1a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("plan", sa.String(), nullable=False, server_default="team"),
        sa.Column("seat_count", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("billing_status", sa.String(), nullable=True),
        sa.Column("branding_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_teams_owner_user_id"), "teams", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_teams_name"), "teams", ["name"], unique=False)

    op.create_table(
        "team_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", sa.Enum("admin", "member", "viewer", name="teamrole"), nullable=False, server_default="member"),
        sa.Column("status", sa.String(), nullable=False, server_default="invited"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_team_members_team_id"), "team_members", ["team_id"], unique=False)
    op.create_index(op.f("ix_team_members_email"), "team_members", ["email"], unique=False)
    op.create_index(op.f("ix_team_members_user_id"), "team_members", ["user_id"], unique=False)

    op.create_table(
        "collections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_collections_team_id"), "collections", ["team_id"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"], unique=False)
    op.create_index(op.f("ix_api_keys_team_id"), "api_keys", ["team_id"], unique=False)
    op.create_index(op.f("ix_api_keys_key_prefix"), "api_keys", ["key_prefix"], unique=False)

    op.create_table(
        "webhooks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("secret", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_webhooks_user_id"), "webhooks", ["user_id"], unique=False)
    op.create_index(op.f("ix_webhooks_team_id"), "webhooks", ["team_id"], unique=False)

    op.create_table(
        "sso_providers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_sso_providers_team_id"), "sso_providers", ["team_id"], unique=False)

    op.create_table(
        "student_verifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(), nullable=False, server_default="sheerid"),
        sa.Column("reference_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_student_verifications_user_id"), "student_verifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_student_verifications_user_id"), table_name="student_verifications")
    op.drop_table("student_verifications")

    op.drop_index(op.f("ix_sso_providers_team_id"), table_name="sso_providers")
    op.drop_table("sso_providers")

    op.drop_index(op.f("ix_webhooks_team_id"), table_name="webhooks")
    op.drop_index(op.f("ix_webhooks_user_id"), table_name="webhooks")
    op.drop_table("webhooks")

    op.drop_index(op.f("ix_api_keys_key_prefix"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_team_id"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_user_id"), table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index(op.f("ix_collections_team_id"), table_name="collections")
    op.drop_table("collections")

    op.drop_index(op.f("ix_team_members_user_id"), table_name="team_members")
    op.drop_index(op.f("ix_team_members_email"), table_name="team_members")
    op.drop_index(op.f("ix_team_members_team_id"), table_name="team_members")
    op.drop_table("team_members")
    op.execute("DROP TYPE IF EXISTS teamrole")

    op.drop_index(op.f("ix_teams_name"), table_name="teams")
    op.drop_index(op.f("ix_teams_owner_user_id"), table_name="teams")
    op.drop_table("teams")
