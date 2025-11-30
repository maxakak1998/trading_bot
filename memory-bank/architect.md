# Tài Liệu Kiến Trúc - Hệ Thống AI Trading

## Cập Nhật Lần Cuối
[2025-11-30 15:00:00] - Cập nhật kiến trúc Local-First + GCP/Drive

---

## 1. Tổng Quan Kiến Trúc Hệ Thống

### 1.1 Triết Lý: LOCAL-FIRST
> **"Build trên Cloud, Run ở Local"**
> - Dùng $300 GCP credit để build & optimize (1-2 tháng)
> - Dùng 2TB Google Drive (1 năm) để backup
> - Sau đó chạy hoàn toàn LOCAL, không phụ thuộc cloud

### 1.2 Tài Nguyên Sẵn Có

| Tài Nguyên | Giá Trị | Thời Hạn | Mục Đích |
|------------|---------|----------|----------|
| Google Cloud | $300 credit | Hết là hết | Build, Train, Optimize |
| Google Drive | 2TB | 1 năm | Backup data, models |
| Local Machine | Sẵn có | Vĩnh viễn | Run bot 24/7 |

### 1.3 Sơ Đồ Kiến Trúc Tổng Thể

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KIẾN TRÚC LOCAL-FIRST                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  GIAI ĐOẠN BUILD (1-2 tháng) - Dùng $300 GCP Credit                   ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                        ║  │
│  ║  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ║  │
│  ║  │ GCP Compute     │    │ Hyperopt        │    │ Train FinBERT   │    ║  │
│  ║  │ Engine (GPU)    │───→│ 1000+ epochs    │───→│ Sentiment Model │    ║  │
│  ║  │ ~$50-100        │    │ ~$50-100        │    │ ~$50-100        │    ║  │
│  ║  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘    ║  │
│  ║           │                      │                      │             ║  │
│  ║           └──────────────────────┼──────────────────────┘             ║  │
│  ║                                  ▼                                    ║  │
│  ║                    ┌─────────────────────────┐                        ║  │
│  ║                    │  Optimized Models       │                        ║  │
│  ║                    │  + Best Parameters      │                        ║  │
│  ║                    └────────────┬────────────┘                        ║  │
│  ║                                 │                                     ║  │
│  ╚═════════════════════════════════╪═════════════════════════════════════╝  │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  GOOGLE DRIVE 2TB (1 năm) - Backup & Sync                             ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   ║  │
│  ║  │ Data OHLCV  │  │ Models      │  │ Backtest    │  │ Config      │   ║  │
│  ║  │ 5 năm       │  │ Checkpoints │  │ Results     │  │ Versions    │   ║  │
│  ║  │ ~20GB       │  │ ~5GB        │  │ ~2GB        │  │ ~100MB      │   ║  │
│  ║  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   ║  │
│  ║         │                │                │                │          ║  │
│  ║         └────────────────┼────────────────┼────────────────┘          ║  │
│  ║                          │   rclone sync  │                           ║  │
│  ╚══════════════════════════╪════════════════╪═══════════════════════════╝  │
│                             │                │                              │
│                             ▼                ▼                              │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  LOCAL MACHINE (Vĩnh viễn) - Production 24/7                          ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                        ║  │
│  ║  ┌─────────────────────────────────────────────────────────────────┐  ║  │
│  ║  │                     Docker Container                             │  ║  │
│  ║  ├─────────────────────────────────────────────────────────────────┤  ║  │
│  ║  │  ┌────────────┐  ┌────────────────┐  ┌─────────────────────┐   │  ║  │
│  ║  │  │ Data Layer │  │ Strategy Layer │  │ AI Engine           │   │  ║  │
│  ║  │  ├────────────┤  ├────────────────┤  ├─────────────────────┤   │  ║  │
│  ║  │  │ • OHLCV    │  │ • FreqAI       │  │ • XGBoost (opt)     │   │  ║  │
│  ║  │  │ • Funding  │  │ • Regime Det.  │  │ • FinBERT (opt)     │   │  ║  │
│  ║  │  │ • F&G API  │  │ • SMC Indic.   │  │ • Ensemble          │   │  ║  │
│  ║  │  └────────────┘  └────────────────┘  └─────────────────────┘   │  ║  │
│  ║  │                          │                                      │  ║  │
│  ║  │                          ▼                                      │  ║  │
│  ║  │  ┌─────────────────────────────────────────────────────────┐   │  ║  │
│  ║  │  │              Risk Management                             │   │  ║  │
│  ║  │  │  • Regime Filter  • ATR Stoploss  • Dynamic Stake       │   │  ║  │
│  ║  │  └─────────────────────────┬───────────────────────────────┘   │  ║  │
│  ║  │                            ▼                                    │  ║  │
│  ║  │  ┌─────────────────────────────────────────────────────────┐   │  ║  │
│  ║  │  │              Order Execution → Binance                   │   │  ║  │
│  ║  │  └─────────────────────────────────────────────────────────┘   │  ║  │
│  ║  └─────────────────────────────────────────────────────────────────┘  ║  │
│  ║                                                                        ║  │
│  ║  Yêu cầu: CPU i5+ | RAM 8GB+ | Storage 50GB | Internet ổn định        ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Chi Tiết Từng Giai Đoạn

### 2.1 Giai Đoạn BUILD (Google Cloud $300)

**Timeline**: 1-2 tháng  
**Mục tiêu**: Tạo ra sản phẩm tối ưu chạy được ở local

| Nhiệm Vụ | Chi Phí | Thời Gian | Output |
|----------|---------|-----------|--------|
| Tải 5 năm data OHLCV | ~$10-20 | 1-2 ngày | Dataset đầy đủ |
| Hyperopt 1000+ epochs | ~$50-100 | 3-5 ngày | Best params |
| Train FinBERT Sentiment | ~$50-100 | 2-3 ngày | Sentiment model |
| Train Ensemble Model | ~$30-50 | 1-2 ngày | Final model |
| Paper Trading Test | ~$20-30 | 1-2 tuần | Xác minh |
| **Tổng** | **~$200-300** | **~1 tháng** | **Sản phẩm hoàn chỉnh** |

### 2.2 Google Drive 2TB (1 năm)

**Mục đích**: Backup & Sync - An toàn dữ liệu

```
Google Drive Structure:
trading-backup/
├── data/                    # ~20GB
│   ├── ohlcv/              # 5 năm data BTC/ETH
│   └── external/           # Fear & Greed, News
├── models/                  # ~5GB
│   ├── xgboost/            # XGBoost checkpoints
│   ├── finbert/            # Sentiment model
│   └── ensemble/           # Combined model
├── backtest_results/        # ~2GB
│   ├── hyperopt/           # Optimization results
│   └── reports/            # Performance reports
└── config/                  # ~100MB
    ├── config.json         # Các version config
    └── strategies/         # Strategy versions
```

**Sync Script** (chạy hàng ngày):
```bash
# rclone sync local → drive
rclone sync ./user_data gdrive:trading-backup --progress
```

### 2.3 Local Machine (Vĩnh viễn)

**Yêu cầu tối thiểu**:
| Thành phần | Tối thiểu | Khuyến nghị |
|------------|-----------|-------------|
| CPU | Intel i5 / Ryzen 5 | i7 / Ryzen 7 |
| RAM | 8 GB | 16 GB |
| Storage | 50 GB SSD | 100 GB SSD |
| OS | macOS / Linux / Windows | Linux preferred |
| Internet | Ổn định | Fiber recommended |

**Cấu hình Docker**:
```yaml
# docker-compose.yml (Production)
services:
  freqtrade:
    image: freqtradeorg/freqtrade:develop
    container_name: freqtrade-prod
    volumes:
      - ./user_data:/freqtrade/user_data
    ports:
      - "8080:8080"
    environment:
      - TZ=Asia/Ho_Chi_Minh
    restart: unless-stopped  # Tự khởi động lại
    command: trade --strategy FreqAIStrategy
```

---

## 3. Luồng Dữ Liệu Chi Tiết

### 3.1 Pipeline Đa Khung Thời Gian

```
Nguồn Dữ Liệu              Xử Lý Đặc Trưng           FreqAI
─────────────────          ──────────────────        ─────────
BTC/USDT 5m  ─┐            ┌─ Chỉ báo kỹ thuật      Ma Trận Đặc Trưng
BTC/USDT 1h  ─┼─ Gộp ─────→├─ Chỉ báo SMC       ─→  (~200 cột)
BTC/USDT 4h  ─┤            ├─ Tương quan BTC
ETH/USDT 5m  ─┤            ├─ Funding Rate (mới)
ETH/USDT 1h  ─┤            └─ Fear & Greed (mới)
ETH/USDT 4h  ─┘
```

### 3.2 Chi Tiết Xử Lý Đặc Trưng

| Loại | Đặc Trưng | Mở Rộng |
|------|-----------|---------|
| Kỹ thuật | RSI, BB, MFI, ADX, ATR | 3 TF × 3 shifts × 2 pairs |
| SMC | Sonic R, EMA 369/630, Moon | 3 TF × 2 pairs |
| Giá | OHLCV, % Thay đổi | Thô + chuẩn hóa |
| Tương quan | Đặc trưng giá BTC | Cho giao dịch altcoin |
| **Mới** | Funding Rate | Phát hiện FOMO/FUD |
| **Mới** | Fear & Greed Index | Sentiment thị trường |

---

## 4. Kiến Trúc Model AI

### 4.1 Hiện Tại: XGBoost Classifier

```
Pipeline Training (trên GCP):
────────────────────────────
Ma Trận Đặc Trưng (200+) 
    │
    ▼
Hyperopt (1000+ epochs)
├── Tìm best: n_estimators
├── Tìm best: max_depth
├── Tìm best: learning_rate
    │
    ▼
XGBoost Optimized
    │
    ▼
Export → Local (.joblib)
```

### 4.2 Mục Tiêu: Ensemble Model

```
┌──────────────────┐     ┌──────────────────┐
│ XGBoost          │     │ FinBERT          │
│ (Kỹ thuật)       │     │ (Sentiment)      │
│ Train: GCP       │     │ Train: GCP GPU   │
└────────┬─────────┘     └────────┬─────────┘
         │   trọng số 0.7         │ trọng số 0.3
         └───────────┬────────────┘
                     ▼
              Ensemble Model
              (Chạy local CPU)
```

---

## 5. Luồng Thực Thi Chiến Lược

```
Máy Trạng Thái (Local):
───────────────────────

[Nến Mới] 
    │
    ▼
[Tải Dữ Liệu] ─→ OHLCV + Funding + F&G
    │
    ▼
[Tính Chỉ Báo]
    │
    ▼
[FreqAI Inference] ─→ Ensemble (XGBoost + Sentiment)
    │
    ├─ Pred > 0.6 ─→ [Tín Hiệu MUA]
    ├─ Pred < 0.4 ─→ [Tín Hiệu BÁN]
    └─ 0.4-0.6 ───→ [GIỮ]
    │
    ▼
[Kiểm Tra Regime]
    │
    ├─ TREND ────→ [Kiểm Tra Rủi Ro] ─→ [Đặt Lệnh]
    └─ SIDEWAY/VOLATILE ─→ [Bỏ Qua]
```

---

## 6. Quản Lý Rủi Ro

### 6.1 Kích Thước Vị Thế

```
Đầu vào:
├── Stake: 50 USDT (cơ bản)
├── Stoploss: -5% (động theo ATR)
├── Rủi ro tối đa: 20% của stake
└── Độ tin cậy AI: 0-1

Tính toán:
─────────
Đòn bẩy = Rủi ro / |Stoploss| = 0.20 / 0.05 = 4x
Vị thế = Stake × Đòn bẩy = 50 × 4 = 200 USDT
Lỗ tối đa = Vị thế × |SL| = 200 × 5% = 10 USDT = 20% Stake ✓
```

### 6.2 Điều Chỉnh Động

| Yếu Tố | Thấp | Trung Bình | Cao |
|--------|------|------------|-----|
| ATR (Biến động) | SL: -2% | SL: -5% | SL: -10% |
| Độ tin cậy AI | Stake: 25 | Stake: 50 | Stake: 60 |
| Regime thị trường | Bỏ qua | Bỏ qua | Giao dịch |

---

## 7. Cấu Trúc Thư Mục

```
trading/
├── docker-compose.yml          # Docker config
├── Dockerfile                  # Custom image
├── Makefile                    # Lệnh tắt
├── scripts/
│   ├── backup_to_drive.sh     # Sync → Google Drive
│   └── restore_from_drive.sh  # Restore từ Drive
├── docs/
│   └── architecture.md
├── memory-bank/                # Context AI
└── user_data/
    ├── config.json            # Config chính
    ├── data/binance/          # OHLCV data
    ├── models/                # Models đã optimize
    │   ├── xgboost/
    │   ├── finbert/
    │   └── ensemble/
    └── strategies/
        ├── FreqAIStrategy.py
        └── indicators/
            └── smc_indicators.py
```

---

## 8. Giám Sát & Cảnh Báo

### 8.1 FreqUI Dashboard (Local)
- **URL**: http://localhost:8080
- **Tính năng**: Biểu đồ, lịch sử, hiệu suất, log

### 8.2 Telegram Integration
- Thông báo giao dịch real-time
- Tóm tắt hiệu suất hàng ngày
- Cảnh báo lỗi

### 8.3 Backup Tự Động
```bash
# Cron job backup hàng ngày (0:00)
0 0 * * * /path/to/scripts/backup_to_drive.sh
```

---

## 9. Timeline Triển Khai

```
Tháng 1 (Tuần 1-4): BUILD PHASE - Dùng $300 GCP
├── Tuần 1: Setup GCP, tải 5 năm data
├── Tuần 2: Hyperopt XGBoost (1000+ epochs)
├── Tuần 3: Train FinBERT, build Ensemble
└── Tuần 4: Paper trading, validate

Tháng 2+: RUN PHASE - Local vĩnh viễn
├── Deploy Docker local
├── Chạy bot 24/7
├── Backup tự động → Google Drive
└── Retrain mỗi 15 ngày (local)
```

---

## 10. Cân Nhắc Hiệu Suất

### 10.1 Ngân Sách Độ Trễ (Local)
| Thao Tác | Mục Tiêu | Ghi Chú |
|----------|----------|---------|
| Fetch dữ liệu | <500ms | Cache local |
| Tính đặc trưng | <100ms | Vectorized |
| XGBoost inference | <50ms | Đã optimize |
| FinBERT inference | <200ms | CPU mode |
| Thực thi lệnh | <200ms | Phụ thuộc sàn |
| **Tổng** | **<1s** | Mỗi nến |

### 10.2 Tài Nguyên Local
| Tài Nguyên | Tối Thiểu | Khuyến Nghị |
|------------|-----------|-------------|
| CPU | i5 / Ryzen 5 | i7 / Ryzen 7 |
| RAM | 8 GB | 16 GB |
| Storage | 50 GB | 100 GB |
| Internet | Ổn định | Fiber |
