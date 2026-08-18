#!/usr/bin/env bash
# Harness Engineering — 一键本地环境搭建
# 用途：装 uv / 装依赖 / 复制 .env / 提示 docker-compose up
# 触发：克隆后第一次进入项目

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "═══════════════════════════════════════════════════════════════"
echo "  Harness Engineering — local dev setup"
echo "═══════════════════════════════════════════════════════════════"

# ── 1. Python 版本检查 ───────────────────────────────────────────
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; }; then
    echo "❌ Python 3.11+ required, but found $PYTHON_VERSION"
    echo "   建议: pyenv install 3.11.9 && pyenv local 3.11.9"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION"

# ── 2. 安装 uv ──────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
    echo "→ installing uv..."
    pip install uv
fi
UV_VERSION=$(uv --version)
echo "✓ uv $UV_VERSION"

# ── 3. 同步依赖 ──────────────────────────────────────────────────
echo "→ syncing dependencies..."
uv sync --all-extras
echo "✓ dependencies synced"

# ── 4. 复制 .env ─────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo "→ copying .env.example → .env"
    cp .env.example .env
    echo "⚠️  请编辑 .env 填入 OPENAI_API_KEY 等密钥"
else
    echo "✓ .env already exists"
fi

# ── 5. 启动 docker-compose（可选）──────────────────────────────
if command -v docker >/dev/null 2>&1; then
    echo ""
    read -rp "→ Start docker-compose (PostgreSQL + Redis)? [y/N] " yn
    if [[ "$yn" =~ ^[Yy]$ ]]; then
        docker compose up -d
        echo "✓ services started (wait ~5s for healthcheck)"
        echo "  → 健康检查: curl http://localhost:8000/api/health"
    else
        echo "→ skip docker-compose"
    fi
else
    echo "⚠️  docker not installed, skip service startup"
fi

# ── 6. 跑质量门禁 ────────────────────────────────────────────────
echo ""
read -rp "→ Run quality gates now (ruff + mypy + redlines)? [y/N] " yn
if [[ "$yn" =~ ^[Yy]$ ]]; then
    make quality || echo "⚠️  some gates failed, run 'make quality' to retry"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✓ setup complete"
echo "  → next: 编辑 .env 填入密钥，然后 make up + make quality"
echo "═══════════════════════════════════════════════════════════════"