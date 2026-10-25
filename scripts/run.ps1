#Requires -Version 5.1
<#
.SYNOPSIS
    Maia installer & management script for Windows.
.DESCRIPTION
    One-liner install:
      irm https://raw.githubusercontent.com/dubhagen/Maia/master/scripts/run.ps1 | iex
    Or from a local clone:
      .\scripts\run.ps1              # install / configure
      .\scripts\run.ps1 start        # start service  (delegates to maia CLI)
      .\scripts\run.ps1 stop|restart|status|logs|config|update|help
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = ""
)

$ErrorActionPreference = "Stop"

# ── ensure UTF-8 everywhere on Windows ───────────────────────────
# Windows PowerShell 5.1 defaults to the system ANSI code page. Set the
# active code page AND the console encodings so our output and any child
# process (git/python) speak UTF-8.
try { chcp 65001 | Out-Null } catch {}
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::InputEncoding  = [System.Text.Encoding]::UTF8
} catch {}
# $OutputEncoding controls how strings are piped to external programs.
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# ── disable console QuickEdit mode ───────────────────────────────
# On Windows, QuickEdit is ON by default: a stray click/selection in the
# window FREEZES all output until the user presses a key. During long steps
# (git clone, pip install) this looks like a hang, and the wake-up key gets
# buffered and later auto-confirms a menu default. Turning QuickEdit off
# removes both the freeze and the phantom keystrokes.
try {
    if (-not ([Console]::IsInputRedirected)) {
        $quickEditType = @'
using System;
using System.Runtime.InteropServices;
public static class ConsoleQuickEdit {
    const int  STD_INPUT_HANDLE   = -10;
    const uint ENABLE_QUICK_EDIT  = 0x0040;
    const uint ENABLE_EXTENDED    = 0x0080;
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr GetStdHandle(int nStdHandle);
    [DllImport("kernel32.dll")]
    static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);
    [DllImport("kernel32.dll")]
    static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
    public static void Disable() {
        IntPtr handle = GetStdHandle(STD_INPUT_HANDLE);
        uint mode;
        if (!GetConsoleMode(handle, out mode)) { return; }
        mode &= ~ENABLE_QUICK_EDIT;   // clear QuickEdit
        mode |=  ENABLE_EXTENDED;     // keep extended flags valid
        SetConsoleMode(handle, mode);
    }
}
'@
        if (-not ([System.Management.Automation.PSTypeName]'ConsoleQuickEdit').Type) {
            Add-Type -TypeDefinition $quickEditType -ErrorAction Stop
        }
        [ConsoleQuickEdit]::Disable()
    }
} catch {}

# ── colours ──────────────────────────────────────────────────────
function Write-Maia   { param([string]$M) Write-Host $M -ForegroundColor Green  }
function Write-Warn  { param([string]$M) Write-Host $M -ForegroundColor Yellow }
function Write-Err   { param([string]$M) Write-Host $M -ForegroundColor Red    }
function Write-Info  { param([string]$M) Write-Host $M -ForegroundColor Cyan   }

# ── detect project directory ─────────────────────────────────────
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { $PWD.Path }
$BaseDir   = Split-Path $ScriptDir -Parent

$IsProjectDir = (Test-Path "$BaseDir\app.py") -and (Test-Path "$BaseDir\config-template.json")
if (-not $IsProjectDir) {
    $BaseDir = $PWD.Path
    $IsProjectDir = (Test-Path "$BaseDir\app.py") -and (Test-Path "$BaseDir\config-template.json")
}

# Drain any buffered console keystrokes. During long steps (git clone, pip
# install) users often hit Enter to "wake up" a seemingly stuck console; those
# keys sit in the input buffer and would otherwise be consumed by the next
# ReadKey, auto-confirming a menu's default. Flush them before reading input.
function Clear-InputBuffer {
    try {
        if ([Console]::IsInputRedirected) { return }
        while ([Console]::KeyAvailable) { [void][Console]::ReadKey($true) }
    } catch {}
}

# ── arrow-key selectable menu with number fallback ───────────────
# Usage: $idx = Select-Menu -Title "..." -Options @("a","b") [-Default 1]
# Returns the selected 1-based index.
function Select-Menu {
    param(
        [string]$Title,
        [string[]]$Options,
        [int]$Default = 1
    )
    $count = $Options.Count
    $cur = [Math]::Max(0, [Math]::Min($Default - 1, $count - 1))

    # Fallback to numbered input when there is no interactive console
    # (e.g. piped input, redirected host).
    $interactive = $true
    try {
        if ([Console]::IsInputRedirected) { $interactive = $false }
    } catch { $interactive = $false }

    if (-not $interactive) {
        Write-Info $Title
        for ($i = 0; $i -lt $count; $i++) {
            Write-Host ("  {0}) {1}" -f ($i + 1), $Options[$i])
        }
        do {
            $sel = Read-Host "Enter number" 
            if (-not $sel) { $sel = "$($cur + 1)" }
        } while ($sel -notmatch '^\d+$' -or [int]$sel -lt 1 -or [int]$sel -gt $count)
        return [int]$sel
    }

    Write-Info $Title
    Write-Host "Use ↑/↓ to move, Enter to select" -ForegroundColor Cyan

    # Discard keystrokes buffered during the previous (possibly long-running)
    # step so a leftover Enter doesn't instantly confirm the default option.
    Clear-InputBuffer

    [Console]::CursorVisible = $false
    $firstDraw = $true
    try {
        while ($true) {
            if (-not $firstDraw) {
                # Move cursor up to the top of the option block to redraw it.
                $top = [Console]::CursorTop - $count
                if ($top -lt 0) { $top = 0 }
                [Console]::SetCursorPosition(0, $top)
            }
            $firstDraw = $false

            for ($i = 0; $i -lt $count; $i++) {
                # Clear the line first to avoid leftover characters.
                Write-Host (" " * ([Console]::WindowWidth - 1)) -NoNewline
                [Console]::SetCursorPosition(0, [Console]::CursorTop)
                if ($i -eq $cur) {
                    Write-Host ("  > " + $Options[$i]) -ForegroundColor Green
                } else {
                    Write-Host ("    " + $Options[$i])
                }
            }

            $key = [Console]::ReadKey($true)
            switch ($key.Key) {
                "UpArrow"   { $cur = (($cur - 1 + $count) % $count) }
                "DownArrow" { $cur = (($cur + 1) % $count) }
                "Enter"     { return ($cur + 1) }
                default {
                    # Number shortcut (1-9) jumps to that option and confirms.
                    $ch = $key.KeyChar
                    if ($ch -match '^[1-9]$') {
                        $n = [int]"$ch"
                        if ($n -ge 1 -and $n -le $count) { return $n }
                    }
                }
            }
        }
    } finally {
        [Console]::CursorVisible = $true
    }
}

# ── Python detection ─────────────────────────────────────────────
function Find-Python {
    # 3.13 compatibility is not great, so prefer 3.7-3.12 and only fall back to 3.13.
    $fallback = $null
    foreach ($cmd in @("python3", "python")) {
        $bin = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $bin) { continue }
        try {
            $ver = & $bin.Source -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2>$null
            $parts = $ver -split '\.'
            $major = [int]$parts[0]; $minor = [int]$parts[1]
            if ($major -eq 3 -and $minor -ge 7 -and $minor -le 12) {
                return $bin.Source
            }
            if ($major -eq 3 -and $minor -eq 13 -and -not $fallback) {
                $fallback = $bin.Source
            }
        } catch {}
    }
    return $fallback
}

$PythonCmd = Find-Python
function Assert-Python {
    if (-not $PythonCmd) {
        Write-Err "Python 3.7-3.13 not found. Please install from https://www.python.org/downloads/"
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Maia ("Found Python" + ": $PythonCmd")
}

# ── clone project ────────────────────────────────────────────────
function Install-Project {
    if (Test-Path "Maia") {
        # Auto-backup the existing directory without prompting.
        $backup = "Maia_backup_$(Get-Date -Format 'yyyyMMddHHmmss')"
        Rename-Item "Maia" $backup
        Write-Warn ("Existing 'Maia' directory backed up to" + " '$backup'")
    }

    $gitBin = Get-Command git -ErrorAction SilentlyContinue
    if (-not $gitBin) {
        Write-Err "Git not found. Please install from https://git-scm.com/download/win"
        Read-Host "Press Enter to exit"
        exit 1
    }

    Write-Maia "Cloning Maia project..."
    $cloneOk = $false

    # Test GitHub connectivity before attempting clone
    try {
        $null = Invoke-WebRequest -Uri "https://github.com" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Maia "GitHub is reachable, cloning from GitHub..."
        $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        git clone --depth 10 --progress "https://github.com/dubhagen/Maia.git" 2>&1 | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -eq 0) { $cloneOk = $true }
        $ErrorActionPreference = $prevEAP
        if (-not $cloneOk) {
            if (Test-Path "Maia") { Remove-Item -Recurse -Force "Maia" }
        }
    } catch {}

    if (-not $cloneOk) {
        Write-Err "Clone failed. Please check your network connection."
        Write-Err "You can also manually clone: git clone https://github.com/dubhagen/Maia.git"
        Read-Host "Press Enter to exit"
        exit 1
    }

    Set-Location "Maia"
    $script:BaseDir = $PWD.Path
    $script:IsProjectDir = $true
    Write-Maia ("Project cloned" + ": $BaseDir")
}

# Test whether a URL is reachable within a short timeout. Uses a HEAD request
# and hides progress so it never blocks the UI for long. Any failure (DNS, TLS,
# timeout) just returns $false so the caller falls back gracefully.
function Test-UrlReachable {
    param([string]$Url, [int]$TimeoutSec = 4)
    $oldPP = $ProgressPreference; $ProgressPreference = "SilentlyContinue"
    try {
        $null = Invoke-WebRequest -Uri $Url -Method Head -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return $true
    } catch {
        return $false
    } finally {
        $ProgressPreference = $oldPP
    }
}

# Official PyPI first. If it is unreachable, fall back to a public mirror.
# Returns an args array to splat into pip (empty = pip default / official PyPI).
function Get-PipMirrorArgs {
    $tuna = "https://pypi.tuna.tsinghua.edu.cn/simple"
    $pypi = "https://pypi.org/simple"
    if ((-not (Test-UrlReachable "$pypi/")) -and (Test-UrlReachable "$tuna/")) {
        Write-Warn ("Using pip mirror" + ": $tuna")
        return @("-i", $tuna)
    }
    return @()
}

# ── install dependencies ─────────────────────────────────────────
function Install-Dependencies {
    Write-Maia "Installing dependencies..."

    # Probe the mirror first (with progress hidden so the slow IWR call doesn't
    # leave the screen blank for too long).
    $oldPP = $ProgressPreference; $ProgressPreference = "SilentlyContinue"
    $pipMirror = Get-PipMirrorArgs
    $ProgressPreference = $oldPP

    # Keep pip output VISIBLE (do not pipe to Out-Null): on slow networks the
    # download can take minutes, and a silent step looks like a hang.
    $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"

    Write-Info "Upgrading pip and basic tools..."
    & $PythonCmd -m pip install --upgrade pip setuptools wheel @pipMirror

    Write-Info "Installing project dependencies (may take a few minutes)..."
    # --prefer-binary: avoid building C extensions (e.g. aiohttp) from source,
    # which would require Microsoft C++ Build Tools that most users don't have.
    & $PythonCmd -m pip install --prefer-binary -r "$BaseDir\requirements.txt" @pipMirror
    $pipExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP
    if ($pipExit -ne 0) {
        Write-Warn "Some dependencies may have issues, but continuing..."
    }

    Write-Maia "Registering maia CLI..."
    $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & $PythonCmd -m pip install -e $BaseDir @pipMirror 2>&1 | Out-Null
    $ErrorActionPreference = $prevEAP

    # Add the Scripts dir (where pip puts maia.exe) to PATH, both for this
    # session and persistently, so `maia` keeps working after a reboot.
    $scriptsDir = & $PythonCmd -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>$null
    if ($scriptsDir -and (Test-Path $scriptsDir)) {
        Add-ScriptsDirToPath $scriptsDir
    }

    $cowBin = Get-Command maia -ErrorAction SilentlyContinue
    if ($cowBin) {
        Write-Maia ("maia CLI registered" + ": $($cowBin.Source)")
    } else {
        Write-Warn ("maia CLI not in PATH. You can use" + ": $PythonCmd -m cli.cli")
    }

    # Optional: bundle ripgrep for a faster search_files tool. Never fatal.
    Install-Ripgrep
}

# ── install ripgrep (best-effort) ────────────────────────────────
# Bundle a fast search backend for the search_files tool. This is OPTIONAL: the search_files
# tool falls back to PowerShell / pure-Python when rg is absent, so ANY failure
# here (no network, download error, unzip error) is swallowed with a warning
# and never blocks the install. We drop rg.exe into the Python Scripts dir,
# which the installer already puts on PATH, so shutil.which("rg") finds it.
function Install-Ripgrep {
    $RgVersion = "15.2.0"
    try {
        # Already available on PATH? Nothing to do.
        if (Get-Command rg -ErrorAction SilentlyContinue) {
            Write-Maia "ripgrep (rg) already available, skipping"
            return
        }

        # Target the Python Scripts dir (already on PATH from Install-Dependencies).
        $scriptsDir = & $PythonCmd -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>$null
        if (-not $scriptsDir -or -not (Test-Path $scriptsDir)) {
            Write-Warn "Skipping ripgrep install (no scripts dir); built-in fallback search will be used"
            return
        }
        $rgTarget = Join-Path $scriptsDir "rg.exe"
        if (Test-Path $rgTarget) { return }

        Write-Maia "Installing ripgrep (faster file search)..."

        $asset = "ripgrep-$RgVersion-x86_64-pc-windows-msvc.zip"
        # GitHub first, then the jsDelivr/Gitee-style mirror for zh networks.
        $urls = @(
            "https://github.com/BurntSushi/ripgrep/releases/download/$RgVersion/$asset"
        )

        $tmpZip = Join-Path $env:TEMP "maia-$asset"
        $tmpDir = Join-Path $env:TEMP "maia-rg-$([guid]::NewGuid().ToString('N'))"
        $downloaded = $false
        foreach ($u in $urls) {
            try {
                $oldPP = $ProgressPreference; $ProgressPreference = "SilentlyContinue"
                Invoke-WebRequest -Uri $u -OutFile $tmpZip -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop
                $ProgressPreference = $oldPP
                $downloaded = $true
                break
            } catch {
                $ProgressPreference = $oldPP
            }
        }
        if (-not $downloaded) {
            Write-Warn "ripgrep download failed; built-in fallback search will be used (no impact)"
            return
        }

        # Extract and pull just rg.exe out of the archive's nested folder.
        New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
        Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force
        $rgExe = Get-ChildItem -Path $tmpDir -Recurse -Filter "rg.exe" | Select-Object -First 1
        if ($rgExe) {
            Copy-Item $rgExe.FullName $rgTarget -Force
            Write-Maia ("ripgrep installed" + ": $rgTarget")
        } else {
            Write-Warn "ripgrep extraction failed; built-in fallback search will be used"
        }

        # Best-effort cleanup of temp files.
        try { Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue } catch {}
        try { Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue } catch {}
    } catch {
        # Never let an rg install problem break the main install flow.
        Write-Warn "ripgrep install skipped (no impact); built-in fallback search will be used"
    }
}

# Add the Python Scripts dir to PATH for this session and persist it to the
# user PATH (User scope needs no admin rights), so `maia` survives a reboot.
function Add-ScriptsDirToPath {
    param([string]$ScriptsDir)

    if ($env:PATH -notlike "*$ScriptsDir*") {
        $env:PATH = "$ScriptsDir;$env:PATH"
    }

    # Persist to the User PATH only if missing from BOTH User and Machine scopes
    # (checking Machine avoids a duplicate when Python is installed for all
    # users). Read raw scope values, not the already-merged $env:PATH.
    try {
        $target = $ScriptsDir.TrimEnd('\')
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $machinePath = ""
        try { $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine") } catch {}

        $allParts = @()
        foreach ($p in @($userPath, $machinePath)) {
            if ($p) { $allParts += ($p -split ';' | Where-Object { $_ -ne "" }) }
        }
        $already = $allParts | Where-Object { $_.TrimEnd('\') -ieq $target }
        if (-not $already) {
            $newPath = if ($userPath) { "$userPath;$ScriptsDir" } else { $ScriptsDir }
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            Write-Maia ("Added maia command directory to user PATH (persists after reboot)" + ": $ScriptsDir")
        }
    } catch {
        Write-Warn "Could not persist PATH automatically; you may need to reconfigure after reboot."
    }
}

# ── model selection ──────────────────────────────────────────────
# One LiteLLM OpenAI-compatible proxy. Model ids pass through unchanged.
function Select-Model {
    Write-Host ""
    $title = "Configure LiteLLM"
    $options = @(
        "Enter the LiteLLM base URL and a model id",
        "⏭  Skip (configure later in the web console)"
    )
    $script:ModelChoice = Select-Menu -Title $title -Options $options -Default 1
}

function Configure-Model {
    $script:ModelName = ""
    $script:LitellmApiBase = ""
    $script:LitellmApiKey = ""

    if ($script:ModelChoice -eq 2) {
        Write-Warn "Model configuration skipped, you can set it later in the web console"
        return
    }

    Write-Maia "Configuring LiteLLM..."
    $base = Read-Host "LiteLLM API base (must end with /v1) [http://127.0.0.1:4000/v1]"
    if (-not $base) { $base = "http://127.0.0.1:4000/v1" }
    $script:LitellmApiBase = $base
    $script:LitellmApiKey = Read-Host "LiteLLM API key (optional)"
    $script:ModelName = Read-Host "Model id (as listed by the proxy, optional)"
}

# ── channel selection ────────────────────────────────────────────
# Chat is the web console. The local terminal stays available separately.
function Select-Channel {
    $script:ChannelChoice = "web"
}

function Configure-Channel {
    $script:ChannelExtra = @{}
    $script:ChannelType = "web"
    $script:ChannelExtra["web_port"] = 9899
    $script:AccessInfo = "Web console" + " : http://localhost:9899/"
}

# ── generate config.json ─────────────────────────────────────────
function New-ConfigFile {
    Write-Maia "Generating config.json..."

    $config = [ordered]@{
        channel_type              = "web"
        bot_type                  = "litellm"
        model                     = if ($script:ModelName) { $script:ModelName } else { "" }
        maia_lang                  = "en"
        litellm_api_base          = if ($script:LitellmApiBase) { $script:LitellmApiBase } else { "" }
        litellm_api_key           = if ($script:LitellmApiKey) { $script:LitellmApiKey } else { "" }
        embedding_model           = ""
        vision_model              = ""
        image_model               = ""
        asr_model                 = ""
        tts_model                 = ""
        tts_voice                 = "alloy"
        agent_fallback_models     = @()
        voice_to_text             = "litellm"
        text_to_voice             = "litellm"
        voice_reply_voice         = $false
        speech_recognition        = $true
        group_speech_recognition  = $false
        agent                     = $true
        agent_max_context_tokens  = 200000
        agent_max_context_turns   = 30
        agent_max_steps           = 100
        self_evolution_enabled    = $true
    }

    # Merge channel-specific fields
    foreach ($k in $script:ChannelExtra.Keys) {
        $config[$k] = $script:ChannelExtra[$k]
    }

    $jsonText = $config | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText("$BaseDir\config.json", $jsonText, (New-Object System.Text.UTF8Encoding $false))
    Write-Maia "Configuration file created."
}

# Resolve the `maia` command, self-healing PATH if needed. When `maia` is missing
# (e.g. an older install whose PATH was never persisted), locate the Scripts dir,
# re-add it to PATH (session + persistent), and retry. Returns $true if callable.
function Resolve-MaiaCommand {
    if (Get-Command maia -ErrorAction SilentlyContinue) { return $true }

    $py = if ($PythonCmd) { $PythonCmd } else { Find-Python }
    if ($py) {
        $scriptsDir = & $py -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>$null
        if ($scriptsDir -and (Test-Path "$scriptsDir\maia.exe")) {
            Add-ScriptsDirToPath $scriptsDir
            if (Get-Command maia -ErrorAction SilentlyContinue) { return $true }
        }
    }
    return $false
}

# ── start via maia CLI ─────────────────────────────────────────────
function Start-Maia {
    Write-Maia "Starting Maia..."
    if (Resolve-MaiaCommand) {
        & maia start
    } else {
        Write-Warn "maia CLI not found, starting directly..."
        & $PythonCmd "$BaseDir\app.py"
    }
}

# ── delegate management commands to maia CLI ──────────────────────
function Invoke-MaiaCommand {
    param([string]$Cmd)
    if (Resolve-MaiaCommand) {
        & maia $Cmd
    } else {
        # Fall back to the module entrypoint so management commands still work
        # even when maia.exe isn't on PATH (e.g. right after a fresh reboot on
        # an older install).
        $py = if ($PythonCmd) { $PythonCmd } else { Find-Python }
        if ($py -and (Test-Path "$BaseDir\app.py")) {
            Write-Warn "maia command not found, falling back to python -m cli.cli..."
            Push-Location $BaseDir
            try { & $py -m cli.cli $Cmd } finally { Pop-Location }
        } else {
            Write-Err "maia CLI not found. Run this script without arguments first to install."
            exit 1
        }
    }
}

# ── usage ─────────────────────────────────────────────────────────
function Show-Usage {
    Write-Info "========================================="
    Write-Info "   Maia Management Script (Windows)"
    Write-Info "========================================="
    Write-Host ""
    Write-Host "Usage:"
    Write-Host ("  .\run.ps1               # " + "Install / Configure")
    Write-Host ("  .\run.ps1 <command>     # " + "Management command")
    Write-Host ""
    Write-Host "Commands:"
    Write-Host ("  start      " + "Start the service")
    Write-Host ("  stop       " + "Stop the service")
    Write-Host ("  restart    " + "Restart the service")
    Write-Host ("  status     " + "Check service status")
    Write-Host ("  logs       " + "View logs")
    Write-Host ("  config     " + "Reconfigure project")
    Write-Host ("  update     " + "Update and restart")
    Write-Host ("  help       " + "Show this message")
    Write-Host ""
}

# ── install mode ──────────────────────────────────────────────────
function Install-Mode {
    Clear-Host
    Write-Info "========================================="
    Write-Info "   Maia Installation (Windows)"
    Write-Info "========================================="
    Write-Host ""

    if ($IsProjectDir) {
        Write-Maia "Detected existing project directory."
        if (Test-Path "$BaseDir\config.json") {
            Write-Maia "Project already configured."
            Write-Host ""
            Show-Usage
            return
        }
        Write-Warn "No config.json found. Let's configure your project!"
        Write-Host ""
        Assert-Python
    } else {
        Assert-Python
        Install-Project
    }

    Install-Dependencies
    Select-Model
    Configure-Model
    Select-Channel
    Configure-Channel
    New-ConfigFile

    # Auto-start after configuration for a true out-of-the-box experience.
    Write-Host ""
    if ($script:AccessInfo) { Write-Maia $script:AccessInfo }
    Write-Warn "Tip: to let the Agent browse the web, run 'maia install-browser' to install the browser tool"
    Start-Maia
}

# ── update ────────────────────────────────────────────────────────
function Update-Project {
    Write-Maia "Updating Maia..."
    Set-Location $BaseDir

    # Stop if running
    $cowBin = Get-Command maia -ErrorAction SilentlyContinue
    if ($cowBin) {
        $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        & maia stop 2>&1 | Out-Null
        $ErrorActionPreference = $prevEAP
    }

    if (Test-Path "$BaseDir\.git") {
        Write-Maia "Pulling latest code..."
        $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        git pull 2>&1 | Out-Null
        $pullExit = $LASTEXITCODE
        $ErrorActionPreference = $prevEAP
        if ($pullExit -ne 0) {
            Write-Err "Failed to pull code. Update aborted. origin was left unchanged."
            Read-Host "Press Enter to exit"
            exit 1
        }
    } else {
        Write-Warn "Not a git repository, skipping code update."
    }

    Assert-Python
    Install-Dependencies

    # Start via python -m cli.cli instead of maia.exe, because the exe may
    # still be cached/locked from the previous installation on Windows.
    Write-Maia "Starting Maia..."
    & $PythonCmd -m cli.cli start
}

# ── main ──────────────────────────────────────────────────────────
switch ($Command.ToLower()) {
    ""        { Install-Mode }
    "start"   { Invoke-MaiaCommand "start" }
    "stop"    { Invoke-MaiaCommand "stop" }
    "restart" { Invoke-MaiaCommand "restart" }
    "status"  { Invoke-MaiaCommand "status" }
    "logs"    { Invoke-MaiaCommand "logs" }
    "config"  {
        Assert-Python
        Install-Dependencies
        Select-Model
        Configure-Model
        Select-Channel
        Configure-Channel
        New-ConfigFile
        $r = Read-Host "Restart service now? [Y/n]"
        if ($r -ne "n" -and $r -ne "N") { Invoke-MaiaCommand "restart" }
    }
    "update"  { Update-Project }
    "help"    { Show-Usage }
    default   {
        Write-Err ("Unknown command" + ": $Command")
        Show-Usage
        exit 1
    }
}
