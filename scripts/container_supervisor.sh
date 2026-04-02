#!/bin/bash
# Freq Container Supervisor
# Handles restarts with exponential backoff and alerting

CONTAINER_NAME="${1:-92351c7fbb00_freqtrade-range}"
MAX_RETRIES=5
INITIAL_BACKOFF=10
LOG_FILE="/root/.openclaw/workspace/logs/supervisor.log"
ALERT_SCRIPT="/root/.openclaw/workspace/scripts/send_alert.sh"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SUPERVISOR] $1" | tee -a "$LOG_FILE"
}

send_alert() {
    local level="$1"
    local msg="$2"
    
    log "[$level] $msg"
    
    # Call alert script if exists
    if [ -x "$ALERT_SCRIPT" ]; then
        "$ALERT_SCRIPT" "$level" "$msg"
    fi
}

restart_with_backoff() {
    local retry_count=0
    local backoff=$INITIAL_BACKOFF
    
    while [ $retry_count -lt $MAX_RETRIES ]; do
        log "Attempting restart $((retry_count + 1))/$MAX_RETRIES..."
        
        # Stop if running
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        sleep 2
        
        # Remove old container
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
        sleep 1
        
        # Start new container
        if docker compose -f /root/.openclaw/workspace/freqtrade/docker-compose.yml up -d "$CONTAINER_NAME" 2>/dev/null || \
           docker run -d \
            --name "$CONTAINER_NAME" \
            --restart unless-stopped \
            -v /root/.openclaw/workspace/freqtrade/user_data:/freqtrade/user_data \
            -p 127.0.0.1:8082:8080 \
            freqtradeorg/freqtrade:stable trade \
            --logfile /freqtrade/user_data/logs/range.log \
            --db-url sqlite:////freqtrade/user_data/trades_range.sqlite \
            --config /freqtrade/user_data/config_range.json \
            --strategy MeanReversionScalper_v1 2>/dev/null; then
            
            log "Container started, waiting for health check..."
            sleep $backoff
            
            # Check if container is healthy
            if docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null | grep -q "running"; then
                send_alert "INFO" "✅ $CONTAINER_NAME recovered after restart (attempt $((retry_count + 1)))"
                return 0
            fi
        fi
        
        retry_count=$((retry_count + 1))
        backoff=$((backoff * 2))
        
        if [ $retry_count -lt $MAX_RETRIES ]; then
            log "Restart failed, waiting ${backoff}s before retry..."
            sleep $backoff
        fi
    done
    
    send_alert "CRITICAL" "🔥 $CONTAINER_NAME failed to start after $MAX_RETRIES attempts"
    return 1
}

# Monitor loop
log "Supervisor started for $CONTAINER_NAME"

while true; do
    # Check container status
    if ! docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null | grep -q "running"; then
        send_alert "WARNING" "⚠️ $CONTAINER_NAME not running, initiating restart..."
        restart_with_backoff
    fi
    
    # Check for excessive resource usage
    CPU=$(docker stats "$CONTAINER_NAME" --no-stream --format "{{.CPUPerc}}" 2>/dev/null | tr -d '%' || echo 0)
    MEM=$(docker stats "$CONTAINER_NAME" --no-stream --format "{{.MemPerc}}" 2>/dev/null | tr -d '%' || echo 0)
    
    if [ "${CPU%.*}" -gt 90 ] 2>/dev/null; then
        send_alert "WARNING" "⚠️ $CONTAINER_NAME high CPU: ${CPU}%"
    fi
    
    if [ "${MEM%.*}" -gt 90 ] 2>/dev/null; then
        send_alert "WARNING" "⚠️ $CONTAINER_NAME high Memory: ${MEM}%"
    fi
    
    # Check for recent crashes
    RESTART_COUNT=$(docker inspect -f '{{.RestartCount}}' "$CONTAINER_NAME" 2>/dev/null || echo 0)
    if [ "$RESTART_COUNT" -gt 5 ]; then
        send_alert "CRITICAL" "🔥 $CONTAINER_NAME has restarted $RESTART_COUNT times"
    fi
    
    sleep 30
done
