# Phân Tích Chuyên Sâu: Hệ Thống Chỉ Báo & Chiến Lược Trading

> **Cập nhật:** 2025-12-05 | **Version:** v3.0 - Strict Confluence

## 1. Tổng Quan Điều Hành (Executive Summary)

Hệ thống FreqAI đã trải qua nhiều vòng tối ưu hóa theo triết lý **"Strict Confluence"** (Hợp lưu Nghiêm ngặt). Kết quả cho thấy việc siết chặt filters giúp giảm đáng kể Drawdown và Total Loss.

### Kết Quả Backtest (2024-01-01 → 2024-05-01)

| Version | Trades | Win% | Total Profit | Drawdown | Thay đổi |
|---------|--------|------|--------------|----------|----------|
| Ban đầu | 337 | 33.8% | **-21.42%** | 22.65% | Baseline |
| Fix Entry Strict | 150 | 34.0% | **-9.1%** | 9.76% | ⬆️ +12% |
| Giảm Features | 166 | 34.9% | **-8.01%** | **8.98%** | ⬆️ +1% |

### Cấu Hình Hiện Tại

| Parameter | Giá trị | Mô tả |
|-----------|---------|-------|
| `buy_pred_threshold` | **0.02** | AI phải dự đoán giá tăng ≥2% |
| `overall_score` (Long) | **> 0.7** | Confluence rất mạnh |
| `overall_score` (Short) | **< 0.3** | Confluence rất yếu |
| `vsa_score` | **> 0.5** | Yêu cầu Valid Move |
| `structure_direction` | **> 0 / < 0** | SMC BOS confirmation |
| Features | **~1500** | Giảm từ 6192 (-75%) |

---

## 2. "Bộ Não": Hệ Thống Điểm Số Hợp Lưu

### 2.1. Điểm Tổng Thể (`%-overall_score`)
- **Công thức**: `0.4 * Trend + 0.35 * Momentum + 0.25 * Money Pressure`
- **Ngưỡng STRICT**:
    - **> 0.7**: Long (từ 0.6 lên 0.7)
    - **< 0.3**: Short (từ 0.4 xuống 0.3)
    - *Vùng 0.3 - 0.7 là vùng trung tính, Bot đứng ngoài.*

### 2.2. VSA Score (`%-vsa_score`)
- **Valid Move (+1)**: Volume cao + Spread lớn → Entry OK
- **Churning (-1)**: Volume cao + Spread nhỏ → BLOCK
- **Fakeout (-0.5)**: Volume thấp + Spread lớn → BLOCK
- **Ngưỡng**: `> 0.5` (từ >= 0)

### 2.3. Structure Direction (`%-structure_direction`)
- **> 0**: BOS/CHoCH Bullish → Long OK
- **< 0**: BOS/CHoCH Bearish → Short OK
- **= 0**: Sideways → BLOCK

---

## 3. Điều Kiện Vào Lệnh (7 Cổng AND)

### Long Entry

| # | Điều Kiện | Ngưỡng | Mô tả |
|---|-----------|--------|-------|
| 1 | AI Prediction | `> 0.02` | Dự đoán tăng ≥2% |
| 2 | Market Regime | `!= VOLATILE/EXTREME` | Tránh thị trường điên |
| 3 | Overall Score | `> 0.7` | Confluence mạnh |
| 4 | Dynamic Trend | `EMA200 up OR RSI < 30` | Trend hoặc Oversold |
| 5 | VSA Score | `> 0.5` | Valid Move |
| 6 | Structure Direction | `> 0` | **NEW** - BOS Bullish |
| 7 | Volume | `> 0` | Có khối lượng |

### Short Entry (8 Cổng)

| # | Điều Kiện | Ngưỡng | Mô tả |
|---|-----------|--------|-------|
| 1 | AI Prediction | `< -0.02` | Dự đoán giảm ≥2% |
| 2 | Market Regime | `!= VOLATILE/EXTREME` | Tránh thị trường điên |
| 3 | Overall Score | `< 0.3` | Confluence yếu |
| 4 | Dynamic Trend | `EMA200 down OR RSI > 70` | Trend hoặc Overbought |
| 5 | VSA Score | `> 0.5` | Valid Move |
| 6 | Structure Direction | `< 0` | **NEW** - BOS Bearish |
| 7 | Volume | `> 0` | Có khối lượng |
| 8 | Fib Protection | `!= Fib 0.618` | Tránh Short hỗ trợ |

---

## 4. Feature Engineering (Tối Ưu)

### Cấu Hình FreqAI

```json
{
  "indicator_periods_candles": [14, 20],  // Giảm từ [10,14,20,50]
  "include_shifted_candles": 1,           // Giảm từ 3
  "include_timeframes": ["5m", "15m", "1h", "4h"]
}
```

### Features Đã Disable
- ❌ **Chart Patterns** (936 features) - Không hiệu quả cho crypto

### Features Đang Dùng
- ✅ **Core** (Log Returns, EMA, RSI, ADX)
- ✅ **SMC** (Order Blocks, FVG, Structure, Liquidity)
- ✅ **Wave** (Fibonacci, Awesome Oscillator)
- ✅ **VSA** (Volume Spread Analysis)
- ✅ **Confluence** (Overall Score, Money Pressure)

---

## 5. Risk Management

| Parameter | Giá trị | Mô tả |
|-----------|---------|-------|
| Max Risk/Trade | **20% margin** | Luôn cố định |
| Stoploss | **-3%** (fixed) | Điểm cắt lỗ |
| Trailing Stop | **DISABLED** | Không trailing |
| Leverage | **Dynamic** | = 20% / SL% |

**Ví dụ Leverage:**
- SL = -3% → Leverage = 20%/3% = **6.67x**
- SL = -5% → Leverage = 20%/5% = **4x**

---

## 6. Kết Luận & Next Steps

### Đã Đạt Được
- ✅ Giảm Drawdown: 22.65% → **8.98%** (-60%)
- ✅ Giảm Loss: -21.42% → **-8.01%** (-63%)
- ✅ Giảm Features: 6192 → ~1500 (-75%)

### Cần Cải Thiện
- ⚠️ Win Rate vẫn thấp: 34.9% (cần 45%+)
- ⚠️ Vẫn lỗ tổng: -8.01%
- ⚠️ Loss nhiều hơn Win: 58/108

### Hướng Tiếp Theo
1. Tăng `buy_pred_threshold` lên 0.02 ✅ (đang test)
2. Hyperopt để tìm optimal thresholds
3. Check feature importance từ model

