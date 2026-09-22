#!/bin/bash
set -eu

NPM_GLOBAL_PREFIX=/home/agent/.npm-global
AGENTLY_CLI_VERSION=1.0.18

export PATH="$NPM_GLOBAL_PREFIX/bin:$PATH"

if ! command -v node >/dev/null 2>&1 || [ ! -x "$NPM_GLOBAL_PREFIX/bin/agently-cli" ]; then
    apt-get update
    apt-get install -y --no-install-recommends curl ca-certificates
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get update
    apt-get install -y --no-install-recommends nodejs
    npm config set prefix "$NPM_GLOBAL_PREFIX"
    npm install --global --prefix "$NPM_GLOBAL_PREFIX" "@tencent-qqmail/agently-cli@${AGENTLY_CLI_VERSION}"
fi

mkdir -p /home/agent/.agently-cli /home/agent/.local/share/agently-cli "$NPM_GLOBAL_PREFIX"
chown -R agent:agent /home/agent/.agently-cli /home/agent/.local/share/agently-cli "$NPM_GLOBAL_PREFIX"

exec /entrypoint.sh
