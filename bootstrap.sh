#!/bin/bash
# MemoryOS 一键引导安装脚本 (macOS / Linux)
# 用法（一行搞定）：
#   curl -sSL https://raw.githubusercontent.com/hebeiwang353-bit/personal-wiki/main/bootstrap.sh | bash

set -e
GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'; CYAN='\033[36m'; NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      MemoryOS 安装引导程序           ║${NC}"
echo -e "${CYAN}║  让所有 AI 工具永久认识你            ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

OS_TYPE="$(uname -s)"

# ── 1. 检测 / 安装 Python 3.10+ ──────────────────────────────
echo -e "▶ ${YELLOW}检测 Python 环境...${NC}"

_python_ok() {
    local py="$1"
    command -v "$py" &>/dev/null || return 1
    "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null
}

PYTHON=""
for p in python3.12 python3.11 python3.10 python3 python; do
    if _python_ok "$p"; then
        PYTHON="$p"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${YELLOW}未检测到 Python 3.10+，正在自动安装...${NC}"

    if [ "$OS_TYPE" = "Darwin" ]; then
        # ── macOS ──
        if command -v brew &>/dev/null; then
            echo "  使用 Homebrew 安装 Python 3.11..."
            brew install python@3.11 --quiet
            # brew 安装后路径
            for p in /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11; do
                if _python_ok "$p"; then PYTHON="$p"; break; fi
            done
        else
            echo "  Homebrew 不可用，从 python.org 下载安装包..."
            PY_PKG="https://www.python.org/ftp/python/3.11.9/python-3.11.9-macos11.pkg"
            TMP_PKG="/tmp/python_installer.pkg"
            curl -L -o "$TMP_PKG" "$PY_PKG" --progress-bar
            sudo installer -pkg "$TMP_PKG" -target / -verboseR 2>/dev/null
            rm -f "$TMP_PKG"
            # macOS 官方安装包位置
            for p in /usr/local/bin/python3.11 /usr/bin/python3; do
                if _python_ok "$p"; then PYTHON="$p"; break; fi
            done
        fi

    elif [ "$OS_TYPE" = "Linux" ]; then
        # ── Linux ──
        if command -v apt-get &>/dev/null; then
            echo "  使用 apt 安装 Python 3.11..."
            sudo apt-get update -qq
            sudo apt-get install -y python3.11 python3.11-venv python3-pip
            PYTHON="python3.11"
        elif command -v dnf &>/dev/null; then
            echo "  使用 dnf 安装 Python 3.11..."
            sudo dnf install -y python3.11 python3-pip
            PYTHON="python3.11"
        elif command -v yum &>/dev/null; then
            echo "  使用 yum 安装 Python 3..."
            sudo yum install -y python3 python3-pip
            PYTHON="python3"
        elif command -v pacman &>/dev/null; then
            echo "  使用 pacman 安装 Python..."
            sudo pacman -S --noconfirm python python-pip
            PYTHON="python3"
        else
            echo -e "  ${RED}✗ 无法自动安装 Python，请手动安装 Python 3.10+${NC}"
            echo "    Ubuntu/Debian：sudo apt install python3.11"
            echo "    CentOS/RHEL：  sudo dnf install python3.11"
            exit 1
        fi
    fi

    # 验证安装成功
    if [ -z "$PYTHON" ] || ! _python_ok "$PYTHON"; then
        echo -e "  ${RED}✗ Python 安装失败，请手动安装 Python 3.10+ 后重试${NC}"
        exit 1
    fi
    echo -e "  ${GREEN}✓ Python 已安装：$("$PYTHON" --version)${NC}"
else
    echo -e "  ${GREEN}✓ 检测到 $("$PYTHON" --version)${NC}"
fi

# ── 2. 确保 pip 可用 ──────────────────────────────────────────
echo ""
echo -e "▶ ${YELLOW}检查 pip...${NC}"
if ! "$PYTHON" -m pip --version &>/dev/null; then
    echo "  安装 pip..."
    curl -sSL https://bootstrap.pypa.io/get-pip.py | "$PYTHON"
fi
echo -e "  ${GREEN}✓ pip 可用${NC}"

# ── 3. pip install memoryos ───────────────────────────────────
echo ""
echo -e "▶ ${YELLOW}安装 MemoryOS（约 1-3 分钟）...${NC}"
"$PYTHON" -m pip install --upgrade memoryos --quiet
echo -e "  ${GREEN}✓ MemoryOS 安装完成${NC}"

# ── 4. 运行 memoryos install ──────────────────────────────────
echo ""
# 找到 memoryos 命令位置
MEMORYOS_CMD=""
for p in \
    "$("$PYTHON" -c "import sys; print(sys.prefix)")/bin/memoryos" \
    "$HOME/.local/bin/memoryos" \
    "$(command -v memoryos 2>/dev/null)"; do
    if [ -f "$p" ]; then
        MEMORYOS_CMD="$p"
        break
    fi
done

if [ -z "$MEMORYOS_CMD" ]; then
    # 刷新 PATH 后再找
    export PATH="$HOME/.local/bin:$PATH"
    MEMORYOS_CMD="$(command -v memoryos 2>/dev/null)"
fi

if [ -n "$MEMORYOS_CMD" ]; then
    "$MEMORYOS_CMD" install
else
    # 直接用 python -m memoryos.cli
    "$PYTHON" -m memoryos.cli install
fi
