#!/bin/bash
# Freq Alert Dispatcher
# Sends alerts via multiple channels

ALERT_LEVEL="$1"
MESSAGE="$2"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
ALERT_LOG="/root/.openclaw/workspace/logs/alerts.log"

# Configuration - EDIT THESE
SLACK_WEBHOOK=""  # Add your Slack webhook URL here
EMAIL_TO=""      # Add your email here
TELEGRAM_BOT_TOKEN=""  # Add your Telegram bot token
TELEGRAM_CHAT_ID=""    # Add your Telegram chat ID

mkdir -p "$(dirname "$ALERT_LOG")"

# Log to file
echo "[$TIMESTAMP] [$ALERT_LEVEL] $MESSAGE" >> "$ALERT_LOG"

# Console output with emoji
case "$ALERT_LEVEL" in
    "CRITICAL")
        echo "🔴 [$TIMESTAMP] CRITICAL: $MESSAGE"
        ;;
    "WARNING")
        echo "🟡 [$TIMESTAMP] WARNING: $MESSAGE"
        ;;
    "INFO")
        echo "🟢 [$TIMESTAMP] INFO: $MESSAGE"
        ;;
    *)
        echo "⚪ [$TIMESTAMP] $ALERT_LEVEL: $MESSAGE"
        ;;
esac

# Slack notification (if configured)
if [ -n "$SLACK_WEBHOOK" ]; then
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"🚨 Freq Alert [$ALERT_LEVEL]: $MESSAGE\"}" \
        "$SLACK_WEBHOOK" 2>/dev/null || true
fi

# Email notification (if configured and mail available)
if [ -n "$EMAIL_TO" ] && command -v mail >/dev/null 2>&1; then
    echo "$MESSAGE" | mail -s "[Freq Alert] $ALERT_LEVEL" "$EMAIL_TO" 2>/dev/null || true
fi

# Telegram notification (if configured)
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=🚨 Freq Alert [$ALERT_LEVEL]: $MESSAGE" \
        2>/dev/null || true
fi

# Also write to WhatsApp-compatible log (for OpenClaw)
echo "[$TIMESTAMP] FREQ_ALERT [$ALERT_LEVEL]: $MESSAGE" >> /root/.openclaw/workspace/logs/whatsapp_alerts.log
