# 20260817-redis-checkpointer

> 状态：production
> 创建：2026-08-17
> Owner：Harness Engineer
> TAPD：none
> branch：-
> commit：-

## 需求描述

将 LangGraph Checkpointer 从 `InMemorySaver` 替换为 `RedisSaver`，使 session 状态跨进程持久化。进程重启后通过 `/api/resume` 恢复中断任务。

## 验收标准

- [ ] AC-1: Redis 服务可用时使用 `RedisSaver`，session 跨进程不丢失
- [ ] AC-2: Redis 服务不可用时自动降级到 `MemorySaver`，不崩溃
- [ ] AC-3: 新增集成测试 `tests/integration/api/test_checkpointer.py` 验证跨 graph 重启的状态恢复

## 优先级

Must

## 影响范围

| 类别 | 现有资产 | 变更 |
| --- | --- | --- |
| Agent | `novel_agent.py` | `build_novel_graph()` 新增 `_build_checkpointer()` 工厂函数 |
| Config | `config/settings.py` | 新增 `redis_url` 字段 |
| Config | `docker-compose.yml` | 新增 `redis` 服务定义 |
| Config | `.env.example` | 新增 `REDIS_URL` 环境变量 |
| Test | `tests/integration/api/test_checkpointer.py` | 新增文件 |
| DB | - | 无 |

## 冲突报告

| 级别 | 冲突 | 缓解 |
| --- | --- | --- |
| 🟢 | 无 | |

## 任务拆分

1. [Engineer] 新增 `redis_url` 配置字段
2. [Engineer] docker-compose 新增 Redis 服务
3. [Engineer] 实现 `_build_checkpointer()` 工厂函数
4. [Engineer] 替换 `MemorySaver` 为 `RedisSaver`
5. [Engineer] 编写 `test_checkpointer.py` 集成测试
6. [Reviewer] 代码评审

## 风险与依赖

- 依赖 Docker 环境有 Redis 端口 6379 可用
- 生产部署需要 `REDIS_URL` 环境变量正确配置

## 回滚方案

- 镜像回滚到上一版本（无 Redis Checkpointer 逻辑）
- 环境变量 `REDIS_URL` 留空则自动降级为 `MemorySaver`

## 评估基线

- 数据集：pytest tests/integration/api/test_checkpointer.py
- 评分器：2/2 通过

## 变更日志

| 日期 | 阶段 | 操作 | commit |
| --- | --- | --- | --- |
| 2026-08-17 | production | 完成实现 | - |
