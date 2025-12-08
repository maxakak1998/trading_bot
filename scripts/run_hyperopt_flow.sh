#!/bin/bash
cd /opt/freqtrade

# Discord Webhook URL
DISCORD_WEBHOOK="https://discord.com/api/webhooks/1447437726038233244/DvfA_bftWa_xUsGVqCOAPcWRUg-i08t7HooV2Q_c91U6Kb4l0j0SjKU20U0_Vl0fWY85"

send_discord() {
    local message="$1"
    # Use jq to safely escape the message for JSON
    # If jq is not available, we use python or simple sed escape
    # But for simplicity on VM, let's just strip double quotes which might break JSON
    local clean_message=$(echo "$message" | sed 's/"/\\"/g')
    wget -q -O- --timeout=10 --post-data="{\"content\": \"$clean_message\"}" --header="Content-Type: application/json" "$DISCORD_WEBHOOK" >/dev/null 2>&1
}

EPOCHS=${1:-100}
TIMERANGE=${2:-"20240101-20240701"}

echo "[1/5] Cleaning old models..." > flow.log
send_discord "🚀 Hyperopt Started - $EPOCHS epochs, timerange: $TIMERANGE"
sudo rm -rf user_data/models/*

echo "[2/5] Hyperopt started ($EPOCHS epochs)..." >> flow.log
# REMOVED 'trailing' and 'stoploss' from spaces to enforce fixed strategy values
sudo docker run --rm \
    -v $(pwd)/user_data:/freqtrade/user_data \
    -v $(pwd)/user_data/config.json:/freqtrade/config.json \
    freqtrade-custom:latest hyperopt \
    --strategy FreqAIStrategy \
    --freqaimodel XGBoostRegressor \
    --hyperopt-loss WinRatioHyperOptLoss \
    --epochs $EPOCHS \
    --spaces buy sell roi stoploss trailing \
    --timerange $TIMERANGE \
    --random-state 42 \
    -j 28 >> hyperopt.log 2>&1

# Improved parsing: Find "Best result:" and get the line with trace/profit stats
# We look for the line containing "trades." which appears after Best result
RESULT=$(grep -A 5 "Best result:" hyperopt.log | grep "trades." | tail -n 1)

echo "[3/5] Backing up results..." >> flow.log
# Ensure rclone is configured or skip
if command -v rclone &> /dev/null; then
    rclone sync user_data/models/freqai-xgboost gdrive:freqtrade-backup/models/freqai-xgboost 2>/dev/null || true
    rclone copy user_data/strategies/FreqAIStrategy.json gdrive:freqtrade-backup/strategies/ 2>/dev/null || true
    rclone copy hyperopt.log gdrive:freqtrade-backup/ 2>/dev/null || true
fi

echo "[4/5] Sending Discord notification..." >> flow.log
if [ -z "$RESULT" ]; then
    send_discord "⚠️ Hyperopt Finished but could not parse Best Result. Check logs."
else
    send_discord "✅ Hyperopt Complete! Result: $RESULT"
fi

echo "[5/5] Stopping VM..." >> flow.log
sudo shutdown -h now
