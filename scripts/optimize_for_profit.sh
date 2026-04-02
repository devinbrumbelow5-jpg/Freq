#!/bin/bash
# optimize_for_profit.sh
# Run hyperopt until profitable parameters found

cd /root/.openclaw/workspace/freqtrade

echo "========================================"
echo "OPTIMIZING AGGRESSIVE SCALPER FOR PROFIT"
echo "========================================"
echo ""

# Run 300 epochs to find best parameters
docker run --rm -v $(pwd)/user_data:/freqtrade/user_data \
  freqtradeorg/freqtrade:stable hyperopt \
  --strategy AggressiveScalper_v1 \
  --config user_data/config_aggressive.json \
  --timerange $(date -d '7 days ago' +%Y%m%d)-$(date +%Y%m%d) \
  --timeframe 1m \
  -e 300 \
  --spaces buy sell roi stoploss \
  --hyperopt-loss OnlyProfitHyperOptLoss \
  2>&1 | tee /root/.openclaw/workspace/profits/hyperopt.log | tail -100