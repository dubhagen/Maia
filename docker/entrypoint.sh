#!/bin/bash
set -e

APP_DIR=/app

# Apply the runtime timezone from TZ so datetime.now() uses local time.
if [ -n "$TZ" ] && [ -f "/usr/share/zoneinfo/$TZ" ]; then
    ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime 2>/dev/null || true
    echo "$TZ" > /etc/timezone 2>/dev/null || true
fi

# Fix ownership of mounted volumes, then drop to the non-root user.
if [ "$(id -u)" = "0" ]; then
    mkdir -p /home/agent/maia "${MAIA_DATA_DIR:-/home/agent/.maia}"
    chown agent:agent /home/agent/maia "${MAIA_DATA_DIR:-/home/agent/.maia}"
    exec su agent -s /bin/bash -c "cd $APP_DIR && python app.py"
fi

cd "$APP_DIR"
exec python app.py
