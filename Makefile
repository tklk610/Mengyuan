# Harness Engineering — Makefile
# ============================================================
# 本地一键跑质量门禁。Windows 上请用 `make` (Git Bash / WSL)
# 或手动调用下方对应命令（PowerShell 友好别名见 README）。
#
# 主入口:
#     make help          # 列出所有 target
#     make install       # 安装依赖
#     make quality       # 全量质量门禁（推荐: lint + type + redlines + test）
#     make redlines      # 仅跑 AI 红线扫描器
#     make test          # 仅跑 pytest
#     make up / down     # 启停 docker-compose 服务
# ============================================================

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# ── 工具探测 ──────────────────────────────────────────────────
PYTHON  ?= python
RUFF    ?= $(PYTHON) -m ruff
MYPY    ?= $(PYTHON) -m mypy
PYTEST  ?= $(PYTHON) -m pytest
DOCKER  ?= docker

# 如果你的环境默认开启了 RUF001/RUF002/RUF003（中英标点检测），
# 可以用 `make lint-soft` 跳过这些 unicode 警告。
RUFF_STRICT_SELECT := E,W,F,I,B,C4,UP,N,SIM,PT,RUF
RUFF_SOFT_SELECT   := E,W,F,I,B,C4,UP,N,SIM,PT

# ── 路径 ──────────────────────────────────────────────────────
SCRIPTS_DIR   := scripts
SCANNER       := $(SCRIPTS_DIR)/check_red_lines.py
SRC_DIR       := src
TESTS_DIR     := tests
PYPROJECT     := pyproject.toml

# ── 颜色输出（仅在 TTY 下生效） ────────────────────────────────
BOLD  := \033[1m
GREEN := \033[32m
RED   := \033[31m
RESET := \033[0m

# ──────────────────────────────────────────────────────────────
.PHONY: help
help: ## 列出所有可用的 make target
	@echo "$(BOLD)Harness Engineering — quality gate$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'

# ──────────────────────────────────────────────────────────────
.PHONY: install
install: ## 安装项目依赖（uv 优先，回退到 pip）
	@if command -v uv >/dev/null 2>&1; then \
	  echo "[install] using uv"; uv sync --all-extras; \
	else \
	  echo "[install] using pip"; $(PYTHON) -m pip install -e ".[dev]"; \
	fi

# ──────────────────────────────────────────────────────────────
.PHONY: lint
lint: ## ruff lint（项目级配置，含 RUF unicode 检查）
	$(RUFF) check $(SRC_DIR) $(TESTS_DIR) $(SCRIPTS_DIR)

.PHONY: lint-soft
lint-soft: ## ruff lint（不含 RUF unicode 检查；中文标点友好）
	$(RUFF) check --select $(RUFF_SOFT_SELECT) $(SRC_DIR) $(TESTS_DIR) $(SCRIPTS_DIR)

.PHONY: format
format: ## ruff format（自动修复）
	$(RUFF) format $(SRC_DIR) $(TESTS_DIR) $(SCRIPTS_DIR)

.PHONY: format-check
format-check: ## ruff format 检查（不修改）
	$(RUFF) format --check $(SRC_DIR) $(TESTS_DIR) $(SCRIPTS_DIR)

.PHONY: type
type: ## mypy 严格模式类型检查
	$(MYPY) $(SRC_DIR)

# ──────────────────────────────────────────────────────────────
.PHONY: redlines
redlines: ## AI 红线扫描（scripts/check_red_lines.py）
	$(PYTHON) $(SCANNER)

.PHONY: redlines-strict
redlines-strict: ## AI 红线扫描（严格模式：warning 也算失败）
	$(PYTHON) $(SCANNER) --strict

.PHONY: redlines-json
redlines-json: ## AI 红线扫描并输出 JSON 报告
	$(PYTHON) $(SCANNER) --report-json reports/red_lines.json

# ──────────────────────────────────────────────────────────────
.PHONY: test
test: ## 跑全部测试
	$(PYTEST) -o addopts="" $(TESTS_DIR)

.PHONY: test-unit
test-unit: ## 仅跑单元测试
	$(PYTEST) -o addopts="" $(TESTS_DIR)/unit -m "not integration and not e2e"

.PHONY: test-guardrail
test-guardrail: ## 仅跑 guardrail 红线单测
	$(PYTEST) -o addopts="" $(TESTS_DIR)/unit/guardrail -v

.PHONY: test-integration
test-integration: ## 跑集成测试（需先 make up）
	$(PYTEST) -o addopts="" $(TESTS_DIR)/integration -v

.PHONY: test-cov
test-cov: ## 跑测试 + 覆盖率报告
	$(PYTEST) --cov=$(SRC_DIR) --cov-fail-under=79 --cov-report=term-missing $(TESTS_DIR)

# ──────────────────────────────────────────────────────────────
.PHONY: up
up: ## 启动 docker-compose 服务（postgres+pgvector, redis）
	$(DOCKER) compose up -d
	@echo "[up] services started. wait ~5s for healthcheck."

.PHONY: down
down: ## 停止并清理 docker-compose 服务
	$(DOCKER) compose down

.PHONY: logs
logs: ## 查看 docker-compose 日志
	$(DOCKER) compose logs -f

# ──────────────────────────────────────────────────────────────
.PHONY: quality
quality: lint-soft type redlines test ## 全量质量门禁（推荐；中文标点友好）
	@echo ""
	@echo "$(GREEN)[OK] all quality gates passed$(RESET)"

.PHONY: quality-strict
quality-strict: lint type redlines-strict test ## 严格模式全量门禁（含 RUF unicode 检查）
	@echo ""
	@echo "$(GREEN)[OK] all strict quality gates passed$(RESET)"

.PHONY: ci
ci: ## 模拟 CI 流水线（= quality + test-cov）
	$(MAKE) quality
	$(MAKE) test-cov

.PHONY: pre-commit
pre-commit: lint-soft format-check redlines ## 提交前自检（中文标点友好）
	@echo ""
	@echo "$(GREEN)[OK] pre-commit checks passed$(RESET)"

# ──────────────────────────────────────────────────────────────
.PHONY: db-migrate
db-migrate: ## 运行待定迁移（需先 make up）
	uv run alembic upgrade head

.PHONY: db-migrate-dry
db-migrate-dry: ## SQLAlchemy autogenerate：生成新迁移（需先修改模型）
	uv run alembic revision --autogenerate -m "$(MSG)"

.PHONY: db-migrate-new
db-migrate-new: ## 手动创建新迁移（无 autogenerate）
	uv run alembic revision -m "$(MSG)"

.PHONY: db-migrate-down
db-migrate-down: ## 回退上一个迁移
	uv run alembic downgrade -1

.PHONY: db-migrate-history
db-migrate-history: ## 查看迁移历史
	uv run alembic history --verbose

.PHONY: db-migrate-check
db-migrate-check: ## 检查当前 DB 版本 vs 代码版本是否一致
	uv run alembic check

# ──────────────────────────────────────────────────────────────
.PHONY: clean
clean: ## 清理临时文件（缓存、报告）
	rm -rf .pytest_cache .ruff_cache .mypy_cache reports/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "[clean] done"

.PHONY: clean-all
clean-all: clean down ## 清理所有（含 docker-compose）

# ──────────────────────────────────────────────────────────────
.PHONY: verify-env
verify-env: ## 验证本地环境（python 版本、docker 可用等）
	@echo "python: $$($(PYTHON) --version)"
	@echo "ruff:   $$($(RUFF) --version 2>&1 | head -1)"
	@echo "mypy:   $$($(MYPY) --version 2>&1 | head -1)"
	@echo "pytest: $$($(PYTEST) --version 2>&1 | head -1)"
	@command -v $(DOCKER) >/dev/null && echo "docker: $$($(DOCKER) --version)" \
	  || echo "docker: NOT INSTALLED (integration tests unavailable)"