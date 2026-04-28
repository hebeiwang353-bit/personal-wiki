#!/bin/bash
# MemoryOS 一键安装脚本 (macOS / Linux)
# 用法：curl -sSL https://raw.githubusercontent.com/xxx/memoryos/main/install.sh | bash
# 或本地运行：bash install.sh

set -e

REPO_URL="https://github.com/xxx/memoryos"   # 发布后替换为真实地址
INSTALL_DIR="$HOME/.memoryos"
VENV_DIR="$INSTALL_DIR/venv"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════╗"
echo "║      MemoryOS 安装程序               ║"
echo "║  让所有 AI 工具永久认识你            ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. 检查 Python ────────────────────────────────────────────
echo "▶ 检查 Python 环境..."
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ 未找到 Python3，请先安装：https://www.python.org/downloads/${NC}"
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

# ── 2. 下载 MemoryOS ──────────────────────────────────────────
echo ""
echo "▶ 下载 MemoryOS..."
mkdir -p "$INSTALL_DIR"

if command -v git &>/dev/null && [ ! -d "$INSTALL_DIR/.git" ]; then
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR/src" 2>/dev/null || {
        echo -e "${YELLOW}  Git 克隆失败，尝试下载压缩包...${NC}"
        _download_zip
    }
elif [ -d "$(dirname "$0")/core" ]; then
    # 本地运行：直接复制
    SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
    echo "  使用本地源码：$SRC_DIR"
    if [ "$SRC_DIR" != "$INSTALL_DIR/src" ]; then
        cp -r "$SRC_DIR" "$INSTALL_DIR/src" 2>/dev/null || true
    fi
fi

# 如果 src 子目录存在则以它为根，否则以 INSTALL_DIR 为根
if [ -d "$INSTALL_DIR/src/core" ]; then
    CODE_DIR="$INSTALL_DIR/src"
else
    CODE_DIR="$INSTALL_DIR"
fi
echo -e "  ${GREEN}✓ 代码路径：$CODE_DIR${NC}"

# ── 3. 创建虚拟环境并安装依赖 ─────────────────────────────────
echo ""
echo "▶ 安装 Python 依赖（首次约需 1-2 分钟）..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install \
    anthropic openai chromadb \
    pypdf python-docx openpyxl \
    tiktoken scikit-learn numpy \
    fastapi uvicorn aiohttp \
    "mcp[cli]" python-dotenv \
    rich tqdm --quiet

echo -e "  ${GREEN}✓ 依赖安装完成${NC}"

# ── 4. 创建 Wiki 目录结构 ─────────────────────────────────────
echo ""
echo "▶ 初始化 Wiki 知识库..."
mkdir -p "$INSTALL_DIR/wiki/projects" "$INSTALL_DIR/wiki/interests" "$INSTALL_DIR/wiki/tools"

# 创建初始页面
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

（待建立）
EOF

echo "$(date '+%Y-%m-%d')" > "$INSTALL_DIR/wiki/log.md"
echo "初始化 Wiki" >> "$INSTALL_DIR/wiki/log.md"

echo -e "  ${GREEN}✓ Wiki 目录：$INSTALL_DIR/wiki/${NC}"

# ── 5. 配置文件 ───────────────────────────────────────────────
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cat > "$INSTALL_DIR/.env" <<'EOF'
# MemoryOS API Key 配置
# 填入你使用的 AI 服务的 Key（至少配置一个）

ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
EOF
    chmod 600 "$INSTALL_DIR/.env"
fi

# ── 6. 注册 macOS LaunchAgent（代理开机自启）─────────────────
echo ""
echo "▶ 注册系统服务..."
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

launchctl load "$PLIST_PATH" 2>/dev/null && \
    echo -e "  ${GREEN}✓ 代理已注册为开机自启服务${NC}" || \
    echo -e "  ${YELLOW}⚠ 代理注册失败，请手动启动：python $CODE_DIR/proxy/proxy_server.py${NC}"

# ── 7. 向 OpenClaw 注册 MCP Server ────────────────────────────
echo ""
echo "▶ 注册 MCP Server 到 OpenClaw..."

OPENCLAW_CONFIG_CANDIDATES=(
    "$HOME/Library/Application Support/OpenClaw/config.json"
    "$HOME/.config/openclaw/config.json"
    "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
    "$HOME/.config/Claude/claude_desktop_config.json"
)

MCP_ENTRY=$(cat <<EOF
{
  "command": "$VENV_DIR/bin/python",
  "args": ["$CODE_DIR/mcp/mcp_server.py"],
  "env": {
    "PYTHONPATH": "$CODE_DIR",
    "MEMORYOS_HOME": "$INSTALL_DIR"
  }
}
EOF
)

REGISTERED=false
for CONFIG_FILE in "${OPENCLAW_CONFIG_CANDIDATES[@]}"; do
    if [ -f "$CONFIG_FILE" ]; then
        echo "  找到配置文件：$CONFIG_FILE"
        # 用 Python 安全地合并 JSON
        "$VENV_DIR/bin/python" - <<PYEOF
import json, sys
config_file = "$CONFIG_FILE"
with open(config_file) as f:
    cfg = json.load(f)
mcp = cfg.setdefault("mcpServers", {})
mcp["memoryos"] = json.loads('''$MCP_ENTRY''')
with open(config_file, "w") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print("  MCP 已注册到", config_file)
PYEOF
        REGISTERED=true
        break
    fi
done

if [ "$REGISTERED" = false ]; then
    echo -e "  ${YELLOW}⚠ 未找到 OpenClaw/Claude Desktop 配置文件${NC}"
    echo "  请手动在 AI 工具的 MCP 设置中添加："
    echo "  $MCP_ENTRY"
fi

# ── 8. 完成提示 ───────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         MemoryOS 安装完成！               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "下一步："
echo ""
echo "  1. 配置 API Key："
echo "     编辑 $INSTALL_DIR/.env，填入你的 API Key"
echo ""
echo "  2. 开始扫描文件："
echo "     $VENV_DIR/bin/python $CODE_DIR/main.py --max-files 200"
echo ""
echo "  3. 设定定时扫描（可选）："
echo "     $VENV_DIR/bin/python $CODE_DIR/mcp/scheduler.py --set \"22:00\""
echo ""
echo "  4. 其他 AI 工具（QClaw / Ollama 等）："
echo "     把 API 地址改为 http://localhost:8765"
echo ""
echo "  代理日志：$INSTALL_DIR/proxy.log"
echo "  Wiki 位置：$INSTALL_DIR/wiki/"
echo ""
