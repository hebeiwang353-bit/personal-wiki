#!/bin/bash
# MemoryOS 一键安装脚本 (macOS / Linux)
# 用法：bash install.sh
# 或远程：curl -sSL https://raw.githubusercontent.com/hebeiwang353-bit/personal-wiki/main/install.sh | bash

set -e

REPO_URL="https://github.com/hebeiwang353-bit/personal-wiki.git"
INSTALL_DIR="$HOME/.memoryos"
VENV_DIR="$INSTALL_DIR/venv"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

# 检测操作系统
OS_TYPE="$(uname -s)"
case "$OS_TYPE" in
    Darwin)  PLATFORM="mac"   ;;
    Linux)   PLATFORM="linux" ;;
    *)       PLATFORM="unknown" ;;
esac

echo ""
echo "╔══════════════════════════════════════╗"
echo "║      MemoryOS 安装程序               ║"
echo "║  让所有 AI 工具永久认识你            ║"
echo "╚══════════════════════════════════════╝"
echo "平台：$PLATFORM"
echo ""

# ── 1. 检查 Python ────────────────────────────────────────────
echo "▶ 检查 Python 环境..."
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ 未找到 Python3${NC}"
    if [ "$PLATFORM" = "mac" ]; then
        echo "  请安装：brew install python@3.11   或访问 https://www.python.org/downloads/"
    else
        echo "  请安装：sudo apt install python3 python3-venv  (Ubuntu/Debian)"
        echo "        或：sudo yum install python3                (CentOS/RHEL)"
    fi
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo -e "${RED}✗ 需要 Python 3.10+，当前版本：$PYTHON_VERSION${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Python $PYTHON_VERSION${NC}"

# ── 2. 准备代码 ───────────────────────────────────────────────
echo ""
echo "▶ 准备 MemoryOS 代码..."
mkdir -p "$INSTALL_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -d "$SCRIPT_DIR/core" ]; then
    # 本地运行：直接使用源码目录
    CODE_DIR="$SCRIPT_DIR"
    echo "  使用本地源码：$CODE_DIR"
else
    # 远程运行：clone 到 ~/.memoryos/src/
    CODE_DIR="$INSTALL_DIR/src"
    if [ ! -d "$CODE_DIR/core" ]; then
        if command -v git &>/dev/null; then
            echo "  从 GitHub 克隆..."
            git clone --depth 1 "$REPO_URL" "$CODE_DIR"
        else
            echo -e "${RED}✗ 需要 git 来克隆代码，请先安装 git${NC}"
            exit 1
        fi
    fi
fi
echo -e "  ${GREEN}✓ 代码路径：$CODE_DIR${NC}"

# ── 3. 创建虚拟环境并安装依赖 ─────────────────────────────────
echo ""
echo "▶ 安装 Python 依赖（首次约 1-2 分钟）..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$CODE_DIR/requirements.txt" --quiet
echo -e "  ${GREEN}✓ 依赖安装完成${NC}"

# ── 4. 创建 Wiki 目录结构 ─────────────────────────────────────
echo ""
echo "▶ 初始化 Wiki 知识库..."
mkdir -p "$INSTALL_DIR/wiki/projects" "$INSTALL_DIR/wiki/interests" "$INSTALL_DIR/wiki/tools"

if [ ! -f "$INSTALL_DIR/wiki/me.md" ]; then
    cat > "$INSTALL_DIR/wiki/index.md" <<'EOF'
# Wiki 索引

## 核心页面
- [关于我](me.md)

## 项目

## 兴趣领域

## 工具链
EOF

    cat > "$INSTALL_DIR/wiki/me.md" <<'EOF'
# 关于我

## 用户自述

（在这里写下你的核心身份、主要项目、沟通偏好。这一节永远不会被自动覆盖。）

EOF

    echo "$(date '+%Y-%m-%d') 初始化 Wiki" > "$INSTALL_DIR/wiki/log.md"
fi
echo -e "  ${GREEN}✓ Wiki 目录：$INSTALL_DIR/wiki/${NC}"

# ── 5. 配置文件 ───────────────────────────────────────────────
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$CODE_DIR/.env.example" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    echo -e "  ${YELLOW}⚠ 请编辑 $INSTALL_DIR/.env 填入你的 API Key${NC}"
fi

# ── 6. 注册系统服务（开机自启代理）────────────────────────────
echo ""
echo "▶ 注册系统服务..."

if [ "$PLATFORM" = "mac" ]; then
    # ── macOS: LaunchAgent ──
    PLIST_PATH="$HOME/Library/LaunchAgents/com.memoryos.proxy.plist"
    mkdir -p "$HOME/Library/LaunchAgents"

    cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.memoryos.proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>$CODE_DIR/proxy/proxy_server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$CODE_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/proxy.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/proxy_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$CODE_DIR</string>
        <key>MEMORYOS_HOME</key>
        <string>$INSTALL_DIR</string>
    </dict>
</dict>
</plist>
EOF

    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl load "$PLIST_PATH" 2>/dev/null && \
        echo -e "  ${GREEN}✓ 代理已注册为开机自启 (LaunchAgent)${NC}" || \
        echo -e "  ${YELLOW}⚠ 自动注册失败，请手动启动：python $CODE_DIR/proxy/proxy_server.py${NC}"

elif [ "$PLATFORM" = "linux" ]; then
    # ── Linux: systemd user service ──
    if command -v systemctl &>/dev/null; then
        SERVICE_DIR="$HOME/.config/systemd/user"
        SERVICE_FILE="$SERVICE_DIR/memoryos-proxy.service"
        mkdir -p "$SERVICE_DIR"

        cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=MemoryOS Proxy Server
After=network.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/python $CODE_DIR/proxy/proxy_server.py
WorkingDirectory=$CODE_DIR
Environment="PYTHONPATH=$CODE_DIR"
Environment="MEMORYOS_HOME=$INSTALL_DIR"
StandardOutput=append:$INSTALL_DIR/proxy.log
StandardError=append:$INSTALL_DIR/proxy_error.log
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF

        systemctl --user daemon-reload 2>/dev/null
        systemctl --user enable memoryos-proxy.service 2>/dev/null
        systemctl --user start memoryos-proxy.service 2>/dev/null && \
            echo -e "  ${GREEN}✓ 代理已注册为 systemd 用户服务${NC}" || \
            echo -e "  ${YELLOW}⚠ systemd 启动失败，请手动启动：python $CODE_DIR/proxy/proxy_server.py${NC}"
    else
        echo -e "  ${YELLOW}⚠ 未检测到 systemd，请手动启动：${NC}"
        echo "    nohup python $CODE_DIR/proxy/proxy_server.py > $INSTALL_DIR/proxy.log 2>&1 &"
    fi
fi

# ── 7. 注册 MCP Server 到常见 AI 客户端 ───────────────────────
echo ""
echo "▶ 尝试自动注册 MCP Server..."

CONFIG_CANDIDATES=(
    "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
    "$HOME/.config/Claude/claude_desktop_config.json"
    "$HOME/.claude.json"
    "$HOME/Library/Application Support/OpenClaw/config.json"
    "$HOME/.config/openclaw/config.json"
    "$HOME/.cursor/mcp.json"
    "$HOME/.config/cursor/mcp.json"
)

REGISTERED=0
for CONFIG_FILE in "${CONFIG_CANDIDATES[@]}"; do
    if [ -f "$CONFIG_FILE" ]; then
        "$VENV_DIR/bin/python" - <<PYEOF
import json
from pathlib import Path
config_file = Path("$CONFIG_FILE")
try:
    cfg = json.loads(config_file.read_text())
except Exception:
    cfg = {}
mcp = cfg.setdefault("mcpServers", {})
mcp["memoryos"] = {
    "command": "$VENV_DIR/bin/python",
    "args": ["$CODE_DIR/memoryos_mcp/mcp_server.py"],
    "env": {
        "PYTHONPATH": "$CODE_DIR",
        "MEMORYOS_HOME": "$INSTALL_DIR",
    },
}
config_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
print(f"  ✓ MCP 已注册到 {config_file.name}")
PYEOF
        REGISTERED=$((REGISTERED + 1))
    fi
done

if [ "$REGISTERED" -eq 0 ]; then
    echo -e "  ${YELLOW}⚠ 未找到 Claude/Cursor 配置文件，将在下方显示手动配置步骤${NC}"
fi

# ── 8. 自动设置每日 11:00 定时扫描 ────────────────────────────
echo ""
echo "▶ 设定每日自动扫描（11:00）..."
PYTHONPATH="$CODE_DIR" MEMORYOS_HOME="$INSTALL_DIR" \
    "$VENV_DIR/bin/python" -m memoryos_mcp.scheduler --set "11:00" 2>/dev/null && \
    echo -e "  ${GREEN}✓ 每日 11:00 自动更新记忆库已设定${NC}" || \
    echo -e "  ${YELLOW}⚠ 定时任务注册失败，可稍后手动运行：${NC}"
echo "    PYTHONPATH=$CODE_DIR $VENV_DIR/bin/python -m memoryos_mcp.scheduler --set \"11:00\""

# ── 9. 检测已安装的 AI 工具，打印针对性接入指令 ────────────────
echo ""
echo "▶ 检测本机 AI 工具..."
echo ""

PROXY_URL="http://localhost:8765/v1"

# 构造 MCP JSON 片段（供需要手动配置的用户复制）
MCP_JSON="{
  \"memoryos\": {
    \"command\": \"$VENV_DIR/bin/python\",
    \"args\": [\"$CODE_DIR/memoryos_mcp/mcp_server.py\"],
    \"env\": {\"PYTHONPATH\": \"$CODE_DIR\", \"MEMORYOS_HOME\": \"$INSTALL_DIR\"}
  }
}"

_check_tool() {
    local name="$1"; local app_paths=("${@:2}")
    for p in "${app_paths[@]}"; do
        if [ -e "$p" ]; then
            echo "$name"
            return 0
        fi
    done
    return 1
}

# Claude Code（命令行）
if command -v claude &>/dev/null; then
    if [ "$REGISTERED" -gt 0 ]; then
        echo -e "  ${GREEN}✓ Claude Code —— MCP 已自动注册，重启 Claude Code 生效${NC}"
    else
        echo -e "  ${YELLOW}○ Claude Code —— 请运行：${NC}"
        echo "      claude mcp add memoryos $VENV_DIR/bin/python $CODE_DIR/memoryos_mcp/mcp_server.py"
    fi
fi

# Claude Desktop
CLAUDE_DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [ -e "/Applications/Claude.app" ] || [ -e "$CLAUDE_DESKTOP_CONFIG" ]; then
    if [ "$REGISTERED" -gt 0 ]; then
        echo -e "  ${GREEN}✓ Claude Desktop —— MCP 已自动注册，重启 Claude 生效${NC}"
    else
        echo -e "  ${YELLOW}○ Claude Desktop —— 在 claude_desktop_config.json 的 mcpServers 节点加入：${NC}"
        echo "      $MCP_JSON"
    fi
fi

# Cursor
if [ -e "/Applications/Cursor.app" ] || [ -e "$HOME/.cursor" ]; then
    if [ -f "$HOME/.cursor/mcp.json" ] && [ "$REGISTERED" -gt 0 ]; then
        echo -e "  ${GREEN}✓ Cursor —— MCP 已自动注册，重启 Cursor 生效${NC}"
    else
        echo -e "  ${YELLOW}○ Cursor —— 在 ~/.cursor/mcp.json 的 mcpServers 节点加入：${NC}"
        echo "      $MCP_JSON"
    fi
fi

# Continue.dev
CONTINUE_CONFIG_JSON="$HOME/.continue/config.json"
if [ -e "$HOME/.continue" ]; then
    CONTINUE_OK=$("$VENV_DIR/bin/python" - 2>/dev/null <<PYEOF
from pathlib import Path
import json
cfg_file = Path("$CONTINUE_CONFIG_JSON")
if cfg_file.exists():
    try:
        cfg = json.loads(cfg_file.read_text())
        mcp_list = cfg.setdefault("experimental", {}).setdefault("modelContextProtocolServers", [])
        already = any(m.get("transport", {}).get("command", "").endswith("mcp_server.py") for m in mcp_list)
        if not already:
            mcp_list.append({
                "transport": {
                    "type": "stdio",
                    "command": "$VENV_DIR/bin/python",
                    "args": ["$CODE_DIR/memoryos_mcp/mcp_server.py"],
                    "env": {"PYTHONPATH": "$CODE_DIR", "MEMORYOS_HOME": "$INSTALL_DIR"}
                }
            })
            cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        print("ok")
    except Exception:
        pass
PYEOF
    )
    if [ "$CONTINUE_OK" = "ok" ]; then
        echo -e "  ${GREEN}✓ Continue.dev —— MCP 已自动注册，重启 VS Code 生效${NC}"
    else
        echo -e "  ${YELLOW}○ Continue.dev —— 在 ~/.continue/config.json 的 experimental.modelContextProtocolServers 中加入：${NC}"
        echo "      { \"transport\": { \"type\": \"stdio\", \"command\": \"$VENV_DIR/bin/python\", \"args\": [\"$CODE_DIR/memoryos_mcp/mcp_server.py\"] } }"
    fi
fi

# Cherry Studio
if [ -e "/Applications/Cherry Studio.app" ]; then
    echo -e "  ${YELLOW}○ Cherry Studio —— 设置 → 模型服务 → 添加服务商：${NC}"
    echo "      名称：MemoryOS Proxy    API地址：$PROXY_URL    Key：any"
fi

# Chatbox
if [ -e "/Applications/Chatbox.app" ] || [ -e "$HOME/Applications/Chatbox.app" ]; then
    echo -e "  ${YELLOW}○ Chatbox —— 设置 → AI服务商 → 自定义 → API地址：${NC}"
    echo "      $PROXY_URL"
fi

# OpenClaw / QClaw
for CLAW_APP in "OpenClaw" "QClaw" "Hermes"; do
    if [ -e "/Applications/${CLAW_APP}.app" ]; then
        echo -e "  ${YELLOW}○ ${CLAW_APP} —— 设置 → API → 地址改为：${NC}"
        echo "      $PROXY_URL"
    fi
done

# Codex CLI
if command -v codex &>/dev/null; then
    echo -e "  ${YELLOW}○ Codex CLI —— 在终端运行时加环境变量：${NC}"
    echo "      OPENAI_BASE_URL=$PROXY_URL codex"
fi

# ── 10. 完成 ──────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         MemoryOS 安装完成！               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${YELLOW}唯一的必做步骤：${NC}"
echo "  填写 API Key → 编辑 $INSTALL_DIR/.env"
echo "  设置 AI_PROVIDER 和 AI_API_KEY 两个字段"
echo ""
echo -e "  ${YELLOW}然后运行一次首次扫描（1-5 分钟，费用约 ¥1-5）：${NC}"
echo "  $VENV_DIR/bin/python $CODE_DIR/main.py --max-files 2000 --no-embed --skip-confirm"
echo ""
echo -e "  ${YELLOW}之后无需任何操作：${NC}"
echo "  · 每天 11:00 自动扫描更新记忆库"
echo "  · 代理服务开机自动启动（localhost:8765）"
echo "  · AI 工具已自动接入（见上方）"
echo ""
echo "  Web UI：$VENV_DIR/bin/python $CODE_DIR/web/server.py → http://localhost:8766"
echo "  代理日志：$INSTALL_DIR/proxy.log"
echo "  Wiki 位置：$INSTALL_DIR/wiki/"
echo ""
