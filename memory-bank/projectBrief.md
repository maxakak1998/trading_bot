# Tóm Tắt Dự Án - Hệ Thống AI Trading

## Cập Nhật Lần Cuối
[2025-11-30 14:45:00] - Chuyển sang tiếng Việt

## 1. Mục Tiêu Dự Án

### Mục Tiêu Chính
- Xây dựng bot giao dịch tiền điện tử tự động sử dụng AI/ML
- Đạt lợi nhuận ổn định với rủi ro được kiểm soát
- Giảm thiểu tín hiệu sai và tránh giao dịch trong điều kiện thị trường bất lợi

### Chỉ Số Mục Tiêu
| Chỉ Số | Mục Tiêu | Hiện Tại |
|--------|----------|----------|
| Tỷ lệ thắng | 60-70% | ~55% |
| Hệ số lợi nhuận | 2.0+ | Chưa xác định |
| Sharpe Ratio | 1.5+ | Chưa xác định |
| Drawdown tối đa | <15% | ~20%+ |

## 2. Ràng Buộc

### Kỹ Thuật
- Phải chạy được trên VPS giá rẻ ($6-12/tháng)
- Chỉ dùng CPU (không cần GPU)
- Triển khai bằng Docker
- Tương thích Binance Futures API

### Vận Hành
- Uptime mục tiêu 99.9%
- Độ trễ dự đoán <100ms
- Thời gian train model <5 phút
- Cảnh báo qua Telegram

### Quản Lý Rủi Ro
- Lỗ tối đa 20% mỗi lệnh (tính trên stake)
- Tối đa 3 lệnh mở cùng lúc
- Stoploss động theo ATR (-2% đến -15%)
- Kích thước lệnh theo độ tin cậy AI

## 3. Các Bên Liên Quan

- **Developer**: Xây dựng và bảo trì hệ thống
- **Trader**: Vận hành bot, theo dõi hiệu suất
- **Bot**: Tự động thực thi chiến lược giao dịch

## 4. Nguyên Tắc Chính

1. **"Train Local, Trade Cloud"** - Train model ở máy local/Colab, chạy bot trên VPS
2. **Nhận Biết Xu Hướng** - Chỉ giao dịch khi thị trường có xu hướng rõ ràng (TREND)
3. **Rủi Ro Thích Ứng** - Kích thước lệnh và stoploss tự động điều chỉnh theo thị trường
4. **Học Liên Tục** - Retrain model mỗi 15 ngày (rolling window)

## 5. Tiêu Chí Thành Công

### Phase 1 (Hoàn thành) ✅
- [x] Setup Freqtrade cơ bản với Docker
- [x] Tích hợp FreqAI với XGBoost
- [x] Phát hiện xu hướng thị trường (Market Regime)
- [x] Stoploss động (theo ATR)
- [x] Stake động (theo độ tin cậy)

### Phase 2 (Đang thực hiện)
- [ ] Tích hợp Funding Rate
- [ ] Chỉ báo Volume Imbalance
- [ ] Fear & Greed Index

### Phase 3 (Kế hoạch)
- [ ] Tích hợp Model đã train sẵn (FinBERT)
- [ ] Ensemble Model (XGBoost + Sentiment)

## 6. Không Nằm Trong Phạm Vi

- Giao dịch tần suất cao (HFT)
- Giao dịch Spot (chỉ Futures)
- Arbitrage đa sàn
- Chiến lược cần can thiệp thủ công
