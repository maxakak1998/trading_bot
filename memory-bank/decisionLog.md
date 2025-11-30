# Nhật Ký Quyết Định - Hệ Thống AI Trading

## Cập Nhật Lần Cuối
[2025-11-30 15:15:00] - Thêm Decision 008: Google Drive Backup

---

## Quyết Định 001: Lựa Chọn Framework
**Ngày**: 2025-11 (Setup ban đầu)  
**Trạng thái**: ✅ Đã phê duyệt

### Bối Cảnh
Cần chọn framework bot giao dịch cho hệ thống AI trading crypto.

### Các Lựa Chọn Xem Xét
1. **Freqtrade** - Mã nguồn mở, tích hợp FreqAI, cộng đồng lớn
2. **Backtrader** - Linh hoạt nhưng chậm, không hỗ trợ AI native
3. **VectorBT** - Backtest nhanh nhưng chưa mature cho live trading
4. **Tự code** - Kiểm soát hoàn toàn nhưng tốn công phát triển

### Quyết Định
**Chọn: Freqtrade**

### Lý Do
- Module FreqAI tích hợp sẵn cho ML
- Cộng đồng active và documentation tốt
- Hỗ trợ Docker để dễ triển khai
- Xử lý kết nối sàn, rate limit, recovery tự động
- Có sẵn FreqUI dashboard

---

## Quyết Định 002: Lựa Chọn Model ML
**Ngày**: 2025-11 (Phase 3)  
**Trạng thái**: ✅ Đã phê duyệt

### Bối Cảnh
Cần chọn model ML để dự đoán giá.

### Các Lựa Chọn Xem Xét
1. **XGBoost** - Nhanh, robust, tốt cho dữ liệu bảng
2. **LightGBM** - Train nhanh hơn, tiết kiệm bộ nhớ
3. **CatBoost** - Tốt với categorical features, ít cần tune
4. **LSTM** - Deep learning, cần GPU, dễ overfitting

### Quyết Định
**Chọn: XGBoost (qua FreqAI)**

### Lý Do
- Freqtrade có XGBoostClassifier native
- Chạy tốt trên CPU (không cần GPU)
- Hiệu suất tốt với time series tài chính
- Dễ phân tích feature importance
- Tương lai: Có thể thêm CatBoost hoặc ensemble

---

## Quyết Định 003: Phát Hiện Xu Hướng Thị Trường
**Ngày**: 2025-11 (Phase 4.1)  
**Trạng thái**: ✅ Đã triển khai

### Bối Cảnh
Bot vào lệnh trong mọi điều kiện thị trường, dẫn đến lỗ trong thị trường sideway.

### Các Lựa Chọn Xem Xét
1. **Dựa trên ADX** - Đo sức mạnh xu hướng
2. **Dựa trên biến động** - ATR hoặc BB Width
3. **Kết hợp** - ADX + BB Width

### Quyết Định
**Chọn: Kết hợp (ADX + Bollinger Band Width)**

### Triển Khai
```python
TREND: ADX > 25 VÀ BB Width > 0.04     # Giao dịch
SIDEWAY: ADX < 20 VÀ BB Width < 0.02   # Bỏ qua
VOLATILE: Còn lại                       # Bỏ qua
```

### Lý Do
- ADX đơn lẻ bỏ qua yếu tố biến động
- BB Width đơn lẻ bỏ qua sức mạnh xu hướng
- Kết hợp cho phân loại chính xác hơn

### Kết Quả
- Bot tránh giao dịch trong điều kiện bất lợi
- 0 lệnh trong backtest 16-30/11 (thị trường sideway)
- Có thể cần điều chỉnh ngưỡng để bắt thêm cơ hội

---

## Quyết Định 004: Chiến Lược Stoploss Động
**Ngày**: 2025-11 (Phase 4.1)  
**Trạng thái**: ✅ Đã triển khai

### Bối Cảnh
Stoploss cố định không thích ứng với biến động thị trường khác nhau.

### Các Lựa Chọn Xem Xét
1. **Cố định %** - Đơn giản nhưng không linh hoạt
2. **Theo ATR** - Thích ứng với biến động
3. **Trailing** - Khóa lợi nhuận nhưng phức tạp

### Quyết Định
**Chọn: Theo ATR với giới hạn**

### Triển Khai
```python
SL = -2 * (ATR / Giá)
Giới hạn: tối thiểu -2%, tối đa -15%
```

### Lý Do
- Biến động cao → SL rộng hơn (tránh bị stop hunt)
- Biến động thấp → SL chặt hơn (bảo vệ vốn)
- Giới hạn ngăn giá trị cực đoan

---

## Quyết Định 005: Chiến Lược Kích Thước Lệnh
**Ngày**: 2025-11 (Phase 4.1)  
**Trạng thái**: ✅ Đã triển khai

### Bối Cảnh
Stake cố định không tận dụng được tín hiệu có độ tin cậy cao.

### Các Lựa Chọn Xem Xét
1. **Cố định** - Đơn giản, rủi ro đều
2. **Kelly Criterion** - Tối ưu nhưng aggressive
3. **Theo độ tin cậy** - Scale theo confidence của AI

### Quyết Định
**Chọn: Scale theo độ tin cậy**

### Triển Khai
```python
Điểm < 0.6:  50% stake (25 USDT)
Điểm 0.6-0.8: 100% stake (50 USDT)
Điểm > 0.8: 120% stake (60 USDT)
```

### Lý Do
- Lệnh lớn hơn cho tín hiệu có độ tin cậy cao
- Lệnh nhỏ hơn cho tín hiệu không chắc chắn
- Sử dụng vốn hiệu quả hơn

---

## Quyết Định 006: Định Dạng Lưu Trữ Dữ Liệu
**Ngày**: 2025-11 (Phase 4.1)  
**Trạng thái**: ✅ Đã triển khai

### Bối Cảnh
Cần lưu trữ dữ liệu OHLCV nhanh để train model.

### Các Lựa Chọn Xem Xét
1. **CSV** - Đơn giản nhưng chậm
2. **SQLite** - Quen thuộc nhưng không tối ưu cho time series
3. **HDF5/Feather** - Nhanh, nén tốt
4. **InfluxDB** - Mạnh nhưng tốn RAM

### Quyết Định
**Chọn: Feather/HDF5 (mặc định của FreqAI)**

### Lý Do
- Nhanh hơn CSV 10-50 lần
- Dung lượng nhỏ hơn 50-70%
- Không cần chạy database service (tiết kiệm RAM)
- FreqAI tự động xử lý

---

## Quyết Định 007: Kiến Trúc Local-First
**Ngày**: 2025-11-30  
**Trạng thái**: ✅ Đã phê duyệt

### Bối Cảnh
Có $300 GCP credit và 2TB Google Drive (1 năm). Cần quyết định cách sử dụng hiệu quả.

### Các Lựa Chọn Xem Xét
1. **Chạy bot trên Cloud** - Phụ thuộc cloud, hết credit = ngừng hoạt động
2. **Hybrid** - Train cloud, run cloud
3. **Local-First** - Build trên cloud, run ở local vĩnh viễn

### Quyết Định
**Chọn: Local-First**

### Triển Khai
```
Tài nguyên sẵn có:
├── Google Cloud: $300 credit (dùng hết là hết)
├── Google Drive: 2TB (1 năm)
└── Local Machine: Sẵn có (vĩnh viễn)

Giai đoạn 1: BUILD (1-2 tháng)
├── Dùng $300 GCP để train, hyperopt, optimize
└── Output: Models tối ưu, best parameters

Giai đoạn 2: RUN (Vĩnh viễn)
├── Chạy bot local 24/7
├── Backup tự động → Google Drive (1 năm)
└── Không phụ thuộc cloud
```

### Lý Do
- $300 GCP dùng hết là hết, không nên phụ thuộc
- 2TB Drive có 1 năm, tận dụng để backup
- Local machine đủ khả năng chạy bot + inference
- Tự chủ hoàn toàn sau giai đoạn build

---

## Quyết Định 008: Google Drive Backup System
**Ngày**: 2025-11-30  
**Trạng thái**: ✅ Đã triển khai

### Bối Cảnh
User đã enable Google Drive API. Cần tận dụng 2TB storage để backup dữ liệu, models, và configs.

### Các Lựa Chọn Xem Xét
1. **Manual backup** - Copy thủ công, dễ quên
2. **Google Drive app** - Sync toàn bộ, không kiểm soát
3. **rclone scripts** - Tự động, kiểm soát được, có logging

### Quyết Định
**Chọn: rclone với custom scripts**

### Triển Khai
```
scripts/
├── setup_gdrive.sh      # Setup rclone với Google Drive API
├── backup_to_drive.sh   # Backup lên Drive (full/incremental)
└── restore_from_drive.sh # Restore từ Drive

Google Drive Structure:
trading-backup/
├── user_data/           # Data, models, strategies
├── config/              # docker-compose, Dockerfile, Makefile
└── memory-bank/         # AI context files
```

### Lý Do
- rclone miễn phí, mã nguồn mở
- Hỗ trợ incremental sync (tiết kiệm bandwidth)
- Có logging chi tiết
- Dễ setup cron job cho backup tự động
- Có thể restore selective (chỉ models, chỉ data...)

### Cron Setup
```bash
# Backup hàng ngày lúc 2:00 AM
0 2 * * * /path/to/scripts/backup_to_drive.sh incremental
```

---

## Quyết Định 009: Feature Engineering Approach
**Ngày**: 2025-11-30  
**Trạng thái**: ✅ Đã triển khai

### Bối Cảnh
Phát hiện rằng các features trước đây không hiệu quả cho ML:
- Dùng giá trị tuyệt đối (EMA = 60000) → AI không học được
- Thiếu Volume indicators quan trọng
- Chưa có Chart Pattern recognition

### Các Lựa Chọn Xem Xét
1. **Giữ nguyên** - Dùng indicators thô như cũ
2. **Chuẩn hóa đơn giản** - Min-Max scaling
3. **Feature Engineering đúng cách** - Log Returns, Distances, Slopes

### Quyết Định
**Chọn: Feature Engineering đúng cách**

### Nguyên Tắc
1. **Không dùng giá trị tuyệt đối** → Dùng biến thiên (Delta/Slope/Distance)
2. **Tránh indicators bị lag** → Ưu tiên Oscillators, Volume
3. **Log Returns là VUA** → Chuẩn hóa giá về dao động quanh 0
4. **Stationary features** → RSI, %, độ biến động

### Triển Khai
```python
# SAI: EMA = 60000 (vô nghĩa cho AI)
dataframe['ema_20'] = ta.EMA(close, 20)

# ĐÚNG: Distance to EMA (chuẩn hóa)
ema = ta.EMA(close, 20)
dataframe['%-dist_to_ema_20'] = (close - ema) / ema

# ĐÚNG: Log Returns (VUA của features)
dataframe['%-log_return_1'] = np.log(close / close.shift(1))
```

### Files Tạo Mới
- `feature_engineering.py` - ~50 features đúng chuẩn ML
- `chart_patterns.py` - 11 pattern features

### Lý Do
- Model XGBoost/ML cần features stationary (không có trend)
- Log Returns biến đổi giá dốc đứng thành dao động quanh 0
- Distance/Slope cho biết tương quan, không phải giá trị tuyệt đối
- Volume indicators (OBV, CMF) thường đi trước giá

---

## Quyết Định Đang Chờ

### Quyết Định 010: Điều Chỉnh Ngưỡng Xu Hướng
**Trạng thái**: 🔄 Đang xem xét

Có nên nới lỏng ngưỡng để bắt nhiều lệnh hơn?
- Hiện tại: ADX > 25, BB Width > 0.04
- Tùy chọn: ADX > 20, BB Width > 0.03

### Quyết Định 011: Tích Hợp Model Pretrained
**Trạng thái**: 🔜 Tương lai

Khi nào thêm phân tích sentiment FinBERT?
- Trong giai đoạn BUILD trên GCP (cần GPU)
- Sau đó export model chạy local (CPU mode)
