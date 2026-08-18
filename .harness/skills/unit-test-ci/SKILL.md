# CI 技能（unit-test-ci）

## 概述
配置和执行持续集成流水线，自动化质量门禁。

## 触发条件
- Push 到任何分支
- 发起 Merge Request / Pull Request
- 定时任务（每晚跑全量回归）

## 流水线

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push:
    branches: [main, develop, "feat/**", "fix/**"]
  pull_request:
    branches: [main, develop]

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: postgres
        ports: [5432:5432]
        options: --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5
      redis:
        image: redis:7
        ports: [6379:6379]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv
        run: pip install uv

      - name: Cache deps
        uses: actions/cache@v4
        with:
          path: .venv
          key: ${{ runner.os }}-uv-${{ hashFiles('pyproject.toml', 'uv.lock') }}

      - name: Install
        run: uv sync --all-extras

      - name: Ruff lint
        run: uv run ruff check .

      - name: Ruff format check
        run: uv run ruff format --check .

      - name: Mypy
        run: uv run mypy src/

      - name: Red-line scanner
        run: uv run python scripts/check_red_lines.py

      - name: Unit tests + coverage
        run: |
          uv run pytest tests/unit/ \
            --cov=src \
            --cov-report=xml \
            --cov-fail-under=80

      - name: Integration tests
        run: uv run pytest tests/integration/ -v
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0

      - name: Coverage report
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

      - name: AI Red Line unit tests
        run: uv run pytest tests/unit/guardrail/ -v
```

## 质量门禁矩阵

| 阶段 | 检查 | Pass 准则 | Fail 处理 |
| --- | --- | --- | --- |
| Lint | ruff check | 0 violation | 阻合并 |
| Format | ruff format --check | 0 diff | 阻合并 |
| Type | mypy strict | 0 error | 阻合并 |
| 红线 | scripts/check_red_lines.py | 0 红线 | 阻合并 |
| 单测 | pytest tests/unit/ | 通过 | 阻合并 |
| 覆盖率 | pytest --cov | ≥ 80% | 阻合并 |
| 集成 | pytest tests/integration/ | 通过 | 警告（不强阻） |

## 本地一键跑完

```bash
make ci  # 见 Makefile（推荐）
```

或手动：

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
python scripts/check_red_lines.py
pytest --cov=src --cov-fail-under=80
```

## 必须的脚本

- `scripts/check_red_lines.py`（AI 特有红线扫描）
- `scripts/check_change_doc.py`（变更留痕检查）
- `scripts/setup_dev_env.sh`（一键本地环境）

## 红线扫描脚本骨架

```python
# scripts/check_red_lines.py
import re
import sys
from pathlib import Path

VIOLATIONS = []

# AI001: f-string 注入
for f in Path("src").rglob("*.py"):
    text = f.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        # 简单启发式
        if re.search(r'prompt\s*=\s*["\']f"', line):
            VIOLATIONS.append(f"{f}:{i} AI001 f-string prompt 拼接")

# AI010: 直接 print 代替日志
for f in Path("src").rglob("*.py"):
    if re.search(r'^\s*print\(', f.read_text(encoding="utf-8"), re.M):
        VIOLATIONS.append(f"{f} AI010 禁止 print 代替日志")

if VIOLATIONS:
    print("❌ Red-line violations:")
    for v in VIOLATIONS:
        print(f"  {v}")
    sys.exit(1)
print("✅ Red-line pass")
```

## 下一步
CI 通过 → **Stage 6 代码评审**
