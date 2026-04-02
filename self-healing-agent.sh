#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Self-Healing Agent - Container Monitor & Auto-Restart Service
# Freq Trading Swarm - Brownwood, Texas
# ═══════════════════════════════════════════════════════════════

# Configuration
WORKSPACE="/root/.openclaw/workspace"
COMPOSE_FILE="$WORKSPACE/docker-compose.yml"
LOG_FILE="$WORKSPACE/memory/restarts.log"
PID_FILE="/tmp/self-healing-agent.pid"
CHECK_INTERVAL=30  # Check every 30 seconds
MAX_RESTART_ATTEMPTS=3
RESTART_WINDOW=300  # 5 minutes

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Timestamp function
timestamp() {
    date '+[%Y-%m-%d %H:%M:%S]'
}

# Log to both terminal and file
log() {
    local level="$1"
    local message="$2"
    local container="${3:-SYSTEM}"
    local ts=$(timestamp)
    
    # Terminal output with colors
    case "$level" in
        "INFO")
            echo -e "${ts} ${BLUE}[HEALER]${NC} [${level}] [${container}] ${message}"
            ;;
        "WARN")
            echo -e "${ts} ${YELLOW}[HEALER]${NC} [${level}] [${container}] ${message}"
            ;;
        "ERROR"|"CRITICAL")
            echo -e "${ts} ${RED}[HEALER]${NC} [${level}] [${container}] ${message}"
            ;;
        "RESTART")
            echo -e "${ts} ${GREEN}[HEALER]${NC} [${level}] [${container}] ${message}"
            ;;
    esac
    
    # File output (no colors)
    echo "${ts} [HEALER] [${level}] [${container}] ${message}" >> "$LOG_FILE"
}

# Initialize log file
init_log() {
    mkdir -p "$WORKSPACE/memory"
    if [ ! -f "$LOG_FILE" ]; then
        touch "$LOG_FILE"
        log "INFO" "Self-healing agent initialized"
        log "INFO" "Monitor interval: ${CHECK_INTERVAL}s | Max restarts: ${MAX_RESTART_ATTEMPTS}"
    fi
    log "INFO" "Self-healing agent started"
}

# Track restart attempts per container
declare -A restart_count
declare -A last_restart_time

# Check if container is healthy
check_container_health() {
    local container_name="$1"
    local status=$(docker ps --filter "name=$container_name" --format "{{.Status}}" 2>/dev/null)
    
    if [ -z "$status" ]; then
        echo "DOWN"
    elif echo "$status" | grep -q "unhealthy"; then
        echo "UNHEALTHY"
    elif echo "$status" | grep -q "Up"; then
        echo "HEALTHY"
    else
        echo "UNKNOWN"
    fi
}

# Get container exit code if it crashed
get_exit_code() {
    local container_name="$1"
    local exit_code=$(docker inspect --format='{{.State.ExitCode}}' "$container_name" 2>/dev/null)
    echo "$exit_code"
}

# Get container uptime
get_uptime() {
    local container_name="$1"
    local uptime=$(docker ps --filter "name=$container_name" --format "{{.RunningFor}}" 2>/dev/null)
    echo "$uptime"
}

# Restart a container via docker-compose
restart_container() {
    local container_name="$1"
    local reason="$2"
    local service_name=""
    
    # Map container name to service name
    case "$container_name" in
        "freqtrade-main") service_name="freqtrade-main" ;;
        "freqtrade-trend") service_name="freqtrade-trend" ;;
        "freqtrade-meanrev") service_name="freqtrade-meanrev" ;;
        "freqtrade-breakout") service_name="freqtrade-breakout" ;;
        "freqtrade-redis") service_name="redis" ;;
        "freqtrade-notifier") service_name="notifier" ;;
        *) service_name="" ;;
    esac
    
    if [ -z "$service_name" ]; then
        log "ERROR" "Unknown container: $container_name"
        return 1
    fi
    
    log "RESTART" "Restarting due to: $reason" "$container_name"
    
    # Record restart time
    local now=$(date +%s)
    last_restart_time["$container_name"]=$now
    
    # Increment restart count
    if [ -z "${restart_count[$container_name]}" ]; then
        restart_count["$container_name"]=1
    else
        restart_count["$container_name"]=$((${restart_count[$container_name]} + 1))
    fi
    
    # Check if we've exceeded max restarts
    if [ "${restart_count[$container_name]}" -gt "$MAX_RESTART_ATTEMPTS" ]; then
        log "CRITICAL" "Max restart attempts exceeded (${MAX_RESTART_ATTEMPTS}). Manual intervention required!" "$container_name"
        return 1
    fi
    
    # Attempt restart
    log "INFO" "Executing docker-compose restart... (attempt ${restart_count[$container_name]})" "$container_name"
    
    cd "$WORKSPACE" || return 1
    
    # Find docker compose (try 'docker compose' first, then 'docker-compose')
    DCMD="docker compose"
    if ! docker compose version >/dev/null 2>&1; then
        if command -v docker-compose >/dev/null 2>&1; then
            DCMD="docker-compose"
        else
            log "ERROR" "Neither 'docker compose' nor 'docker-compose' found" "$container_name"
            return 1
        fi
    fi
    
    # Stop the container
    $DCMD -f "$COMPOSE_FILE" stop "$service_name" 2>&1 | while read line; do
        log "INFO" "STOP: $line" "$container_name"
    done
    
    # Remove the container to ensure clean restart
    docker rm -f "$container_name" 2>/dev/null || true
    
    # Start the container
    local start_output=$($DCMD -f "$COMPOSE_FILE" up -d "$service_name" 2>&1)
    local start_status=$?
    
    if [ $start_status -eq 0 ]; then
        sleep 5  # Give it time to start
        local new_status=$(check_container_health "$container_name")
        if [ "$new_status" == "HEALTHY" ]; then
            log "RESTART" "✅ Container restarted successfully" "$container_name"
            return 0
        else
            log "ERROR" "❌ Container started but not healthy (status: $new_status)" "$container_name"
            return 1
        fi
    else
        log "ERROR" "❌ Failed to restart: $start_output" "$container_name"
        return 1
    fi
}

# Reset restart count if container has been stable
reset_restart_count_if_stable() {
    local container_name="$1"
    local now=$(date +%s)
    local last_restart="${last_restart_time[$container_name]:-0}"
    local time_since_restart=$((now - last_restart))
    
    # If container has been running for 10 minutes without issues, reset count
    if [ "$time_since_restart" -gt 600 ] && [ "${restart_count[$container_name]:-0}" -gt 0 ]; then
        restart_count["$container_name"]=0
        log "INFO" "Reset restart count - container stable for 10+ minutes" "$container_name"
    fi
}

# Main monitoring loop
monitor_loop() {
    local containers=("freqtrade-main" "freqtrade-trend" "freqtrade-meanrev" "freqtrade-breakout" "freqtrade-redis" "freqtrade-notifier")
    
    while true; do
        for container in "${containers[@]}"; do
            local status=$(check_container_health "$container")
            
            case "$status" in
                "DOWN")
                    local exit_code=$(get_exit_code "$container")
                    log "WARN" "Container DOWN (exit code: ${exit_code})" "$container"
                    restart_container "$container" "Container crashed/exited with code ${exit_code}"
                    ;;
                "UNHEALTHY")
                    log "WARN" "Health check failed" "$container"
                    restart_container "$container" "Health check failing"
                    ;;
                "HEALTHY")
                    reset_restart_count_if_stable "$container"
                    ;;
                "UNKNOWN")
                    log "WARN" "Container in unknown state" "$container"
                    restart_container "$container" "Unknown container state"
                    ;;
            esac
        done
        
        # Sleep before next check
        sleep "$CHECK_INTERVAL"
    done
}

# Signal handlers
cleanup() {
    log "INFO" "Self-healing agent shutting down"
    rm -f "$PID_FILE"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Show status
show_status() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Self-Healing Agent Status${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    local containers=("freqtrade-main" "freqtrade-trend" "freqtrade-meanrev" "freqtrade-breakout" "freqtrade-redis" "freqtrade-notifier")
    
    for container in "${containers[@]}"; do
        local status=$(check_container_health "$container")
        local uptime=$(get_uptime "$container")
        
        case "$status" in
            "HEALTHY")
                echo -e "  ${GREEN}●${NC} $container - $status ($uptime)"
                ;;
            "DOWN")
                echo -e "  ${RED}●${NC} $container - $status"
                ;;
            *)
                echo -e "  ${YELLOW}●${NC} $container - $status"
                ;;
        esac
    done
    
    echo ""
    echo "  Log file: $LOG_FILE"
    echo ""
    
    if [ -f "$LOG_FILE" ]; then
        echo -e "${BLUE}  Recent Restart Events:${NC}"
        echo ""
        grep "\[RESTART\]" "$LOG_FILE" | tail -5 || echo "  No restarts recorded yet"
        echo ""
    fi
}

# Parse arguments
case "${1:-}" in
    --status)
        show_status
        exit 0
        ;;
    --stop)
        if [ -f "$PID_FILE" ]; then
            local pid=$(cat "$PID_FILE")
            kill "$pid" 2>/dev/null || true
            rm -f "$PID_FILE"
            echo "Self-healing agent stopped"
        else
            echo "Self-healing agent not running"
        fi
        exit 0
        ;;
    --logs)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "No log file found. Start the agent first."
            exit 1
        fi
        exit 0
        ;;
    --help|-h)
        echo "Self-Healing Agent - Container Monitor & Auto-Restart Service"
        echo ""
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  (none)    Start the monitoring agent in foreground"
        echo "  --status  Show container status and restart history"
        echo "  --stop    Stop the running agent"
        echo "  --logs    Follow the restart log"
        echo "  --help    Show this help message"
        echo ""
        echo "Monitored containers:"
        echo "  - freqtrade-main (Main trading bot)"
        echo "  - freqtrade-trend (Trend following bot)"
        echo "  - freqtrade-meanrev (Mean reversion bot)"
        echo "  - freqtrade-breakout (Breakout scalper bot)"
        echo "  - freqtrade-redis (Redis service)"
        echo "  - freqtrade-notifier (Notification service)"
        exit 0
        ;;
esac

# Check if already running (skip if SKIP_CHECK_RUNNING is set)
if [ -z "$SKIP_CHECK_RUNNING" ]; then
    if [ -f "$PID_FILE" ]; then
        local old_pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$old_pid" ] && ps -p "$old_pid" > /dev/null 2>&1; then
            if ps -p "$old_pid" -o cmd= 2>/dev/null | grep -q "self-healing-agent"; then
                echo "Self-healing agent already running (PID: $old_pid)"
                exit 1
            fi
        fi
        rm -f "$PID_FILE"
    fi
fi

# Write our PID (parent process)
echo $$ > "$PID_FILE"

# Main execution
init_log
log "INFO" "Monitoring started (interval: ${CHECK_INTERVAL}s)"
log "INFO" "Max restarts: ${MAX_RESTART_ATTEMPTS} per container per ${RESTART_WINDOW}s window"
monitor_loop