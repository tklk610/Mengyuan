"""initial schema: users, projects, chapters

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-08-17

PoC 阶段核心业务表，对应 NOVEL_CRAFT_PROJECT_PLAN.md 第三节数据模型设计。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Enum 类型 ────────────────────────────────────────────────────────────
    genre_enum = postgresql.ENUM(
        "仙侠", "修仙", "奇幻", "悬疑", "言情", "科幻",
        name="genre",
        create_type=False,
    )
    genre_enum.create(op.get_bind(), checkfirst=True)

    project_status_enum = postgresql.ENUM(
        "创作中", "已完成", "已归档",
        name="project_status",
        create_type=False,
    )
    project_status_enum.create(op.get_bind(), checkfirst=True)

    chapter_status_enum = postgresql.ENUM(
        "草稿", "润色", "定稿",
        name="chapter_status",
        create_type=False,
    )
    chapter_status_enum.create(op.get_bind(), checkfirst=True)

    narrative_pov_enum = postgresql.ENUM(
        "第一人称", "第三人称", "全知视角",
        name="narrative_pov",
        create_type=False,
    )
    narrative_pov_enum.create(op.get_bind(), checkfirst=True)

    ending_pref_enum = postgresql.ENUM(
        "HE", "BE", "NE", "开放",
        name="ending_preference",
        create_type=False,
    )
    ending_pref_enum.create(op.get_bind(), checkfirst=True)

    pacing_enum = postgresql.ENUM(
        "快节奏", "中等", "慢热",
        name="pacing_preference",
        create_type=False,
    )
    pacing_enum.create(op.get_bind(), checkfirst=True)

    # ── Users ────────────────────────────────────────────────────────────────
    op.create_table(  # noqa: E501
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),  # noqa: E501
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),  # noqa: E501
        sa.Column("preferences", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── Projects ────────────────────────────────────────────────────────────
    op.create_table(  # noqa: E501
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),  # noqa: E501
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("genre", genre_enum, nullable=False),
        sa.Column("outline", postgresql.JSONB, nullable=True),
        sa.Column("style_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", project_status_enum, server_default="创作中", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),  # noqa: E501
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),  # noqa: E501
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    # ── Chapters ────────────────────────────────────────────────────────────
    op.create_table(  # noqa: E501
        "chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),  # noqa: E501
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", chapter_status_enum, server_default="草稿", nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),  # noqa: E501
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),  # noqa: E501
    )
    op.create_index("ix_chapters_project_id", "chapters", ["project_id"])
    op.create_index("ix_chapters_project_chapter", "chapters", ["project_id", "chapter_number"], unique=True)  # noqa: E501

    # ── StyleProfiles ────────────────────────────────────────────────────────
    op.create_table(  # noqa: E501
        "style_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),  # noqa: E501
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("genre_tags", postgresql.ARRAY(sa.String(32)), nullable=True),
        sa.Column("characteristics", postgresql.JSONB, nullable=True),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("sample_source", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),  # noqa: E501
    )
    op.create_index("ix_style_profiles_user_id", "style_profiles", ["user_id"])

    # ── NovelSamples ────────────────────────────────────────────────────────
    op.create_table(  # noqa: E501
        "novel_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),  # noqa: E501
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("author", sa.String(128), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunks", postgresql.JSONB, nullable=True),
        sa.Column("style_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("style_profiles.id", ondelete="SET NULL"), nullable=True),  # noqa: E501
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),  # noqa: E501
    )
    op.create_index("ix_novel_samples_user_id", "novel_samples", ["user_id"])
    op.create_index("ix_novel_samples_style_profile_id", "novel_samples", ["style_profile_id"])

    # ── UserPreferences ──────────────────────────────────────────────────────
    op.create_table(  # noqa: E501
        "user_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),  # noqa: E501
        sa.Column("narrative_pov", narrative_pov_enum, nullable=True),
        sa.Column("target_word_count", sa.Integer(), nullable=True),
        sa.Column("ending_preference", ending_pref_enum, nullable=True),
        sa.Column("pacing_preference", pacing_enum, nullable=True),
        sa.Column("avoid_elements", postgresql.ARRAY(sa.String(64)), nullable=True),
        sa.Column("preferred_tones", postgresql.ARRAY(sa.String(32)), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),  # noqa: E501
    )

    # ── Foreshadowing ───────────────────────────────────────────────────────
    op.create_table(  # noqa: E501
        "foreshadowing",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),  # noqa: E501
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("planted_chapter", sa.Integer(), nullable=False),
        sa.Column("expected_reveal_chapter", sa.Integer(), nullable=True),
        sa.Column("status", postgresql.ENUM("埋伏", "揭示", "遗忘", name="foreshadowing_status", create_type=False), server_default="埋伏", nullable=False),  # noqa: E501
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),  # noqa: E501
    )
    op.create_index("ix_foreshadowing_project_id", "foreshadowing", ["project_id"])


def downgrade() -> None:
    op.drop_table("foreshadowing")
    op.drop_table("user_preferences")
    op.drop_table("novel_samples")
    op.drop_table("style_profiles")
    op.drop_table("chapters")
    op.drop_table("projects")
    op.drop_table("users")

    # Drop enums
    from sqlalchemy.dialects import postgresql as pg
    bind = op.get_bind()
    reflect_enums = ["foreshadowing_status", "pacing_preference", "ending_preference",
                     "narrative_pov", "chapter_status", "project_status", "genre"]
    for enum_name in reflect_enums:
        enum_type = pg.ENUM(name=enum_name)
        enum_type.drop(bind, checkfirst=True)
