# AI Trading System - Architecture Documentation

## 1. Overview

Hệ thống AI Trading này sử dụng **Freqtrade** kết hợp **FreqAI** để thực hiện giao dịch tự động trên thị trường Crypto Futures. Hệ thống bao gồm các thành phần chính: Data Layer, Feature Engineering, AI Model Training, Strategy Execution, và Risk Management.

## 2. Enhanced High-Level Architecture

```mermaid
graph TB
    subgraph "External Data Sources"
        Binance[Binance API<br/>OHLCV + Funding Rate]
        NewsAPI[News/Twitter API<br/>Sentiment Data]
        FearGreed[Fear & Greed Index]
    end
    
    subgraph "Docker Container - Enhanced"
        subgraph "Data Pipeline"
            DataDownload[Data Download]
            FundingFetch[Funding Rate Fetcher]
            DataStore[(HDF5 Storage<br/>Fast Access)]
        end
        
        subgraph "Strategy Intelligence"
            Strategy[FreqAIStrategy.py]
            Regime[Market Regime Detector<br/>TREND/SIDEWAY/VOLATILE]
            Indicators[SMC + Volume Indicators]
        end
        
        subgraph "AI Engine - Hybrid"
            FeatureEng[Feature Engineering<br/>200+ → 50 features]
            PretrainedModel[Pretrained Models<br/>FinBERT Sentiment]
            XGBoost[XGBoost Classifier]
            Ensemble[Ensemble Predictor<br/>Weighted Average]
        end
        
        subgraph "Smart Risk Management"
            RegimeFilter[Regime-based Filter]
            DynamicStake[Dynamic Stake Amount<br/>Based on Confidence]
            ATRStoploss[ATR-based Stoploss<br/>Volatility Adaptive]
            DynamicLev[Dynamic Leverage<br/>Risk-adjusted]
        end
        
        subgraph "Execution"
            OrderExec[Order Execution]
        end
    end
    
    subgraph "Monitoring"
        FreqUI[FreqUI Dashboard]
        Alerts[Telegram Alerts]
    end
    
    %% Data Flow
    Binance -->|OHLCV 5m/1h/4h| DataDownload
    Binance -->|Funding Rate| FundingFetch
    NewsAPI -->|Headlines| PretrainedModel
    FearGreed -->|Daily Index| RegimeFilter
    
    DataDownload & FundingFetch -->|Store| DataStore
    DataStore -->|Load| Strategy
    Strategy -->|Detect| Regime
    Strategy -->|Calculate| Indicators
    
    Regime & Indicators -->|Features| FeatureEng
    FeatureEng -->|Train| XGBoost
    PretrainedModel -->|Sentiment| Ensemble
    XGBoost -->|Technical Pred| Ensemble
    
    Ensemble -->|Prediction| RegimeFilter
    RegimeFilter -->|Filter Signals| DynamicStake
    DynamicStake -->|Size Position| ATRStoploss
    ATRStoploss -->|Set SL| DynamicLev
    DynamicLev -->|Final Order| OrderExec
    
    OrderExec -->|Execute| Binance
    Strategy -.->|Visualize| FreqUI
    OrderExec -.->|Notify| Alerts
    
    style Ensemble fill:#ff9,stroke:#333,stroke-width:3px
    style Regime fill:#9f9,stroke:#333,stroke-width:3px
    style DynamicStake fill:#f99,stroke:#333,stroke-width:3px
```

### Key Enhancements:
1. **🎯 Market Regime Detection** - Filters trades based on market condition
2. **💪 Hybrid AI** - Combines XGBoost + Pretrained FinBERT
3. **⚖️ Dynamic Risk** - Stake, Stoploss, and Leverage adapt in real-time
4. **📊 Rich Data** - Funding Rate, Sentiment, Fear & Greed Index

## 3. Data Flow Architecture

### 3.1 Multi-Timeframe Data Pipeline

```mermaid
flowchart LR
    subgraph "Historical Data"
        BTC_5m[BTC/USDT 5m<br/>60 days]
        ETH_5m[ETH/USDT 5m<br/>60 days]
        BTC_1h[BTC/USDT 1h<br/>60 days]
        ETH_1h[ETH/USDT 1h<br/>60 days]
        BTC_4h[BTC/USDT 4h<br/>60 days]
        ETH_4h[ETH/USDT 4h<br/>60 days]
    end
    
    subgraph "Feature Engineering"
        Merge[Merge Timeframes]
        TechInd[Technical Indicators<br/>RSI, BB, MFI, ADX]
        SMC[SMC Indicators<br/>Sonic R, EMA, Moon]
        Corr[BTC Correlation Features]
    end
    
    subgraph "FreqAI Features"
        FeatureMatrix[Feature Matrix<br/>~200+ columns]
    end
    
    BTC_5m & ETH_5m & BTC_1h & ETH_1h & BTC_4h & ETH_4h --> Merge
    Merge --> TechInd
    Merge --> SMC
    Merge --> Corr
    TechInd & SMC & Corr --> FeatureMatrix
    
    style FeatureMatrix fill:#fbb,stroke:#333
```

### 3.2 Feature Engineering Detail

```mermaid
graph TD
    subgraph "Raw OHLCV"
        O[Open]
        H[High]
        L[Low]
        C[Close]
        V[Volume]
    end
    
    subgraph "expand_all<br/>(Multi-TF, Shifted)"
        RSI[RSI 14]
        BB[Bollinger Bands]
        MFI[Money Flow Index]
        ADX[ADX 14]
        Sonic[Sonic R Dragon Lines]
        EMA[EMA 369/630]
        Moon[Moon Phase Features]
        SMC[SMC Distance to High/Low]
    end
    
    subgraph "expand_basic"
        PctChange[% Change]
        RawPrice[Raw Price]
    end
    
    subgraph "standard<br/>(Normalization)"
        Norm[Min-Max Scaling]
    end
    
    subgraph "Target"
        Target["Target: Price in 20 candles<br/>(0 or 1 for up/down)"]
    end
    
    O & H & L & C & V --> RSI & BB & MFI & ADX & Sonic & EMA & Moon & SMC
    RSI & BB & MFI & ADX & Sonic & EMA & Moon & SMC --> PctChange & RawPrice
    PctChange & RawPrice --> Norm
    Norm --> Target
    
    style Target fill:#bfb,stroke:#333
```

**Chi tiết các features:**
- **expand_all**: Mỗi indicator được tính cho 3 timeframes (5m, 1h, 4h) × 3 shifted candles × 2 pairs (BTC, ETH) = ~180 features
- **expand_basic**: Thêm raw values và % change
- **standard**: Chuẩn hóa dữ liệu về khoảng [0, 1]
- **Target**: AI học dự đoán giá sẽ tăng hay giảm sau 20 candles

## 4. FreqAI Training Pipeline

```mermaid
sequenceDiagram
    participant Backtest
    participant FreqAI
    participant DataSplit
    participant XGBoost
    participant Model
    
    Backtest->>FreqAI: Start Training (15 days)
    FreqAI->>DataSplit: Split Train/Test
    Note over DataSplit: Train: 80%<br/>Test: 20%
    DataSplit->>XGBoost: Feed Training Data
    XGBoost->>XGBoost: Build Decision Trees
    Note over XGBoost: 100 trees<br/>max_depth=6<br/>learning_rate=0.1
    XGBoost->>Model: Save Trained Model
    Model->>FreqAI: Return Model
    FreqAI->>Backtest: Generate Predictions
    Note over Backtest: Backtest Period: 7 days
```

**Chu trình Training:**
1. **Rolling Window**: Mỗi 15 ngày, model được train lại
2. **Backtest Period**: Test model trong 7 ngày tiếp theo
3. **Model Storage**: Model được lưu tại `user_data/models/freqai-xgboost/`

## 5. Strategy Execution Flow

```mermaid
stateDiagram-v2
    [*] --> LoadData: New Candle
    LoadData --> CalcIndicators: OHLCV + Multi-TF
    CalcIndicators --> FreqAI: Features Ready
    FreqAI --> Prediction: XGBoost Inference
    
    state Prediction {
        [*] --> CheckPrediction
        CheckPrediction --> BuySignal: Pred > 0.6
        CheckPrediction --> SellSignal: Pred < 0.4
        CheckPrediction --> Hold: 0.4 ≤ Pred ≤ 0.6
    }
    
    BuySignal --> RiskCheck
    SellSignal --> RiskCheck
    Hold --> [*]
    
    state RiskCheck {
        [*] --> CalcLeverage
        CalcLeverage --> CheckPosition
        CheckPosition --> PlaceOrder: OK
        CheckPosition --> Reject: Max Trades Reached
    }
    
    PlaceOrder --> MonitorPosition
    Reject --> [*]
    
    state MonitorPosition {
        [*] --> CheckStoploss
        CheckStoploss --> CloseAtLoss: Price hit SL
        CheckStoploss --> CheckROI
        CheckROI --> CloseAtProfit: ROI target hit
        CheckROI --> CheckExit
        CheckExit --> CloseAtSignal: Exit signal
        CheckExit --> Continue: Still in position
    }
    
    CloseAtLoss --> [*]
    CloseAtProfit --> [*]
    CloseAtSignal --> [*]
    Continue --> [*]
```

## 6. Risk Management & Leverage Calculation

### 6.1 Position Sizing Logic

```mermaid
flowchart TD
    Start[New Trade Signal]
    Start --> Config{Config Values}
    
    Config -->|Stake| S[Stake = 50 USDT]
    Config -->|Stoploss| SL[Stoploss = -5%]
    Config -->|Risk| R[Max Risk = 20%]
    
    S & SL & R --> CalcLev[Calculate Leverage]
    
    CalcLev --> Formula["Leverage = Risk / |Stoploss|<br/>= 0.20 / 0.05 = 4x"]
    
    Formula --> Cap{Cap Check}
    Cap -->|If > 20x| Cap20[Leverage = 20x]
    Cap -->|If ≤ 20x| UseCalc[Use Calculated]
    
    Cap20 & UseCalc --> Final[Final Leverage = 4x]
    
    Final --> Position["Position Size = Stake × Leverage<br/>= 50 × 4 = 200 USDT"]
    
    Position --> Loss["Max Loss at SL<br/>= 200 × 5% = 10 USDT<br/>= 20% of Stake ✓"]
    
    style Formula fill:#bbf,stroke:#333
    style Loss fill:#fbb,stroke:#333
```

### 6.2 Ví dụ thực tế

**Scenario 1: Vào lệnh LONG BTC/USDT**
- **Entry Price**: 40,000 USDT
- **Stake**: 50 USDT (margin)
- **Leverage**: 4x
- **Position Size**: 200 USDT (0.005 BTC)
- **Stoploss**: -5% → 38,000 USDT

**Nếu chạm Stoploss:**
- Loss = (40,000 - 38,000) / 40,000 = 5%
- Loss in USDT = 200 × 5% = **10 USDT**
- % of Margin = 10 / 50 = **20%** ✓

**Scenario 2: Profit tại ROI 5%**
- Exit Price: 42,000 USDT
- Profit = 200 × 5% = **10 USDT**
- % of Margin = 10 / 50 = **20%** profit

## 7. Component Details

### 7.1 File Structure

```
trading/
├── docker-compose.yml          # Docker orchestration
├── Dockerfile                  # Custom image with XGBoost
├── Makefile                    # Shortcuts (make start, make stop)
├── docs/
│   ├── trains/
│   │   └── advanced_ai_architecture.md
│   └── architecture.md         # This file
├── user_data/
│   ├── config.json            # Main configuration
│   ├── data/binance/          # Downloaded OHLCV data
│   ├── models/                # Trained AI models
│   └── strategies/
│       ├── FreqAIStrategy.py  # Main strategy
│       ├── BasicStrategy.py   # Backup strategy
│       └── indicators/
│           └── smc_indicators.py  # Custom indicators
```

### 7.2 Key Configuration Parameters

**config.json highlights:**
```json
{
  "stake_amount": 50,           // 50 USDT per trade
  "trading_mode": "futures",    // Futures trading
  "margin_mode": "isolated",    // Isolated margin
  "max_open_trades": 3,         // Max 3 concurrent positions
  "freqai": {
    "enabled": true,
    "train_period_days": 15,    // Retrain every 15 days
    "backtest_period_days": 7,  // Test on 7 days
    "include_timeframes": ["5m", "1h", "4h"],
    "include_corr_pairlist": ["BTC/USDT"]
  }
}
```

## 8. Monitoring & Visualization

```mermaid
graph LR
    subgraph "FreqUI Dashboard"
        Charts[Price Charts<br/>+ Indicators]
        Trades[Trade History]
        Performance[Performance Metrics]
        Logs[Bot Logs]
    end
    
    subgraph "Plotted Indicators"
        Main[Main Chart:<br/>Sonic R, EMA 369/630, BB]
        Sub1[Subplot: Moon Phase<br/>Illumination & Category]
        Sub2[Subplot: SMC<br/>Distance to High/Low]
    end
    
    Trades --> Charts
    Charts --> Main
    Charts --> Sub1
    Charts --> Sub2
    
    style Main fill:#e1f5e1,stroke:#333
```

**Access FreqUI**: http://127.0.0.1:8080

## 9. Next Steps: Hyperopt

Hyperopt sẽ tối ưu các tham số sau:

1. **Entry/Exit Thresholds**:
   - Ngưỡng dự đoán để vào lệnh (hiện tại: 0.6)
   - Ngưỡng để thoát lệnh (hiện tại: 0.4)

2. **ROI Levels**:
   - Mức profit để tự động chốt lời

3. **Stoploss**:
   - Mức cắt lỗ tối ưu (ảnh hưởng đến leverage)

**Command**:
```bash
docker compose run --rm freqtrade hyperopt \
  --strategy FreqAIStrategy \
  --hyperopt-loss SharpeHyperOptLoss \
  --spaces buy sell roi stoploss \
  --epochs 100
```
