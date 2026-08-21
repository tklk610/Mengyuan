"""SkillSandboxLoader - Skill 安全加载器

在沙箱环境中安全加载 Skill 文件。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, NamedTuple

import structlog
import yaml

from ai_agent.sandbox.core.sandbox import FileSandbox
from ai_agent.sandbox.guards.content_guard import ContentGuard
from ai_agent.sandbox.guards.path_guard import PathGuard

logger = structlog.get_logger(__name__)


class SkillLoadResult(NamedTuple):
    """Skill 加载结果"""

    success: bool
    """是否成功"""
    skill_data: dict | None
    """Skill 数据"""
    skill_path: str | None
    """Skill 路径"""
    error: str | None
    """错误信息"""
    was_quarantined: bool
    """是否被隔离"""


class SkillSandboxLoader:
    """Skill 安全加载器

    功能：
    - 沙箱保护的 Skill 目录
    - SKILL.md 内容扫描
    - frontmatter 验证
    - 签名验证（可选）
    """

    def __init__(
        self,
        sandbox: FileSandbox,
        content_guard: ContentGuard | None = None,
        verify_signature: bool = False,
        scan_before_load: bool = True,
        quarantine_suspicious: bool = True,
    ):
        """初始化 Skill 加载器

        Args:
            sandbox: 沙箱实例
            content_guard: 内容守卫（如果为 None，使用沙箱的）
            verify_signature: 是否验证签名
            scan_before_load: 加载前是否扫描内容
            quarantine_suspicious: 是否隔离可疑 Skill
        """
        self._sandbox = sandbox
        self._content_guard = content_guard or ContentGuard()
        self._verify_signature = verify_signature
        self._scan_before_load = scan_before_load
        self._quarantine_suspicious = quarantine_suspicious

        logger.info(
            "skill_loader.init",
            sandbox_root=sandbox.root_dir,
            verify_signature=verify_signature,
            scan_before_load=scan_before_load,
        )

    def load_skill(self, skill_path: str) -> SkillLoadResult:
        """安全加载 Skill

        Args:
            skill_path: Skill 目录或 SKILL.md 路径

        Returns:
            SkillLoadResult: 加载结果
        """
        try:
            # 1. 规范化路径
            if not skill_path.endswith("/SKILL.md") and not skill_path.endswith("\\SKILL.md"):
                skill_path = os.path.join(skill_path, "SKILL.md")

            # 2. 路径安全检查
            if not self._sandbox.is_path_safe(skill_path):
                logger.warning("skill_loader.path_denied", path=skill_path)
                return SkillLoadResult(
                    success=False,
                    skill_data=None,
                    skill_path=skill_path,
                    error=f"Path not allowed: {skill_path}",
                    was_quarantined=False,
                )

            # 3. 读取 Skill 内容
            import asyncio
            content = asyncio.run(self._sandbox.read(skill_path))

            if content is None:
                return SkillLoadResult(
                    success=False,
                    skill_data=None,
                    skill_path=skill_path,
                    error="Failed to read skill file",
                    was_quarantined=False,
                )

            # 4. 内容扫描
            if self._scan_before_load:
                scan_result = self._content_guard.scan(content)
                if not scan_result.is_safe:
                    logger.warning(
                        "skill_loader.content_unsafe",
                        path=skill_path,
                        risk_level=scan_result.risk_level,
                        issues=scan_result.issues,
                    )

                    if self._quarantine_suspicious:
                        # 隔离可疑 Skill
                        logger.warning("skill_loader.quarantine", path=skill_path)
                        return SkillLoadResult(
                            success=False,
                            skill_data=None,
                            skill_path=skill_path,
                            error=f"Skill quarantined: {', '.join(scan_result.issues)}",
                            was_quarantined=True,
                        )

            # 5. 解析 frontmatter
            skill_data = self._parse_frontmatter(content, skill_path)
            if skill_data is None:
                return SkillLoadResult(
                    success=False,
                    skill_data=None,
                    skill_path=skill_path,
                    error="Invalid SKILL.md format: missing frontmatter",
                    was_quarantined=False,
                )

            # 6. 签名验证（可选）
            if self._verify_signature:
                if not self._verify_skill_signature(skill_data, skill_path):
                    return SkillLoadResult(
                        success=False,
                        skill_data=None,
                        skill_path=skill_path,
                        error="Signature verification failed",
                        was_quarantined=False,
                    )

            logger.info("skill_loader.success", path=skill_path)
            return SkillLoadResult(
                success=True,
                skill_data=skill_data,
                skill_path=skill_path,
                error=None,
                was_quarantined=False,
            )

        except Exception as e:
            logger.error("skill_loader.error", path=skill_path, error=str(e))
            return SkillLoadResult(
                success=False,
                skill_data=None,
                skill_path=skill_path,
                error=str(e),
                was_quarantined=False,
            )

    def _parse_frontmatter(self, content: str, skill_path: str) -> dict | None:
        """解析 SKILL.md 的 frontmatter

        Args:
            content: 文件内容
            skill_path: 文件路径

        Returns:
            dict | None: 解析后的数据，失败返回 None
        """
        lines = content.split("\n")

        # 查找 frontmatter 边界
        if not lines[0].strip().startswith("---"):
            logger.warning("skill_loader.no_frontmatter", path=skill_path)
            return None

        # 找到结束标记
        end_idx = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip().startswith("---"):
                end_idx = i
                break

        if end_idx is None:
            logger.warning("skill_loader.unclosed_frontmatter", path=skill_path)
            return None

        # 解析 YAML
        yaml_content = "\n".join(lines[1:end_idx])
        try:
            frontmatter = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.error("skill_loader.yaml_error", path=skill_path, error=str(e))
            return None

        if not isinstance(frontmatter, dict):
            logger.warning("skill_loader.invalid_frontmatter", path=skill_path)
            return None

        # 验证必需字段
        if "name" not in frontmatter:
            logger.warning("skill_loader.missing_name", path=skill_path)
            return None

        if "description" not in frontmatter:
            logger.warning("skill_loader.missing_description", path=skill_path)
            return None

        # 返回完整数据
        return {
            "name": frontmatter.get("name", ""),
            "description": frontmatter.get("description", ""),
            "content": "\n".join(lines[end_idx + 1:]),
            "frontmatter": frontmatter,
            "skill_dir": str(Path(skill_path).parent.name),
        }

    def _verify_skill_signature(self, skill_data: dict, skill_path: str) -> bool:
        """验证 Skill 签名（预留接口）"""
        # TODO: 实现签名验证
        # 目前仅做占位
        return True

    def list_available_skills(self, skills_dir: str) -> list[str]:
        """列出可用的 Skills

        Args:
            skills_dir: Skills 目录路径

        Returns:
            list[str]: 可用 Skill 名称列表
        """
        if not self._sandbox.is_path_safe(skills_dir):
            return []

        import asyncio
        paths = self._sandbox.list_files(os.path.join(skills_dir, "*", "SKILL.md"))

        skills = []
        for path in paths:
            result = self.load_skill(str(path))
            if result.success and result.skill_data:
                skills.append(result.skill_data["name"])

        return skills
