# MemoryOS 一键安装脚本 (Windows PowerShell)
# 用法：右键 install.ps1 → "用 PowerShell 运行"
# 或在 PowerShell 中：Set-ExecutionPolicy Bypass -Scope Process; .\install.ps1

$ErrorActionPreference = "Stop"

$REPO_URL    = "https://github.com/hebeiwang353-bit/personal-wiki"
$INSTALL_DIR = "$env:USERPROFILE\.memoryos"
$VENV_DIR    = "$INSTALL_DIR\venv"
$PYTHON_EXE  = "$VENV_DIR\Scripts\python.exe"
$PROXY_URL   = "http://localhost:8765/v1"

function Write-Step { param($msg) Write-Host "`n▶ $msg" -ForegroundColor Yellow }
function Write-OK   { param($msg) Write-Host "  ✓ $msg" -ForegroundColor Green  }
function Write-Warn { param($msg) Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Info { param($msg) Write-Host "    $msg" -ForegroundColor Gray   }

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      MemoryOS 安装程序               ║" -ForegroundColor Cyan
Write-Host "║  让所有 AI 工具永久认识你            ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. 检查 Python 3.10+ ──────────────────────────────────────
Write-Step "检查 Python 环境..."
try {
    $pyOut = python --version 2>&1
    if ($pyOut -notmatch "Python 3\.(1[0-9]|[2-9]\d)") {
        Write-Host "✗ 需要 Python 3.10+，当前：$pyOut" -ForegroundColor Red
        Write-Info "请前往 https://www.python.org/downloads/ 安装（勾选 Add to PATH）"
        Read-Host "按 Enter 退出"; exit 1
    }
    Write-OK $pyOut
} catch {
    Write-Host "✗ 未找到 Python" -ForegroundColor Red
    Write-Info "请安装：https://www.python.org/downloads/"
    Read-Host "按 Enter 退出"; exit 1
}

# ── 2. 准备代码 ───────────────────────────────────────────────
Write-Step "准备 MemoryOS 代码..."
New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path "$SCRIPT_DIR\core") {
    # 本地运行（从下载的压缩包或 clone 的目录）
    $CODE_DIR = $SCRIPT_DIR
    Write-OK "使用本地源码：$CODE_DIR"
} else {
    # 从 GitHub 下载
    $CODE_DIR = "$INSTALL_DIR\src"
    if (-not (Test-Path "$CODE_DIR\core")) {
        Write-Host "  正在从 GitHub 下载..." -ForegroundColor Yellow
        $git_ok = $false
        try {
            git clone --depth 1 $REPO_URL $CODE_DIR 2>&1 | Out-Null
            $git_ok = $true
        } catch {}

        if (-not $git_ok) {
            # 无 git，改用 ZIP 下载
            Write-Host "  git 不可用，改用 ZIP 下载..." -ForegroundColor Yellow
            $ZIP_URL  = "$REPO_URL/archive/refs/heads/main.zip"
            $ZIP_PATH = "$env:TEMP\memoryos.zip"
            try {
                Invoke-WebRequest $ZIP_URL -OutFile $ZIP_PATH -UseBasicParsing
                Expand-Archive $ZIP_PATH -DestinationPath "$INSTALL_DIR\_extract" -Force
                $extracted = Get-ChildItem "$INSTALL_DIR\_extract" -Directory | Select-Object -First 1
                if ($extracted) {
                    Move-Item $extracted.FullName $CODE_DIR -Force
                    Remove-Item "$INSTALL_DIR\_extract" -Recurse -Force -ErrorAction SilentlyContinue
                }
                Remove-Item $ZIP_PATH -Force -ErrorAction SilentlyContinue
            } catch {
                Write-Host "✗ 下载失败：$_" -ForegroundColor Red
                Write-Info "请手动下载：$REPO_URL/archive/refs/heads/main.zip"
                Read-Host "按 Enter 退出"; exit 1
            }
        }
    }
    Write-OK "代码路径：$CODE_DIR"
}

# ── 3. 创建虚拟环境并安装依赖 ─────────────────────────────────
Write-Step "安装 Python 依赖（首次约需 2-4 分钟）..."
python -m venv $VENV_DIR
& "$VENV_DIR\Scripts\pip" install --upgrade pip --quiet
& "$VENV_DIR\Scripts\pip" install -r "$CODE_DIR\requirements.txt" --quiet
Write-OK "依赖安装完成"

# ── 4. 创建 Wiki 目录结构 ─────────────────────────────────────
Write-Step "初始化 Wiki 知识库..."
@("wiki\projects", "wiki\interests", "wiki\tools") | ForEach-Object {
    New-Item -ItemType Directory -Force -Path "$INSTALL_DIR\$_" | Out-Null
}

if (-not (Test-Path "$INSTALL_DIR\wiki\me.md")) {
    $meContent = @"
# 关于我

## 用户自述

（在这里写下你的核心身份、主要项目、沟通偏好。这一节永远不会被自动覆盖。）

"@
    Set-Content "$INSTALL_DIR\wiki\me.md"    $meContent -Encoding UTF8

    $indexContent = @"
# Wiki 索引

## 核心页面
- [关于我](me.md)

## 项目

## 兴趣领域

## 工具链
"@
    Set-Content "$INSTALL_DIR\wiki\index.md" $indexContent -Encoding UTF8
    Set-Content "$INSTALL_DIR\wiki\log.md"   "$(Get-Date -Format 'yyyy-MM-dd') 初始化 Wiki" -Encoding UTF8
}
Write-OK "Wiki 目录：$INSTALL_DIR\wiki\"

# ── 5. 配置文件 ───────────────────────────────────────────────
Write-Step "准备配置文件..."
if (-not (Test-Path "$INSTALL_DIR\.env")) {
    Copy-Item "$CODE_DIR\.env.example" "$INSTALL_DIR\.env"
    Write-Warn "请编辑 $INSTALL_DIR\.env 填入你的 API Key"
}
Write-OK "配置文件：$INSTALL_DIR\.env"

# ── 6. 注册代理开机自启（Task Scheduler）────────────────────
Write-Step "注册代理开机自启..."

# 创建一个包装 bat，确保 PYTHONPATH 生效
$BAT_PATH = "$INSTALL_DIR\start_proxy.bat"
$proxyBatContent = @"
@echo off
set PYTHONPATH=$CODE_DIR
set MEMORYOS_HOME=$INSTALL_DIR
"$PYTHON_EXE" "$CODE_DIR\proxy\proxy_server.py"
"@
[System.IO.File]::WriteAllText($BAT_PATH, $proxyBatContent, [System.Text.Encoding]::ASCII)

$action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BAT_PATH`""
$trigger  = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew

try {
    Register-ScheduledTask -TaskName "MemoryOS_Proxy" `
        -Action $action -Trigger $trigger -Settings $settings `
        -Description "MemoryOS 个人上下文代理 (localhost:8765)" -Force | Out-Null
    Start-ScheduledTask -TaskName "MemoryOS_Proxy" -ErrorAction SilentlyContinue
    Write-OK "代理已注册为开机自启，已立即启动（localhost:8765）"
} catch {
    Write-Warn "自动注册失败（需管理员权限），稍后请手动运行："
    Write-Info  "$PYTHON_EXE $CODE_DIR\proxy\proxy_server.py"
}

# ── 7. 注册 MCP Server 到常见 AI 客户端 ───────────────────────
Write-Step "注册 MCP Server..."

$MCP_SCRIPT = "$CODE_DIR\memoryos_mcp\mcp_server.py"
$MCP_ENTRY  = [ordered]@{
    command = $PYTHON_EXE
    args    = @($MCP_SCRIPT)
    env     = [ordered]@{ PYTHONPATH = $CODE_DIR; MEMORYOS_HOME = $INSTALL_DIR }
}

$CONFIG_CANDIDATES = @(
    "$env:APPDATA\Claude\claude_desktop_config.json",
    "$env:USERPROFILE\.claude.json",
    "$env:USERPROFILE\.cursor\mcp.json",
    "$env:APPDATA\Cursor\mcp.json"
)

$REGISTERED = 0
foreach ($cfgPath in $CONFIG_CANDIDATES) {
    if (Test-Path $cfgPath) {
        try {
            $cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if (-not $cfg.PSObject.Properties["mcpServers"]) {
                $cfg | Add-Member -MemberType NoteProperty -Name mcpServers -Value ([ordered]@{})
            }
            $cfg.mcpServers | Add-Member -MemberType NoteProperty -Name "memoryos" -Value $MCP_ENTRY -Force
            $cfg | ConvertTo-Json -Depth 10 | Set-Content $cfgPath -Encoding UTF8
            Write-OK "MCP 已注册到 $(Split-Path $cfgPath -Leaf)"
            $REGISTERED++
        } catch {
            Write-Warn "注册到 $(Split-Path $cfgPath -Leaf) 失败：$_"
        }
    }
}

if ($REGISTERED -eq 0) {
    Write-Warn "未找到 Claude Desktop / Cursor 配置文件，安装后可手动添加"
}

# ── 8. 设定每日 11:00 自动扫描 ────────────────────────────────
Write-Step "设定每日 11:00 自动扫描..."

$SCAN_BAT = "$INSTALL_DIR\daily_scan.bat"
$scanBatContent = @"
@echo off
set PYTHONPATH=$CODE_DIR
set MEMORYOS_HOME=$INSTALL_DIR
"$PYTHON_EXE" "$CODE_DIR\main.py" --max-files 2000 --no-embed --skip-confirm >> "$INSTALL_DIR\scan.log" 2>&1
"@
[System.IO.File]::WriteAllText($SCAN_BAT, $scanBatContent, [System.Text.Encoding]::ASCII)

$scanAction  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$SCAN_BAT`""
$scanTrigger = New-ScheduledTaskTrigger -Daily -At "11:00"
$scanSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable $true

try {
    Register-ScheduledTask -TaskName "MemoryOS_DailyScan" `
        -Action $scanAction -Trigger $scanTrigger -Settings $scanSettings `
        -Description "MemoryOS 每日记忆更新" -Force | Out-Null
    Write-OK "每日 11:00 自动扫描已设定"
} catch {
    Write-Warn "定时扫描注册失败（需管理员权限），请手动运行首次扫描"
}

# ── 9. 检测已安装的 AI 工具，给出针对性接入指令 ───────────────
Write-Step "检测本机 AI 工具..."
Write-Host ""

# Cursor
$cursor_mcp = "$env:USERPROFILE\.cursor\mcp.json"
if ((Test-Path "$env:LOCALAPPDATA\Programs\cursor") -or (Test-Path $cursor_mcp)) {
    if ($REGISTERED -gt 0) {
        Write-OK "Cursor —— MCP 已自动注册，重启 Cursor 生效"
    } else {
        Write-Warn "Cursor —— 在 %USERPROFILE%\.cursor\mcp.json 的 mcpServers 节点加入 memoryos 配置"
    }
}

# Claude Desktop
if (Test-Path "$env:APPDATA\Claude") {
    if ($REGISTERED -gt 0) {
        Write-OK "Claude Desktop —— MCP 已自动注册，重启 Claude 生效"
    } else {
        Write-Warn "Claude Desktop —— 在 claude_desktop_config.json 的 mcpServers 加入 memoryos 配置"
    }
}

# Cherry Studio
if ((Test-Path "$env:LOCALAPPDATA\Programs\Cherry Studio") -or (Test-Path "$env:APPDATA\Cherry Studio")) {
    Write-Host "  " -NoNewline
    Write-Host "○ Cherry Studio" -ForegroundColor Yellow -NoNewline
    Write-Host " —— 设置 → 模型服务 → 添加服务商："
    Write-Info "名称：MemoryOS Proxy    API地址：$PROXY_URL    Key：any"
}

# Chatbox
if (Test-Path "$env:APPDATA\Chatbox") {
    Write-Host "  " -NoNewline
    Write-Host "○ Chatbox" -ForegroundColor Yellow -NoNewline
    Write-Host " —— 设置 → AI服务商 → 自定义 → API地址："
    Write-Info $PROXY_URL
}

# OpenClaw / QClaw
foreach ($claw in @("OpenClaw", "QClaw", "Hermes")) {
    if ((Test-Path "$env:APPDATA\$claw") -or (Test-Path "$env:LOCALAPPDATA\Programs\$claw")) {
        Write-Host "  " -NoNewline
        Write-Host "○ $claw" -ForegroundColor Yellow -NoNewline
        Write-Host " —— 设置 → API → 地址改为："
        Write-Info $PROXY_URL
    }
}

# ── 10. 完成 ──────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║         MemoryOS 安装完成！               ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "唯一的必做步骤：" -ForegroundColor Yellow
Write-Host "  用记事本打开 $INSTALL_DIR\.env"
Write-Host "  填写 AI_PROVIDER 和 AI_API_KEY 两个字段"
Write-Host ""
Write-Host "填好后运行首次扫描（2-5 分钟，费用约 ¥1-5）：" -ForegroundColor Yellow
Write-Host "  $PYTHON_EXE $CODE_DIR\main.py --max-files 2000 --no-embed --skip-confirm"
Write-Host ""
Write-Host "之后无需任何操作：" -ForegroundColor Yellow
Write-Host "  · 每天 11:00 自动扫描更新记忆库"
Write-Host "  · 代理服务开机自动启动（localhost:8765）"
Write-Host "  · AI 工具接入见上方提示"
Write-Host ""
Write-Host "Web UI：$PYTHON_EXE $CODE_DIR\web\server.py → http://localhost:8766"
Write-Host "Wiki 位置：$INSTALL_DIR\wiki\"
Write-Host ""
Read-Host "按 Enter 关闭"
