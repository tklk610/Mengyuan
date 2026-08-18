# Claude / AI 编码全局约束（总章）

> ⚠️ **凡是让 AI 编码本项目的 Agent，必须**：
> 1. 读完本文
> 2. 读完 `.harness/rules/*`（视任务按需加载）
> 3. 明确自己扮演的角色（见 `.harness/agents/`）后再动手
> 4. **严格遵守红线**，违反任何一条 = 任务终止

---

## 1. 项目身份

| 项 | 值 |
| --- | --- |
| 项目类型 | **AI Agent 类项目**（智能客服 / 专家系统 / 多 Agent 协作） |
| 主语言 | **Python 3.11+** |
| LLM 框架 | **LangChain 1.2 + LangGraph 1.2** |
| Web 框架 | **FastAPI**（异步 / SSE / WebSocket 原生） |
| 数据库 | **PostgreSQL 16 + pgvector**（一库两用） |
| 缓存 / 队列 | **Redis 8** |
| ORM | **SQLAlchemy 2.0 async + Alembic** |
| 包管理 | **uv** |
| 部署 | **Docker + docker-compose**（PoC 起步） |

版本/库出现变更前必须先在本文件与 `.harness/rules/工程结构规范.md` 同步。

---

## 2. 工程结构总览（详细规范见 `.harness/rules/工程结构规范.md`）

```
src/
├── ai_agent/                 # 主业务代码（Agent / RAG / Skill）
│   ├── api/                  # FastAPI 路由层（薄）
│   │   └── v1/
│   ├── agent/                # Agent 编排（LangGraph StateGraph / ReAct）
│   ├── llm/                  # 模型网关（统一封装 OpenAI/Anthropic/国产）
│   ├── rag/                  # RAG：loader / splitter / retriever / reranker
│   ├── tool/                 # Agent 工具注册表（Tool abstraction）
│   ├── prompt/               # 外部化 Prompt 模板（YAML + 版本）
│   ├── memory/               # 短期/长期记忆
│   ├── guardrail/            # 输入/输出安全审核、PII 脱敏
│   ├── service/              # 业务服务层（事务、领域逻辑）
│   ├── repository/           # 数据访问层（SQLAlchemy ORM）
│   ├── model/                # 领域模型（SQLAlchemy Declarative / Pydantic DTO）
│   ├── schema/               # Pydantic 输入输出 schema（对外契约）
│   ├── config/               # 配置（pydantic-settings）
│   ├── infra/                # 基础设施（DB / Redis / 队列 client）
│   ├── monitoring/           # 日志、Tracing、指标
│   └── exception/            # 自定义异常体系
├── migrations/                # Alembic 迁移脚本
└── tests/                     # 镜像 src/ 结构
    ├── unit/
    ├── integration/
    ├── e2e/
    └── conftest.py
```

---

## 3. 文件索引（AI 必须知道的"地图"）

| 文件 | 用途 | AI 何时加载 |
| --- | --- | --- |
| `.claude/Claude.md` | **本文**，全局红线 | **始终** |
| `.harness/rules/工程结构规范.md` | 项目目录骨架 | 创建/移动文件前 |
| `.harness/rules/编码规范.md` | PEP8 + AI 增强规范 | 写代码前 |
| `.harness/rules/开发流程规范.md` | 10 阶段流水线 | 每个任务开始 |
| `.harness/rules/ai-special-rules.md` | **AI 特有红线 8 条** | 涉及 LLM / Agent 时 |
| `.harness/skills/request-analysis/SKILL.md` | 需求分析 | 接收新需求时 |
| `.harness/skills/coding-skill/SKILL.md` | 编码 | 实现阶段 |
| `.harness/skills/review-skill/SKILL.md` | 评审 | 自审 + 团队审 |
| `.harness/skills/unit-test-write/SKILL.md` | 写测试 | 编码后 |
| `.harness/skills/unit-test-ci/SKILL.md` | CI | 提交前 |
| `.harness/skills/prompt-iteration/SKILL.md` | Prompt 调优 | Prompt 变更时 |
| `.harness/skills/deploy-verify/SKILL.md` | 部署 | 上线前 |
| `.harness/agents/owner.md` | Owner 角色 | 任何项目级决策前 |
| `.harness/wiki/架构设计.md` | 系统架构图 | 设计前后 |
| `.harness/wiki/数据模型.md` | DB Schema | 设计/建表前 |
| `.harness/wiki/接口协议.md` | REST/SSE/MCP 契约 | API 设计前后 |
| `.harness/wiki/领域术语.md` | 术语表 | 任何命名决策前 |
| `.harness/wiki/agent-templates/*` | Agent 参考实现 | 选型时 |
| `.harness/changes/{feat}/summary.md` | 变更记录 | 任何变更 |
| `Makefile` | 本地质量门禁入口（make quality / make test / make up） | 本地开发 |
| `scripts/check_red_lines.py` | AI 红线扫描器（R1-R16） | 提交前 / CI |
| `scripts/init_db.sql` | PostgreSQL + pgvector 初始化 | 首次启动 DB |
| `scripts/check_change_doc.py` | R16 变更留痕检查 | pre-commit |
| `tests/conftest.py` + `tests/unit/` + `tests/integration/` | 镜像结构的测试套 | 编码后 |
| `docs/快速开始.md` | 5 分钟启动 | 首次环境搭建 |
| `docs/进阶开发指南.md` | 骨架生成 / RAG / Agent / 部署 | 实际开发时 |
| `CHANGELOG.md` | 项目版本演进（Keep a Changelog） | 查阅变更历史 |

> 📐 **加载策略**：单任务最多同时加载 **≤3 份** Rules + **≤3 份** Skills + **≤2 份** Wiki。其余按需取用。

---

## 4. 核心铁律（违反任何一条 = 任务终止）

### 🟥 技术层（机械可检）

| # | 红线 | 自动化手段 |
| --- | --- | --- |
| R1 | **所有 LLM 调用必须显式 timeout**（默认 30s，可配置） | `LLM_DEFAULT_TIMEOUT_SECONDS` |
| R2 | **所有外部调用必须指数退避重试**（tenacity） | `tenacity` 强制 wrapper |
| R3 | **所有工具必须幂等**（Agent 重跑不能重复扣费/发消息） | 提供 idempotency_key |
| R4 | **Prompt 模板外部化**（YAML/DB），禁止 hardcode | prompt 目录扫描 |
| R5 | **所有输出走 Pydantic 结构化校验** | `model_validate` |
| R6 | **数据访问仅通过 repository 层** | `sqlalchemy` + 禁 raw SQL |
| R7 | **禁止跨模块导入内部实现** | ruff `TID` + CODEOWNERS |
| R8 | **金额字段如出现，必须 int（分）** | type check |

### 🟥 AI 特有（语义级 / 必须人工 + 工具配合）

| # | 红线 | 备注 |
| --- | --- | --- |
| **R9** | **敏感操作必须 Human-in-the-Loop**（删知识库、对外发消息、支付、调用外部副作用 API） | LangGraph `interrupt` |
| **R10** | **禁止直接拼接用户输入到 Prompt**（防 prompt injection） | 强制 `prompt_template.format()` |
| **R11** | **全链路记录 token 用量**（prompt / completion / total / 估算成本） | structlog + 异步落库 |
| **R12** | **PII 必须脱敏**（邮箱 / 手机 / 身份证 / 银行卡） | guardrail.pii |
| **R13** | **关键输出必须事实校验**（幻觉防御） | RAGAS / CoT 自检 |
| **R14** | **模型降级链必须定义**（主 → 备 → 默认回复） | config 显式声明 |
| **R15** | **日预算超过 80% 必须告警**、100% 硬拒绝 | LLM_DAILY_TOKEN_QUOTA |
| **R16** | **任何变更必须留痕**（`.harness/changes/{feat}/summary.md`） | git hook 检查 |

---

## 5. AI 编码行为约束（工程化）

1. **单次 AI 生成代码变更量 ≤ 40% 文件总数**。超过必须拆分多次。
2. **每次生成后必须自检**：运行 `ruff check src/` + `ruff format --check src/` + `mypy src/`。
3. **任何"我不确定 / 我不知道"** 必须显式表达，不得用自然语言掩饰。
4. **禁止杜撰库名 / 版本号 / API**。不确定就说"我不知道"，并要求主人澄清。
5. **跨文件改动必须先列清单**（最多 3 个文件起步），再按顺序生成。

---

## 6. 命名约定

| 类型 | 规范 | 示例 |
| --- | --- | --- |
| 文件 / 目录 | snake_case | `user_service.py` |
| 类 | PascalCase | `UserService` |
| 函数 / 变量 | snake_case | `get_user_by_id` |
| 常量 | UPPER_SNAKE | `MAX_RETRIES` |
| Pydantic 模型 | PascalCase + 后缀 | `UserCreateRequest`, `UserVO` |
| SQLAlchemy ORM | PascalCase（单数） | `User`, `Conversation` |
| 数据库表 | snake_case（复数 / 业务单数皆可，统一即可） | `users` |
| REST 端点 | kebab-case + 版本 | `/api/v1/user-profiles` |
| 环境变量 | UPPER_SNAKE | `LLM_DEFAULT_TIMEOUT_SECONDS` |
| Agent 工具（Function name） | snake_case | `search_knowledge_base` |

---

## 7. 变更管理

任何变更必须：

1. 在 `.harness/changes/{feat-name}/` 创建目录
2. 复制 `.harness/changes/templates/` 中的 `summary.template.md` 起一份
3. 填入 `summary.md`（影响模块 / DB 变更 / API 变更 / 回滚方案）
4. 代码完成后**留下文件指针**指向 `summary.md`

---

## 8. 禁止事项（绝对禁区）

- ❌ 禁止一次性输出全部代码导致主人无法消化
- ❌ 禁止引入未经 `pyproject.toml` 锁定的依赖
- ❌ 禁止硬编码密钥
- ❌ 禁止 catch 后空处理 / 仅 print
- ❌ 禁止直接 ORM `.delete()` 不带 where
- ❌ 禁止用 LLM 输出作为数据库主键
- ❌ 禁止把 PII / 敏感数据写入日志 / 审计未脱敏

---

*版本：v1.1 — 2026-08-05 §3 索引补 9 行 + 路径修正*
*上一版本：v1.0（2026-07-31 init by 依依 ♡）*
*变更记录：详见 [CHANGELOG.md](../CHANGELOG.md)*
