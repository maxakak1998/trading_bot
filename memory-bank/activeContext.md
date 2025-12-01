# Ngữ Cảnh Hiện Tại - Hệ Thống AI Trading

## Cập Nhật Lần Cuối
[2025-12-01 10:05:00] - Đang xử lý feature mismatch issue

## 1. Trọng Tâm Hiện Tại

**Giai Đoạn**: Phase 4.3 - Bug Fixing & Backtest Verification  
**Trạng Thái**: ⚠️ BLOCKED - Models không khớp với code mới

## 2. Bugs Đã Fix Trong Session Này

### ✅ Bug 1: Custom Stoploss Trailing Effect (CRITICAL - Đã Fix)
**File:** `FreqAIStrategy.py` line 136  
**Vấn đề:** Dùng `current_rate` → trailing effect → -91 USDT loss từ 33 trades  
**Fix:** Đổi `current_rate` → `trade.open_rate`  
**Impact:** KHÔNG cần retrain (runtime logic)

### ✅ Bug 2: ATR/EMA None Check (Đã Fix nhưng gây incompatibility)
**File:** `wave_indicators.py`  
**Vấn đề:** `ta.atr()` trả về None khi không đủ data → crash  
**Fix:** Thêm helper functions `safe_atr()` và `safe_ema()`  
**Impact:** CẦN retrain vì thay đổi code flow

## 3. Tình Trạng Hiện Tại

### ⚠️ Feature Mismatch Issue
- Models đã train với code cũ (wave_indicators.py chưa có safe_atr)
- Code mới có thêm null safety checks
- FreqAI báo lỗi: "different features furnished by current strategy"

### 🎯 Lựa Chọn:
| Option | Mô tả | Thời gian |
|--------|-------|-----------|
| **Option 1** | Retrain từ đầu với code mới | ~2-3 giờ |
| **Option 2** | Revert wave_indicators, chỉ giữ fix custom_stoploss | Ngay lập tức |

### Models Available (Google Drive):
- `models_20251201_074154` - 467 MB (96 models, 1-year data)
- `models_20251201_000849` - 445 MB
- `models_20251130_180612` - 211 MB

## 4. Thành Tựu Trước Đó

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
