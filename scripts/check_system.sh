#!/bin/bash
# System readiness check for Freq Ultimate Scalper

echo "=== FREQ SCALPER SYSTEM CHECK ==="
echo "Timestamp: $(date)"
echo ""

# Check CPU
echo "[CPU]"
cat /proc/cpuinfo | grep "model name" | head -1
echo "Cores: $(nproc)"
echo ""

# Check RAM
echo "[RAM]"
free -h | grep "Mem:"
echo ""

# Check Docker
echo "[DOCKER]"
docker --version
docker compose version 2>/dev/null || echo "docker-compose: NOT FOUND"
echo ""

# Check GPU
echo "[GPU]"
nvidia-smi 2>/dev/null || echo "NVIDIA GPU: Not detected (CPU-only mode)"
echo ""

# Check disk space
echo "[DISK]"
df -h / | tail -1
echo ""

# Check network
echo "[NETWORK]"
ping -c 1 8.8.8.8 >/dev/null 2>&& echo "Internet: OK" || echo "Internet: DOWN"
echo ""

echo "=== CHECK COMPLETE ==="