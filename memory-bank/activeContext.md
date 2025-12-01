# Ngữ Cảnh Hiện Tại - Hệ Thống AI Trading

## Cập Nhật Lần Cuối
[2025-12-01 17:00:00] - Pipeline test PASS, sẵn sàng hyperopt 1 năm

## 1. Trọng Tâm Hiện Tại

**Giai Đoạn**: Phase 4.3 - Hyperopt Optimization  
**Trạng Thái**: ⏳ READY - Sẵn sàng chạy hyperopt 1 năm data

## 2. Hoạt Động Gần Nhất

### ✅ Pipeline Test PASS (2025-12-01 16:43)
- **Test hyperopt 1 tháng (Oct 2024):** THÀNH CÔNG
- **Kết quả:** 3 trades, 100% win rate, +4.29 USDT
- **Best params đã lưu:** `user_data/strategies/FreqAIStrategy.json`
- **Models backed up:** `models_20251201_164333` (48.67 MB)

### ✅ Makefile Updates
- **`clean-models`**: Xóa models + hyperopt_results + docker cache
- **`clean-models-force`**: Force delete không hỏi
- **`show-params`**: Xem params hiện tại từ JSON
- **`reset-params`**: Reset về defaults trong code
- **Fixed**: `atr_multiplier` KeyError (bỏ `stoploss` khỏi HYPEROPT_SPACES)

### ⏳ Chuẩn Bị Hyperopt 1 Năm
- **Timerange:** 20231101-20241101 (1 năm)
- **Epochs:** 500
- **Spaces:** buy, sell, roi
- **Data:** ✅ Đã có đủ (Sep 2023 - Dec 2024)
- **Models:** ✅ Đã xóa clean

## 3. Tình Trạng Hiện Tại

### Best Parameters (từ test 1 tháng)
```json
{
  "buy": {
    "buy_adx_threshold": 27,
    "buy_pred_threshold": 0.007,
    "buy_rsi_high": 66,
    "buy_rsi_low": 29,
    "confidence_threshold": 0.685
  },
  "sell": {
    "sell_pred_threshold": -0.021,
    "sell_rsi_threshold": 73
  },
  "roi": {
    "0": 0.112,
    "40": 0.049,
    "91": 0.018,
    "137": 0
  }
}
```

### Models Available (Google Drive):
- `models_20251201_164333` - 48 MB (10 models, 1-month test)
- `models_20251201_074154` - 467 MB (96 models, 6-month data)
- `models_20251130_180612` - 211 MB

## 4. Thành Tựu Trước Đó

### Pipeline Test Results (2025-12-01 16:43)

| Metric | Value |
|--------|-------|
| Epochs | 100 |
| Timerange | Oct 2024 (1 tháng) |
| Trades | 3 |
| Win Rate | 100% |
| Total Profit | +4.29 USDT |
| Avg Duration | 2h 17m |

### Training Results Analysis ✅ [2025-11-30]

**KẾT QUẢ:** -1.81% loss (64 trades, 46.9% win rate)

| Exit Reason | Trades | Profit | Win Rate |
|-------------|--------|--------|----------|
| roi | 28 | +80.27 USDT | 100% ✅ |
| trailing_stop_loss | 33 | -91.32 USDT | 0% ❌ |
| exit_signal | 3 | -7.07 USDT | 0% |

**ROOT CAUSE:** `custom_stoploss()` dùng `current_rate` → trailing effect

### Phase 3: Feature Engineering Refactor (HOÀN THÀNH) ✅ [2025-11-30 16:00]

**Vấn Đề Đã Giải Quyết:**
- Features trước đây dùng giá trị tuyệt đối (EMA = 60000) → AI không học được
- Thiếu Volume indicators quan trọng (OBV, CMF, VWAP)
- Chưa có Chart Pattern recognition

**Giải Pháp - Nguyên Tắc Feature Engineering Đúng:**
1. **Không dùng giá trị tuyệt đối** → Dùng biến thiên (Delta/Slope/Distance)
2. **Tránh indicators bị lag** → Ưu tiên Oscillators, Volume
3. **Log Returns là VUA** → Chuẩn hóa giá về dao động quanh 0
4. **Stationary features** → RSI, %, độ biến động

**Files Đã Tạo:**
- `indicators/feature_engineering.py` - ~50 features đúng chuẩn ML
- `indicators/chart_patterns.py` - 11 pattern features

**Features Mới (~65 total):**
| Category | Số Features | Mô Tả |
|----------|-------------|-------|
| Log Returns | 5 | Core features - ln(price/price.shift) |
| Momentum | 10+ | ROC, RSI, Williams %R, CCI, StochRSI |
| Trend | 12+ | EMA distances, slopes, ADX, DI |
| Volatility | 8+ | ATR%, BB width, BB position |
| Volume | 8+ | OBV, CMF, MFI, VWAP, Volume ratio |
| Candle | 6+ | Body, shadow, direction, streak |
| S/R | 5+ | Distance to highs/lows |
| Chart Patterns | 11 | Double top/bottom, H&S, wedges, triangles, flags |

### Phase 2: Data Enhancement (HOÀN THÀNH) ✅ [2025-11-30]

| Nhiệm Vụ | Trạng Thái | Chi Tiết |
|----------|------------|----------|
| Fear & Greed Index | ✅ Xong | API alternative.me, cache 1h |
| Volume Imbalance | ✅ Xong | Buy/sell pressure từ candle |
| Funding Rate Proxy | ✅ Xong | Price premium/discount |

## 3. Trạng Thái Hiện Tại

### Hyperopt Đang Chạy:
```bash
make hyperopt
# --epochs 500
# --hyperopt-loss SortinoHyperOptLossDaily  
# --spaces buy sell roi stoploss
# --timerange 20231201-20241101
```

### Model Config:
- **Identifier:** `freqai-xgboost-v2-stationary`
- **Model:** XGBoostRegressor (n_est=800, depth=7, lr=0.03)
- **Training:** 48 timeranges × 2 pairs (BTC, ETH)
- **Features:** ~400+ (expand_basic × 3 TFs + expand_all)

### Thay Đổi Cấu Hình Hiện Tại
- `config.json`: `"use_custom_stoploss": true`
- `config.json`: `"stake_amount": "unlimited"`
- Giao dịch Futures enabled (50 USDT cơ bản, đòn bẩy 4x)

## 4. Bước Tiếp Theo

### Sau Khi Hyperopt Xong:
1. **Xem kết quả:** `make hyperopt-show`
2. **Apply best params:** Export vào strategy hoặc config
3. **Backtest với optimized params:** `make backtest-optimized`
4. **Fix custom_stoploss:** Đổi `current_rate` → `trade.open_rate`

### Ưu Tiên Tiếp Theo:
1. **Dry-run paper trading:** `make dry-run`
2. **Test LightGBM/CatBoost:** `make test-lightgbm`
3. **Live trading (sau khi confident):** `make live`

## 5. Câu Hỏi Mở

1. ~~Chạy Hyperopt trước hay train FreqAI model mới trước?~~ → Train model trước để test features
2. Số epochs hyperopt phù hợp (50 hay 100)?
3. Có nên thêm pairs khác (SOL, BNB)?

## 6. Trở Ngại

### ⚠️ Custom Stoploss Issue (CẦN FIX)
- `custom_stoploss()` dùng `current_rate` → trailing effect
- **Impact:** -91 USDT loss từ 33 trades bị stop
- **Fix:** Đổi `current_rate` → `trade.open_rate` trong FreqAIStrategy.py line 137

### ✅ Đã Giải Quyết:
- ~~FreqAI không train~~ → Fixed `self.freqai.start()`
- ~~Models bị mất~~ → Added auto-backup to Makefile
