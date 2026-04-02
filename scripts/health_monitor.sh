#!/bin/bash
# Freq Ultimate Health Monitor
# Runs every 60 seconds, sends alerts on failure

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/root/.openclaw/workspace/logs/health_monitor.log"
ALERT_LOG="/root/.openclaw/workspace/logs/alerts.log"
PID_FILE="/root/.openclaw/workspace/health_monitor.pid"
CONTAINER_NAME="92351c7fbb00_freqtrade-range"
CONFIG_FILE="/root/.openclaw/workspace/config/monitor.conf"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Write PID
echo $$ > "$PID_FILE"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Alert function (customize with your webhook/email)
send_alert() {
    local severity="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "[$timestamp] [$severity] $message" >> "$ALERT_LOG"
    
    # Console alert (can be replaced with email/Slack)
    echo "🚨 ALERT [$severity]: $message"
    
    # TODO: Add your webhook here
    # curl -X POST -H 'Content-type: application/json' \
    #   --data '{"text":"🚨 Freq Alert: '"$message"'"}' \
    #   YOUR_SLACK_WEBHOOK_URL
}

# Health check: Docker container
check_container() {
    local container="$1"
    local status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null)
    
    if [ "$status" != "running" ]; then
        send_alert "CRITICAL" "Container $container is $status"
        return 1
    fi
    
    # Check if container is healthy (no recent restarts)
    local start_time=$(docker inspect -f '{{.State.StartedAt}}' "$container" 2>/dev/null)
    local uptime_seconds=$(($(date +%s) - $(date -d "$start_time" +%s 2>/dev/null || echo 0)))
    
    if [ "$uptime_seconds" -lt 300 ]; then  # Less than 5 minutes
        send_alert "WARNING" "Container $container restarted recently (uptime: ${uptime_seconds}s)"
    fi
    
    return 0
}

# Health check: Exchange connectivity
check_exchange() {
    local exchange="$1"
    local url="$2"
    
    if ! curl -sf --max-time 10 "$url" >/dev/null 2>&1; then
        send_alert "CRITICAL" "Exchange $exchange unreachable: $url"
        return 1
    fi
    
    return 0
}

# Health check: Cloudflare
check_cloudflare() {
    if ! curl -sf --max-time 5 https://1.1.1.1 >/dev/null 2>&1; then
        send_alert "WARNING" "Cloudflare DNS unreachable - possible network issue"
        return 1
    fi
    return 0
}

# Health check: Websocket status (via freqtrade API)
check_websocket() {
    local container="$1"
    local ws_errors=$(docker logs "$container" --since "2m" 2>/dev/null | grep -c "websocket\|timeout\|Connection refused" || echo 0)
    
    if [ "$ws_errors" -gt 5 ]; then
        send_alert "WARNING" "Container $container has $ws_errors websocket errors in last 2 minutes"
        return 1
    fi
    
    return 0
}

# Health check: Rate limits
check_rate_limits() {
    local container="$1"
    local rate_errors=$(docker logs "$container" --since "5m" 2>/dev/null | grep -c "rate.*limit\|429\|Too Many Requests" || echo 0)
    
    if [ "$rate_errors" -gt 0 ]; then
        send_alert "WARNING" "Rate limit hits detected: $rate_errors in last 5 minutes"
        return 1
    fi
    
    return 0
}

# Health check: Disk space
check_disk() {
    local usage=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    
    if [ "$usage" -gt 85 ]; then
        send_alert "CRITICAL" "Disk usage at ${usage}%"
        return 1
    elif [ "$usage" -gt 75 ]; then
        send_alert "WARNING" "Disk usage at ${usage}%"
        return 1
    fi
    
    return 0
}

# Health check: Memory
check_memory() {
    local usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    
    if [ "$usage" -gt 90 ]; then
        send_alert "CRITICAL" "Memory usage at ${usage}%"
        return 1
    elif [ "$usage" -gt 80 ]; then
        send_alert "WARNING" "Memory usage at ${usage}%"
        return 1
    fi
    
    return 0
}

# Restart container with exponential backoff
restart_container() {
    local container="$1"
    local max_retries=5
    local retry_count=0
    local backoff=10
    
    log "Attempting to restart $container..."
    
    while [ $retry_count -lt $max_retries ]; do
        docker restart "$container" 2>/dev/null
        sleep $backoff
        
        if check_container "$container"; then
            log "Container $container restarted successfully"
            send_alert "INFO" "Container $container recovered after restart"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        backoff=$((backoff * 2))  # Exponential backoff
        log "Retry $retry_count/$max_retries - waiting ${backoff}s..."
    done
    
    send_alert "CRITICAL" "Failed to restart $container after $max_retries attempts"
    return 1
}

# Main monitoring loop
main() {
    log "Health Monitor started (PID: $$)"
    
    local consecutive_failures=0
    local max_consecutive_failures=3
    
    while true; do
        local all_checks_passed=true
        
        # Check container health
        if ! check_container "$CONTAINER_NAME"; then
            all_checks_passed=false
            restart_container "$CONTAINER_NAME"
        fi
        
        # Check websockets
        check_websocket "$CONTAINER_NAME" || all_checks_passed=false
        
        # Check rate limits
        check_rate_limits "$CONTAINER_NAME" || true  # Don't fail on this
        
        # Check exchanges
        check_exchange "OKX" "https://www.okx.com" || all_checks_passed=false
        check_exchange "Binance" "https://api.binance.com/api/v3/ping" || true  # Optional
        check_exchange "Bybit" "https://api.bybit.com" || true  # Optional
        
        # Check Cloudflare
        check_cloudflare || all_checks_passed=false
        
        # Check system resources
        check_disk || all_checks_passed=false
        check_memory || all_checks_passed=false
        
        # Track consecutive failures
        if [ "$all_checks_passed" = false ]; then
            consecutive_failures=$((consecutive_failures + 1))
            if [ $consecutive_failures -ge $max_consecutive_failures ]; then
                send_alert "CRITICAL" "System unhealthy for $consecutive_failures consecutive checks"
            fi
        else
            consecutive_failures=0
        fi
        
        # Sleep for 60 seconds
        sleep 60
    done
}

# Handle shutdown gracefully
cleanup() {
    log "Health Monitor shutting down..."
    rm -f "$PID_FILE"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Run main loop
main
