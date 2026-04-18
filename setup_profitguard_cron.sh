#!/bin/bash
# PROFITGUARD AI Cron Setup Script
# Run this to add automated monitoring to system crontab

CRONTAB_FILE="/tmp/profitguard_crontab.txt"

# Export current crontab
crontab -l > "$CRONTAB_FILE" 2>/dev/null || echo "# New crontab" > "$CRONTAB_FILE"

# Check if already installed
if grep -q "PROFITGUARD AI" "$CRONTAB_FILE"; then
    echo "PROFITGUARD AI cron jobs already installed."
    echo "To update, remove existing entries first."
    exit 0
fi

# Add PROFITGUARD AI jobs
cat >> "$CRONTAB_FILE" << 'EOF'

# PROFITGUARD AI — Automated Monitoring (Added 2026-04-13)
# Hourly report at top of hour Central Time
0 * * * * TZ=America/Chicago cd /root/.openclaw/workspace && python3 profitguard_hourly_report.py >> logs/profitguard_hourly.log 2>&1

# Risk check every 5 minutes Central Time
*/5 * * * * TZ=America/Chicago cd /root/.openclaw/workspace && python3 profitguard_risk_check.py >> logs/profitguard_risk.log 2>&1

# Soul file reinforcement every 3 hours Central Time
0 */3 * * * TZ=America/Chicago cd /root/.openclaw/workspace && python3 profitguard_soul_maintenance.py >> logs/profitguard_soul.log 2>&1

# Process health check every 2 minutes
*/2 * * * * TZ=America/Chicago cd /root/.openclaw/workspace && python3 profitguard_health_check.py >> logs/profitguard_health.log 2>&1
EOF

# Install new crontab
crontab "$CRONTAB_FILE"

# Verify
if [ $? -eq 0 ]; then
    echo "✅ PROFITGUARD AI cron jobs installed successfully!"
    echo ""
    echo "Jobs installed:"
    echo "  - Hourly report (every hour at :00)"
    echo "  - Risk check (every 5 minutes)"
    echo "  - Soul maintenance (every 3 hours)"
    echo "  - Health check (every 2 minutes)"
    echo ""
    echo "All times in Central Time (America/Chicago)"
    echo ""
    echo "Next hourly report: Top of next hour"
else
    echo "❌ Failed to install cron jobs"
    exit 1
fi

# Cleanup
rm -f "$CRONTAB_FILE"
