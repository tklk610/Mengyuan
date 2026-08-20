# 20260820-subagent-task-delegation — Subagent 任务委派功能

> 状态：completed
> 创建：2026-08-20
> Owner：Harness Engineer
> TAPD：none
> branch：feat/subagent-task-delegation
> commit：-

## 需求描述

实现 Subagent 任务委派功能：
1. 主 Agent 拥有 task 工具，每次调用创建全新 Agent 实例
2. 独立上下文，执行完返回单个报告
3. 支持并行执行和特殊化配置

## 验收标准

- [x] AC-1: 主 Agent 可调用 task 工具创建 Subagent
- [x] AC-2: 每个 Subagent 拥有独立上下文
- [x] AC-3: Subagent 执行完毕返回单个报告
- [x] AC-4: 支持多个 Subagent 并行执行
- [x] AC-5: 支持 Subagent 特殊化配置（模型、温度、系统提示词等）
- [x] AC-6: 集成到 NovelCraft 主 Agent（delegator_node）

## 影响范围

| 类别 | 现有资产 | 变更 |
|------|----------|------|
| Tools | `src/ai_agent/tools/` | 新增 subagent task 工具 |
| Agents | `src/ai_agent/agents/subagent.py` | Subagent 实例化逻辑 |
| Schema | `src/ai_agent/schemas/task.py` | Task 定义 |

## 回滚方案

- 删除相关文件
- 恢复原有代码
