# Ngữ Cảnh Hiện Tại - Hệ Thống AI Trading

## Cập Nhật Lần Cuối
[2025-11-30 16:00:00] - Phase 4.3 Feature Engineering Refactor HOÀN THÀNH

## 1. Trọng Tâm Hiện Tại

**Giai Đoạn**: Phase 4 - Kiến Trúc AI Nâng Cao  
**Trạng Thái**: Phase 3 (Feature Engineering + Chart Patterns) ĐÃ XONG, Phase 4 (Hyperopt) ĐANG CHỜ

## 2. Thành Tựu Gần Đây

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

### Sẵn Sàng Cho:
- ✅ Train FreqAI model mới với ~65 features đúng chuẩn
- ✅ Hyperopt optimization
- ✅ Backtest để đánh giá hiệu quả

### Thay Đổi Cấu Hình Hiện Tại
- `config.json`: `"use_custom_stoploss": true`
- `config.json`: `"stake_amount": "unlimited"`
- Giao dịch Futures enabled (50 USDT cơ bản, đòn bẩy 4x)

## 4. Bước Tiếp Theo

### Ưu Tiên 1: Train FreqAI Model Mới
Để model học các features Phase 3 mới:
```bash
docker compose run --rm freqtrade backtesting \
  --strategy FreqAIStrategy \
  --timerange 20251001-20251130 \
  --freqaimodel XGBoostClassifier
```

### Ưu Tiên 2: Hyperopt Optimization
```bash
docker compose run --rm freqtrade hyperopt \
  --strategy FreqAIStrategy \
  --hyperopt-loss SharpeHyperOptLoss \
  --epochs 50 \
  --freqaimodel XGBoostClassifier
```

### Ưu Tiên 3: Phase 4.4 Pretrained Models
- Nghiên cứu FinBERT, TimeGPT
- Ensemble với XGBoost hiện tại

## 5. Câu Hỏi Mở

1. ~~Chạy Hyperopt trước hay train FreqAI model mới trước?~~ → Train model trước để test features
2. Số epochs hyperopt phù hợp (50 hay 100)?
3. Có nên thêm pairs khác (SOL, BNB)?

## 6. Trở Ngại

Hiện tại không có. Hệ thống đã được refactor với Feature Engineering đúng chuẩn.
