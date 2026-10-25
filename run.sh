#!/bin/bash
set -e

# ============================
# Maia Management Script
# ============================

# ANSI colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Emojis
EMOJI_ROCKET="🚀"
EMOJI_MAIA="✦"
EMOJI_CHECK="✅"
EMOJI_CROSS="❌"
EMOJI_WARN="⚠️"
EMOJI_STOP="🛑"
EMOJI_WRENCH="🔧"

# Check if using Bash
if [ -z "$BASH_VERSION" ]; then
    echo -e "${RED}❌ Please run this script with Bash.${NC}"
    exit 1
fi

# ============================
# i18n: install-flow language
# ============================
# Install and management prompts are English.
UI_LANG="en"

# A terminal we can read from. When the script runs via `curl | bash`, stdin is
# the script pipe (EOF on read), so interactive prompts must read from the tty.
TTY_DEV="/dev/tty"
HAS_TTY=false
if [ -r /dev/tty ] && [ -w /dev/tty ]; then
    HAS_TTY=true
fi

# t <unused> <english>. The first argument is kept so existing call sites
# stay valid. Prompts always print the English text.
t() {
    printf '%s' "$2"
}

# Read a line from the controlling terminal (works under `curl | bash`).
# Usage: tty_read VAR "prompt"
tty_read() {
    local __var=$1 __prompt=$2 __input=""
    if [ "$HAS_TTY" = true ]; then
        # Ensure the tty is in normal line mode. A preceding arrow-key menu
        # may have left it in cbreak/-echo mode; without this, `read` could
        # return immediately or not echo typed characters.
        stty sane < "$TTY_DEV" 2>/dev/null || true
        # Print the prompt explicitly (not via read -p, whose prompt can be
        # swallowed right after an arrow-key menu) and read from the tty.
        # `|| true` so a non-zero read (EOF) does NOT trip `set -e`.
        printf '%s' "$__prompt" > /dev/tty
        read -r __input < "$TTY_DEV" || true
    else
        read -r -p "$__prompt" __input || true
    fi
    printf -v "$__var" '%s' "$__input"
}

# Arrow-key selectable menu with number fallback.
# Usage: select_menu OUT_VAR "Title" "opt1" "opt2" ...
# Result: OUT_VAR is set to the selected index (1-based).
select_menu() {
    # Interactive function: never let a non-zero command (read EOF, arithmetic
    # evaluating to 0, etc.) abort the caller under `set -e`.
    set +e
    local __out=$1; shift
    local title=$1; shift
    local options=("$@")
    local count=${#options[@]}
    # Initial highlight: MENU_DEFAULT (1-based) if set, else first option.
    local cur=0
    if [[ "${MENU_DEFAULT:-}" =~ ^[0-9]+$ ]] && (( MENU_DEFAULT >= 1 && MENU_DEFAULT <= count )); then
        cur=$((MENU_DEFAULT - 1))
    fi
    MENU_DEFAULT=""

    # Fallback to numbered input when no interactive terminal is available
    # (e.g. CI, non-tty pipe). Arrow-key rendering needs a real tty.
    if [ "$HAS_TTY" != true ] || [ ! -t 1 ]; then
        local def=$((cur + 1))
        echo -e "${CYAN}${BOLD}${title}${NC}"
        local i=1
        for opt in "${options[@]}"; do
            echo -e "  ${YELLOW}${i})${NC} ${opt}"
            i=$((i + 1))
        done
        local choice=""
        while true; do
            tty_read choice "Enter number [1-${count}, default ${def}]: "
            choice=${choice:-$def}
            if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= count )); then
                break
            fi
            echo -e "${RED}Invalid choice, enter 1-${count}${NC}"
        done
        printf -v "$__out" '%s' "$choice"
        return
    fi

    # Interactive arrow-key menu.
    # Use literal escape characters (via $'...') and printf instead of
    # `echo -e`, because `echo`'s backslash handling is not portable and
    # leaks raw "\e[K" text on some shells/terminals.
    local ESC=$'\033'
    local UP="${ESC}[A"          # move cursor up one line
    local CLR="${ESC}[K"         # clear to end of line

    # fd 3 is a long-lived (read) handle to the controlling terminal, opened
    # once by menu_session_begin() before the install flow. Reusing one fd
    # across all menus avoids the bash 3.2 bug where re-opening /dev/tty per
    # menu makes the second menu read EOF and auto-select the default.
    # Detect whether fd 3 is already open using a READ redirection (fd 3 is
    # read-only; testing with `>&3` would wrongly report it as closed).
    local _own_fd3=false
    if ! { : <&3; } 2>/dev/null; then
        exec 3<"$TTY_DEV"
        _own_fd3=true
    fi

    # Put the terminal into cbreak/raw input mode so single keystrokes arrive
    # immediately and are not echoed.
    #   -echo    : don't echo keystrokes (otherwise arrow keys leak as ^[[A)
    #   -icanon  : disable line buffering
    #   min 1 time 0 : read returns as soon as 1 byte is available
    local _restore="tput cnorm 2>/dev/null; stty echo icanon <${TTY_DEV} 2>/dev/null"
    trap "$_restore" EXIT INT TERM
    tput civis 2>/dev/null || true
    stty -echo -icanon min 1 time 0 <&3 2>/dev/null || true

    printf '%b\n' "${CYAN}${BOLD}${title}${NC}"
    printf '%b\n' "${CYAN}Use ↑/↓ to move, Enter to select${NC}"

    local first_draw=true
    while true; do
        # Move cursor up to the top of the option block to redraw it.
        if [ "$first_draw" = false ]; then
            local i=0
            while [ $i -lt $count ]; do
                printf '%s' "$UP"
                i=$((i + 1))
            done
        fi
        first_draw=false

        local idx=0
        for opt in "${options[@]}"; do
            if [ $idx -eq $cur ]; then
                printf '%s%b\n' "$CLR" "  ${GREEN}${BOLD}❯ ${opt}${NC}"
            else
                printf '%s%b\n' "$CLR" "    ${opt}"
            fi
            idx=$((idx + 1))
        done

        # Read one key from the shared terminal fd 3.
        local key=""
        IFS= read -rsn1 key <&3
        local rc=$?
        if [ $rc -ne 0 ]; then
            # No usable terminal: restore and fall back to numbered input.
            eval "$_restore"; trap - EXIT INT TERM
            [ "${_own_fd3:-}" = true ] && exec 3<&- 2>/dev/null
            local choice=""
            while true; do
                tty_read choice "Enter number [1-${count}]: "
                choice=${choice:-$((cur + 1))}
                if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= count )); then
                    break
                fi
            done
            printf -v "$__out" '%s' "$choice"
            return
        fi

        # Empty key means Enter/Return (read -n1 strips the newline delimiter).
        if [ -z "$key" ]; then
            break
        fi

        case "$key" in
            "$ESC")
                # Arrow key: ESC [ A/B (or ESC O A/B). Read the two trailing
                # bytes one at a time, no timeout (bash 3.2 has no fractional
                # read -t; in cbreak mode the bytes are already buffered).
                local b2="" b3=""
                IFS= read -rsn1 b2 <&3 2>/dev/null || b2=""
                IFS= read -rsn1 b3 <&3 2>/dev/null || b3=""
                case "${b2}${b3}" in
                    "[A" | "OA") cur=$(( (cur - 1 + count) % count )) ;;  # up
                    "[B" | "OB") cur=$(( (cur + 1) % count )) ;;          # down
                esac
                ;;
            $'\n' | $'\r')
                break
                ;;
            [0-9])
                if (( key >= 1 && key <= count )); then
                    cur=$((key - 1))
                    break
                fi
                ;;
            $'\003')
                # Ctrl-C: restore and abort.
                eval "$_restore"; trap - EXIT INT TERM
                [ "${_own_fd3:-}" = true ] && exec 3<&- 2>/dev/null
                printf '\n%b\n' "${RED}Installation cancelled${NC}"
                exit 130
                ;;
        esac
    done

    eval "$_restore"
    trap - EXIT INT TERM
    [ "${_own_fd3:-}" = true ] && exec 3<&- 2>/dev/null
    printf -v "$__out" '%s' "$((cur + 1))"
}

# Open/close a long-lived terminal handle (fd 3) shared by all menus in an
# install/config session. Opening fd 3 once avoids per-menu re-open issues on
# bash 3.2 (second menu reading EOF). Safe no-ops when there is no tty.
menu_session_begin() {
    [ "$HAS_TTY" = true ] || return 0
    exec 3<"$TTY_DEV" 2>/dev/null || true
}
menu_session_end() {
    exec 3<&- 2>/dev/null || true
}

# Install prompts are English. maia_lang in a new config is "en".
select_language() {
    UI_LANG="en"
    INSTALL_LANG="en"
}

# Cross-platform timeout: prefer GNU timeout/gtimeout, fallback to a pure-bash implementation
# that uses background process + sleep to enforce a hard time limit.
if command -v timeout &> /dev/null; then
    _timeout() { timeout "$@"; }
elif command -v gtimeout &> /dev/null; then
    _timeout() { gtimeout "$@"; }
else
    _timeout() {
        local secs=$1; shift
        "$@" &
        local cmd_pid=$!
        ( sleep "$secs"; kill $cmd_pid 2>/dev/null ) &
        local watcher_pid=$!
        wait $cmd_pid 2>/dev/null
        local exit_code=$?
        kill $watcher_pid 2>/dev/null
        wait $watcher_pid 2>/dev/null
        return $exit_code
    }
fi

# Get current script directory.
# When launched via process substitution (`bash <(curl ...)`) or a pipe,
# $0 points at /dev/fd/* or "bash", so dirname is meaningless. Fall back to
# the current working directory in that case (remote install will cd into
# the cloned project dir and reset BASE_DIR afterwards).
_script_src="$0"
case "$_script_src" in
    /dev/fd/* | /proc/self/fd/* | bash | sh | -* | "")
        export BASE_DIR="$(pwd)"
        ;;
    *)
        export BASE_DIR=$(cd "$(dirname "$_script_src")" 2>/dev/null && pwd || pwd)
        ;;
esac

# Detect if in project directory
IS_PROJECT_DIR=false
if [ -f "${BASE_DIR}/config-template.json" ] && [ -f "${BASE_DIR}/app.py" ]; then
    IS_PROJECT_DIR=true
fi

# Check and install tool
check_and_install_tool() {
    local tool_name=$1
    if ! command -v "$tool_name" &> /dev/null; then
        echo -e "${YELLOW}⚙️  $tool_name not found, installing...${NC}"
        if command -v yum &> /dev/null; then
            sudo yum install "$tool_name" -y
        elif command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install "$tool_name" -y
        elif command -v brew &> /dev/null; then
            brew install "$tool_name"
        else
            echo -e "${RED}❌ Unsupported package manager. Please install $tool_name manually.${NC}"
            return 1
        fi

        if ! command -v "$tool_name" &> /dev/null; then
            echo -e "${RED}❌ Failed to install $tool_name.${NC}"
            return 1
        else
            echo -e "${GREEN}✅ $tool_name installed successfully.${NC}"
            return 0
        fi
    else
        echo -e "${GREEN}✅ $tool_name is already installed.${NC}"
        return 0
    fi
}

# Detect and set Python command
detect_python_command() {
    FOUND_NEWER_VERSION=""
    
    # Try to find Python command in order of preference
    for cmd in python3 python python3.12 python3.11 python3.10 python3.9 python3.8 python3.7 python3.13; do
        if command -v $cmd &> /dev/null; then
            # Check Python version
            major_version=$($cmd -c 'import sys; print(sys.version_info[0])' 2>/dev/null)
            minor_version=$($cmd -c 'import sys; print(sys.version_info[1])' 2>/dev/null)
            
            if [[ "$major_version" == "3" ]]; then
                # Supported range is 3.7+.
                if (( minor_version >= 7 )); then
                    PYTHON_CMD=$cmd
                    PYTHON_VERSION="${major_version}.${minor_version}"
                    break
                fi
            fi
        fi
    done
    
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${YELLOW}Tried: python3, python, python3.12, python3.11, python3.10, python3.9, python3.8, python3.7, python3.13${NC}"
        echo -e "${RED}❌ No suitable Python found. Please install Python 3.7 or newer${NC}"
        exit 1
    fi

    # Export for global use
    export PYTHON_CMD
    export PYTHON_VERSION
    
    echo -e "${GREEN}✅ Found Python: $PYTHON_CMD (version $PYTHON_VERSION)${NC}"
}

# Check Python version (>= 3.7)
check_python_version() {
    detect_python_command
    
    # Verify pip is available
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        echo -e "${RED}❌ pip not found for $PYTHON_CMD. Please install pip.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ pip is available for $PYTHON_CMD${NC}"
}

# Clone project
clone_project() {
    echo -e "${GREEN}🔍 Cloning Maia project...${NC}"

    if [ -d "Maia" ]; then
        # An existing directory is automatically backed up (no prompt) so the
        # installer stays one-shot / hands-off.
        local backup_dir="Maia_backup_$(date +%s)"
        echo -e "${YELLOW}⚠️  Directory 'Maia' exists, backing up to '$backup_dir'...${NC}"
        mv Maia "$backup_dir"
    fi

    check_and_install_tool git

    if ! command -v git &> /dev/null; then
        echo -e "${YELLOW}⚠️  Git not available. Trying wget/curl...${NC}"
        local zip_url="https://github.com/dubhagen/Maia/archive/refs/heads/master.zip"
        if command -v wget &> /dev/null; then
            wget "$zip_url" -O Maia.zip
        elif command -v curl &> /dev/null; then
            curl -L "$zip_url" -o Maia.zip
        else
            echo -e "${RED}❌ Cannot download project. Please install Git, wget, or curl.${NC}"
            exit 1
        fi
        # Unzip: prefer `unzip`, otherwise fall back to Python's zipfile (no
        # extra dependency) so minimal environments without unzip still work.
        if command -v unzip &> /dev/null; then
            unzip Maia.zip
        elif command -v python3 &> /dev/null; then
            python3 -m zipfile -e Maia.zip .
        elif command -v python &> /dev/null; then
            python -m zipfile -e Maia.zip .
        else
            echo -e "${RED}❌ Cannot extract archive. Please install 'unzip' or Python.${NC}"
            exit 1
        fi
        # Archive top-level dir name may vary (Maia-master, etc.); detect it.
        local _extracted="Maia-master"
        if [ ! -d "$_extracted" ]; then
            _extracted=$(ls -d Maia-*/ 2>/dev/null | head -1 | sed 's:/*$::')
        fi
        [ -n "$_extracted" ] && [ -d "$_extracted" ] && mv "$_extracted" Maia
        rm -f Maia.zip
    else
        local clone_ok=false
        # Detect and temporarily disable invalid git proxy settings
        local _git_proxy_unset=false
        local _http_proxy=$(git config --global http.proxy 2>/dev/null)
        local _https_proxy=$(git config --global https.proxy 2>/dev/null)
        if [ -n "$_http_proxy" ] && ! curl -s --connect-timeout 3 --max-time 5 --proxy "$_http_proxy" https://github.com > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Invalid git proxy detected: $_http_proxy, temporarily disabling...${NC}"
            git config --global --unset http.proxy
            [ -n "$_https_proxy" ] && git config --global --unset https.proxy
            _git_proxy_unset=true
        fi
        # Test GitHub connectivity before attempting clone
        if curl -sI --connect-timeout 5 --max-time 10 https://github.com > /dev/null 2>&1; then
            echo -e "${YELLOW}🌐 GitHub is reachable, cloning from GitHub...${NC}"
            _timeout 60 git clone --depth 10 --progress https://github.com/dubhagen/Maia.git && clone_ok=true
        fi
        if [ "$clone_ok" = false ]; then
            echo -e "${RED}❌ Project clone failed. Please check network connection.${NC}"
            if git config --global http.proxy &> /dev/null || git config --global https.proxy &> /dev/null || [ -n "$http_proxy" ] || [ -n "$https_proxy" ] || [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ]; then
                echo -e "${YELLOW}💡 Detected proxy settings. If proxy is misconfigured, try removing it with:${NC}"
                echo -e "${YELLOW}   git config --global --unset http.proxy${NC}"
                echo -e "${YELLOW}   git config --global --unset https.proxy${NC}"
                echo -e "${YELLOW}   unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY${NC}"
            fi
            exit 1
        fi
    fi

    cd Maia || { echo -e "${RED}❌ Failed to enter project directory.${NC}"; exit 1; }
    export BASE_DIR=$(pwd)
    echo -e "${GREEN}✅ Project cloned successfully: $BASE_DIR${NC}"
    
    # Add execute permission to management script
    if [ -f "${BASE_DIR}/run.sh" ]; then
        chmod +x "${BASE_DIR}/run.sh" 2>/dev/null || true
        echo -e "${GREEN}✅ Execute permission added to run.sh${NC}"
    fi
    
    sleep 1
}

# Install dependencies
install_dependencies() {
    echo -e "${GREEN}📦 Installing dependencies...${NC}"
    # Pick the pip index by install language, then fall back to the other if the
    # preferred one is unreachable:
    #   - zh users: Tsinghua mirror first (fast in China), official PyPI fallback
    #   - others : official PyPI first, Tsinghua mirror fallback
    local PIP_MIRROR=""
    local _tuna="https://pypi.tuna.tsinghua.edu.cn/simple"
    local _pypi="https://pypi.org/simple"
    if [ "$UI_LANG" = "zh" ]; then
        # Prefer Tsinghua; if it's down, fall back to official PyPI (pip default).
        if curl -s --connect-timeout 5 "${_tuna}/" > /dev/null 2>&1; then
            PIP_MIRROR="-i $_tuna"
        fi
    else
        # Prefer official PyPI; only use Tsinghua if PyPI is unreachable.
        if ! curl -s --connect-timeout 5 "${_pypi}/" > /dev/null 2>&1 \
           && curl -s --connect-timeout 5 "${_tuna}/" > /dev/null 2>&1; then
            PIP_MIRROR="-i $_tuna"
        fi
    fi
    if [ -n "$PIP_MIRROR" ]; then
        echo -e "${YELLOW}Using pip mirror: ${_tuna}${NC}"
    fi

    # Only pass --break-system-packages if this pip actually supports it
    # (pip >= 23.x). Older pip versions error out with "no such option",
    # which previously dumped a confusing usage message and failed the install.
    PIP_EXTRA_ARGS=""
    if $PYTHON_CMD -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null \
       && $PYTHON_CMD -m pip install --help 2>/dev/null | grep -q -- "--break-system-packages"; then
        PIP_EXTRA_ARGS="--break-system-packages"
        echo -e "${YELLOW}Python 3.11+ with break-system-packages support detected${NC}"
    fi

    echo -e "${YELLOW}Upgrading pip and basic tools...${NC}"
    set +e
    $PYTHON_CMD -m pip install --upgrade pip setuptools wheel importlib_metadata --ignore-installed $PIP_EXTRA_ARGS $PIP_MIRROR > /tmp/pip_upgrade.log 2>&1
    [ $? -ne 0 ] && echo -e "${YELLOW}⚠️  Some tools failed to upgrade, but continuing...${NC}"
    set -e
    rm -f /tmp/pip_upgrade.log

    echo -e "${YELLOW}Installing project dependencies...${NC}"
    set +e
    $PYTHON_CMD -m pip install -r requirements.txt $PIP_EXTRA_ARGS $PIP_MIRROR > /tmp/pip_install.log 2>&1
    local exit_code=$?
    set -e
    cat /tmp/pip_install.log

    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ Dependencies installed successfully.${NC}"
    elif grep -qE "distutils installed project|uninstall-no-record-file|installed by debian" /tmp/pip_install.log; then
        echo -e "${YELLOW}⚠️  Detected system package conflict, retrying with workaround...${NC}"
        local IGNORE_PACKAGES=""
        for pkg in PyYAML setuptools wheel certifi charset-normalizer; do
            IGNORE_PACKAGES="$IGNORE_PACKAGES --ignore-installed $pkg"
        done
        set +e
        $PYTHON_CMD -m pip install -r requirements.txt $IGNORE_PACKAGES $PIP_EXTRA_ARGS $PIP_MIRROR \
            && echo -e "${GREEN}✅ Dependencies installed successfully (workaround applied).${NC}" \
            || echo -e "${YELLOW}⚠️  Some dependencies may have issues, but continuing...${NC}"
        set -e
    elif grep -q "externally-managed-environment" /tmp/pip_install.log; then
        echo -e "${YELLOW}⚠️  Detected externally-managed environment, retrying with --break-system-packages...${NC}"
        set +e
        $PYTHON_CMD -m pip install -r requirements.txt --break-system-packages $PIP_MIRROR \
            && echo -e "${GREEN}✅ Dependencies installed successfully (system packages override applied).${NC}" \
            || echo -e "${YELLOW}⚠️  Some dependencies may have issues, but continuing...${NC}"
        set -e
    else
        echo -e "${YELLOW}⚠️  Installation had errors, but continuing...${NC}"
    fi

    rm -f /tmp/pip_install.log

    # Register `maia` CLI command via editable install
    echo -e "${YELLOW}Registering maia CLI...${NC}"
    set +e
    $PYTHON_CMD -m pip install -e . $PIP_EXTRA_ARGS $PIP_MIRROR > /dev/null 2>&1
    if command -v maia &> /dev/null; then
        echo -e "${GREEN}✅ maia CLI registered.${NC}"
    else
        echo -e "${YELLOW}⚠️  maia CLI not in PATH, you can still use: $PYTHON_CMD -m cli.cli${NC}"
    fi
    set -e
}

# Select model. Every model id is sent to one LiteLLM proxy.
select_model() {
    echo ""
    local title sel
    title="Configure LiteLLM"
    select_menu sel "$title" \
        "Enter the LiteLLM base URL and a model id" \
        "⏭  Skip (configure later in the web console)"
    model_choice="$sel"
}

# Configure model. The skip choice leaves the endpoint empty so the user can
# finish configuration in the web console after first start.
configure_model() {
    LITELLM_API_BASE=""
    LITELLM_API_KEY=""
    MODEL_NAME=""
    case "$model_choice" in
        1)
            echo -e "${GREEN}Configuring LiteLLM...${NC}"
            local _base _key _model
            tty_read _base "LiteLLM API base (must end with /v1) [http://127.0.0.1:4000/v1]: "
            _base="${_base:-http://127.0.0.1:4000/v1}"
            tty_read _key "LiteLLM API key (optional): "
            tty_read _model "Model id (as listed by the proxy, optional): "
            LITELLM_API_BASE="$_base"
            LITELLM_API_KEY="$_key"
            MODEL_NAME="$_model"
            if [ -z "$MODEL_NAME" ]; then
                MODEL_SKIPPED="true"
            fi
            ;;
        2)
            MODEL_SKIPPED="true"
            echo -e "${YELLOW}Model configuration skipped, you can set it later in the web console${NC}"
            ;;
    esac
}

# The only chat surface the installer configures is the web console.
# The local terminal channel stays available as channel_type "terminal".
select_channel() {
    channel_choice="web"
}

configure_channel() {
    CHANNEL_TYPE="web"
    WEB_PORT="9899"
    ACCESS_INFO="Web console : http://localhost:9899/"
}

# Generate config file
create_config_file() {
    echo -e "${GREEN}📝 Generating config.json...${NC}"

    CHANNEL_TYPE="web" \
    MODEL_NAME="${MODEL_NAME:-}" \
    LITELLM_API_BASE="${LITELLM_API_BASE:-}" \
    LITELLM_API_KEY="${LITELLM_API_KEY:-}" \
    WEB_PORT="${WEB_PORT:-9899}" \
    MAIA_LANG="${INSTALL_LANG:-en}" \
    $PYTHON_CMD -c "
import json, os
e = os.environ.get
def _to_int(val, default):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default
base = {
    'channel_type': 'web',
    'bot_type': 'litellm',
    'model': e('MODEL_NAME') or '',
    'maia_lang': e('MAIA_LANG', 'en'),
    'litellm_api_base': e('LITELLM_API_BASE') or '',
    'litellm_api_key': e('LITELLM_API_KEY') or '',
    'embedding_model': '',
    'vision_model': '',
    'image_model': '',
    'asr_model': '',
    'tts_model': '',
    'tts_voice': 'alloy',
    'agent_fallback_models': [],
    'voice_to_text': 'litellm',
    'text_to_voice': 'litellm',
    'voice_reply_voice': False,
    'speech_recognition': True,
    'group_speech_recognition': False,
    'web_port': _to_int(e('WEB_PORT'), 9899),
    'agent': True,
    'agent_max_context_tokens': 200000,
    'agent_max_context_turns': 30,
    'agent_max_steps': 100,
    'self_evolution_enabled': True,
}
with open('config.json', 'w') as f:
    json.dump(base, f, indent=2, ensure_ascii=False)
"

    echo -e "${GREEN}✅ Configuration file created successfully.${NC}"
}

# Start project
start_project() {
    echo ""
    echo -e "${GREEN}${EMOJI_ROCKET} Starting Maia...${NC}"
    sleep 1

    local USE_COW=false
    if command -v maia &> /dev/null; then
        USE_COW=true
    fi

    if $USE_COW; then
        cd "${BASE_DIR}"
        maia start --no-logs
    else
        if [ ! -f "${BASE_DIR}/nohup.out" ]; then
            touch "${BASE_DIR}/nohup.out"
        fi

        OS_TYPE=$(uname)

        if [[ "$OS_TYPE" == "Linux" ]]; then
            nohup setsid $PYTHON_CMD "${BASE_DIR}/app.py" > "${BASE_DIR}/nohup.out" 2>&1 &
            echo -e "${GREEN}${EMOJI_MAIA} Maia started on Linux (using $PYTHON_CMD)${NC}"
        elif [[ "$OS_TYPE" == "Darwin" ]]; then
            nohup $PYTHON_CMD "${BASE_DIR}/app.py" > "${BASE_DIR}/nohup.out" 2>&1 &
            echo -e "${GREEN}${EMOJI_MAIA} Maia started on macOS (using $PYTHON_CMD)${NC}"
        else
            echo -e "${RED}❌ Unsupported OS: ${OS_TYPE}${NC}"
            exit 1
        fi
    fi

    sleep 2
    echo ""
    echo -e "${CYAN}${BOLD}=========================================${NC}"
    echo -e "${GREEN}${EMOJI_CHECK} Maia is now running in background!${NC}"
    echo -e "${GREEN}${EMOJI_CHECK} Process will continue after closing terminal.${NC}"
    echo -e "${CYAN}$ACCESS_INFO${NC}"

    # If the model was skipped, guide the user to finish setup in the web console.
    if [ "${MODEL_SKIPPED:-}" = "true" ]; then
        local _port="${WEB_PORT:-9899}"
        echo ""
        echo -e "${YELLOW}${EMOJI_WARN} Model not configured yet, please finish setup in the web console:${NC}"
        echo -e "${CYAN}   http://localhost:${_port}/${NC}"
    fi
    echo ""
    echo -e "${CYAN}${BOLD}Management Commands:${NC}"
    if $USE_COW; then
        echo -e "  ${GREEN}maia stop${NC}       Stop the service"
        echo -e "  ${GREEN}maia restart${NC}    Restart the service"
        echo -e "  ${GREEN}maia status${NC}     Check status"
        echo -e "  ${GREEN}maia logs${NC}       View logs"
        echo -e "  ${GREEN}maia update${NC}     Update and restart"
        echo -e "  ${GREEN}maia install-browser${NC}  Install browser tool"
    else
        echo -e "  ${GREEN}./run.sh stop${NC}       Stop the service"
        echo -e "  ${GREEN}./run.sh restart${NC}    Restart the service"
        echo -e "  ${GREEN}./run.sh status${NC}     Check status"
        echo -e "  ${GREEN}./run.sh logs${NC}       View logs"
        echo -e "  ${GREEN}./run.sh update${NC}     Update and restart"
        echo -e "  ${GREEN}maia install-browser${NC}  Install browser tool"
    fi
    echo ""
    echo -e "${YELLOW}Tip: to let the Agent browse the web, run 'maia install-browser' to install the browser tool${NC}"
    echo -e "${CYAN}${BOLD}=========================================${NC}"
    echo ""

    echo -e "${YELLOW}Showing recent logs (Ctrl+C to exit, agent keeps running):${NC}"
    sleep 2
    tail -n 30 -f "${BASE_DIR}/nohup.out"
}

# Show usage
show_usage() {
    echo -e "${CYAN}${BOLD}=========================================${NC}"
    echo -e "${CYAN}${BOLD}   ${EMOJI_MAIA} Maia Management Script${NC}"
    echo -e "${CYAN}${BOLD}=========================================${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ${GREEN}./run.sh${NC}               ${CYAN}# Install/Configure project${NC}"
    echo -e "  ${GREEN}./run.sh <command>${NC}     ${CYAN}# Execute management command${NC}"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo -e "  ${GREEN}start${NC}      Start the service"
    echo -e "  ${GREEN}stop${NC}       Stop the service"
    echo -e "  ${GREEN}restart${NC}    Restart the service"
    echo -e "  ${GREEN}status${NC}     Check service status"
    echo -e "  ${GREEN}logs${NC}       View logs (tail -f)"
    echo -e "  ${GREEN}config${NC}     Reconfigure project"
    echo -e "  ${GREEN}update${NC}     Update and restart"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo -e "  ${GREEN}./run.sh start${NC}"
    echo -e "  ${GREEN}./run.sh logs${NC}"
    echo -e "  ${GREEN}./run.sh status${NC}"
    echo -e "${CYAN}${BOLD}=========================================${NC}"
}

# Ensure PYTHON_CMD is set
ensure_python_cmd() {
    if [ -z "$PYTHON_CMD" ]; then
        detect_python_command > /dev/null 2>&1 || PYTHON_CMD="python3"
    fi
}

# Get service PID (empty string if not running)
get_pid() {
    ensure_python_cmd > /dev/null 2>&1
    ps ax | grep -i app.py | grep "${BASE_DIR}" | grep "$PYTHON_CMD" | grep -v grep | awk '{print $1}' | grep -E '^[0-9]+$' | head -1
}

# Check if service is running
is_running() {
    [ -n "$(get_pid)" ]
}

# Check if maia CLI is available
has_maia() {
    command -v maia &> /dev/null
}

# Start service
cmd_start() {
    if [ ! -f "${BASE_DIR}/config.json" ]; then
        echo -e "${RED}${EMOJI_CROSS} config.json not found${NC}"
        echo -e "${YELLOW}Please run './run.sh' to configure first${NC}"
        exit 1
    fi

    if has_maia; then
        cd "${BASE_DIR}"
        maia start
    else
        if is_running; then
            echo -e "${YELLOW}${EMOJI_WARN} Maia is already running (PID: $(get_pid))${NC}"
            echo -e "${YELLOW}Use './run.sh restart' to restart${NC}"
            return
        fi
        check_python_version
        start_project
    fi
}

# Stop service
cmd_stop() {
    # Don't let kill/return non-zero (e.g. process already gone) abort the
    # caller (cmd_restart) under `set -e`.
    set +e
    if has_maia; then
        cd "${BASE_DIR}"
        maia stop
    else
        echo -e "${GREEN}${EMOJI_STOP} Stopping Maia...${NC}"

        if ! is_running; then
            echo -e "${YELLOW}${EMOJI_WARN} Maia is not running${NC}"
            return 0
        fi

        pid=$(get_pid)
        if [ -z "$pid" ] || ! echo "$pid" | grep -qE '^[0-9]+$'; then
            echo -e "${RED}❌ Failed to get valid PID (${pid})${NC}"
            return 0
        fi

        echo -e "${GREEN}Found running process (PID: ${pid})${NC}"

        kill ${pid} 2>/dev/null || true
        sleep 3

        if ps -p ${pid} > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Process not stopped, forcing termination...${NC}"
            kill -9 ${pid} 2>/dev/null || true
        fi

        echo -e "${GREEN}${EMOJI_CHECK} Maia stopped${NC}"
    fi
}

# Restart service
cmd_restart() {
    if has_maia; then
        cd "${BASE_DIR}"
        maia restart
    else
        cmd_stop
        sleep 1
        cmd_start
    fi
}

# Check status
cmd_status() {
    if has_maia; then
        cd "${BASE_DIR}"
        maia status
    else
        echo -e "${CYAN}${BOLD}=========================================${NC}"
        echo -e "${CYAN}${BOLD}   ${EMOJI_MAIA} Maia Status${NC}"
        echo -e "${CYAN}${BOLD}=========================================${NC}"

        if is_running; then
            pid=$(get_pid)
            echo -e "${GREEN}Status:${NC} ✅ Running"
            echo -e "${GREEN}PID:${NC}    ${pid}"
            if [ -f "${BASE_DIR}/nohup.out" ]; then
                echo -e "${GREEN}Logs:${NC}   ${BASE_DIR}/nohup.out"
            fi
        else
            echo -e "${YELLOW}Status:${NC} ⭐ Stopped"
        fi

        if [ -f "${BASE_DIR}/config.json" ]; then
            # `|| true`: grep returns 1 when the key is absent (set -e safe).
            model=$(grep -o '"model"[[:space:]]*:[[:space:]]*"[^"]*"' "${BASE_DIR}/config.json" 2>/dev/null | cut -d'"' -f4 || true)
            channel=$(grep -o '"channel_type"[[:space:]]*:[[:space:]]*"[^"]*"' "${BASE_DIR}/config.json" 2>/dev/null | cut -d'"' -f4 || true)
            echo -e "${GREEN}Model:${NC}  ${model:-(not set)}"
            echo -e "${GREEN}Channel:${NC} ${channel:-(not set)}"
        fi

        echo -e "${CYAN}${BOLD}=========================================${NC}"
    fi
}

# View logs
cmd_logs() {
    if has_maia; then
        cd "${BASE_DIR}"
        maia logs -f
    else
        if [ -f "${BASE_DIR}/nohup.out" ]; then
            echo -e "${YELLOW}Viewing logs (Ctrl+C to exit):${NC}"
            tail -f "${BASE_DIR}/nohup.out"
        else
            echo -e "${RED}❌ Log file not found: ${BASE_DIR}/nohup.out${NC}"
        fi
    fi
}

# Reconfigure
cmd_config() {
    # Interactive flow: disable `set -e` (see install_mode for rationale).
    set +e
    # One shared terminal handle for all menus in this session.
    menu_session_begin

    select_language
    echo ""
    echo -e "${YELLOW}${EMOJI_WRENCH} Reconfiguring Maia...${NC}"
    
    if [ -f "${BASE_DIR}/config.json" ]; then
        backup_file="${BASE_DIR}/config.json.backup.$(date +%s)"
        cp "${BASE_DIR}/config.json" "${backup_file}"
        echo -e "${GREEN}✅ Backed up config to: ${backup_file}${NC}"
    fi
    
    check_python_version
    install_dependencies
    select_model
    configure_model
    select_channel
    configure_channel
    menu_session_end
    create_config_file
    
    echo ""
    local restart_now
    tty_read restart_now "Restart service now? [Y/n]: "
    if [[ ! $restart_now == [Nn]* ]]; then
        cmd_restart
    fi
}

# Update project
cmd_update() {
    echo -e "${GREEN}${EMOJI_WRENCH} Updating Maia...${NC}"
    cd "${BASE_DIR}"
    
    # Pull latest code first (service still running)
    local pull_ok=false
    if [ -d .git ]; then
        echo -e "${GREEN}🔄 Pulling latest code...${NC}"
        if git pull; then
            pull_ok=true
        else
            echo -e "${RED}❌ Failed to pull code. Update aborted. origin was left unchanged..${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠️  Not a git repository, skipping code update${NC}"
    fi
    
    # Re-exec with the updated run.sh to pick up new logic
    exec "$0" _post_update
}

# Post-update: called by cmd_update after git pull to run with new code
cmd_post_update() {
    cd "${BASE_DIR}"

    # Stop service
    if is_running; then
        cmd_stop
    fi

    # Reinstall dependencies
    check_python_version
    install_dependencies

    # Restart service
    cmd_start
}

# Installation mode
install_mode() {
    # Interactive flow: disable `set -e` so a single non-zero command (e.g. an
    # arithmetic `(( ))` evaluating to 0, a `read` hitting EOF, or an optional
    # step failing) does not silently abort the whole installer.
    set +e
    clear
    echo -e "${CYAN}${BOLD}=========================================${NC}"
    echo -e "${CYAN}${BOLD}   ${EMOJI_MAIA} Maia Installation${NC}"
    echo -e "${CYAN}${BOLD}=========================================${NC}"
    echo ""

    # Open one shared terminal handle for ALL menus in this session (language,
    # model, channel). One long-lived fd 3 avoids per-menu re-open issues on
    # bash 3.2. Closed on early return and before config generation.
    menu_session_begin

    select_language
    echo ""
    sleep 1

    if [ "$IS_PROJECT_DIR" = true ]; then
        echo -e "${GREEN}✅ Detected existing project directory.${NC}"
        
        if [ -f "${BASE_DIR}/config.json" ]; then
            menu_session_end
            echo -e "${GREEN}✅ Project already configured${NC}"
            echo ""
            show_usage
            return
        fi
        
        echo -e "${YELLOW}📝 No config.json found. Let's configure your project!${NC}"
        echo ""
        
        # Project directory already exists, skip clone
        check_python_version
    else
        # Remote install mode, need to clone project
        check_python_version
        clone_project
    fi
    
    # Install dependencies and configure
    install_dependencies
    select_model
    configure_model
    select_channel
    configure_channel
    menu_session_end
    create_config_file
    
    # Auto-start after configuration for a true out-of-the-box experience.
    echo ""
    start_project
}

# Require running inside the project directory
require_project_dir() {
    if [ "$IS_PROJECT_DIR" = false ]; then
        echo -e "${RED}${EMOJI_CROSS} Must run in project directory${NC}"
        exit 1
    fi
}

# Management commands use the same English prompts as install.
init_ui_lang() {
    UI_LANG="en"
}

# Main function
main() {
    init_ui_lang

    case "$1" in
        start|stop|restart|status|logs|config|update|_post_update)
            require_project_dir
            ;;
    esac

    case "$1" in
        start)   cmd_start ;;
        stop)    cmd_stop ;;
        restart) cmd_restart ;;
        status)  cmd_status ;;
        logs)    cmd_logs ;;
        config)  cmd_config ;;
        update)  cmd_update ;;
        _post_update) cmd_post_update ;;
        help|--help|-h)
            show_usage
            ;;
        "")
            install_mode
            ;;
        *)
            echo -e "${RED}${EMOJI_CROSS} Unknown command: $1${NC}"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"
