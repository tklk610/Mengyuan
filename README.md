# Harness Engineering — AI Agent 项目

[![CI](https://github.com/{org}/{repo}/actions/workflows/ci.yml/badge.svg)](https://github.com/{org}/{repo}/actions/workflows/ci.yml)

> **项目目标**：用 Harness Engineering 方法论，建设 **AI Agent 类项目**（智能客服 / 专家系统） 的标准化工程环境。

---

## ✦ 这是什么

本项目**不是**一个具体业务代码仓库，而是**约束环境**：约束 AI 编码行为、约束工程流程、约束交付质量。

所有被本环境约束的具体业务项目，落地时应放在本仓库的 **`src/`** 目录内（或通过 monorepo 子路径接入），并以 `.harness/` 中的规范为唯一权威。

---

## ✦ 当前状态（PoC）

> ⚠️ **当前为 PoC 阶段**，约束环境 + 测试骨架已交付，NovelCraft 业务代码为最小可行状态（Narrator + Scribe Agent，Redis Checkpointer，FastAPI 端点）。

> **技术决策**：不使用 deepagents 框架，采用原生 LangGraph 1.x。详见 [`docs/NOVEL_CRAFT_PROJECT_PLAN.md`](./docs/NOVEL_CRAFT_PROJECT_PLAN.md) 第十三节。

| 类别 | 状态 | 备注 |
| --- | --- | --- |
| `.harness/` 约束文件 | ✅ 已交付 | 4 rules + 7 skills + 4 agents + 4 wiki + 3 agent-templates |
| `docs/` 指南 | ✅ 已交付 | 快速开始 + 进阶开发指南 |
| `scripts/` 工具脚本 | ✅ 已交付 | check_red_lines.py + init_db.sql + check_change_doc.py + setup_dev_env.sh + smoke_test.sh |
| `tests/` 测试骨架 | ✅ 已交付 | R1/R3/R10/R11/R12/R14/R15 红线单测 + 质量门禁集成测试 |
| `pyproject.toml` / `Makefile` / `docker-compose.yml` / `.env.example` | ✅ 已交付 | 完整质量门禁 |
| `migrations/` | ✅ 已交付 | Alembic 初始化 + `001_initial_schema`（users/projects/chapters 等 7 张表）|
| `.github/workflows/ci.yml` | ✅ 已交付 | GitHub Actions CI（lint / type / redlines / pytest / cov）|
| `src/ai_agent/` 业务代码 | ⏳ **PoC 最小可行** | Narrator + Scribe Agent，Redis Checkpointer，FastAPI 端点 |

**变更历史**：详见 [`CHANGELOG.md`](./CHANGELOG.md)。

---

## ✦ 适用场景

| 场景 | 示例 | 本项目对应约定 |
| --- | --- | --- |
| 智能客服 | 多轮对话 + 知识库 RAG + 工具调用 | `wiki/agent-templates/customer-service.md` |
| 专家系统 | 领域知识 + 推理链 + 结构化输出 | `wiki/agent-templates/expert-system.md` |
| 多 Agent 协作 | Planner / Executor / Reviewer 编排 | `wiki/agent-templates/multi-agent.md` |

---

## ✦ 目录速览

```
Harness_Engineering/
├── .claude/                      # AI 编码全局约束（红线 / 总章）
│   └── Claude.md
├── .harness/
│   ├── rules/                    # 项目必须遵守的硬规则
│   │   ├── 工程结构规范.md
│   │   ├── 编码规范.md
│   │   ├── 开发流程规范.md
│   │   └── ai-special-rules.md
│   ├── skills/                   # AI 可以自动激活的工作流技能
│   │   ├── request-analysis/
│   │   ├── coding-skill/
│   │   ├── review-skill/
│   │   ├── unit-test-write/
│   │   ├── unit-test-ci/
│   │   ├── prompt-iteration/
│   │   └── deploy-verify/
│   ├── agents/                   # AI Agent 角色定义（Owner/Planner/Coder/Reviewer）
│   ├── wiki/                     # 静态知识库（架构 / 数据模型 / 接口 / 术语 / Agent 模板）
│   └── changes/                  # 每次变更必须留痕
│       └── templates/             # 变更模板（summary/review/tasks/design）
├── docs/                         # 人读的快速开始与进阶指南
├── origin-prompt.md              # 项目初始指令存档
├── pyproject.toml                # Python 项目元数据（PEP 621）
├── .python-version               # Python 版本固定
├── .env.example                  # 环境变量模板
└── README.md                     # 本文件
```

---

## ✦ 如何使用本 Harness

### 1️⃣ 启动一个新 AI Agent 项目

1. 在本仓库新建 `src/your_project/` 子目录（或新建 monorepo 仓库以本仓库为 `.harness/` 来源）
2. 让 AI 阅读：`.claude/Claude.md` → `.harness/rules/*` → `.harness/skills/request-analysis/SKILL.md`
3. 先输出**需求分析**，写入 `.harness/changes/{feat-name}/summary.md`

### 2️⃣ 每个变更必须走 10 阶段流水线

详见 `.harness/rules/开发流程规范.md`。

### 3️⃣ 红线不可违反

详见 `.claude/Claude.md` 末尾的「红线区」和 `.harness/rules/ai-special-rules.md`。

---

## ✦ 来源说明

本仓库的目录结构与约定模板 **参考自**：

```
C:\Users\Lenovo\Desktop\新建文件夹\下载\Harness Engineering\reference_project
```

原参考模板面向 Java/Spring Boot 电商后端。**本仓库已全面重构**为：
- 面向 **Python 3.11+ / LangChain 0.2 / LangGraph / FastAPI** 的工程化基线
- 面向 **AI Agent（客服 / 专家系统）** 的业务领域
- 引入 **AI 特有红线**（token 限额、HITL、PII 防泄漏、prompt 注入防御等）

原参考项目的具体文件可在 `origin-prompt.md` 中追溯。

---

## ✦ 维护者

- 项目 Owner：详见 `.harness/agents/owner.md`

*版本：v0.1 (2026-07-31 init)*
