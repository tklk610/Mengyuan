"""NovelCraft Configuration - PoC Version

PoC 阶段使用 pydantic-settings + 环境变量
生产环境需切换到 Vault/AWS Secret Manager
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === 应用基础 ===
    app_name: str = "NovelCraft"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # === LLM 配置 ===
    llm_provider: Literal["minimax", "openai", "anthropic"] = "minimax"
    minimax_api_key: str = Field(default="", alias="MINMAX_API_KEY")
    minimax_model: str = "MiniMax-Text-01"
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = "claude-sonnet-4-20250514"

    # LLM 调用参数
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 120

    # === API 配置 ===
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    # === Deep Agents 配置 ===
    deep_agents_skills_dir: str = "./skills"
    deep_agents_interrupt_on_write: bool = True

    # === Redis 配置（LangGraph Checkpointer）===
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # === Qdrant 配置（向量数据库 - 风格特征存储）===
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_collection: str = Field(default="novelcraft_styles", alias="QDRANT_COLLECTION")

    # === JWT Auth ===
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_expire_hours: int = 24

    # === 项目路径 ===
    project_root: Path = Path(__file__).parent.parent.parent.parent
    prompts_dir: Path = Path(__file__).parent.parent / "prompts" / "templates"


settings = Settings()
