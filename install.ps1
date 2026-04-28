# MemoryOS 一键安装脚本 (Windows PowerShell)
# 用法：右键 install.ps1 → "用 PowerShell 运行"
# 或在 PowerShell 中：.\install.ps1

$ErrorActionPreference = "Stop"

$INSTALL_DIR = "$env:USERPROFILE\.memoryos"
$VENV_DIR    = "$INSTALL_DIR\venv"
$REPO_URL    = "https://github.com/xxx/memoryos"   # 发布后替换

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      MemoryOS 安装程序               ║" -ForegroundColor Cyan
Write-Host "║  让所有 AI 工具永久认识你            ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. 检查 Python ────────────────────────────────────────────
Write-Host "▶ 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    if ($pyVersion -notmatch "Python 3\.(1[0-9]|[2-9]\d)") {
        Write-Host "✗ 需要 Python 3.10+，当前：$pyVersion" -ForegroundColor Red
        Write-Host "  请前往 https://www.python.org/downloads/ 下载安装" -ForegroundColor Red
        Read-Host "按 Enter 退出"
        exit 1
    }
    Write-Host "  ✓ $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ 未找到 Python，请先安装：https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}

# ── 2. 下载 / 复制代码 ────────────────────────────────────────
Write-Host ""
Write-Host "▶ 准备 MemoryOS 代码..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path "$SCRIPT_DIR\core") {
    # 本地运行
    $CODE_DIR = $SCRIPT_DIR
    Write-Host "  使用本地源码：$CODE_DIR" -ForegroundColor Green
} else {
    # 从 GitHub 下载
    $CODE_DIR = "$INSTALL_DIR\src"
    if (-not (Test-Path $CODE_DIR)) {
        Write-Host "  正在从 GitHub 下载..." -ForegroundColor Yellow
        try {
            git clone --depth 1 $REPO_URL $CODE_DIR 2>&1 | Out-Null
        } catch {
            $ZIP_URL = "$REPO_URL/archive/refs/heads/main.zip"
            $ZIP_PATH = "$env:TEMP\memoryos.zip"
            Invoke-WebRequest $ZIP_URL -OutFile $ZIP_PATH
            Expand-Archive $ZIP_PATH -DestinationPath $INSTALL_DIR -Force
            Rename-Item "$INSTALL_DIR\memoryos-main" $CODE_DIR -Force
        }
    }
    Write-Host "  ✓ 代码路径：$CODE_DIR" -ForegroundColor Green
}

# ── 3. 创建虚拟环境并安装依赖 ─────────────────────────────────
Write-Host ""
Write-Host "▶ 安装 Python 依赖（首次约需 2-3 分钟）..." -ForegroundColor Yellow
python -m venv $VENV_DIR
& "$VENV_DIR\Scripts\pip" install --upgrade pip --quiet
& "$VENV_DIR\Scripts\pip" install `
    anthropic openai chromadb `
    pypdf python-docx openpyxl `
    tiktoken scikit-learn numpy `
    fastapi uvicorn aiohttp `
    mcp python-dotenv `
    rich tqdm --quiet

Write-Host "  ✓ 依赖安装完成" -ForegroundColor Green

# ── 4. 创建 Wiki 目录结构 ─────────────────────────────────────
Write-Host ""
Write-Host "▶ 初始化 Wiki 知识库..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$INSTALL_DIR\wiki\projects"  | Out-Null
New-Item -ItemType Directory -Force -Path "$INSTALL_DIR\wiki\interests" | Out-Null
New-Item -ItemType Directory -Force -Path "$INSTALL_DIR\wiki\tools"     | Out-Null

if (-not (Test-Path "$INSTALL_DIR\wiki\me.md")) {
    Set-Content "$INSTALL_DIR\wiki\me.md"    "# 关于我`n`n（待建立）" -Encoding UTF8
    Set-Content "$INSTALL_DIR\wiki\index.md" "# Wiki 索引`n`n## 核心页面`n- [关于我](me.md)`n`n## 项目`n`n## 兴趣领域`n`n## 工具链" -Encoding UTF8
    Set-Content "$INSTALL_DIR\wiki\log.md"   "# 操作日志`n`n$(Get-Date -Format 'yyyy-MM-dd') 初始化 Wiki" -Encoding UTF8
}
Write-Host "  ✓ Wiki 目录：$INSTALL_DIR\wiki\" -ForegroundColor Green

# ── 5. 配置文件 ───────────────────────────────────────────────
if (-not (Test-Path "$INSTALL_DIR\.env")) {
    Set-Content "$INSTALL_DIR\.env" @"
# MemoryOS API Key 配置
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
"@ -Encoding UTF8
}

# ── 6. 注册 Windows 任务计划（代理开机自启）──────────────────
Write-Host ""
Write-Host "▶ 注册系统服务（开机自启）..." -ForegroundColor Yellow
$PYTHON_EXE = "$VENV_DIR\Scripts\python.exe"
$PROXY_SCRIPT = "$CODE_DIR\proxy\proxy_server.py"

$action  = New-ScheduledTaskAction -Execute $PYTHON_EXE -Argument "`"$PROXY_SCRIPT`"" -WorkingDirectory $CODE_DIR
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask -TaskName "MemoryOS_Proxy" `
        -Action $action -Trigger $trigger -Settings $settings `
        -Description "MemoryOS 个人上下文代理" -Force | Out-Null
    Write-Host "  ✓ 代理已注册为开机自启任务" -ForegroundColor Green

    # 立即启动
    Start-ScheduledTask -TaskName "MemoryOS_Proxy"
    Write-Host "  ✓ 代理已启动（http://localhost:8765）" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ 自动注册失败，请以管理员身份运行脚本" -ForegroundColor Yellow
}

# ── 7. 向 OpenClaw / Claude Desktop 注册 MCP ─────────────────
Write-Host ""
Write-Host "▶ 注册 MCP Server..." -ForegroundColor Yellow

$CONFIG_CANDIDATES = @(
    "$env:APPDATA\OpenClaw\config.json",
    "$env:APPDATA\Claude\claude_desktop_config.json"
)

$MCP_CONFIG = @{
    command = $PYTHON_EXE
    args    = @($PROXY_SCRIPT)
    env     = @{ PYTHONPATH = $CODE_DIR; MEMORYOS_HOME = $INSTALL_DIR }
}

$REGISTERED = $false
foreach ($cfgPath in $CONFIG_CANDIDATES) {
    if (Test-Path $cfgPath) {
        try {
            $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
            if (-not $cfg.mcpServers) { $cfg | Add-Member -MemberType NoteProperty -Name mcpServers -Value @{} }
            $cfg.mcpServers | Add-Member -MemberType NoteProperty -Name "memoryos" -Value $MCP_CONFIG -Force
            $cfg | ConvertTo-Json -Depth 10 | Set-Content $cfgPath -Encoding UTF8
            Write-Host "  ✓ MCP 已注册到 $cfgPath" -ForegroundColor Green
            $REGISTERED = $true
            break
        } catch {
            Write-Host "  ⚠ 注册到 $cfgPath 失败：$_" -ForegroundColor Yellow
        }
    }
}

if (-not $REGISTERED) {
    Write-Host "  ⚠ 未找到 OpenClaw 配置文件" -ForegroundColor Yellow
    Write-Host "  请在 AI 工具的 MCP 设置中手动添加：" -ForegroundColor Yellow
    Write-Host "  命令：$PYTHON_EXE" -ForegroundColor Gray
    Write-Host "  参数：$CODE_DIR\mcp\mcp_server.py" -ForegroundColor Gray
}

# ── 8. 完成 ───────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║         MemoryOS 安装完成！               ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. 配置 API Key："
Write-Host "     用记事本打开：$INSTALL_DIR\.env"
Write-Host ""
Write-Host "  2. 开始扫描文件："
Write-Host "     $PYTHON_EXE $CODE_DIR\main.py --max-files 200"
Write-Host ""
Write-Host "  3. 其他 AI 工具（QClaw 等）："
Write-Host "     把 API 地址改为 http://localhost:8765"
Write-Host ""
Write-Host "  Wiki 位置：$INSTALL_DIR\wiki\"
Write-Host ""
Read-Host "按 Enter 关闭"
