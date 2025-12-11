#!/bin/bash
cd /opt/freqtrade

# Discord Webhook URL
DISCORD_WEBHOOK="https://discord.com/api/webhooks/1447437726038233244/DvfA_bftWa_xUsGVqCOAPcWRUg-i08t7HooV2Q_c91U6Kb4l0j0SjKU20U0_Vl0fWY85"

send_discord() {
    local message="$1"
    local clean_message=$(echo "$message" | sed 's/"/\\"/g')
    wget -q -O- --timeout=10 --post-data="{\"content\": \"$clean_message\"}" --header="Content-Type: application/json" "$DISCORD_WEBHOOK" >/dev/null 2>&1
}

TIMERANGE=${1:-"20240101-20241201"}
STRATEGY=${2:-"FreqAIStrategy"}

# ============ STEP 1: START ============
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting backtest..." > backtest.log
send_discord "🚀 **BACKTEST STARTED**
📅 Timerange: $TIMERANGE
📊 Strategy: $STRATEGY
⏰ Start time: $(date '+%Y-%m-%d %H:%M:%S')"

# ============ STEP 2: CLEAN OLD MODELS ============
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [1/5] Cleaning old models..." >> backtest.log
send_discord "🧹 [Step 1/5] Cleaning old models..."
# COMMENTED OUT: Không xóa models vì sẽ reuse từ hyperopt
# sudo rm -rf user_data/models/*

# ============ STEP 3: DOWNLOAD LATEST DATA ============
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [2/5] Downloading latest data..." >> backtest.log
send_discord "📥 [Step 2/5] Downloading latest OHLCV data..."
sudo docker run --rm \
    -v $(pwd)/user_data:/freqtrade/user_data \
    -v $(pwd)/user_data/config.json:/freqtrade/config.json \
    freqtrade-custom:latest download-data \
    --timerange $TIMERANGE \
    --timeframes 5m 15m 1h 4h \
    -p BTC/USDT:USDT ETH/USDT:USDT >> backtest.log 2>&1

# ============ STEP 4: RUN BACKTEST ============
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [3/5] Running backtest..." >> backtest.log
send_discord "⏳ [Step 3/5] Running 1-year backtest with FreqAI (this will take 20-30 mins)..."

BACKTEST_START=$(date +%s)
sudo docker run --rm \
    -v $(pwd)/user_data:/freqtrade/user_data \
    -v $(pwd)/user_data/config.json:/freqtrade/config.json \
    freqtrade-custom:latest backtesting \
    --strategy $STRATEGY \
    --freqaimodel XGBoostRegressor \
    --timerange $TIMERANGE > backtest_result.log 2>&1
BACKTEST_END=$(date +%s)
DURATION=$((BACKTEST_END - BACKTEST_START))
DURATION_MIN=$((DURATION / 60))

# ============ STEP 5: PARSE RESULTS ============
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [4/5] Parsing results..." >> backtest.log
send_discord "📊 [Step 4/5] Backtest complete! Duration: ${DURATION_MIN} minutes. Parsing results..."

# Extract key metrics
TOTAL_TRADES=$(grep "Total/Daily Avg Trades" backtest_result.log | awk -F'│' '{print $3}' | xargs)
WIN_RATE=$(grep -E "Win  Draw  Loss  Win%" backtest_result.log | tail -1 | awk -F'│' '{print $8}' | xargs)
TOTAL_PROFIT=$(grep "Total profit %" backtest_result.log | awk -F'│' '{print $3}' | xargs)
ABSOLUTE_PROFIT=$(grep "Absolute profit" backtest_result.log | awk -F'│' '{print $3}' | xargs)
DRAWDOWN=$(grep "Absolute drawdown" backtest_result.log | awk -F'│' '{print $3}' | xargs)
PROFIT_FACTOR=$(grep "Profit factor" backtest_result.log | awk -F'│' '{print $3}' | xargs)
SHARPE=$(grep "Sharpe" backtest_result.log | awk -F'│' '{print $3}' | xargs)

# Get the full strategy summary line
SUMMARY=$(grep "FreqAIStrategy" backtest_result.log | tail -1)

# ============ STEP 6: SEND FINAL RESULTS ============
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [5/5] Sending final results..." >> backtest.log
send_discord "✅ **BACKTEST COMPLETE!**

📊 **1-YEAR RESULTS (${TIMERANGE})**
━━━━━━━━━━━━━━━━━━━━━
📈 Total Trades: $TOTAL_TRADES
🎯 Win Rate: $WIN_RATE
💰 Total Profit: $TOTAL_PROFIT
💵 Absolute Profit: $ABSOLUTE_PROFIT
📉 Max Drawdown: $DRAWDOWN
⚖️ Profit Factor: $PROFIT_FACTOR
📐 Sharpe Ratio: $SHARPE
⏱️ Duration: ${DURATION_MIN} minutes
━━━━━━━━━━━━━━━━━━━━━
🔧 Strategy: $STRATEGY
📁 Full log: /opt/freqtrade/backtest_result.log"

# ============ BACKUP TO DRIVE ============
if command -v rclone &> /dev/null; then
    rclone copy backtest_result.log gdrive:freqtrade-backup/ 2>/dev/null || true
    send_discord "☁️ Results backed up to Google Drive"
fi

# ============ SHUTDOWN VM ============
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done! Shutting down VM..." >> backtest.log
send_discord "🔌 VM shutting down. Backtest flow complete!"
sudo shutdown -h now
