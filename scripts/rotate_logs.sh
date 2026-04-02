#!/bin/bash
# Log Rotation Script for Freq
# Run daily via cron

LOG_DIR="/root/.openclaw/workspace/logs"
FREQTRADE_LOG_DIR="/root/.openclaw/workspace/freqtrade/user_data/logs"
MAX_SIZE_MB=100
MAX_AGE_DAYS=7

rotate_logs() {
    local dir="$1"
    
    [ -d "$dir" ] || return
    
    for log in "$dir"/*.log; do
        [ -f "$log" ] || continue
        
        local size_mb=$(du -m "$log" | cut -f1)
        
        if [ "$size_mb" -gt "$MAX_SIZE_MB" ]; then
            # Rotate: move current to .1, compress, delete old
            mv "$log" "${log}.1"
            gzip "${log}.1"
            rm -f "${log}.7.gz"  # Keep only 7 rotations
            
            # Shift old rotations
            for i in 6 5 4 3 2 1; do
                if [ -f "${log}.${i}.gz" ]; then
                    mv "${log}.${i}.gz" "${log}.$((i+1)).gz"
                fi
            done
            
            # Create new log
            touch "$log"
        fi
    done
    
    # Clean old logs
    find "$dir" -name "*.log.*.gz" -mtime +$MAX_AGE_DAYS -delete 2>/dev/null || true
}

# Rotate all log directories
rotate_logs "$LOG_DIR"
rotate_logs "$FREQTRADE_LOG_DIR"

# Also clean freqtrade strategy logs
find "$FREQTRADE_LOG_DIR" -name "*.log" -size +${MAX_SIZE_MB}M -exec sh -c '
    mv "$1" "${1}.1" && gzip "${1}.1" && touch "$1"
' _ {} \; 2>/dev/null || true

echo "Log rotation completed at $(date)"
