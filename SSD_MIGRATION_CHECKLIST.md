# SSD Migration Checklist

## Before SSD Arrives
- [ ] Review this checklist
- [ ] Ensure backup power (UPS) if available
- [ ] Note current freqtrade location: /root/.openclaw/workspace/freqtrade

## SSD Installation Day
- [ ] Stop all trading: `./scripts/stop_all.sh` or `docker stop $(docker ps -q --filter name=freqtrade)`
- [ ] Run pre-migration: `./scripts/prep_for_ssd.sh`
- [ ] Physically install SSD
- [ ] Mount SSD (example: `sudo mount /dev/nvme0n1p1 /mnt/ssd`)
- [ ] Run migration: `./scripts/ssd_migration.sh /mnt/ssd`
- [ ] Update fstab for auto-mount on boot
- [ ] Restart swarm and verify

## Post-Migration Verification
- [ ] All containers start without errors
- [ ] SQLite databases accessible
- [ ] FreqAI models load correctly
- [ ] 4h retrain cycle completes < 15 minutes (vs 30+ on HDD)
- [ ] Backtest runs < 5 minutes (vs 20+ on HDD)

## Cleanup (after 24h success)
- [ ] Remove old HDD data: `rm -rf /root/.openclaw/workspace/freqtrade.old`
- [ ] Archive backup if space needed
