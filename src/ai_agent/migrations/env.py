"""Alembic migration environment.

配置说明：
- sqlalchemy.url 默认从 alembic.ini 读取，可被环境变量 DATABASE_URL 覆盖
- target_metadata 用于 autogenerate 迁移（模型变更时自动生成 diff）
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Engine

# 从环境变量覆盖 alembic.ini 中的数据库 URL
# 格式: postgresql://user:pass@host:port/dbname
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    context.config.set_main_option("sqlalchemy.url", _db_url)

# Interpret the config file for Python logging.
if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

# target_metadata 用于 autogenerate 支持。
# 当 ai_agent.models 下的 ORM 模型定义好后，在此导入 Base.metadata。
# 目前 PoC 阶段模型为空目录，设为 None，手动编写迁移脚本。
try:
    from ai_agent.models.orm import Base  # type: ignore[attr-defined]

    target_metadata = Base.metadata
except ImportError:
    target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (无需 DB 连接)."""
    url = context.config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable: Engine = engine_from_config(
        context.config.get_section(context.config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
