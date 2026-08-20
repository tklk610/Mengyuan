# Harness Engineering - NovelCraft PoC

> AI Agent 工程化框架演示项目：小说创作多智能体系统

## 项目状态

| 版本 | 状态 | 说明 |
|------|------|------|
| v0.3.0 | ✅ 完成 | Phase 2: 风格学习与记忆 |
| v0.2.0 | ✅ 完成 | NovelCraft PoC Phase 1 MVP |

## 核心功能

- **多智能体协作** - Narrator Agent（大纲规划）+ Scribe Agent（正文续写）
- **HITL 中断机制** - 人工审阅草稿，决定接受/重写/重启
- **风格学习** - 上传小说样本，自动提取风格特征并注入创作约束
- **用户偏好** - 持久化叙事视角、字数、结局等偏好

## 技术栈

| 组件 | 技术 |
|------|------|
| Agent 框架 | LangGraph 1.x |
| Web 框架 | FastAPI |
| 向量数据库 | Qdrant |
| 关系数据库 | PostgreSQL |
| 缓存 | Redis |
| 部署 | Docker Compose |

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url>
cd Harness_Engineering

# 2. 启动服务
docker-compose up -d

# 3. 访问 API 文档
open http://localhost:8000/docs
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/session` | POST | 创建创作会话 |
| `/api/chat` | POST | SSE 聊天/创作 |
| `/api/resume` | POST | 恢复中断任务 |
| `/api/styles` | GET/POST | 风格档案管理 |
| `/api/styles/search` | POST | 相似风格搜索 |
| `/api/preferences` | GET/PUT | 用户偏好管理 |

## 测试

```bash
# 运行全部测试
pytest tests/ -v

# Phase 2 风格学习测试
pytest tests/integration/test_style_learning.py -v
pytest tests/unit/rag/test_style_learning_unit.py -v
```

## 项目结构

```
Harness_Engineering/
├── src/ai_agent/          # 业务代码
│   ├── agents/            # Agent 实现 (novel_agent, stylist_agent)
│   ├── api/               # FastAPI 端点
│   ├── rag/               # RAG 组件 (qdrant, embeddings, style_analyzer)
│   ├── schemas/          # Pydantic DTO
│   └── config/           # 配置
├── tests/                 # 测试 (unit/integration/e2e)
├── .harness/             # Harness 约束
│   ├── rules/            # 工程规范
│   ├── skills/           # Skill 定义
│   ├── agents/           # Agent 模板
│   └── changes/          # 变更记录
├── docs/                 # 项目文档
└── scripts/              # 工具脚本
```

## 约束与规范

本项目遵循 **Harness Engineering** 约束：

- `.claude/Claude.md` - AI 编码全局红线（R1-R16）
- `.harness/rules/` - 工程规范 / 编码规范 / 开发流程 / AI 特殊红线

## Changelog

详见 [CHANGELOG.md](CHANGELOG.md)
