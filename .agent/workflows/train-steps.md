---
description: GCP Training/Hyperopt Workflow - Full automation pipeline
---

# GCP Training & Hyperopt Workflow

Complete workflow for running FreqAI hyperopt on GCP VM with auto-backup and auto-shutdown.

## Prerequisites

- GCP VM `trading-bot` exists (create with `make gcp-create` if needed)
- `rclone` configured on VM (run `make gcp-setup-rclone` once)
- Local code is working (test with `make hyperopt HYPEROPT_EPOCHS=1 TRAIN_TIMERANGE=20240101-20240102`)

---

## Phase 1: Prepare & Deploy

### Step 1.1: Commit Local Changes
```bash
# turbo
git add .
git commit -m "Prepare for GCP hyperopt run"
git push
```

### Step 1.2: Start GCP VM
```bash
# turbo
make gcp-start
```
Wait for VM to be RUNNING (~30 seconds).

### Step 1.3: Sync Code to VM
```bash
# turbo
make gcp-sync
```
This will:
- Push local commits to GitHub
- Pull latest code on VM
- Upload `config.json` to VM

---

## Phase 2: Run Hyperopt

### Step 2.1: SSH into VM and Start Hyperopt
```bash
gcloud compute ssh trading-bot --zone=asia-southeast1-b --command="cd /opt/freqtrade && setsid /opt/freqtrade/run_hyperopt_flow.sh 800 20240101-20240701 </dev/null >/opt/freqtrade/flow_debug.log 2>&1 &"
```

Or use the wrapper script if available:
```bash
make gcp-flow-hyperopt HYPEROPT_EPOCHS=800 TRAIN_TIMERANGE=20240101-20240701
```

> **Note:** VM will auto-shutdown when hyperopt completes.

### Step 2.2: Monitor Progress
```bash
# Check if running
# turbo
make gcp-status

# View hyperopt logs
make gcp-logs
```

---

## Phase 3: Evaluate Results

### Step 3.1: Check VM Status
```bash
# turbo
gcloud compute instances describe trading-bot --zone=asia-southeast1-b --format='get(status)'
```
- `TERMINATED` = Hyperopt finished
- `RUNNING` = Still processing

### Step 3.2: Start VM to View Results (if TERMINATED)
```bash
# turbo
make gcp-start
```

### Step 3.3: View Hyperopt Results
```bash
gcloud compute ssh trading-bot --zone=asia-southeast1-b --command="cd /opt/freqtrade && sudo docker run --rm -v \$(pwd)/user_data:/freqtrade/user_data freqtrade-custom:latest hyperopt-show --best -n 5"
```

### Step 3.4: Download Results to Local
```bash
make gcp-download
```

### Step 3.5: Check Google Drive Backup
Results are automatically backed up to:
- `gdrive:freqtrade-backup/models/freqai-xgboost/`
- `gdrive:freqtrade-backup/strategies/FreqAIStrategy.json`
- `gdrive:freqtrade-backup/hyperopt.log`

---

## Phase 4: Evaluate Success Criteria

### ✅ Success Criteria (ALL must pass)

| Metric | Target | How to Check |
|--------|--------|--------------|
| Win Rate | ≥ 65% | `Win%` column in hyperopt result |
| Long/Short Alignment | Long > Short in Bull, Short > Long in Bear | `Long / Short trades` and `Long / Short profit %` |
| Total Profit | > 0% | `Total profit %` |
| Drawdown | < 10% | `Max Drawdown (Acct)` |
| Profit Factor | > 1.0 | `Profit factor` |
| Sortino | > 0 | `Sortino` |

### Example Good Result:
```
Win Rate:       68%
Long/Short:     45 / 12 (Bull market, 2024-01 to 2024-07)
Total Profit:   +15.3%
Drawdown:       6.2%
Profit Factor:  1.85
```

### Example Bad Result:
```
Win Rate:       48%           ❌ Below 65%
Long/Short:     12 / 45       ❌ More shorts in bull market
Total Profit:   -8.2%         ❌ Losing money
Drawdown:       15.3%         ❌ Above 10%
```

---

## Phase 5: Iteration Loop (If Criteria Not Met)

### Step 5.1: Analyze Failure
1. Check which criteria failed
2. Common issues:
   - **Low Win Rate**: Entry thresholds too loose
   - **Wrong Long/Short ratio**: Trend filter not working
   - **High Drawdown**: Stoploss too wide or trailing stop not effective
   - **Low Profit Factor**: ROI targets not optimal

### Step 5.2: Refine Code Locally
Edit files as needed:
- `FreqAIStrategy.py` - Entry/exit logic
- `FreqAIStrategy.json` - Hyperopt parameters
- `config.json` - Feature flags

### Step 5.3: Local Quick Test
```bash
# turbo
make hyperopt HYPEROPT_EPOCHS=1 TRAIN_TIMERANGE=20240101-20240102
```
Verify no errors before deploying to GCP.

### Step 5.4: Repeat from Phase 1
Go back to Step 1.1 and run the full pipeline again.

---

## Phase 6: Apply & Validate (If Criteria Met ✅)

### Step 6.1: Apply Best Params to Strategy
Hyperopt exports best params to `FreqAIStrategy.json` automatically.
Verify the file has been updated:
```bash
cat user_data/strategies/FreqAIStrategy.json
```

### Step 6.2: Out-of-Sample Backtest
Test on data **NOT used in hyperopt** to check for overfitting:
```bash
# If hyperopt used Jan-Jun 2024, test on Jul-Sep 2024
make backtest BACKTEST_TIMERANGE=20240701-20241001
```

### Step 6.3: Validate Out-of-Sample Results
Compare hyperopt results vs out-of-sample backtest:

| Metric | Hyperopt (In-Sample) | Backtest (Out-of-Sample) | Status |
|--------|---------------------|--------------------------|--------|
| Win Rate | 68% | 62%+ | ✅ OK if within 10% |
| Profit | +15% | +5%+ | ✅ OK if still positive |
| Drawdown | 6% | <15% | ✅ OK if reasonable |

**Red Flags (Overfitting):**
- Win rate drops >20% → Parameters too fitted to training data
- Profit becomes negative → Overfitting confirmed
- Completely different behavior → Need more diverse training data

### Step 6.4: Log Experiment
```bash
make experiment-log NAME="v1.0_passed" NOTES="Passed OOS backtest"
```

---

## Phase 7: Deploy to Production

### Step 7.1: Dry-Run Test (Paper Trading)
Test with real market data, but no real money:
```bash
make trade-dry
```
Run for at least **24-48 hours** to observe behavior.

### Step 7.2: Monitor Dry-Run
Check trades being made:
```bash
make logs
```

Look for:
- ✅ Entering trades as expected
- ✅ Respecting stoploss/ROI
- ✅ Long/Short ratio matches market condition
- ❌ Excessive trades = overtrading
- ❌ No trades = entry conditions too strict

### Step 7.3: Review Dry-Run Performance
After 24-48 hours:
```bash
# View trade history
$(DOCKER_COMPOSE) run --rm freqtrade show-trades --db-url sqlite:///user_data/tradesv3.dryrun.sqlite
```

### Step 7.4: Live Trading (Real Money)
⚠️ **Only after successful dry-run!**

1. Configure exchange API keys in `config.json`
2. Set `dry_run: false`
3. Start with **small stake amount** (e.g., $100)

```bash
make start
```

### Step 7.5: Ongoing Monitoring
- Check trades daily
- Watch for market regime changes
- Re-run hyperopt monthly or when performance degrades

---

## Quick Reference Commands

| Action | Command |
|--------|---------|
| Start VM | `make gcp-start` |
| Stop VM | `make gcp-stop` |
| Sync code | `make gcp-sync` |
| Check status | `make gcp-status` |
| View logs | `make gcp-logs` |
| Download results | `make gcp-download` |
| Backup to Drive | `make gcp-backup` |

---

## 🔬 Experiment Automation Tools

### 1. Experiment Tracker
Log and compare hyperopt runs:
```bash
# Log current result
make experiment-log NAME="baseline_v1" NOTES="First run with SMC"

# Compare last 15 experiments
make experiment-compare
```

### 2. Feature Ablation
Test impact of individual features:
```bash
# List all features
make features-list

# Toggle single feature
make features-toggle FEATURE=vsa

# Run full ablation study
make features-ablation
```

### 3. Grid Search
Run pre-defined test configurations:
```bash
# List available tests
make grid-list

# Run locally (for quick tests)
make grid-run-local TEST="Quick Sanity"

# Run on GCP (for full tests)
make grid-run-gcp TEST="SMC Optimal"

# Apply feature set to config
make grid-apply-features SET=smc_focus
```

### Available Grid Tests:
| Test | Timerange | Epochs | Est. Time |
|------|-----------|--------|-----------|
| Quick Sanity | Q1 2024 | 100 | 15 min |
| SMC Optimal | H1 2024 | 500 | 1-2 hours |
| Full Production | 2023 | 800 | 3-4 hours |

### Available Feature Sets:
| Set | Description |
|-----|-------------|
| `minimal` | Core indicators only |
| `smc_focus` | SMC + VSA + Filters |
| `full_features` | Everything enabled |

---

## Cost Management

- **Spot VM (n2-standard-32)**: ~$0.32/hour
- **Disk (100GB)**: ~$4/month
- **Always stop/delete VM when not in use!**

```bash
# Stop VM (keep data, stop compute charges)
make gcp-stop

# Delete VM (stop ALL charges, lose data if not backed up)
make gcp-delete
```