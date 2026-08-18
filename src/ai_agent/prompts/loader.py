"""Prompt Loader - YAML 模板加载器

遵循编码规范 §3.2:
- Prompt 必须外部化为 YAML 文件
- 版本号必填
- 业务代码只引用模板名
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ai_agent.config.settings import settings


class PromptLoader:
    """Prompt 模板加载器"""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self.prompts_dir = prompts_dir or settings.prompts_dir

    def load(self, template_name: str, version: int = 1) -> dict[str, Any]:
        """加载指定版本模板

        Args:
            template_name: 模板名称（不含版本号和扩展名）
            version: 版本号

        Returns:
            模板字典 {name, version, template, variables}

        Raises:
            FileNotFoundError: 模板不存在
        """
        template_path = self.prompts_dir / f"{template_name}_v{version}.yaml"
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        with open(template_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return data

    def render(
        self, template_name: str, version: int, variables: dict[str, Any]
    ) -> str:
        """加载并渲染模板

        Args:
            template_name: 模板名称
            version: 版本号
            variables: 变量字典

        Returns:
            渲染后的模板字符串
        """
        template_data = self.load(template_name, version)
        template_str = template_data["template"]

        # 简单变量替换（支持 {{variable}} 语法）
        for key, value in variables.items():
            template_str = template_str.replace(f"{{{{{key}}}}}", str(value))

        return template_str

    def load_genre_guide(self, genre: str) -> str:
        """加载题材风格指南

        Args:
            genre: 题材名称

        Returns:
            风格指南字符串
        """
        guide_path = self.prompts_dir / "genre_guides.yaml"
        with open(guide_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return data["content"].get(genre, data["content"]["仙侠"])


# 全局单例
prompt_loader = PromptLoader()
