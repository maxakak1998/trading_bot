# 🚀 $300 GCP Optimization Pipeline - Implementation Plan

**Created:** 2025-11-30
**Budget:** $300 Google Cloud Credit
**Goal:** Optimize FreqAI trading strategy through systematic model comparison and hyperopt

---

## 📋 Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       $300 GCP PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PHASE 1: Local Testing (Mac M4)                                       │
│  ├── Test LightGBM config                                               │
│  ├── Test CatBoost config                                               │
│  └── Compare baseline performance                                       │
│                                                                         │
│  PHASE 2: GCP Setup                                                     │
│  ├── Create GCP project                                                 │
│  ├── Setup Spot VM scripts                                              │
│  └── Prepare Docker deployment                                          │
│                                                                         │
│  PHASE 3: Cloud Optimization                                            │
│  ├── Massive Hyperopt (5000 epochs)                                     │
│  ├── Model Tournament (XGBoost vs LightGBM vs CatBoost)                │
│  └── Stress Test (4 years data)                                         │
│                                                                         │
│  PHASE 4: Production                                                    │
│  └── Deploy best model to e2-small VPS                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 💰 Budget Allocation (Optimized)

| Phase | VM Type | Rate (Spot) | Duration | Est. Cost |
|-------|---------|-------------|----------|-----------|
| Hyperopt | c2-standard-60 | $0.75/hr | 6 hrs | **$45** |
| Model Tournament | c2-standard-16 x3 | $0.20/hr | 4 hrs | **$24** |
| Stress Test 4yr | e2-highmem-8 | $0.10/hr | 3 hrs | **$3** |
| Live VPS (5 months) | e2-small | $0.02/hr | 3600 hrs | **$72** |
| Data Transfer | - | - | - | **$10** |
| **Buffer** | - | - | - | **$46** |
| **TOTAL** | | | | **$200** |

> 💡 **Note:** Using Spot VMs saves 60-80% vs standard pricing!

---

## 🔧 PHASE 1: Local Testing (Mac M4)

### Step 1.1: Create Alternative Model Configs

```bash
# Run this to create configs for different models
make create-model-configs
```

**Files created:**
- `user_data/configs/config-xgboost.json` (baseline)
- `user_data/configs/config-lightgbm.json`
- `user_data/configs/config-catboost.json`

### Step 1.2: Test Each Model

```bash
# Test LightGBM (recommended to try first - usually faster)
make test-lightgbm

# Test CatBoost
make test-catboost
```

### Step 1.3: Model Config Comparison (Upgraded for Mac M4 24GB)

| Parameter | XGBoost | LightGBM | CatBoost |
|-----------|---------|----------|----------|
| n_estimators/iterations | 1000 | 1000 | 1000 |
| max_depth | 8 | 10 | 8 |
| learning_rate | 0.03 | 0.03 | 0.03 |
| num_leaves | - | 128 | - |
| regularization | reg_alpha=0.2, reg_lambda=1.5 | reg_alpha=0.2, reg_lambda=1.5 | l2_leaf_reg=5.0 |
| early_stopping | 100 | 100 | 100 |
| shifted_candles | 3 | 3 | 3 |
| indicator_periods | [10,14,20,50] | [10,14,20,50] | [10,14,20,50] |

### Step 1.4: Quick Backtest Comparison

```bash
# After training each model, run backtest
make backtest
# Compare results in user_data/backtest_results/
```

### Expected Outcomes (Phase 1):
- [ ] LightGBM training time vs XGBoost
- [ ] CatBoost training time vs XGBoost
- [ ] Initial performance comparison
- [ ] Decide which models to scale on Cloud

---

## 🌐 PHASE 2: GCP Setup

### Step 2.1: Create GCP Project

```bash
# Install gcloud CLI (if not installed)
brew install google-cloud-sdk

# Login and create project
gcloud auth login
gcloud projects create freqtrade-trading --name="FreqTrade Trading Bot"
gcloud config set project freqtrade-trading

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable container.googleapis.com
```

### Step 2.2: Create Firewall Rules

```bash
gcloud compute firewall-rules create allow-freqtrade-api \
  --allow tcp:8080 \
  --source-ranges 0.0.0.0/0 \
  --description "Allow FreqTrade API access"
```

### Step 2.3: Create Spot VM Script

Run: `make gcp-setup` which will create all necessary scripts.

---

## ⚡ PHASE 3: Cloud Optimization

### 3.1: Massive Hyperopt (c2-standard-60)

```bash
# SSH into VM
gcloud compute ssh freqtrade-hyperopt --zone=us-central1-a

# Run hyperopt with 5000 epochs
docker run --rm -v $(pwd)/user_data:/freqtrade/user_data \
  freqtradeorg/freqtrade:develop_freqai hyperopt \
  --strategy FreqAIStrategy \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --spaces buy sell roi stoploss \
  --epochs 5000 \
  --random-state 42 \
  -j 60  # Use all 60 CPUs
```

**Hyperopt Parameters to Optimize:**
- `label_period_candles`: [10, 15, 20, 30, 50]
- `indicator_periods_candles`: Various combinations
- ROI table
- Stoploss values
- Feature parameters

### 3.2: Model Tournament (Parallel VMs)

```bash
# Launch 3 VMs in parallel
make gcp-model-tournament

# Each VM runs:
# VM1: XGBoost with best hyperopt params
# VM2: LightGBM with best hyperopt params  
# VM3: CatBoost with best hyperopt params

# Collect results
make gcp-collect-results
```

### 3.3: Stress Test with 4 Years Data

```bash
# Download extended data
docker run --rm -v $(pwd)/user_data:/freqtrade/user_data \
  freqtradeorg/freqtrade:develop_freqai download-data \
  --exchange binance \
  --pairs BTC/USDT ETH/USDT \
  --timeframes 5m 15m 1h 4h \
  --timerange 20201130-20241130

# Run backtest on full 4 years
docker run --rm -v $(pwd)/user_data:/freqtrade/user_data \
  freqtradeorg/freqtrade:develop_freqai backtesting \
  --strategy FreqAIStrategy \
  --timerange 20201130-20241130 \
  --freqaimodel XGBoostRegressor
```

---

## 🚀 PHASE 4: Production Deployment

### Step 4.1: Create Production VM

```bash
gcloud compute instances create freqtrade-live \
  --zone=us-central1-a \
  --machine-type=e2-small \
  --boot-disk-size=30GB \
  --image-family=debian-11 \
  --image-project=debian-cloud \
  --tags=freqtrade-server
```

### Step 4.2: Deploy Best Model

```bash
# Copy trained model and config to production
gcloud compute scp --recurse user_data/models/best-model freqtrade-live:~/freqtrade/user_data/models/
gcloud compute scp user_data/configs/production.json freqtrade-live:~/freqtrade/user_data/

# SSH and start bot
gcloud compute ssh freqtrade-live
docker compose up -d
```

### Step 4.3: Setup Monitoring

```bash
# Enable Telegram notifications
# Update config with Telegram bot token
# Enable API server for remote monitoring
```

---

## 📁 File Structure

```
trading/
├── scripts/
│   ├── gcp/
│   │   ├── setup-project.sh      # GCP project setup
│   │   ├── create-hyperopt-vm.sh # Spot VM for hyperopt
│   │   ├── create-tournament.sh  # 3 VMs for model comparison
│   │   ├── create-live-vm.sh     # Production VM
│   │   ├── deploy.sh             # Deploy to VM
│   │   └── teardown.sh           # Cleanup all resources
│   └── local/
│       ├── test-models.sh        # Local model testing
│       └── compare-results.sh    # Compare backtest results
├── user_data/
│   └── configs/
│       ├── config-xgboost.json
│       ├── config-lightgbm.json
│       ├── config-catboost.json
│       └── config-hyperopt.json
└── docs/
    └── gcp-pipeline-plan.md      # This file
```

---

## ✅ Checklist

### Phase 1: Local Testing
- [x] Create LightGBM config ✅ (2025-11-30)
- [x] Create CatBoost config ✅ (2025-11-30)
- [x] XGBoost 5-month test: 53.1% win, +1.51% profit ✅
- [ ] XGBoost 1-year training 🔄 IN PROGRESS
- [ ] Test LightGBM on Mac
- [ ] Test CatBoost on Mac
- [ ] Compare initial results

### Phase 2: GCP Setup
- [ ] Create GCP project
- [ ] Enable billing with $300 credit
- [ ] Create firewall rules
- [x] Create setup scripts ✅ (2025-11-30)

### Phase 3: Cloud Optimization
- [ ] Run hyperopt (5000 epochs)
- [ ] Run model tournament
- [ ] Run 4-year stress test
- [ ] Analyze and select best model

### Phase 4: Production
- [ ] Create production VM
- [ ] Deploy best model
- [ ] Setup monitoring
- [ ] Enable live trading

---

## 🎯 Success Criteria

| Metric | Target | Current (5-month) | Status |
|--------|--------|-------------------|--------|
| Win Rate | > 50% | **53.1%** | ✅ |
| Total Profit | > 5% | **+1.51%** | 🔄 |
| Max Drawdown | < 10% | **2.42%** | ✅ |
| Sharpe Ratio | > 1.0 | 0.52 | 🔄 |
| Sortino Ratio | > 1.0 | **1.08** | ✅ |
| Profit Factor | > 1.2 | **1.36** | ✅ |

## 📊 Training Progress Log

| Date | Config | Timerange | Result |
|------|--------|-----------|--------|
| 2025-11-30 | n_est=500, depth=6 | 5 months | 53.1% win, +1.51% |
| 2025-11-30 | n_est=1000, depth=8 | 1 year | 🔄 RUNNING |

---

## ⚠️ Risk Management

1. **Spot VM Interruption**: Save checkpoints frequently, use `--continue` flag
2. **Budget Overrun**: Set billing alerts at $50, $100, $200
3. **Data Loss**: Backup to Google Drive before teardown
4. **Overfitting**: Use walk-forward validation, test on unseen data

---

## 📞 Quick Commands Reference

```bash
# Local Testing
make test-lightgbm        # Test LightGBM locally
make test-catboost        # Test CatBoost locally
make compare-models       # Compare all model results

# GCP Operations
make gcp-setup           # Setup GCP project
make gcp-hyperopt        # Launch hyperopt VM
make gcp-tournament      # Launch model tournament
make gcp-teardown        # Delete all VMs (save money!)

# Production
make gcp-deploy          # Deploy to production
make gcp-status          # Check VM status
make gcp-logs            # View bot logs
```

---

**Next Step:** Run `make create-model-configs` to create LightGBM and CatBoost configurations for local testing.
