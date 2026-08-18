# 部署验证技能（deploy-verify）

## 概述
规范化部署流程和验证步骤，确保上线安全可控。

## 触发条件
- Stage 8 / 9（预发 / 上线）

## 环境清单

| Env | URL 模式 | 用途 | 访问 |
| --- | --- | --- | --- |
| dev | http://localhost:8000 | 开发联调 | 开发自己 |
| test | http://test.harness.local | 集成测试 | 测试团队 |
| staging | http://staging.harness.local | 预发验证 | 全员 |
| production | https://api.harness.example.com | 线上生产 | 运维 + Owner |

## 部署前检查清单

### 代码检查
- [ ] 所有代码已合并到 `release/x.y.z` 分支
- [ ] CI 全绿（lint / type / 单测 / 集成 / 覆盖率）
- [ ] 代码评审 0 个 🟥 问题
- [ ] AI 红线 8 条全过（`scripts/check_red_lines.py`）
- [ ] 相关 `summary.md` / `review.md` 已落档

### 数据库检查
- [ ] Alembic 迁移脚本已写（`alembic upgrade head` 演练）
- [ ] 回滚脚本已写（`alembic downgrade -1` 演练）
- [ ] 大表变更已评估（pt-online-schema-change 等）

### 配置 / 密钥检查
- [ ] `HUMAN_IN_THE_LOOP_ENABLED=true`
- [ ] `PII_REDACTION_ENABLED=true`
- [ ] `CONTENT_SAFETY_ENABLED=true`
- [ ] `LLM_DAILY_TOKEN_QUOTA` 已配置
- [ ] `MODEL_FALLBACK_CHAIN` 已配置
- [ ] 模型 API Key 已注入（Vault / Secret Manager）
- [ ] 数据库密码 / JWT_SECRET 已轮换

### LLM / Agent 检查
- [ ] 主模型 / 备用模型都已测过
- [ ] 模型降级路径演练过（人为拔网 / 抛 500）
- [ ] Prompt 当前版本是 `stable`
- [ ] `prompt-templates/` 已部署到目标环境

### 监控 / 告警检查
- [ ] LangSmith / OpenTelemetry 端点通
- [ ] 关键指标已埋点（QPS / 延迟 / 错误率 / Token 用量 / 拒答率）
- [ ] 告警阈值已配置（错误率 > 1% / P95 > X ms / Token 配额 > 80%）
- [ ] 告警通知已对接（飞书 / 钉钉 / Slack）

## 部署步骤（Staging）

```bash
git checkout release/v1.0.0
git pull

# 数据库
alembic upgrade head

# 启动
docker compose -f docker-compose.staging.yml up -d

# 健康检查
curl -fsS http://localhost:8000/api/health

# 冒烟测试
bash scripts/smoke_test.sh
```

## 部署步骤（Production 灰度）

```bash
# 1. 发布 1%
kubectl set image deployment/api api=image:v1.0.0 --namespace=prod
# 等流量侧 1% 走新版本（5 分钟）

# 2. 验证指标
# 错误率 < 0.5% / P95 延迟 < X ms / 配额 < 70%

# 3. 扩到 10%
# 4. 50%
# 5. 100%

# 每个阶段等待 30 分钟
```

## 回滚步骤

```bash
# 紧急回滚
kubectl rollout undo deployment/api

# 数据库回滚（如果涉及 schema 变更，先确认可写回）
alembic downgrade -1
```

## 验证脚本示例

```bash
# scripts/smoke_test.sh
#!/usr/bin/env bash
set -e

BASE_URL="${1:-http://localhost:8000}"

# 1. 健康检查
echo "→ health check"
curl -fsS "$BASE_URL/api/health" | jq .

# 2. 简单对话
echo "→ simple chat"
curl -fsS -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"smoke","question":"你好"}' | jq .

# 3. 知识库检索
echo "→ kb search"
curl -fsS -X POST "$BASE_URL/api/v1/knowledge/search" \
  -H "Content-Type: application/json" \
  -d '{"kb_id":"KB_smoke","query":"测试"}' | jq .
```

## 上线后观测（Stage 10）

| 指标 | 阈值 | 观测频率 |
| --- | --- | --- |
| QPS | 流量稳定 | 1 min |
| 错误率 | < 1% | 1 min |
| P95 延迟 | < 3 s | 1 min |
| Token 日配额 | < 80% | 5 min |
| 拒答率 | < 5%（客服场景） | 15 min |
| 用户反馈 | 无异常投诉 | 实时 |

## 禁止
- ❌ 跳过 staging
- ❌ 一次性 100% 流量切换
- ❌ 上线后立即离开（必须 24h 观测）
- ❌ 没有告警就上线

## 下一步
通过 → **Stage 10 线上观测**
