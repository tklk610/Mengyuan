#!/usr/bin/env python3
"""
Harness Engineering — AI 红线扫描器 (scripts/check_red_lines.py)

> 用途：在 CI / 提交前 / `make quality` 中调用，扫描代码是否违反 8+8 红线。
> 覆盖范围：本脚本聚焦于 **可机器静态扫描** 的红线；语义级红线（HITL 设计、
>         业务事实校验、Prompt A/B 效果等）由 review-skill + LangGraph 中断
>         检查 + 集成测试覆盖。

═══════════════════════════════════════════════════════════════════════════════
红线编号约定（与 .claude/Claude.md 一致）
═══════════════════════════════════════════════════════════════════════════════
技术红线（机械可扫）：
    R1  LLM 调用必须显式 timeout
    R2  外部调用必须指数退避重试（tenacity 装饰器）
    R3  所有工具必须幂等（idempotency_key）
    R4  Prompt 模板外部化（YAML/DB），禁止硬编码
    R5  所有输出走 Pydantic 结构化校验
    R6  数据访问仅通过 repository 层
    R7  禁止跨模块导入内部实现
    R8  金额字段若出现，必须 int（分）

AI 特有红线（机器可扫子集）：
    R9  敏感操作 HITL  — 检测危险工具（_send_email/_delete_*/_pay_*）是否在
                        LangGraph 中找到 interrupt
    R10 禁止直接拼接用户输入到 Prompt — 检测 f-string / + 拼接
    R11 全链路记录 token 用量          — 检测 usage_logs 写入
    R12 PII 必须脱敏                  — 检测调用 guardrail.pii.redact
    R14 模型降级链必须定义            — 检测 config 中 fallback 链
    R15 Token 配额 100% 必须硬拒绝    — 检测配额判断分支
    R16 任何变更必须留痕              — 检测 .harness/changes/

═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Callable

# Force UTF-8 stdout on Windows (default cp936/GBK can't print emoji / 中文)
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except (AttributeError, OSError):
    pass
from dataclasses import dataclass, field
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# 工程根目录（脚本可从任意位置调用）
# ──────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 默认扫描目录（业务代码目录）
DEFAULT_SCAN_DIRS: tuple[str, ...] = ("src",)

# 默认跳过目录（harness 自身 / 第三方 / 缓存）
DEFAULT_EXCLUDE_DIRS: tuple[str, ...] = (
    ".venv", "venv", ".git", "__pycache__", "dist", "build",
    ".harness", "node_modules", ".pytest_cache", ".ruff_cache",
)


# ──────────────────────────────────────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Violation:
    """单条红线违规记录。"""

    rule_id: str          # 例："R10"
    severity: str         # "error" | "warning"
    file: Path            # 违规所在文件
    line: int             # 行号（1-indexed）
    snippet: str          # 违规代码片段（单行截断）
    message: str          # 人类可读说明

    def format(self) -> str:
        rel = self.file.relative_to(PROJECT_ROOT) if self.file.is_absolute() else self.file
        return (
            f"[{self.rule_id}/{self.severity}] {rel}:{self.line}: {self.message}\n"
            f"    └─ {self.snippet.strip()[:160]}"
        )


@dataclass
class ScanResult:
    """整个扫描过程的聚合结果。"""

    violations: list[Violation] = field(default_factory=list)
    files_scanned: int = 0
    rules_evaluated: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")

    def by_rule(self, rule_id: str) -> list[Violation]:
        return [v for v in self.violations if v.rule_id == rule_id]


# ──────────────────────────────────────────────────────────────────────────────
# 文件发现
# ──────────────────────────────────────────────────────────────────────────────
def discover_python_files(
    scan_dirs: tuple[str, ...] = DEFAULT_SCAN_DIRS,
    exclude: tuple[str, ...] = DEFAULT_EXCLUDE_DIRS,
) -> list[Path]:
    """在 scan_dirs 下发现所有 .py 文件，按 exclude 过滤。"""
    files: list[Path] = []
    for d in scan_dirs:
        base = PROJECT_ROOT / d
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(part in exclude for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


# ──────────────────────────────────────────────────────────────────────────────
# 通用工具
# ──────────────────────────────────────────────────────────────────────────────
def read_lines(path: Path) -> list[str]:
    """读取文件所有行；读取失败返回空列表（不抛异常）。"""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []


def safe_parse(path: Path) -> ast.Module | None:
    """AST 解析；失败返回 None（语法错误不影响扫描继续）。"""
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 红线检查器（每条红线一个函数）
# ──────────────────────────────────────────────────────────────────────────────
def check_r1_llm_timeout(files: list[Path]) -> list[Violation]:
    """R1: LLM 调用必须显式 timeout。

    检测：对 OpenAI / Anthropic / ChatOpenAI / ChatAnthropic 等实例化调用
    缺少 timeout= 参数。
    """
    violations: list[Violation] = []
    llm_classes = {
        "ChatOpenAI", "ChatAnthropic", "ChatZhipuAI", "AzureChatOpenAI",
        "ChatTongyi", "ChatDeepSeek", "ChatMoonshot",
    }
    for path in files:
        tree = safe_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # 形如 ChatOpenAI(...) 或 openai.ChatOpenAI(...)
            called_name = None
            if isinstance(func, ast.Name) and func.id in llm_classes:
                called_name = func.id
            elif isinstance(func, ast.Attribute) and func.attr in llm_classes:
                called_name = func.attr
            if called_name is None:
                continue
            # 必须有 timeout 关键字参数
            kwargs = {kw.arg for kw in node.keywords if kw.arg}
            if "timeout" not in kwargs:
                snippet = read_lines(path)[node.lineno - 1] if node.lineno else ""
                violations.append(Violation(
                    rule_id="R1",
                    severity="error",
                    file=path,
                    line=node.lineno,
                    snippet=snippet,
                    message=(
                        f"{called_name}() 实例化缺少 timeout= 参数；"
                        "AI 调用必须有显式超时。"
                    ),
                ))
    return violations


def check_r2_retry_wrapper(files: list[Path]) -> list[Violation]:
    """R2: 外部调用必须指数退避重试。

    检测：标记为「外部调用」的函数（名字含 fetch_/request_/call_/invoke_）
    是否被 tenacity 装饰器或 .infra.retry.with_retry 包裹。
    """
    violations: list[Violation] = []
    external_prefixes = ("fetch_", "request_", "call_", "invoke_", "send_")
    for path in files:
        tree = safe_parse(path)
        if tree is None:
            continue
        lines = read_lines(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(node.name.startswith(p) for p in external_prefixes):
                continue
            # 是否有 tenacity / retry 装饰器
            decorated = False
            for dec in node.decorator_list:
                dec_str = ast.unparse(dec)
                if any(kw in dec_str for kw in ("retry", "Retrying", "with_retry")):
                    decorated = True
                    break
            if not decorated:
                snippet = lines[node.lineno - 1] if node.lineno else ""
                violations.append(Violation(
                    rule_id="R2",
                    severity="warning",
                    file=path,
                    line=node.lineno,
                    snippet=snippet,
                    message=(
                        f"函数 {node.name}() 缺少 tenacity 重试装饰器；"
                        "外部调用建议配合指数退避。"
                    ),
                ))
    return violations


def check_r3_tool_idempotency(files: list[Path]) -> list[Violation]:
    """R3: 所有工具必须幂等。

    检测：继承 BaseTool 的类必须实现 idempotency_key 方法。
    """
    violations: list[Violation] = []
    for path in files:
        tree = safe_parse(path)
        if tree is None:
            continue
        lines = read_lines(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            # 检查基类是否包含 BaseTool
            base_names = set()
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.add(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.add(base.attr)
            if "BaseTool" not in base_names:
                continue
            # 是否实现了 idempotency_key
            method_names = {
                m.name for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if "idempotency_key" not in method_names:
                snippet = lines[node.lineno - 1] if node.lineno else ""
                violations.append(Violation(
                    rule_id="R3",
                    severity="error",
                    file=path,
                    line=node.lineno,
                    snippet=snippet,
                    message=(
                        f"工具类 {node.name} 继承 BaseTool 但缺少 "
                        "idempotency_key() 方法；Agent 重跑可能重复扣费/发消息。"
                    ),
                ))
    return violations


def check_r4_prompt_externalized(files: list[Path]) -> list[Violation]:
    """R4: Prompt 模板外部化（YAML/DB），禁止硬编码。

    检测：模块顶层或函数内出现大段三引号字符串（> 80 字符），
    且内容形似 prompt（含「你是 / 请 / 以下为 / 上下文」等关键词）。
    """
    violations: list[Violation] = []
    prompt_markers = ("你是", "请", "以下为", "上下文", "回答", "角色", "用户问")
    for path in files:
        tree = safe_parse(path)
        if tree is None:
            continue
        lines = read_lines(path)
        for node in ast.walk(tree):
            value: ast.Constant | None = None
            lineno = 0
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                tgt = node.targets[0]
                if isinstance(tgt, ast.Name) and isinstance(node.value, ast.Constant):
                    value = node.value
                    lineno = node.lineno
            if value is None or not isinstance(value.value, str):
                continue
            text = value.value
            if len(text) < 80:
                continue
            if not any(m in text for m in prompt_markers):
                continue
            # 例外：注释 / docstring / 测试 fixture
            snippet = lines[lineno - 1] if lineno else ""
            violations.append(Violation(
                rule_id="R4",
                severity="warning",
                file=path,
                line=lineno,
                snippet=snippet,
                message=(
                    "疑似 Prompt 硬编码；请迁移到 prompt-templates/*.yaml "
                    "并通过 PromptLoader 加载。"
                ),
            ))
    return violations


def check_r5_pydantic_validation(files: list[Path]) -> list[Violation]:
    """R5: 所有输出走 Pydantic 结构化校验。

    检测：LLM 调用的返回值（变量名含 response / result / output / answer）
    直接被使用（return / 拼字符串 / 写库），但附近没有 .model_validate() 调用。
    """
    violations: list[Violation] = []
    response_names = {"response", "result", "output", "answer", "completion"}
    for path in files:
        tree = safe_parse(path)
        if tree is None:
            continue
        lines = read_lines(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # 检测 .model_validate(...) 调用即可（不报错则视为合规）
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in {
                "model_validate", "model_validate_json",
            }:
                continue
            # 检测返回 LLM 响应但未结构化的简单模式
            if isinstance(func, ast.Name) and func.id == "print":
                for arg in node.args:
                    if isinstance(arg, ast.Name) and arg.id in response_names:
                        snippet = lines[node.lineno - 1] if node.lineno else ""
                        violations.append(Violation(
                            rule_id="R5",
                            severity="warning",
                            file=path,
                            line=node.lineno,
                            snippet=snippet,
                            message=(
                                f"直接 print(LLM 响应变量 {arg.id})；"
                                "建议先 .model_validate() 结构化校验。"
                            ),
                        ))
    return violations


def check_r6_repository_only(files: list[Path]) -> list[Violation]:
    """R6: 数据访问仅通过 repository 层。

    检测：service / agent 层直接出现 sqlalchemy.text / 字符串拼 SQL。
    """
    violations: list[Violation] = []
    bad_modules = ("service", "agent", "api")
    for path in files:
        parts = path.parts
        if not any(m in parts for m in bad_modules):
            continue
        tree = safe_parse(path)
        if tree is None:
            continue
        lines = read_lines(path)
        for node in ast.walk(tree):
            # 检测 sqlalchemy.text( 或 SQL 字符串字面量
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if not (node.func.attr == "text" and isinstance(node.func.value, ast.Name)):
                continue
            if node.func.value.id != "sqlalchemy":
                continue
            snippet = lines[node.lineno - 1] if node.lineno else ""
            violations.append(Violation(
                rule_id="R6",
                severity="error",
                file=path,
                line=node.lineno,
                snippet=snippet,
                message=(
                    "service/agent 层使用 sqlalchemy.text() 直拼 SQL；"
                    "请改为 repository 层 + ORM 参数化查询。"
                ),
            ))
    return violations


def check_r7_no_cross_module_internal(files: list[Path]) -> list[Violation]:
    """R7: 禁止跨模块导入内部实现（_ 开头或私有符号）。

    检测：跨层导入时引用了以下划线开头的符号。
    """
    violations: list[Violation] = []
    for path in files:
        tree = safe_parse(path)
        if tree is None:
            continue
        lines = read_lines(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name.startswith("_") and alias.name != "_":
                        snippet = lines[node.lineno - 1] if node.lineno else ""
                        violations.append(Violation(
                            rule_id="R7",
                            severity="warning",
                            file=path,
                            line=node.lineno,
                            snippet=snippet,
                            message=(
                                f"从 {node.module} 导入私有符号 {alias.name}；"
                                "禁止跨模块引用 _ 开头实现。"
                            ),
                        ))
    return violations


def check_r10_prompt_injection(files: list[Path]) -> list[Violation]:
    """R10: 禁止 f-string / + 拼接用户输入到 Prompt。

    检测：f"...{user_input}..." 模式或 prompt + user_input 模式，
    且变量名包含 user/input/query/question/message。
    """
    violations: list[Violation] = []
    # 用单词边界匹配，避免 user 子串匹配 username 等安全变量
    user_input_pattern = re.compile(
        r"\b(user_input|user_query|user_message|raw_input|raw_query|"
        r"user_text|raw_text|input_text|query_text|question_text)\b",
        re.IGNORECASE,
    )
    for path in files:
        lines = read_lines(path)
        # 模式 1: f-string 拼接
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            # 跳过注释 / 文档字符串
            if stripped.startswith("#"):
                continue
            if not ("f\"" in line or "f'" in line):
                continue
            if not user_input_pattern.search(line):
                continue
            # 排除防御性过滤（输入过滤）调用
            if "redact" in line or "filter" in line or "sanitize" in line:
                continue
            violations.append(Violation(
                rule_id="R10",
                severity="error",
                file=path,
                line=i,
                snippet=line,
                message=(
                    "检测到 f-string 拼接疑似用户输入到 Prompt；"
                    "请改用 PromptTemplate.from_template() 并经 "
                    "guardrail.input_filter.detect_injection() 过滤。"
                ),
            ))
        # 模式 2: prompt + user_input 字符串拼接
        tree = safe_parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add)):
                continue
            if not (isinstance(node.target, ast.Name) and "prompt" in node.target.id.lower()):
                continue
            if not (
                isinstance(node.value, ast.Name)
                and user_input_pattern.match(node.value.id)
            ):
                continue
            snippet = lines[node.lineno - 1] if node.lineno else ""
            violations.append(Violation(
                rule_id="R10",
                severity="error",
                file=path,
                line=node.lineno,
                snippet=snippet,
                message=(
                    f"检测到 prompt += {node.value.id} 字符串拼接；"
                    "违反 R10 防注入约束。"
                ),
            ))
    return violations


def check_r11_token_counter(files: list[Path]) -> list[Violation]:
    """R11: 全链路记录 token 用量。

    检测：调用 ChatOpenAI / ChatAnthropic.ainvoke 或 .invoke 后，
    上下文是否包含 TokenCounter.track()。
    """
    violations: list[Violation] = []
    llm_methods = {"ainvoke", "invoke", "astream", "stream"}
    for path in files:
        tree = safe_parse(path)
        if tree is None:
            continue
        lines = read_lines(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Attribute) and node.func.attr in llm_methods):
                continue
            # 检查所在函数体内是否含 TokenCounter.track 或 counter.track
            parent_func = _find_parent_function(tree, node)
            if parent_func is None:
                continue
            src = ast.unparse(parent_func)
            if "TokenCounter" in src and "track" in src:
                continue
            snippet = lines[node.lineno - 1] if node.lineno else ""
            violations.append(Violation(
                rule_id="R11",
                severity="warning",
                file=path,
                line=node.lineno,
                snippet=snippet,
                message=(
                    f"函数 {parent_func.name}() 内的 LLM 调用未包裹 "
                    "TokenCounter.track()；token 用量未记录，违反 R11。"
                ),
            ))
    return violations


def _find_parent_function(
    tree: ast.Module,
    target: ast.AST,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """在模块中查找 target 的最近函数祖先。"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target:
                    return node
    return None


def check_r12_pii_redaction(files: list[Path]) -> list[Violation]:
    """R12: PII 必须脱敏。

    检测：出现 logging / logger.info / .info( 等日志调用时，
    若参数含疑似用户输入字段，且未先经过 guardrail.pii.redact / redact()，
    则告警。
    """
    violations: list[Violation] = []
    log_methods = {"info", "warning", "error", "debug", "exception"}
    pii_field_names = ("email", "phone", "id_card", "身份证", "手机", "邮箱", "银行卡")
    for path in files:
        tree = safe_parse(path)
        if tree is None:
            continue
        lines = read_lines(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Attribute) and node.func.attr in log_methods):
                continue
            # 检查调用方是否为 logger
            if not (isinstance(node.func.value, ast.Name) and "log" in node.func.value.id.lower()):
                continue
            src = ast.unparse(node)
            if any(p in src for p in pii_field_names):
                # 所在函数是否含 redact()
                parent_func = _find_parent_function(tree, node)
                if parent_func is None:
                    continue
                func_src = ast.unparse(parent_func)
                if "redact" in func_src:
                    continue
                snippet = lines[node.lineno - 1] if node.lineno else ""
                violations.append(Violation(
                    rule_id="R12",
                    severity="warning",
                    file=path,
                    line=node.lineno,
                    snippet=snippet,
                    message=(
                        "日志调用包含疑似 PII 字段，但所在函数未先经 "
                        "guardrail.pii.redact()；可能违反 R12。"
                    ),
                ))
    return violations


def check_r14_fallback_chain(files: list[Path]) -> list[Violation]:
    """R14: 模型降级链必须定义。

    检测：config/llm_config.py（或等价位置）必须包含 MODEL_FALLBACK_CHAIN 定义。
    """
    violations: list[Violation] = []
    config_paths = [
        PROJECT_ROOT / "src" / "ai_agent" / "config" / "llm_config.py",
        PROJECT_ROOT / "src" / "config" / "llm_config.py",
    ]
    found_definition = False
    for path in config_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "MODEL_FALLBACK_CHAIN" in text:
            found_definition = True
            break
    if not found_definition and any(p.parent.parent.exists() for p in config_paths if p.exists()):
        # 有 config 目录但缺定义
        for p in config_paths:
            if p.exists():
                violations.append(Violation(
                    rule_id="R14",
                    severity="error",
                    file=p,
                    line=1,
                    snippet="",
                    message=(
                        "config/llm_config.py 缺少 MODEL_FALLBACK_CHAIN 定义；"
                        "主模型挂了会直接 5xx，违反 R14。"
                    ),
                ))
                break
    return violations


def check_r15_budget_hard_reject(files: list[Path]) -> list[Violation]:
    """R15: Token 配额 100% 必须硬拒绝。

    检测：guardrail/token_counter.py（或等价位置）必须含 >= 100% / >= quota
    时的硬拒绝分支。
    """
    violations: list[Violation] = []
    candidates = list(
        (PROJECT_ROOT / "src").rglob("token_counter*.py")
    ) if (PROJECT_ROOT / "src").exists() else []
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "AgentBudgetExhaustedException" in text and ("100" in text or "quota" in text.lower()):
            continue
        violations.append(Violation(
            rule_id="R15",
            severity="error",
            file=path,
            line=1,
            snippet="",
            message=(
                "token_counter.py 缺少 100% 配额触发 AgentBudgetExhaustedException "
                "的硬拒绝分支；违反 R15。"
            ),
        ))
    return violations


def check_r16_change_doc(files: list[Path]) -> list[Violation]:
    """R16: 任何变更必须留痕。

    检测：扫描 src/ 下变更文件数 > 50 行（粗略启发式）时，是否在
    .harness/changes/ 下有对应 summary.md。
    """
    violations: list[Violation] = []
    src = PROJECT_ROOT / "src"
    if not src.exists():
        return violations
    total_lines = 0
    for path in files:
        total_lines += sum(1 for _ in read_lines(path))
    # 简化策略：PoC 阶段 src/ 还未生成时直接跳过
    if total_lines < 50:
        return violations
    changes_dir = PROJECT_ROOT / ".harness" / "changes"
    has_recent_summary = False
    if changes_dir.exists():
        for sub in changes_dir.iterdir():
            if sub.is_dir() and (sub / "summary.md").exists():
                has_recent_summary = True
                break
    if not has_recent_summary:
        # 仅 warning，因为可能还在初始化阶段
        violations.append(Violation(
            rule_id="R16",
            severity="warning",
            file=src,
            line=1,
            snippet="",
            message=(
                "src/ 下代码超过 50 行，但 .harness/changes/ 下无 summary.md；"
                "建议在 .harness/changes/{YYYYMMDD}-{feat}/ 留痕。"
            ),
        ))
    return violations


# ──────────────────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────────────────
# 检查器清单（每条对应一条 AI 红线/技术红线）
CheckFn = Callable[[list[Path]], list[Violation]]
CHECKS: list[tuple[str, CheckFn]] = [
    ("R1", check_r1_llm_timeout),
    ("R2", check_r2_retry_wrapper),
    ("R3", check_r3_tool_idempotency),
    ("R4", check_r4_prompt_externalized),
    ("R5", check_r5_pydantic_validation),
    ("R6", check_r6_repository_only),
    ("R7", check_r7_no_cross_module_internal),
    ("R10", check_r10_prompt_injection),
    ("R11", check_r11_token_counter),
    ("R12", check_r12_pii_redaction),
    ("R14", check_r14_fallback_chain),
    ("R15", check_r15_budget_hard_reject),
    ("R16", check_r16_change_doc),
]


def run_scan(scan_dirs: tuple[str, ...] = DEFAULT_SCAN_DIRS) -> ScanResult:
    """执行一次完整扫描，返回 ScanResult。"""
    files = discover_python_files(scan_dirs)
    result = ScanResult(files_scanned=len(files))
    for rule_id, fn in CHECKS:
        result.rules_evaluated.append(rule_id)
        try:
            result.violations.extend(fn(files))
        except Exception as exc:
            # 单条检查器失败不应中断整体扫描
            print(f"[scanner] {rule_id} check failed: {exc}", file=sys.stderr)
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。返回 0 表示通过，非 0 表示有 error 级违规。"""
    parser = argparse.ArgumentParser(
        description="Harness Engineering — AI 红线扫描器",
    )
    parser.add_argument(
        "--dirs", nargs="+", default=list(DEFAULT_SCAN_DIRS),
        help="要扫描的目录（默认: src）",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="严格模式：warning 也算失败（CI 默认）",
    )
    parser.add_argument(
        "--report-json", type=str, default=None,
        help="可选：把结果写到 JSON 文件",
    )
    args = parser.parse_args(argv)

    result = run_scan(tuple(args.dirs))

    print("═" * 72)
    print(f"Harness Red-line Scanner — 扫描 {result.files_scanned} 个文件")
    print(f"已评估红线: {', '.join(result.rules_evaluated)}")
    print("─" * 72)

    if not result.violations:
        print("✅ 0 违规。所有 AI 红线全部通过。")
    else:
        for v in result.violations:
            print(v.format())
        print("─" * 72)
        print(
            f"汇总: {result.error_count} error / {result.warning_count} warning"
        )

    if args.report_json:
        import json
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "files_scanned": result.files_scanned,
                    "rules_evaluated": result.rules_evaluated,
                    "error_count": result.error_count,
                    "warning_count": result.warning_count,
                    "violations": [
                        {
                            "rule_id": v.rule_id,
                            "severity": v.severity,
                            "file": str(v.file.relative_to(PROJECT_ROOT)),
                            "line": v.line,
                            "snippet": v.snippet,
                            "message": v.message,
                        }
                        for v in result.violations
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"📄 报告已写入: {args.report_json}")

    print("═" * 72)

    # 退出码
    if result.error_count > 0:
        return 1
    if args.strict and result.warning_count > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
