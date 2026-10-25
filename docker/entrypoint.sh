#!/bin/bash
set -e

# build prefix
CHATGPT_ON_WECHAT_PREFIX=${CHATGPT_ON_WECHAT_PREFIX:-""}
# path to config.json
CHATGPT_ON_WECHAT_CONFIG_PATH=${CHATGPT_ON_WECHAT_CONFIG_PATH:-""}
# execution command line
CHATGPT_ON_WECHAT_EXEC=${CHATGPT_ON_WECHAT_EXEC:-""}

# use environment variables to pass parameters
# if you have not defined environment variables, set them below
# export OPEN_AI_API_KEY=${OPEN_AI_API_KEY:-'YOUR API KEY'}
# export OPEN_AI_PROXY=${OPEN_AI_PROXY:-""}
# export SINGLE_CHAT_PREFIX=${SINGLE_CHAT_PREFIX:-'["bot", "@bot"]'}
# export SINGLE_CHAT_REPLY_PREFIX=${SINGLE_CHAT_REPLY_PREFIX:-'"[bot] "'}
# export GROUP_CHAT_PREFIX=${GROUP_CHAT_PREFIX:-'["@bot"]'}
# export CONVERSATION_MAX_TOKENS=${CONVERSATION_MAX_TOKENS:-"1000"}
# export SPEECH_RECOGNITION=${SPEECH_RECOGNITION:-"False"}
# export EXPIRES_IN_SECONDS=${EXPIRES_IN_SECONDS:-"3600"}

# CHATGPT_ON_WECHAT_PREFIX is empty, use /app
if [ "$CHATGPT_ON_WECHAT_PREFIX" == "" ] ; then
    CHATGPT_ON_WECHAT_PREFIX=/app
fi

# CHATGPT_ON_WECHAT_CONFIG_PATH is empty, use '/app/config.json'
if [ "$CHATGPT_ON_WECHAT_CONFIG_PATH" == "" ] ; then
    CHATGPT_ON_WECHAT_CONFIG_PATH=$CHATGPT_ON_WECHAT_PREFIX/config.json
fi

# CHATGPT_ON_WECHAT_EXEC is empty, use ‘python app.py’
if [ "$CHATGPT_ON_WECHAT_EXEC" == "" ] ; then
    CHATGPT_ON_WECHAT_EXEC="python app.py"
fi

# modify content in config.json
# if [ "$OPEN_AI_API_KEY" == "YOUR API KEY" ] || [ "$OPEN_AI_API_KEY" == "" ]; then
#     echo -e "\033[31m[Warning] You need to set OPEN_AI_API_KEY before running!\033[0m"
# fi


# apply runtime timezone from TZ env so datetime.now() uses local time
if [ -n "$TZ" ] && [ -f "/usr/share/zoneinfo/$TZ" ]; then
    ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime 2>/dev/null || true
    echo "$TZ" > /etc/timezone 2>/dev/null || true
fi

# fix ownership of mounted volumes then drop to non-root user
if [ "$(id -u)" = "0" ]; then
    mkdir -p /home/agent/maia "${MAIA_DATA_DIR:-/home/agent/.maia}"
    chown agent:agent /home/agent/maia "${MAIA_DATA_DIR:-/home/agent/.maia}"
    exec su agent -s /bin/bash -c "cd $CHATGPT_ON_WECHAT_PREFIX && $CHATGPT_ON_WECHAT_EXEC"
fi

# fallback: already running as agent
cd $CHATGPT_ON_WECHAT_PREFIX
$CHATGPT_ON_WECHAT_EXEC


