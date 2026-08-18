#!/usr/bin/env bash
# Harness Engineering — 部署冒烟测试
# 用途：上线 / Staging 后跑一次，验证基本链路通畅
# 参考：.harness/skills/deploy-verify/SKILL.md

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
echo "═══════════════════════════════════════════════════════════════"
echo "  Harness Engineering — smoke test"
echo "  target: $BASE_URL"
echo "═══════════════════════════════════════════════════════════════"

# ── 1. 健康检查 ─────────────────────────────────────────────────
echo ""
echo "→ 1. health check"
HTTP_CODE=$(curl -fsS -o /tmp/smoke_health.json -w "%{http_code}" "$BASE_URL/api/health" || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ health check failed: HTTP $HTTP_CODE"
    cat /tmp/smoke_health.json 2>/dev/null || true
    exit 1
fi
echo "✓ $(cat /tmp/smoke_health.json)"

# ── 2. 简单对话（非流式）───────────────────────────────────────
echo ""
echo "→ 2. simple chat (non-stream)"
HTTP_CODE=$(curl -fsS -o /tmp/smoke_chat.json -w "%{http_code}" \
    -X POST "$BASE_URL/api/v1/chat" \
    -H "Content-Type: application/json" \
    -d '{"user_id":"smoke-test","question":"你好","stream":false}' \
    || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    echo "⚠️  chat endpoint returned HTTP $HTTP_CODE (PoC 阶段可能未实现，可忽略)"
    cat /tmp/smoke_chat.json 2>/dev/null || true
else
    echo "✓ $(cat /tmp/smoke_chat.json | head -c 200)"
fi

# ── 3. 知识库检索 ───────────────────────────────────────────────
echo ""
echo "→ 3. kb search"
HTTP_CODE=$(curl -fsS -o /tmp/smoke_kb.json -w "%{http_code}" \
    -X POST "$BASE_URL/api/v1/knowledge/search" \
    -H "Content-Type: application/json" \
    -d '{"kb_id":"KB_smoke","query":"测试","top_k":3}' \
    || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    echo "⚠️  kb search returned HTTP $HTTP_CODE (PoC 阶段可能未实现，可忽略)"
    cat /tmp/smoke_kb.json 2>/dev/null || true
else
    echo "✓ $(cat /tmp/smoke_kb.json | head -c 200)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✓ smoke test done"
echo "═══════════════════════════════════════════════════════════════"