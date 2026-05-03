# MemoryOS 一键引导安装脚本 (Windows PowerShell)
# 用法：右键 bootstrap.ps1 → 用 PowerShell 运行
# 或先解除执行限制：Set-ExecutionPolicy Bypass -Scope Process
# 一行安装（PowerShell）：
#   irm https://raw.githubusercontent.com/hebeiwang353-bit/personal-wiki/main/bootstrap.ps1 | iex

$ErrorActionPreference = "Stop"

function Write-Step { param($msg) Write-Host "`n▶ $msg" -ForegroundColor Yellow }
function Write-OK   { param($msg) Write-Host "  ✓ $msg" -ForegroundColor Green  }
function Write-Warn { param($msg) Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Info { param($msg) Write-Host "    $msg" -ForegroundColor Gray   }
function Write-Err  { param($msg) Write-Host "  ✗ $msg" -ForegroundColor Red    }

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      MemoryOS 安装引导程序           ║" -ForegroundColor Cyan
Write-Host "║  让所有 AI 工具永久认识你            ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. 检测 Python 3.10+ ──────────────────────────────────────
Write-Step "检测 Python 环境..."

function Test-PythonOk {
    param([string]$cmd)
    try {
        $v = & $cmd --version 2>&1
        return ($v -match "Python 3\.(1[0-9]|[2-9]\d)")
    } catch { return $false }
}

function Find-Python {
    # 按优先级逐一尝试
    foreach ($cmd in @("python", "python3", "py -3.11", "py -3.10")) {
        if (Test-PythonOk $cmd) { return $cmd }
    }
    # 检查常见安装路径
    $paths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe"
    )
    foreach ($p in $paths) {
        if ((Test-Path $p) -and (Test-PythonOk $p)) { return $p }
    }
    return $null
}

$PYTHON = Find-Python

if (-not $PYTHON) {
    Write-Warn "未检测到 Python 3.10+，正在自动安装..."

    $installed = $false

    # 方式 A：winget（Windows 10 1709+ / Windows 11 内置）
    if (-not $installed) {
        try {
            $wingetVer = winget --version 2>&1
            if ($wingetVer) {
                Write-Info "使用 winget 安装 Python 3.11..."
                winget install --id Python.Python.3.11 --silent `
                    --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
                $installed = $true
            }
        } catch {}
    }

    # 方式 B：直接从 python.org 下载安装包（最可靠的后备）
    if (-not $installed) {
        Write-Info "winget 不可用，从 python.org 下载 Python 3.11..."
        $pyUrl  = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        $pyInst = "$env:TEMP\python_installer.exe"
        try {
            Write-Info "下载中（约 25MB）..."
            $ProgressPreference = "SilentlyContinue"
            Invoke-WebRequest $pyUrl -OutFile $pyInst -UseBasicParsing
            Write-Info "安装中..."
            # /quiet：静默  PrependPath：加入 PATH  InstallAllUsers=0：当前用户
            Start-Process $pyInst -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1" -Wait
            Remove-Item $pyInst -Force -ErrorAction SilentlyContinue
            $installed = $true
        } catch {
            Write-Err "Python 下载/安装失败：$_"
            Write-Info "请手动前往 https://www.python.org/downloads/ 安装后重试"
            Read-Host "按 Enter 退出"; exit 1
        }
    }

    # 刷新当前会话的 PATH（让新装的 python 立即可用）
    $userPath    = [System.Environment]::GetEnvironmentVariable("PATH", "User")
    $machinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
    $env:PATH = "$userPath;$machinePath"

    # 重新查找
    $PYTHON = Find-Python
    if (-not $PYTHON) {
        # 最后尝试已知路径
        $knownPath = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
        if (Test-Path $knownPath) { $PYTHON = $knownPath }
    }

    if (-not $PYTHON) {
        Write-Err "Python 安装完成但找不到可执行文件，请重新打开 PowerShell 后重试"
        Read-Host "按 Enter 退出"; exit 1
    }
    Write-OK "Python 已安装：$(& $PYTHON --version 2>&1)"
} else {
    Write-OK "检测到 $(& $PYTHON --version 2>&1)"
}

# ── 2. 确保 pip 可用 ──────────────────────────────────────────
Write-Step "检查 pip..."
try {
    & $PYTHON -m pip --version 2>&1 | Out-Null
    Write-OK "pip 可用"
} catch {
    Write-Warn "pip 不可用，正在安装..."
    $getPip = "$env:TEMP\get-pip.py"
    Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
    & $PYTHON $getPip --quiet
    Remove-Item $getPip -Force -ErrorAction SilentlyContinue
    Write-OK "pip 已安装"
}

# ── 3. pip install memoryos ───────────────────────────────────
Write-Step "安装 MemoryOS（约 2-4 分钟，下载依赖中）..."
& $PYTHON -m pip install --upgrade memoryos --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Err "pip install 失败，请检查网络连接后重试"
    Read-Host "按 Enter 退出"; exit 1
}
Write-OK "MemoryOS 安装完成"

# ── 4. 运行 memoryos install ──────────────────────────────────
Write-Step "配置 MemoryOS..."

# 找到 memoryos.exe 的位置
$pythonDir = Split-Path $PYTHON -Parent
$memoryosExe = Join-Path $pythonDir "memoryos.exe"

if (-not (Test-Path $memoryosExe)) {
    # 尝试 Scripts 子目录
    $memoryosExe = Join-Path $pythonDir "Scripts\memoryos.exe"
}

if (Test-Path $memoryosExe) {
    & $memoryosExe install
} else {
    # 直接用 python -m memoryos.cli
    & $PYTHON -m memoryos.cli install
}

Write-Host ""
Read-Host "安装完成！按 Enter 关闭"
