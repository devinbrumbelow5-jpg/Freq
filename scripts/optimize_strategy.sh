#!/bin/bash
# optimize_strategy.sh
# Run hyperopt to find profitable parameters

cd /root/.openclaw/workspace/freqtrade

echo "Starting hyperopt for SimpleScalper_v1..."
echo "This will test 100 parameter combinations to find profitable settings"
echo ""

docker run --rm -v $(pwd)/user_data:/freqtrade/user_data \
  freqtradeorg/freqtrade:stable hyperopt \
  --strategy SimpleScalper_v1 \
  --config user_data/config_backtest.json \
  --timerange $(date -d '7 days ago' +%Y%m%d)-$(date +%Y%m%d) \
  --timeframe 1m \
  -e 100 \
  --spaces buy sell roi stoploss trailing \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --enable-protections 2>&1 | tail -100