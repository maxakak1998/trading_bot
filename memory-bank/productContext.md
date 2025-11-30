# Ngữ Cảnh Sản Phẩm - Hệ Thống AI Trading

## Cập Nhật Lần Cuối
[2025-11-30 15:00:00] - Cập nhật kiến trúc Local-First + tài nguyên Cloud

## 1. Tổng Quan Dự Án

Hệ thống giao dịch tiền điện tử tự động sử dụng **AI/ML**, được xây dựng trên nền tảng **Freqtrade** kết hợp **FreqAI** để giao dịch tự động trên Binance Futures. Hệ thống kết hợp phân tích kỹ thuật truyền thống với học máy để đưa ra quyết định giao dịch thông minh.

### Triết Lý: LOCAL-FIRST
> **"Build trên Cloud, Run ở Local"**
> - Sử dụng tài nguyên cloud để build & optimize
> - Sau đó chạy hoàn toàn LOCAL, không phụ thuộc cloud

### Tài Nguyên Sẵn Có

| Tài Nguyên | Giá Trị | Thời Hạn | Mục Đích |
|------------|---------|----------|----------|
| Google Cloud | $300 credit | Dùng hết là hết | Build, Train, Optimize |
| Google Drive | 2TB | 1 năm | Backup data, models |
| Local Machine | Sẵn có | Vĩnh viễn | Run bot 24/7 |

## 2. Kiến Trúc Tổng Quan

### Các Thành Phần Chính
```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                         │
├─────────────────────────────────────────────────────────────┤
│  Xử Lý Dữ Liệu    │  Chiến Lược Thông Minh  │  AI Engine   │
│  ─────────────    │  ────────────────────   │  ─────────   │
│  • Tải dữ liệu    │  • FreqAIStrategy.py    │  • XGBoost   │
│  • Funding Rate   │  • Phát hiện xu hướng   │  • 200+ đặc  │
│  • Lưu HDF5       │  • Chỉ báo SMC          │    trưng     │
├─────────────────────────────────────────────────────────────┤
│              Quản Lý Rủi Ro Thông Minh                      │
│  • Lọc xu hướng  • Stake động  • Stoploss theo ATR         │
└─────────────────────────────────────────────────────────────┘
```

### Tính Năng Chính
1. **🎯 Phát Hiện Xu Hướng Thị Trường** - Lọc giao dịch theo TREND/SIDEWAY/VOLATILE
2. **💪 AI Kết Hợp** - XGBoost + FinBERT (phân tích cảm xúc tin tức)
3. **⚖️ Rủi Ro Động** - Stake, Stoploss, Đòn bẩy tự động điều chỉnh
4. **📊 Đa Khung Thời Gian** - Phân tích 5 phút, 1 giờ, 4 giờ

## 3. Công Nghệ Sử Dụng

| Thành Phần | Công Nghệ | Mục Đích |
|------------|-----------|----------|
| Framework | Freqtrade | Engine giao dịch chính |
| AI Engine | FreqAI + XGBoost | Dự đoán bằng ML |
| Sàn | Binance Futures | Nơi giao dịch |
| Container | Docker | Triển khai |
| Lưu trữ | HDF5/Feather | Truy cập dữ liệu nhanh |
| Ngôn ngữ | Python 3.10+ | Phát triển |
| Giám sát | FreqUI + Telegram | Dashboard & cảnh báo |

## 4. Cấu Hình Giao Dịch

- **Số tiền mỗi lệnh**: 50 USDT
- **Chế độ**: Futures (Isolated Margin)
- **Tối đa lệnh mở**: 3 lệnh
- **Đòn bẩy**: Động (tối đa 20x, tính theo Risk/|Stoploss|)
- **Cặp tiền**: BTC/USDT, ETH/USDT

## 5. Luồng Dữ Liệu

```
Binance API → Tải dữ liệu → Lưu HDF5 → Xử lý đặc trưng 
→ XGBoost dự đoán → Lọc xu hướng → Quản lý rủi ro → Đặt lệnh
```

## 6. Cấu Trúc Thư Mục

```
trading/
├── docker-compose.yml          # Cấu hình Docker
├── Dockerfile                  # Image tùy chỉnh với XGBoost
├── Makefile                    # Lệnh tắt
├── docs/
│   ├── architecture.md         # Sơ đồ hệ thống
│   └── trains/
│       └── advanced_ai_architecture.md
├── memory-bank/                # Lưu ngữ cảnh
└── user_data/
    ├── config.json            # Cấu hình chính
    ├── data/binance/          # Dữ liệu OHLCV (.feather)
    ├── models/                # Model AI đã train
    └── strategies/
        ├── FreqAIStrategy.py  # Chiến lược chính
        ├── BasicStrategy.py   # Chiến lược dự phòng
        └── indicators/
            └── smc_indicators.py  # Chỉ báo tùy chỉnh
```
