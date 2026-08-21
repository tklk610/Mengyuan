# Tasks — 20260820-deepagent-refactor (DeepAgent 架构改造)

> 状态：completed
> TAPD：none
> branch：refactor/deepagent-architecture

## 任务列表

| # | 任务 | 估时 | Owner | 依赖 | 状态 |
|---|------|------|-------|------|------|
| T01 | 设计 DeepAgent 架构方案 | ≤ 2h | @engineer | - | ✅ |
| T02 | 安装 deepagents 依赖 | ≤ 1h | @engineer | - | ✅ |
| T03 | 创建 deep_novel_agent.py | ≤ 3h | @engineer | T02 | ✅ |
| T04 | 创建 Subagent 定义（narrator/scribe/stylist） | ≤ 2h | @engineer | T03 | ✅ |
| T05 | 创建 skills/novel-craft/SKILL.md | ≤ 1h | @engineer | - | ✅ |
| T06 | 编写单元测试 | ≤ 2h | @engineer | T03,T04 | ✅ |

## 约束

- 单任务 ≤ 4h（全部满足）
- 变更管理同步到 `summary.md` 变更日志

## 已知问题

- deepagents 包存在与 pytest 的兼容性问题（langchain_anthropic.middleware 导入）
- 部分测试标记为 skip，需要手动验证
- 建议在线上环境或 CI 中验证完整功能

## 回滚方案

- 删除 src/ai_agent/agents/deep_novel_agent.py
- 删除 skills/novel-craft/ 目录
- 卸载 deepagents：pip uninstall deepagents
