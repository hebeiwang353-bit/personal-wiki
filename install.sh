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
    echo -e "  ${YELLOW}⚠ 未找到任何 MCP 客户端配置文件${NC}"
    echo "  请参考 INTEGRATIONS.md 手动配置"
fi

# ── 8. 完成 ───────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         MemoryOS 安装完成！               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "下一步："
echo ""
echo -e "  ${YELLOW}1.${NC} 配置 API Key（必做）："
echo "     编辑 $INSTALL_DIR/.env"
echo ""
echo -e "  ${YELLOW}2.${NC} 开始扫描："
echo "     $VENV_DIR/bin/python $CODE_DIR/main.py --max-files 500 --no-embed --skip-confirm"
echo ""
echo -e "  ${YELLOW}3.${NC} 接入 AI 工具："
echo "     查看 $CODE_DIR/INTEGRATIONS.md"
echo ""
echo -e "  ${YELLOW}4.${NC} 打开 Web UI："
echo "     $VENV_DIR/bin/python $CODE_DIR/web/server.py"
echo "     → http://localhost:8766"
echo ""
echo "代理日志：$INSTALL_DIR/proxy.log"
echo "Wiki 位置：$INSTALL_DIR/wiki/"
echo ""
