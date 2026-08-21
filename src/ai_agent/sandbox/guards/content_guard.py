"""ContentGuard - 内容守卫

扫描文本内容，检测恶意代码、注入攻击、敏感信息等。
"""
from __future__ import annotations

import re
from typing import NamedTuple

import structlog

logger = structlog.get_logger(__name__)


class ContentScanResult(NamedTuple):
    """内容扫描结果"""

    is_safe: bool
    """是否安全"""
    risk_level: str | None
    """风险等级：low/medium/high/critical"""
    issues: list[str]
    """发现的问题列表"""
    sanitized_content: str | None
    """净化后的内容（如果可净化）"""


class ContentGuard:
    """内容守卫

    功能：
    - 检测恶意代码模式
    - 检测 Prompt 注入
    - 检测敏感信息泄露
    - 可疑内容隔离
    """

    # 恶意代码模式
    MALICIOUS_PATTERNS = [
        # 代码执行
        r"__import__\s*\(",
        r"eval\s*\(",
        r"exec\s*\(",
        r"compile\s*\(",
        # 系统命令
        r"os\.system\s*\(",
        r"os\.popen\s*\(",
        r"subprocess\.",
        r"\[\s*\]",
        # 文件操作
        r"open\s*\([^)]*,\s*['\"]w['\"]",
        r"write\s*\(",
        r"shutil\.(rmtree|copy)",
        # 路径遍历
        r"\.\./",
        r"\.\.\\",
    ]

    # Prompt 注入模式
    INJECTION_PATTERNS = [
        # 角色扮演注入
        r"ignore\s+(previous|above|all)\s+(instructions?|rules?|constraints?)",
        r"(you\s+are\s+now|you\s+should\s+act\s+as)\s+(a\s+)?",
        # 系统提示注入
        r"(system|prompt|instruction)\s*:\s*",
        r"#\s*system\s*message",
        # 越狱提示
        r"(DAN|do\s+anything\s+now)",
        r"(jailbreak|bypass)",
        # 隐藏指令
        r"\[\s*INST\s*\]",
        r"<\|system\|>",
    ]

    # 敏感信息模式
    SENSITIVE_PATTERNS = [
        # API 密钥
        r"api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9]{20,}",
        r"secret[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9]{20,}",
        r"password\s*[:=]\s*['\"][^'\"]+['\"]",
        # 私钥
        r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
        r"-----BEGIN\s+EC\s+PRIVATE\s+KEY-----",
        # 数据库连接
        r"postgresql://[^\s]+:[^\s]+@",
        r"mysql://[^\s]+:[^\s]+@",
        r"mongodb://[^\s]+:[^\s]+@",
    ]

    def __init__(
        self,
        enable_malicious_scan: bool = True,
        enable_injection_scan: bool = True,
        enable_sensitive_scan: bool = True,
        quarantine_suspicious: bool = False,
    ):
        """初始化内容守卫

        Args:
            enable_malicious_scan: 是否扫描恶意代码
            enable_injection_scan: 是否扫描注入攻击
            enable_sensitive_scan: 是否扫描敏感信息
            quarantine_suspicious: 是否将可疑内容隔离
        """
        self._enable_malicious = enable_malicious_scan
        self._enable_injection = enable_injection_scan
        self._enable_sensitive = enable_sensitive_scan
        self._quarantine = quarantine_suspicious

        # 编译正则模式
        self._malicious_regex = [
            re.compile(p, re.IGNORECASE) for p in self.MALICIOUS_PATTERNS
        ]
        self._injection_regex = [
            re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS
        ]
        self._sensitive_regex = [
            re.compile(p, re.IGNORECASE) for p in self.SENSITIVE_PATTERNS
        ]

        logger.info(
            "content_guard.init",
            enable_malicious_scan=enable_malicious_scan,
            enable_injection_scan=enable_injection_scan,
            enable_sensitive_scan=enable_sensitive_scan,
            quarantine_suspicious=quarantine_suspicious,
        )

    def scan(self, content: str, content_type: str = "general") -> ContentScanResult:
        """扫描内容是否安全

        Args:
            content: 要扫描的内容
            content_type: 内容类型（skill/prompt/general）

        Returns:
            ContentScanResult: 扫描结果
        """
        if not content:
            return ContentScanResult(
                is_safe=True,
                risk_level=None,
                issues=[],
                sanitized_content="",
            )

        issues: list[str] = []
        risk_level = "low"

        # 1. 扫描恶意代码
        if self._enable_malicious:
            malicious_issues = self._detect_malicious(content)
            issues.extend(malicious_issues)

        # 2. 扫描注入攻击
        if self._enable_injection:
            injection_issues = self._detect_injection(content)
            issues.extend(injection_issues)

        # 3. 扫描敏感信息
        if self._enable_sensitive:
            sensitive_issues = self._detect_sensitive(content)
            issues.extend(sensitive_issues)

        # 4. 确定风险等级
        if any("critical" in i.lower() for i in issues):
            risk_level = "critical"
        elif any("high" in i.lower() for i in issues):
            risk_level = "high"
        elif any("medium" in i.lower() for i in issues):
            risk_level = "medium"
        elif issues:
            risk_level = "low"

        is_safe = len(issues) == 0

        # 5. 如果需要隔离且有问题，进行隔离处理
        sanitized = None
        if not is_safe and self._quarantine:
            sanitized = self._sanitize(content, issues)

        logger.info(
            "content_guard.scan",
            content_type=content_type,
            is_safe=is_safe,
            risk_level=risk_level,
            issue_count=len(issues),
        )

        return ContentScanResult(
            is_safe=is_safe,
            risk_level=risk_level if not is_safe else None,
            issues=issues,
            sanitized_content=sanitized,
        )

    def _detect_malicious(self, content: str) -> list[str]:
        """扫描恶意代码"""
        issues = []
        for pattern in self._malicious_regex:
            matches = pattern.findall(content)
            if matches:
                issues.append(
                    f"Malicious code pattern detected: {pattern.pattern[:30]}..."
                )
        return issues

    def _detect_injection(self, content: str) -> list[str]:
        """扫描注入攻击"""
        issues = []
        for pattern in self._injection_regex:
            matches = pattern.findall(content)
            if matches:
                issues.append(
                    f"Prompt injection pattern detected: {pattern.pattern[:30]}..."
                )
        return issues

    def _detect_sensitive(self, content: str) -> list[str]:
        """扫描敏感信息"""
        issues = []
        for pattern in self._sensitive_regex:
            matches = pattern.findall(content)
            if matches:
                issues.append(
                    f"Sensitive information detected: {pattern.pattern[:30]}..."
                )
        return issues

    def _sanitize(self, content: str, issues: list[str]) -> str:
        """净化内容（将敏感部分替换为标记）"""
        sanitized = content

        # 替换敏感信息
        for pattern in self._sensitive_regex:
            sanitized = pattern.sub("[REDACTED]", sanitized)

        return sanitized

    def is_safe(self, content: str) -> bool:
        """快速检查内容是否安全"""
        result = self.scan(content)
        return result.is_safe
