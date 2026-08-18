# 原始项目指令（存档）

> 2026-07-31 主人下达的初始任务说明。本文件保留作来源追溯，**不参与运行时**，仅供 AI 启动时作为 cold-start 上下文。

---

## 主人原文

> 你是一个顶级 Harness Engineering 工程师，擅长使用 Harness Engineering 方式，使用 AI 进行编码工作，精通 Harness Engineering 环境搭建，特别是各种约束文件的编写。
>
> 我现在需要进行 AI Agent 的项目开发，比如智能客服，专家系统等，需要搭建一套对应的 Harness Engineering 环境，及对应的约束文件，要求你：
>
> 1. 定位到项目开发目录：**`D:\Project\Harness_Engineering`**，所有操作只能在这个目录下进行，不允许改动这各路径外的任何文件，切记；
> 2. 参考如下路径的文件：**`C:\Users\Lenovo\Desktop\新建文件夹\下载\Harness Engineering\reference_project`**；
> 3. 按照 Harness Engineering 开发原则，根据 AI Agent 的项目的开发要求，在 `D:\Project\Harness_Engineering`，这个路径下搭建 Harness Engineering 环境，主要是项目文件架构，各种约束文件编写；
> 4. 可以参考上面的参考项目，也可以根据你的判断重构文件架构和约束文件的内容；
> 5. 参考项目是针对 JAVA 项目的，**不可以直接照抄**，要根据 Python 项目的特点，重新规划；
> 6. 有任何问题和不明白的，需要先问我。

---

## 依依的关键决策（2026-07-31 主人确认「按推荐方案」后落地）

| 决策点 | 选择 | 理由 |
| --- | --- | --- |
| 业务方向 | 兼容三类 Agent（客服 / 专家系统 / 多 Agent） | Harness 是约束层，应向上兼容 |
| 后端语言 | **Python 3.11+** | 主人明确要求 |
| LLM 框架 | **LangChain 0.2 + LangGraph 0.2** | 生态成熟、生产级 |
| Web 框架 | **FastAPI** | 异步、SSE/WS 原生好 |
| 数据库 | **PostgreSQL 16 + pgvector** | 一库两用 |
| 缓存 / 队列 | **Redis 7** | 通用 |
| ORM | **SQLAlchemy 2.0 async + Alembic** | Python 主流 |
| 包管理 | **uv** | 性能 / 可复现性 |
| 前端 | **React 18 + TypeScript + Vite**（占位骨架） | 主流、可后续替换 |
| 部署 | **Docker + docker-compose**（PoC） | 极简起步 |
| 交付节奏 | **PoC 优先**：一次性把骨架搭好，后续业务项目边开发边补充 | 不一次堆完 |
| 路径组织 | `.harness/`（与参考项目一致） | 生态命名 |

---

## ✦ 与原参考项目的差异（重要）

| 维度 | Java 参考项目 | 本 Python Agent Harness |
| --- | --- | --- |
| 业务领域 | 电商后端 | **AI Agent（客服/专家系统）** |
| 框架基线 | Spring Boot + MyBatis | **LangChain + LangGraph + FastAPI** |
| 主数据存储 | MySQL + 独立 ES | **PostgreSQL + pgvector（向量内嵌）** |
| MQ | RocketMQ 5.x | **Redis Pub/Sub + 异步任务（Celery 或 APScheduler）** |
| 异常体系 | BusinessException 体系 | **Pydantic Validation + 自定义 AIException 层级** |
| 金额字段 | Integer 分 | **不重要（按需，业务有则加）** |
| 测试 | JUnit 5 + Mockito | **pytest + pytest-asyncio + httpx + respx** |
| CI | Maven + JaCoCo | **GitHub Actions + pytest --cov + ruff** |
| **AI 特有红线** | 无 | **8 条新增（见 ai-special-rules.md）** |
| **Skills 变化** | 5 个 | **7 个：新增 prompt-iteration / review-skill** |
| **Agents** | 无 | **4 个角色：Owner/Planner/Coder/Reviewer** |
| **Wiki** | 接口协议 / 领域术语 | **新增 架构设计 / 数据模型 / Agent 模板** |

---

*此文件仅作存档，禁止修改。如发现与现行 `.harness/` 不一致，以 `.harness/` 为准。*
