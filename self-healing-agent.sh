#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Freq Ultimate Scalper v2.0 - Self-Healing Agent (Production 2026)
# Zero-downtime restart, healthcheck-driven, resource-aware
# ═══════════════════════════════════════════════════════════════════

# Configuration
WORKSPACE="${WORKSPACE:-/root/.openclaw/workspace}"
COMPOSE_FILE="${COMPOSE_FILE:-$WORKSPACE/freqtrade/docker-compose.yml}"
LOG_FILE="${LOG_FILE:-$WORKSPACE/logs/healing-agent.log}"
PID_FILE="${PID_FILE:-/tmp/freq-healing-agent.pid}"
ALERT_LOG="${ALERT_LOG:-$WORKSPACE/logs/alerts.log}"

CHECK_INTERVAL="${CHECK_INTERVAL:-30}"
MAX_RESTART_ATTEMPTS="${MAX_RESTART_ATTEMPTS:-5}"
RESTART_WINDOW="${RESTART_WINDOW:-300}"
HEALTHY_THRESHOLD="${HEALTHY_THRESHOLD:-180}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ═════════════════════════════════════════════════════════════════
# LOGGING
# ═════════════════════════════════════════════════════════════════
timestamp() { date '+[%Y-%m-%d %H:%M:%S]'; }

log() {
    local level="$1"
    local message="$2"
    local container="${3:-AGENT}"
    local ts=$(timestamp)
    
    case "$level" in
        "INFO") echo -e "${ts} ${BLUE}[HEALER]${NC} [${level}] [${container}] ${message}" ;;
        "WARN") echo -e "${ts} ${YELLOW}[HEALER]${NC} [${level}] [${container}] ${message}" ;;
        "ERROR"|"CRITICAL") echo -e "${ts} ${RED}[HEALER]${NC} [${level}] [${container}] ${message}" ;;
        "RESTART") echo -e "${ts} ${GREEN}[HEALER]${NC} [${level}] [${container}] ${message}" ;;
    esac
    
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "${ts} [HEALER] [${level}] [${container}] ${message}" >> "$LOG_FILE"
}

# ═════════════════════════════════════════════════════════════════
# CONTAINER MANAGEMENT
# ═════════════════════════════════════════════════════════════════
declare -A RESTART_COUNT
declare -A LAST_RESTART_TIME

get_container_status() {
    local name="$1"
    local health=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null)
    local status=$(docker inspect --format='{{.State.Status}}' "$name" 2>/dev/null)
    local running=$(docker inspect --format='{{.State.Running}}' "$name" 2>/dev/null)
    
    if [ "$status" = "running" ] && [ "$running" = "true" ]; then
        if [ "$health" = "healthy" ] || [ "$health" = "none" ] || [ -z "$health" ]; then
            echo "HEALTHY"
        elif [ "$health" = "starting" ]; then
            echo "STARTING"
        else
            echo "UNHEALTHY"
        fi
    elif [ "$status" = "restarting" ]; then
        echo "RESTARTING"
    elif [ "$status" = "exited" ] || [ "$status" = "dead" ]; then
        echo "DOWN"
    else
        echo "UNKNOWN"
    fi
}

get_container_stats() {
    local name="$1"
    docker stats "$name" --no-stream --format "CPU:{{.CPUPerc}} MEM:{{.MemPerc}}" 2>/dev/null || echo "N/A"
}

zero_downtime_restart() {
    local service="$1"
    local container="$2"
    
    log "RESTART" "Initiating zero-downtime restart" "$container"
    
    # Pull latest image if needed
    docker compose -f "$COMPOSE_FILE" pull "$service" 2>/dev/null || true
    
    # Scale up new container first (rolling update style)
    local temp_name="${container}-temp-$$"
    
    # Start new container
    if ! docker compose -f "$COMPOSE_FILE" run -d --name "$temp_name" "$service" 2>/dev/null; then
        log "ERROR" "Failed to start temporary container" "$container"
        return 1
    fi
    
    # Wait for new container to be healthy
    local wait_count=0
    while [ $wait_count -lt 30 ]; do
        local status=$(get_container_status "$temp_name")
        if [ "$status" = "HEALTHY" ]; then
            log "INFO" "New container healthy, switching traffic" "$container"
            break
        fi
        sleep 2
        wait_count=$((wait_count + 1))
    done
    
    if [ $wait_count -ge 30 ]; then
        log "ERROR" "New container failed health check" "$container"
        docker rm -f "$temp_name" 2>/dev/null
        return 1
    fi
    
    # Stop old container
    docker stop "$container" 2>/dev/null || true
    docker rm -f "$container" 2>/dev/null || true
    
    # Rename new container
    docker rename "$temp_name" "$container" 2>/dev/null || true
    
    log "RESTART" "✅ Zero-downtime restart completed" "$container"
    return 0
}

restart_with_backoff() {
    local service="$1"
    local container="$2"
    local reason="$3"
    
    local count=${RESTART_COUNT[$container]:-0}
    local last=${LAST_RESTART_TIME[$container]:-0}
    local now=$(date +%s)
    
    # Reset count if outside window
    if [ $((now - last)) -gt $RESTART_WINDOW ]; then
        count=0
    fi
    
    if [ $count -ge $MAX_RESTART_ATTEMPTS ]; then
        log "CRITICAL" "Max restarts exceeded ($MAX_RESTART_ATTEMPTS). Manual intervention required!" "$container"
        echo "[{\"severity\":\"CRITICAL\",\"message\":\"Container $container exceeded max restarts\",\"timestamp\":\"$(date -Iseconds)\"}]" >> "$ALERT_LOG"
        return 1
    fi
    
    log "RESTART" "Attempt $((count + 1))/$MAX_RESTART_ATTEMPTS: $reason" "$container"
    
    # Exponential backoff
    local backoff=$((10 * (2 ** count)))
    [ $backoff -gt 300 ] && backoff=300
    
    RESTART_COUNT[$container]=$((count + 1))
    LAST_RESTART_TIME[$container]=$now
    
    # Try zero-downtime restart first
    if ! zero_downtime_restart "$service" "$container"; then
        log "WARN" "Zero-downtime restart failed, using standard restart" "$container"
        
        # Standard restart
        docker compose -f "$COMPOSE_FILE" stop "$service" 2>/dev/null
        docker rm -f "$container" 2>/dev/null
        sleep $backoff
        docker compose -f "$COMPOSE_FILE" up -d "$service"
        
        # Wait and verify
        sleep 10
        local new_status=$(get_container_status "$container")
        if [ "$new_status" != "HEALTHY" ]; then
            log "ERROR" "❌ Restart failed, container not healthy" "$container"
            return 1
        fi
    fi
    
    log "RESTART" "✅ Restart successful" "$container"
    return 0
}

# ═════════════════════════════════════════════════════════════════
# REGIME FILTER INTEGRATION
# ═════════════════════════════════════════════════════════════════
check_regime_filter() {
    local pause_file="/tmp/trading_paused"
    if [ -f "$pause_file" ]; then
        local reason=$(cat "$pause_file" 2>/dev/null)
        log "WARN" "Trading paused by regime filter: $reason"
        return 1
    fi
    return 0
}

# ═════════════════════════════════════════════════════════════════
# MONITORING LOOP
# ═════════════════════════════════════════════════════════════════
MONITOR_LOOP() {
    local services=("freqtrade-range" "regime-filter")
    
    log "INFO" "Self-healing agent started"
    log "INFO" "Check interval: ${CHECK_INTERVAL}s | Max restarts: ${MAX_RESTART_ATTEMPTS}"
    log "INFO" "Zero-downtime restart: ENABLED"
    
    while true; do
        for service in "${services[@]}"; do
            local container="freqtrade-${service}"
            [ "$service" = "regime-filter" ] && container="freqtrade-${service}"
            [ "$service" = "freqtrade-range" ] && container="92351c7fbb00_freqtrade-range"
            
            # Check if container exists
            if ! docker ps -a --format "{{.Names}}" | grep -q "^${container}$"; then
                # Try to find actual container name
                container=$(docker ps -a --format "{{.Names}}" | grep "$service" | head -1)
                [ -z "$container" ] && continue
            fi
            
            local status=$(get_container_status "$container")
            local stats=$(get_container_stats "$container")
            
            case "$status" in
                "DOWN"|"UNKNOWN")
                    log "WARN" "Container DOWN (status: $status, stats: $stats)" "$container"
                    restart_with_backoff "$service" "$container" "Container crashed"
                    ;;
                "UNHEALTHY")
                    log "WARN" "Health check failing (stats: $stats)" "$container"
                    restart_with_backoff "$service" "$container" "Health check failed"
                    ;;
                "STARTING")
                    log "INFO" "Container starting..." "$container"
                    ;;
                "HEALTHY")
                    # Check resource usage
                    local cpu=$(echo "$stats" | grep -oP 'CPU:\K[0-9.]+' || echo "0")
                    local mem=$(echo "$stats" | grep -oP 'MEM:\K[0-9.]+' || echo "0")
                    
                    if [ "${cpu%.*}" -gt 90 ] 2>/dev/null; then
                        log "WARN" "High CPU usage: ${cpu}%" "$container"
                    fi
                    if [ "${mem%.*}" -gt 90 ] 2>/dev/null; then
                        log "WARN" "High memory usage: ${mem}%" "$container"
                    fi
                    ;;
            esac
        done
        
        # Check regime filter
        check_regime_filter
        
        sleep "$CHECK_INTERVAL"
    done
}

# ═════════════════════════════════════════════════════════════════
# SIGNAL HANDLERS
# ═════════════════════════════════════════════════════════════════
cleanup() {
    log "INFO" "Shutting down gracefully..."
    rm -f "$PID_FILE"
    exit 0
}

trap cleanup SIGTERM SIGINT

# ═════════════════════════════════════════════════════════════════
# STATUS DISPLAY
# ═════════════════════════════════════════════════════════════════
show_status() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Freq Self-Healing Agent - Status${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    local containers=$(docker ps --filter "name=freqtrade" --format "{{.Names}}" 2>/dev/null)
    for container in $containers; do
        local status=$(get_container_status "$container")
        local stats=$(get_container_stats "$container)
        
        case "$status" in
            "HEALTHY") echo -e "  ${GREEN}●${NC} $container - $status" ;;
            "DOWN") echo -e "  ${RED}●${NC} $container - $status" ;;
            *) echo -e "  ${YELLOW}●${NC} $container - $status" ;;
        esac
        echo "      Stats: $stats"
    done
    
    echo ""
    echo "  Log: $LOG_FILE"
    echo "  Alerts: $ALERT_LOG"
    echo ""
}

# ═════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════
case "${1:-}" in
    --status)
        show_status
        exit 0
        ;;
    --stop)
        if [ -f "$PID_FILE" ]; then
            kill "$(cat "$PID_FILE")" 2>/dev/null && echo "Stopped" || echo "Not running"
            rm -f "$PID_FILE"
        fi
        exit 0
        ;;
    --logs)
        tail -f "$LOG_FILE" 2>/dev/null || echo "No logs yet"
        exit 0
        ;;
esac

# Check if already running
if [ -f "$PID_FILE" ]; then
    if ps -p "$(cat "$PID_FILE")" >/dev/null 2>&1; then
        echo "Already running (PID: $(cat "$PID_FILE"))"
        exit 1
    fi
    rm -f "$PID_FILE"
fi

# Create directories
mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$ALERT_LOG")"

# Write PID
echo $$ > "$PID_FILE"

# Start monitoring
MONITOR_LOOP
