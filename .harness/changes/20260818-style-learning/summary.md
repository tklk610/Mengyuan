# 20260818-style-learning — Phase 2: 风格学习与记忆

> 状态：completed
> 创建：2026-08-18
> Owner：Harness Engineer
> TAPD：none
> branch：feat/style-learning
> commit：-

## 需求描述

实现风格学习与用户偏好记忆功能，让 AI 能够：
1. 解析用户上传的小说样本，提取风格特征
2. 将风格特征存储到 Qdrant 向量数据库
3. 在创作时注入风格约束
4. 持久化用户创作偏好

## 验收标准

- [x] AC-1: 用户上传 .txt 小说样本，系统能解析并提取风格特征
- [x] AC-2: 风格特征向量存储到 Qdrant，可通过向量检索召回
- [x] AC-3: Scribe Agent 创作时能注入风格约束
- [x] AC-4: 用户偏好（叙事视角/每章字数/结局倾向等）可保存/加载
- [x] AC-5: 新增 `/api/styles` 端点列出用户风格档案
- [x] AC-6: 新增 `/api/preferences` 端点获取/更新用户偏好

## 优先级

Must

## 影响范围

| 类别 | 现有资产 | 变更 |
|------|----------|------|
| Agent | `novel_agent.py` | 新增 Stylist Agent |
| RAG | `rag/` | 新增 Qdrant 集成 |
| API | `main.py` | 新增 /api/styles, /api/preferences 端点 |
| DB | PostgreSQL | UserPreference 表 |
| Vector DB | Qdrant | 新增 style_profiles collection |
| Config | `settings.py` | 新增 QDRANT_URL 等配置 |

## 冲突报告

| 级别 | 冲突 | 缓解 |
|------|------|------|
| 🟡 | Qdrant 引入新依赖 | docker-compose 新增 qdrant 服务 |
| 🟢 | 用户偏好与现有 state 兼容 | NovelState 已预留字段 |

## 任务拆分

详见 `tasks.md`

## 风险与依赖

- 依赖 Qdrant 服务可用（docker-compose 配置）
- 风格特征提取依赖 LLM API

## 回滚方案

- 代码回滚到上一版本
- Qdrant collection 删除即可

## 评估基线

- pytest tests/integration/test_style_learning.py - 11 tests
- pytest tests/unit/rag/test_style_learning_unit.py - 4 tests
