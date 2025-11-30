# Mẫu Thiết Kế Hệ Thống - AI Trading

## Cập Nhật Lần Cuối
[2025-11-30 14:45:00] - Chuyển sang tiếng Việt

## 1. Mẫu Kiến Trúc

### Triển Khai Dựa Trên Container
- Docker Compose để điều phối
- Dockerfile tùy chỉnh với XGBoost
- Volume mounts để lưu trữ dữ liệu bền vững

### Mẫu Lưu Trữ Dữ Liệu
```
Dữ liệu thô (Binance API) 
  → Định dạng Feather/HDF5 (I/O nhanh)
    → Xử lý đặc trưng (200+ features)
      → Train/Inference Model
```

### Train Cửa Sổ Trượt (Rolling Window)
- Chu kỳ train: 15 ngày
- Chu kỳ backtest: 7 ngày
- Tự động retrain khi có dữ liệu mới

## 2. Mẫu Chiến Lược

### Phân Tích Đa Khung Thời Gian
```python
# Chính: 5m (tín hiệu vào/ra)
# Phụ: 1h (xác nhận xu hướng)
# Bổ sung: 4h (xu hướng lớn)
include_timeframes = ["5m", "1h", "4h"]
```

### Phát Hiện Xu Hướng Thị Trường
```python
def detect_market_regime(dataframe):
    adx = dataframe['adx']
    bb_width = dataframe['bb_width']
    
    if adx > 25 and bb_width > 0.04:
        return "TREND"      # Giao dịch
    elif adx < 20 and bb_width < 0.02:
        return "SIDEWAY"    # Bỏ qua
    else:
        return "VOLATILE"   # Bỏ qua
```

### Mẫu Xử Lý Đặc Trưng
```python
# Phân cấp mở rộng đặc trưng:
# expand_all: Đa TF × Shifted × Pairs → ~180 features
# expand_basic: Giá trị thô + % thay đổi
# standard: Chuẩn hóa Min-Max [0, 1]
```

## 3. Mẫu Quản Lý Rủi Ro

### Stoploss Động (theo ATR)
```python
def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
    atr = self.get_atr(pair)
    dynamic_sl = -2 * (atr / current_rate)
    return max(dynamic_sl, -0.15)  # Giới hạn -15%
```

### Kích Thước Lệnh Theo Độ Tin Cậy
```python
def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake, **kwargs):
    confidence = self.get_prediction_confidence(pair)
    
    if confidence < 0.6:
        return proposed_stake * 0.5   # 25 USDT
    elif confidence > 0.8:
        return proposed_stake * 1.2   # 60 USDT
    else:
        return proposed_stake         # 50 USDT
```

### Tính Toán Đòn Bẩy
```python
# Công thức: Đòn bẩy = Rủi ro / |Stoploss|
# Ví dụ: 0.20 / 0.05 = 4x
# Giới hạn: tối đa 20x
leverage = min(max_risk / abs(stoploss), 20)
```

## 4. Mẫu Chỉ Báo

### Chỉ Báo SMC (Tùy Chỉnh)
Nằm trong `user_data/strategies/indicators/smc_indicators.py`:
- Sonic R Dragon Lines
- EMA 369/630
- Moon Phase Features (Pha trăng)
- Khoảng cách đến High/Low

### Chỉ Báo Kỹ Thuật Chuẩn
```python
# Các chỉ báo cốt lõi
indicators = {
    'rsi': ta.RSI(close, 14),
    'bb_upper': ta.BBANDS(close)[0],
    'bb_lower': ta.BBANDS(close)[2],
    'mfi': ta.MFI(high, low, close, volume),
    'adx': ta.ADX(high, low, close),
    'atr': ta.ATR(high, low, close)
}
```

## 5. Quy Ước Code

### Tổ Chức File
```
strategies/
├── FreqAIStrategy.py      # Chiến lược AI chính
├── BasicStrategy.py       # Chiến lược dự phòng
└── indicators/
    └── smc_indicators.py  # Chỉ báo tùy chỉnh
```

### Quy Ước Đặt Tên
- Lớp chiến lược: PascalCase (ví dụ: `FreqAIStrategy`)
- Hàm chỉ báo: snake_case (ví dụ: `calculate_sonic_r`)
- Cột đặc trưng: snake_case với tiền tố (ví dụ: `&s-rsi`, `%-change`)

### Mẫu Cấu Hình
```json
{
  "stake_amount": "unlimited",    // Cho phép stake tùy chỉnh
  "use_custom_stoploss": true,    // Bật SL động
  "freqai": {
    "enabled": true,
    "train_period_days": 15,
    "backtest_period_days": 7
  }
}
```

## 6. Mẫu Kiểm Thử

### Lệnh Backtest
```bash
# Backtest chuẩn
docker compose run --rm freqtrade backtesting \
  --strategy FreqAIStrategy \
  --timerange 20251101-20251130

# Hyperopt (tối ưu tham số)
docker compose run --rm freqtrade hyperopt \
  --strategy FreqAIStrategy \
  --hyperopt-loss SharpeHyperOptLoss \
  --spaces buy sell roi stoploss \
  --epochs 100
```

### Checklist Xác Minh
1. Kiểm tra log để xác nhận phân loại xu hướng
2. Xác minh stake thay đổi theo độ tin cậy
3. Xác nhận stoploss điều chỉnh theo ATR
4. So sánh chỉ số trước/sau thay đổi
