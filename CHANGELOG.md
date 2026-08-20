# Changelog

> 所有项目变更都会记录在此文件。
> 本文档遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/) 规范。
> 版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [0.4.0] - Unreleased

### Added（新增）

- **Phase 3: 高级功能** —— 进行中
  - 多章节创作流程（`total_chapters` 参数，章节递增）
  - `POST /api/export` —— txt 格式导出端点
  - `GET /api/sessions` —— 列出历史会话
  - `GET /api/sessions/{thread_id}` —— 获取会话详情
  - `PUT /api/outline` —— 大纲编辑端点
  - `src/ai_agent/exporters/` —— 导出模块
  - `src/ai_agent/agents/state.py` —— 新增 `total_chapters`, `completed_chapters` 字段
  - `tests/integration/api/test_phase3_features.py` —— Phase 3 集成测试（10 tests）

## [0.3.0] - 2026-08-19

### Added（新增）

- **Phase 2: 风格学习与记忆** —— 完成 AC-1 ~ AC-6 全部验收标准
  - `src/ai_agent/agents/stylist_agent.py` —— Stylist Agent 风格控制
  - `src/ai_agent/rag/qdrant_client.py` —— Qdrant 向量存储客户端
  - `src/ai_agent/rag/embeddings.py` —— Embedding 生成
  - `src/ai_agent/rag/style_analyzer.py` —— LLM 风格特征提取
  - `src/ai_agent/main.py` —— `/api/styles`, `/api/preferences` 端点
  - `src/ai_agent/agents/novel_agent.py` —— Scribe Agent 风格约束注入
  - `tests/integration/test_style_learning.py` —— 风格学习集成测试（11/11 通过）
  - `tests/unit/rag/test_style_learning_unit.py` —— 风格学习单元测试（4/4 通过）

## [0.2.0] - 2026-08-17

### Added（新增）

- **NovelCraft PoC Phase 1 完成** —— 小说创作 AI Agent 多智能体系统
  - `src/ai_agent/agents/novel_agent.py` —— Narrator + Scribe Agent 实现
  - `src/ai_agent/main.py` —— FastAPI SSE 接口（/api/chat, /api/resume, /api/session）
  - `src/ai_agent/config/settings.py` —— LLM + Redis 配置
  - `src/ai_agent/schemas/chat.py` —— Pydantic 请求/响应 DTO
  - `tests/integration/api/test_novel_craft_e2e.py` —— E2E 集成测试（7/7 通过）
  - `tests/integration/api/test_checkpointer.py` —— Checkpointer 测试（4/4 通过）
- **Redis Checkpointer** —— LangGraph RedisSaver + MemorySaver 降级
- **HITL 中断机制** —— interrupt/resume 完整实现
- **Docker Compose 配置** —— redis + backend + frontend 一键启动
- **GitHub Actions CI** —— lint / type / redlines / pytest / cov
- **Alembic 数据库迁移** —— `001_initial_schema` 7 张表

### Fixed（修复）

- `Security(auto_error=False)` → HTTPBearer 不支持该参数，已移除
- 测试文件缺失 `user_id` 字段，已补全
- JSON 请求体重复 `user_id` key 已去重

## [Unreleased]

### Added（新增）

- **CHANGELOG.md** —— 集中记录版本演进（本文）
- **CHANGELOG.md** §「R 编号交叉引用」—— 4 个 rules 文件加 R 编号映射表（编码规范 §0、工程结构规范 §8、开发流程规范 §6、AI 特殊红线 §映射表）
- **.env.example** 新增 3 个 AI 红线相关字段：
  - `MODEL_FALLBACK_CHAIN`（R14 模型降级链，默认 `openai/gpt-4o-mini,anthropic/claude-3-5-haiku,zhipuai/glm-4-flash`）
  - `LLM_DEGRADED_MESSAGE`（R14 兑底默认回复）
  - `R9_HITL_DEFAULT_TIMEOUT_SECONDS`（R9 HITL 默认超时 = 300s）
  - `HITL_TIMEOUT_POLICY`（reject / approve / raise）
  - `PROMPT_TEMPLATES_DIR`（R4 Prompt 加载路径）
- **`.harness/changes/templates/review.template.md`** —— 评审记录模板（合入前必填）
- **`.harness/changes/templates/tasks.template.md`** —— 任务拆分模板（planner §4.3 对齐）
- **`.harness/changes/templates/design.template.md`** —— 方案设计模板（可选）
- **`scripts/check_change_doc.py`** —— R16 变更留痕检查脚本（git pre-commit 调用）
- **`scripts/setup_dev_env.sh`** —— 一键本地环境（装 uv / 装依赖 / 复制 .env / 提示 docker-compose up）
- **`scripts/smoke_test.sh`** —— 部署冒烟测试（健康检查 + 简单对话 + KB 检索）
- **`.claude/Claude.md` §3** —— 文件索引补 9 行（Makefile / scripts 3 个 / tests / docs 2 个 / CHANGELOG）
- **README.md** —— 加 §「PoC 状态声明」段，明确当前为约束环境 + 列出「未建目录」
- **`pyproject.toml`** —— 加 `[tool.uv]` section；将 `unstructured[md,pdf,docx]` 拆到 `[project.optional-dependencies] docs-loader`
- **`pyproject.toml`** —— 加 `[dependency-groups] docs` 可选组（含 doc 文档构建依赖，可选）

### Changed（变更）

- **`__template__/` → `templates/`** —— 修正 8 文件 9 处错误引用：
  - `README.md:48`
  - `.claude/Claude.md:152`
  - `.harness/agents/coder.md:108`
  - `.harness/agents/planner.md:87`
  - `.harness/agents/reviewer.md:38, 69, 106`
  - `.harness/rules/开发流程规范.md:144`
  - `docs/快速开始.md:79`
- **`.harness/rules/开发流程规范.md` §6** —— 质量检查点表加「对应红线」列
- **`架构设计.md`** —— 修正 typo 「splite」→「split」

### Architecture（架构调整）

- **架构从「通用 Clean Architecture」改为「混合架构 agent-first」**
- **主干依赖方向**：`api/ → agents/ → tools/ → repositories/ → models/`（5 层严格递减）
- **路径/目录名**：
  - `agent/` → `agents/`（成为项目核心）
  - `tool/` → `tools/`
  - `repository/` → `repositories/`
  - `model/` → `models/`
  - `schema/` → `schemas/`
- **service/ 层移除**：业务编排由 `agents/` 承担，工具能力在 `tools/`，数据访问在 `repositories/`
- **repositories/ 限定使用范围**：仅在 `tools/` 内部使用
- **横切层调整**：
  - 新增 `middleware/`（FastAPI + LangGraph middleware）
  - `monitoring/` 重命名为 `observability/`
- **graph node 约束**：必须是 thin wrapper（只调 tools/，不做业务）
- 涉及的 11 个文件：
  - `.claude/Claude.md` §2（v1.0 → v1.1）
  - `.harness/rules/工程结构规范.md`（v1.1 → v1.2）
  - `.harness/rules/编码规范.md` §0（v1.1 → v1.2）
  - `.harness/agents/coder.md`（v2.1 → v2.2）
  - `.harness/agents/owner.md`（v2.1 → v2.2）
  - `.harness/agents/planner.md`（v2.1 → v2.2）
  - `.harness/agents/reviewer.md`（v2.1 → v2.2）
  - `.harness/wiki/agent-templates/customer-service.md`（v1.0 → v1.1）
  - `.harness/wiki/agent-templates/expert-system.md`（v1.0 → v1.1）
  - `.harness/wiki/agent-templates/multi-agent.md`（v1.0 → v1.1）

### Fixed（修复）

- 修正 `__template__/` 单复数不一致（应统一为 `templates/`）
- README 目录树与实际目录不一致（补 `docs/`、`scripts/`、`tests/`；标注 `src/`、`migrations/`、`.github/` 为 PoC 阶段未建）
- 4 个 rules 与 Claude.md R1-R16 编号体系无显式交叉引用

### Deprecated（弃用）

- **`Harness Engineering提示词.txt`** —— 历史遗留文件，**不再维护**。其内容已完整包含在 `origin-prompt.md` 中（"主人原文"引用块）。保留文件本身作为历史档案，**不删除**。

---

## [0.2.0] - 2026-08-04

### Changed

- 4 个 agents 重构至 v2.0（coder / owner / planner / reviewer）：
  - 加强「输入契约」/「输出契约」/「协作契约」三段式
  - 每个 agent 加「自检 Checklist」段
  - Reviewer 加 R1-R16 逐条审视 checklist

---

## [0.1.0] - 2026-07-31

### Added

- Harness Engineering 约束环境初始化
- **`.claude/Claude.md`** —— AI 编码全局约束（红线 R1-R16）
- **`.harness/rules/`** —— 4 个规则文件（工程结构 / 编码 / 开发流程 / AI 特殊红线）
- **`.harness/agents/`** —— 4 个 agent（owner / planner / coder / reviewer）
- **`.harness/skills/`** —— 7 个 skill（request-analysis / coding-skill / review-skill / unit-test-write / unit-test-ci / prompt-iteration / deploy-verify）
- **`.harness/wiki/`** —— 4 个 wiki（架构设计 / 数据模型 / 接口协议 / 领域术语）+ 3 个 agent-templates（customer-service / expert-system / multi-agent）
- **`.harness/changes/templates/summary.template.md`** —— 变更概述模板
- **`scripts/check_red_lines.py`** —— AI 红线扫描器（R1-R16 机器可检子集）
- **`scripts/init_db.sql`** —— PostgreSQL + pgvector 初始化
- **`tests/conftest.py`** + `tests/unit/guardrail/` —— R1/R3/R10/R11/R12/R14/R15 红线单元测试
- **`tests/integration/test_agent_quality_gate.py`** —— 质量门禁集成测试
- **`pyproject.toml`** + **`Makefile`** + **`docker-compose.yml`** + **`.env.example`** + **`.python-version`**
- **`docs/快速开始.md`** + **`docs/进阶开发指南.md`**
- **`README.md`** + **`origin-prompt.md`** + **`CHANGELOG.md`**（本文件）

---

## 版本对照表

| 版本 | 日期 | 主要变更 |
| --- | --- | --- |
| 0.4.0 | Unreleased | Phase 3: 多章节创作/导出/历史会话 |
| 0.3.0 | 2026-08-19 | Phase 2: 风格学习与记忆完成 |
| 0.2.0 | 2026-08-17 | NovelCraft PoC Phase 1 完成 |
| 0.2.0 | 2026-08-04 | 4 agents 重构至 v2.0 |
| 0.1.0 | 2026-07-31 | init —— 约束环境初始化 |

---

*本文档采用 Keep a Changelog 1.1.0。任何变更请在 [Unreleased] 段追加。*