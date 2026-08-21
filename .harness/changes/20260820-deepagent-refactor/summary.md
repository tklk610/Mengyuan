# 20260820-deepagent-refactor — DeepAgent 架构改造

> 状态：completed
> 创建：2026-08-20
> Owner：Harness Engineer
> TAPD：none
> branch：refactor/deepagent-architecture
> commit：-

## 需求描述

参考 DeepAgent skill，将当前 NovelCraft 项目架构改造为 DeepAgent 架构：

1. 使用 `create_deep_agent()` 重构主 Agent
2. 配置 Middleware（TodoList/Filesystem/SubAgent/HITL/Skills/Memory）
3. 迁移现有功能到新架构
4. 保持向后兼容

## 验收标准

- [ ] AC-1: 使用 create_deep_agent() 创建主 Agent
- [ ] AC-2: 配置 SubAgentMiddleware（task 工具委派）
- [ ] AC-3: 配置 TodoListMiddleware（write_todos 任务规划）
- [ ] AC-4: 配置 HumanInTheLoopMiddleware（草稿审阅中断）
- [ ] AC-5: 配置 SkillsMiddleware（skill 加载）
- [ ] AC-6: 配置 MemoryMiddleware（记忆持久化）
- [ ] AC-7: 迁移现有 Narrator/Scribe Agent 到 DeepAgent subagents
- [ ] AC-8: 运行测试验证功能正常

## 影响范围

| 类别 | 现有资产 | 变更 |
|------|----------|------|
| Agent | `novel_agent.py` | 重构为 DeepAgent |
| Agent | `stylist_agent.py` | 迁移为 subagent |
| Agent | `subagent.py` | 整合到 Middleware |
| State | `state.py` | 使用 DeepAgent 内置 state |
| Tools | `tools/subagent_task.py` | 整合到 SubAgentMiddleware |
| Middleware | 新增 `src/ai_agent/middleware/` | DeepAgent Middleware |

## 回滚方案

- 回滚代码到改造前
- 恢复原有依赖版本

## DeepAgent 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    create_deep_agent()                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ TodoList    │  │ Filesystem  │  │ SubAgent            │ │
│  │ Middleware  │  │ Middleware  │  │ Middleware          │ │
│  │             │  │             │  │                     │ │
│  │ write_todos │  │ ls/read/    │  │ task(tool)          │ │
│  │             │  │ write_file  │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ HITL        │  │ Skills      │  │ Memory              │ │
│  │ Middleware  │  │ Middleware  │  │ Middleware          │ │
│  │             │  │             │  │                     │ │
│  │ interrupt_on│  │ skills/     │  │ store               │ │
│  │             │  │ dir loading │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    Main Agent                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Subagents: Narrator, Scribe, Stylist               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```
