"""initial schema (unified)

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-25 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role = sa.Enum("admin", "author", name="user_role")
pi_status = sa.Enum(
    "draft",
    "awaiting_authors",
    "awaiting_signatures",
    "awaiting_corrections",
    "completed",
    name="pi_status",
)
pi_author_status = sa.Enum("pending", "completed", name="pi_author_status")
pi_type = sa.Enum(
    "software",
    "patente",
    "desenho_industrial",
    "marca",
    "cultivar",
    "topografia",
    "outro",
    name="pi_type",
)
ifms_bond = sa.Enum("servidor", "estudante", "outros", name="ifms_bond")
document_type = sa.Enum(
    "anexo_i",
    "anexo_ii",
    "anexo_iii",
    "anexo_iv",
    "anexo_v",
    "registro_marca",
    name="document_type",
)
author_document_type = sa.Enum("cpf", "rg", name="author_document_type")
notification_type = sa.Enum("new_pi", "correction_submitted", name="notification_type")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="author"),
        sa.Column("google_sub", sa.String(255), nullable=True),
        sa.Column("picture", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("google_sub", name="uq_users_google_sub"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "application_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.UniqueConstraint("code", name="uq_application_fields_code"),
    )
    op.create_index("ix_application_fields_code", "application_fields", ["code"])

    op.create_table(
        "program_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.UniqueConstraint("code", name="uq_program_types_code"),
    )
    op.create_index("ix_program_types_code", "program_types", ["code"])

    op.create_table(
        "pis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("type", pi_type, nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", pi_status, nullable=False, server_default="awaiting_authors"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("programming_language", sa.String(255), nullable=True),
        sa.Column("creation_date", sa.Date(), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("source_hash", sa.String(512), nullable=True),
        sa.Column("is_derived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("derived_title", sa.String(500), nullable=True),
        sa.Column("derived_registration", sa.String(255), nullable=True),
        sa.Column("video_path", sa.String(512), nullable=True),
        sa.Column("video_original_filename", sa.String(255), nullable=True),
        sa.Column("source_code_path", sa.String(512), nullable=True),
        sa.Column("source_code_original_filename", sa.String(255), nullable=True),
        sa.Column("brand_name", sa.String(255), nullable=True),
        sa.Column("brand_type", sa.String(50), nullable=True),
        sa.Column("brand_image_path", sa.String(512), nullable=True),
        sa.Column("brand_image_original_filename", sa.String(255), nullable=True),
        sa.Column("brand_has_foreign_language", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("brand_foreign_term", sa.String(255), nullable=True),
        sa.Column("brand_translation", sa.String(255), nullable=True),
        sa.Column("brand_collision_terms", sa.Text(), nullable=True),
        sa.Column("brand_nice_classification", sa.String(255), nullable=True),
        sa.Column("brand_vienna_classification", sa.String(255), nullable=True),
        sa.Column("brand_protection_requested", sa.Boolean(), nullable=True),
        sa.Column("brand_protection_justification", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "pi_application_fields",
        sa.Column("pi_id", sa.Integer(), sa.ForeignKey("pis.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "application_field_id",
            sa.Integer(),
            sa.ForeignKey("application_fields.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "pi_program_types",
        sa.Column("pi_id", sa.Integer(), sa.ForeignKey("pis.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "program_type_id",
            sa.Integer(),
            sa.ForeignKey("program_types.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "pi_institutions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pi_id", sa.Integer(), sa.ForeignKey("pis.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_ifms", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("cnpj", sa.String(32), nullable=True),
        sa.Column("contact", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_pi_institutions_pi_id", "pi_institutions", ["pi_id"])

    op.create_table(
        "pi_authors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pi_id", sa.Integer(), sa.ForeignKey("pis.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "institution_id",
            sa.Integer(),
            sa.ForeignKey("pi_institutions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", pi_author_status, nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("pi_id", "email", name="uq_pi_author_email"),
    )
    op.create_index("ix_pi_authors_email", "pi_authors", ["email"])

    op.create_table(
        "author_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pi_author_id",
            sa.Integer(),
            sa.ForeignKey("pi_authors.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("cpf", sa.String(20), nullable=False),
        sa.Column("rg", sa.String(30), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("nationality", sa.String(80), nullable=False),
        sa.Column("marital_status", sa.String(40), nullable=False),
        sa.Column("occupation", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("cellphone", sa.String(30), nullable=False),
        sa.Column("address_street", sa.String(200), nullable=False),
        sa.Column("address_number", sa.String(20), nullable=False),
        sa.Column("address_district", sa.String(120), nullable=False),
        sa.Column("address_city", sa.String(120), nullable=False),
        sa.Column("address_state", sa.String(2), nullable=False),
        sa.Column("address_zip", sa.String(15), nullable=False),
        sa.Column("ifms_bond", ifms_bond, nullable=False),
        sa.Column("ifms_bond_other", sa.String(255), nullable=True),
        sa.Column("campus", sa.String(50), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pi_author_id", sa.Integer(), sa.ForeignKey("pi_authors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(96), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token", name="uq_invitations_token"),
    )
    op.create_index("ix_invitations_token", "invitations", ["token"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pi_id", sa.Integer(), sa.ForeignKey("pis.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", document_type, nullable=False),
        sa.Column("pdf_path", sa.String(512), nullable=False),
        sa.Column("pi_author_id", sa.Integer(), sa.ForeignKey("pi_authors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_signed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("signed_file_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "author_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pi_author_id", sa.Integer(), sa.ForeignKey("pi_authors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", author_document_type, nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pi_author_id", "type", name="uq_author_documents_author_type"),
    )
    op.create_index("ix_author_documents_pi_author_id", "author_documents", ["pi_author_id"])

    op.create_table(
        "admin_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pi_id", sa.Integer(), sa.ForeignKey("pis.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_notifications_is_read", "admin_notifications", ["is_read"])


def downgrade() -> None:
    op.drop_index("ix_admin_notifications_is_read", table_name="admin_notifications")
    op.drop_table("admin_notifications")
    op.drop_index("ix_author_documents_pi_author_id", table_name="author_documents")
    op.drop_table("author_documents")
    op.drop_table("documents")
    op.drop_index("ix_invitations_token", table_name="invitations")
    op.drop_table("invitations")
    op.drop_table("author_profiles")
    op.drop_index("ix_pi_authors_email", table_name="pi_authors")
    op.drop_table("pi_authors")
    op.drop_index("ix_pi_institutions_pi_id", table_name="pi_institutions")
    op.drop_table("pi_institutions")
    op.drop_table("pi_program_types")
    op.drop_table("pi_application_fields")
    op.drop_table("pis")
    op.drop_index("ix_program_types_code", table_name="program_types")
    op.drop_table("program_types")
    op.drop_index("ix_application_fields_code", table_name="application_fields")
    op.drop_table("application_fields")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    for enum in (
        notification_type,
        author_document_type,
        document_type,
        ifms_bond,
        pi_type,
        pi_author_status,
        pi_status,
        user_role,
    ):
        enum.drop(bind, checkfirst=True)
