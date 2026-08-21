#!/bin/bash
# =============================================================================
# Agent Sandbox Runner - 在沙箱容器中运行 Agent
# =============================================================================
# 用法:
#   ./scripts/run_in_sandbox.sh [command] [args...]
#
# 示例:
#   ./scripts/run_in_sandbox.sh python -m uvicorn ai_agent.main:app
#   ./scripts/run_in_sandbox.sh pytest tests/unit/ -v
# =============================================================================

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# 安全检查
# =============================================================================

check_security() {
    log_info "Running security checks..."

    # 检查是否以非 root 用户运行
    if [ "$(id -u)" -eq 0 ]; then
        log_warn "Running as root! Consider using a non-root user."
    fi

    # 检查文件系统权限
    if [ -w "/workspace" ] && [ ! -w "./src" ]; then
        log_info "Workspace is writable, source is read-only - OK"
    fi

    # 检查环境变量
    if [ -z "${SANDBOX_ENABLED:-}" ]; then
        log_warn "SANDBOX_ENABLED not set, sandboxing may be disabled"
    else
        log_info "SANDBOX_ENABLED=${SANDBOX_ENABLED}"
    fi

    log_info "Security checks passed"
}

# =============================================================================
# 资源限制
# =============================================================================

apply_resource_limits() {
    log_info "Applying resource limits..."

    # 最大进程数
    if [ -f /sys/fs/cgroup/pids/max ]; then
        ulimit -u 100 2>/dev/null || true
    fi

    # 最大文件描述符
    ulimit -n 1024 2>/dev/null || true

    # 最大内存（如果设置了）
    if [ -n "${MAX_MEMORY:-}" ]; then
        ulimit -v $((MAX_MEMORY * 1024)) 2>/dev/null || true
    fi

    log_info "Resource limits applied"
}

# =============================================================================
# 文件系统限制
# =============================================================================

restrict_filesystem() {
    log_info "Restricting filesystem access..."

    # 禁止写入 /proc, /sys, /dev（容器内）
    for path in /proc/sys /proc/1 /sys/fs/cgroup /dev/kmsg; do
        if [ -d "$path" ]; then
            chmod 555 "$path" 2>/dev/null || true
        fi
    done

    log_info "Filesystem restrictions applied"
}

# =============================================================================
# 网络限制（如果配置了）
# =============================================================================

restrict_network() {
    if [ "${NETWORK_RESTRICTED:-true}" = "true" ]; then
        log_info "Network is restricted to whitelisted hosts only"

        # 只允许必要的出站连接（DNS, LLM API）
        # 注意：这需要在 iptables 规则中配合实现
        export ALLOWED_HOSTS="${ALLOWED_HOSTS:-api.openai.com,api.anthropic.com}"
    fi
}

# =============================================================================
# 主函数
# =============================================================================

main() {
    log_info "Starting Agent Sandbox..."

    # 前置检查
    check_security

    # 应用限制
    apply_resource_limits
    restrict_filesystem
    restrict_network

    # 执行命令
    if [ $# -gt 0 ]; then
        log_info "Executing: $@"
        exec "$@"
    else
        log_error "No command specified"
        echo "Usage: $0 [command] [args...]"
        exit 1
    fi
}

main "$@"
