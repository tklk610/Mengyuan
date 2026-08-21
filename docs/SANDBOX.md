# Docker Sandbox Security Configuration

## Overview

This document describes the Docker-level security sandbox for the NovelCraft Agent system.

## Security Layers

```
┌─────────────────────────────────────────────────────────────┐
│                Network Layer (iptables/eBPF)                │
│   Allowlist: api.openai.com, api.anthropic.com, DNS         │
├─────────────────────────────────────────────────────────────┤
│                Container Layer (Docker)                      │
│   - no-new-privileges                                     │
│   - read-only filesystem                                  │
│   - non-root user                                        │
│   - resource limits (cpu, memory, pids)                   │
├─────────────────────────────────────────────────────────────┤
│                Filesystem Layer                           │
│   - tmpfs for /tmp                                      │
│   - read-only mounts for code/skills/prompts               │
│   - seccomp syscall filtering                            │
├─────────────────────────────────────────────────────────────┤
│                Application Layer (Python)                  │
│   - PathGuard, ContentGuard, PolicyGuard                 │
│   - VirtualFileSystem                                   │
│   - SkillSandboxLoader                                  │
└─────────────────────────────────────────────────────────────┘
```

## Docker Security Options

### 1. no-new-privileges

```yaml
security_opt:
  - no-new-privileges:true
```

Prevents the container or any children from gaining new privileges via suid binaries etc.

### 2. Read-only Root Filesystem

```yaml
read_only: true
```

### 3. User Namespace Remapping

```yaml
user: "1000:1000"
```

Run as non-root user inside container.

### 4. Resource Limits

```yaml
deploy:
  resources:
    limits:
      cpus: "0.5"
      memory: 512M
      pids: 100
```

### 5. tmpfs for Write Areas

```yaml
tmpfs:
  - /tmp:size=50M,noexec,nosuid,nodev
  - /var/cache:pids,size=20M,noexec,nosuid,nodev
```

### 6. Capabilities Drop

```yaml
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE  # Only if needed
```

## Network Policies

### Outbound Whitelist

Only allow connections to necessary hosts:

```bash
# iptables example (on host)
-A OUTPUT -p tcp -d api.openai.com --dport 443 -m state --state NEW,ESTABLISHED -j ACCEPT
-A OUTPUT -p tcp -d api.anthropic.com --dport 443 -m state --state NEW,ESTABLISHED -j ACCEPT
-A OUTPUT -p tcp -d 8.8.8.8 --dport 53 -m state --state NEW,ESTABLISHED -j ACCEPT
-A OUTPUT -m state --state ESTABLISHED -j ACCEPT
-A OUTPUT -j REJECT --reject-with icmp-port-unreachable
```

## Seccomp Profile

Custom seccomp profile restricting syscalls:

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "syscalls": [
    {
      "names": ["read", "write", "open", "close", "exit", "sched_yield"],
      "action": "SCMP_ACT_ALLOW"
    }
  ]
}
```

## Usage

### Start sandboxed agent

```bash
# Build sandbox image
docker build -f Dockerfile.sandbox -t novelcraft-sandbox .

# Run with sandbox configuration
docker-compose -f docker-compose.sandbox.yml up agent-sandboxed

# Or run custom command in sandbox
docker run --rm \
  --security-opt no-new-privileges:true \
  --read-only \
  --user 1000:1000 \
  --tmpfs /tmp:size=50M,noexec,nosuid \
  -v $(pwd)/src:/workspace/src:ro \
  novelcraft-sandbox \
  python -m pytest tests/unit/
```

### Verify sandbox is active

```bash
# Inside container
cat /proc/self/status | grep -E "^(Uid|Gid)"


# Should show non-zero UID/GID (not 0 = root)

# Check read-only filesystem
mount | grep -E "^/dev.*on\s+/\s+"
# Should show something like: ro
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| SANDBOX_ENABLED | true | Enable sandboxing |
| SANDBOX_VIRTUAL_MODE | false | Use virtual filesystem |
| SANDBOX_ROOT_DIR | /workspace | Root directory |
| ALLOWED_HOSTS | api.openai.com,api.anthropic.com | Allowed outbound hosts |
| MAX_MEMORY | 512 | Max memory in MB |
| NETWORK_RESTRICTED | true | Restrict network access |
