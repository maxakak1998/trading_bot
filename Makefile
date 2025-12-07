# Makefile for Freqtrade

# ===========================================
# CONFIGURATION - Sửa ở đây để áp dụng cho tất cả commands
# ===========================================

# Strategy & Model
STRATEGY := FreqAIStrategy
FREQAI_MODEL := XGBoostRegressor

TRAIN_TIMERANGE := 20240101-20240401
BACKTEST_TIMERANGE := 20240101-20240701

# Hyperopt settings - Optimized for Win Rate
HYPEROPT_EPOCHS ?= 100
HYPEROPT_LOSS ?= WinRatioHyperOptLoss
HYPEROPT_SPACES := buy sell roi
RANDOM_STATE := 42

# GCP settings
GCP_ZONE := us-central1-a
GCP_PROJECT := $(shell gcloud config get-value project 2>/dev/null)

# Docker
DOCKER_COMPOSE := docker compose
DOCKER_IMAGE ?= freqtradeorg/freqtrade:develop_freqai

# Trading pairs and mode for data download
PAIRS := BTC/USDT:USDT ETH/USDT:USDT
TRADING_MODE := futures
TIME_FRAMES := 5m 15m 1h 4h
TIME_RANGE := 20230801-20251201

.PHONY: help start stop restart logs update trade-dry create-userdir list-strategies train backtest hyperopt backup

help: ## Show this help message
	@echo 'Usage:'
	@echo '  make [target]'
	@echo ''
	@echo 'Configuration (edit in Makefile):'
	@echo '  STRATEGY:          $(STRATEGY)'
	@echo '  FREQAI_MODEL:      $(FREQAI_MODEL)'
	@echo '  TRAIN_TIMERANGE:   $(TRAIN_TIMERANGE)'
	@echo '  BACKTEST_TIMERANGE:$(BACKTEST_TIMERANGE)'
	@echo '  HYPEROPT_EPOCHS:   $(HYPEROPT_EPOCHS)'
	@echo '  HYPEROPT_LOSS:     $(HYPEROPT_LOSS)'
	@echo '  HYPEROPT_SPACES:   $(HYPEROPT_SPACES)'
	@echo ''
	@echo 'Override at runtime: make train TRAIN_TIMERANGE=20231201-20241101'
	@echo ''
	@echo 'Targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

start: ## Start Freqtrade in background (Daemon mode)
	$(DOCKER_COMPOSE) up -d

stop: ## Stop Freqtrade container
	$(DOCKER_COMPOSE) down

restart: stop start ## Restart Freqtrade

logs: ## View Freqtrade logs
	$(DOCKER_COMPOSE) logs -f

update: ## Update Freqtrade docker image
	$(DOCKER_COMPOSE) pull

trade-dry: ## Run Freqtrade in dry-run mode (foreground)
	$(DOCKER_COMPOSE) run --rm freqtrade trade --dry-run --strategy $(STRATEGY) --freqaimodel $(FREQAI_MODEL)

create-userdir: ## Initialize user directory
	$(DOCKER_COMPOSE) run --rm freqtrade create-userdir --userdir user_data

list-strategies: ## List available strategies
	$(DOCKER_COMPOSE) run --rm freqtrade list-strategies --userdir user_data

# ===========================================
# FreqAI Training & Optimization
# ===========================================

train: clean-models ## Train FreqAI model với TRAIN_TIMERANGE + auto backup
	@echo "🚀 Starting FreqAI training..."
	@echo "   Strategy: $(STRATEGY)"
	@echo "   Model: $(FREQAI_MODEL)"
	@echo "   Timerange: $(TRAIN_TIMERANGE)"
	@echo "   Docker Image: $(DOCKER_IMAGE)"
ifeq ($(DOCKER_IMAGE),freqtradeorg/freqtrade:develop_freqai)
	$(DOCKER_COMPOSE) run --rm --remove-orphans freqtrade backtesting \
		--strategy $(STRATEGY) \
		--timerange $(TRAIN_TIMERANGE) \
		--freqaimodel $(FREQAI_MODEL)
else
	sudo docker run --rm \
		-v $$(pwd)/user_data:/freqtrade/user_data \
		-v $$(pwd)/user_data/config.json:/freqtrade/config.json \
		$(DOCKER_IMAGE) backtesting \
		--strategy $(STRATEGY) \
		--timerange $(TRAIN_TIMERANGE) \
		--freqaimodel $(FREQAI_MODEL)
endif
	@echo "✅ Training complete!"
	-./scripts/backup_to_drive.sh incremental 2>/dev/null || true
	@echo "☁️ Backup attempted (might fail on GCP)"

backtest: ## Run backtesting với BACKTEST_TIMERANGE
	@echo "📊 Running backtest..."
	@echo "   Timerange: $(BACKTEST_TIMERANGE)"
	$(DOCKER_COMPOSE) run --rm freqtrade backtesting \
		--strategy $(STRATEGY) \
		--timerange $(BACKTEST_TIMERANGE) \
		--freqaimodel $(FREQAI_MODEL)

backtest-optimized: ## Backtest với export results
	$(DOCKER_COMPOSE) run --rm freqtrade backtesting \
		--strategy $(STRATEGY) \
		--timerange $(BACKTEST_TIMERANGE) \
		--freqaimodel $(FREQAI_MODEL) \
		--export-filename user_data/backtest_results/optimized-backtest.json

dry-run: ## Paper trading
	$(DOCKER_COMPOSE) run --rm freqtrade trade \
		--strategy $(STRATEGY) \
		--freqaimodel $(FREQAI_MODEL) \
		--dry-run
down-timerange-data: 
	$(DOCKER_COMPOSE) run --rm freqtrade download-data --trading-mode $(TRADING_MODE) --pairs $(PAIRS) --timeframes $(TIME_FRAMES) --timerange $(TIME_RANGE)
	

live: ## Live trading (REAL MONEY - cẩn thận!)
	@echo "⚠️  WARNING: This will trade with REAL MONEY!"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ] || exit 1
	$(DOCKER_COMPOSE) run --rm freqtrade trade \
		--strategy $(STRATEGY) \
		--freqaimodel $(FREQAI_MODEL)

hyperopt:
	@echo "🚀 Starting hyperopt..."
	@echo "   Timerange: $(TRAIN_TIMERANGE)"
	@echo "   Epochs: $(HYPEROPT_EPOCHS)"
	@echo "   Loss: $(HYPEROPT_LOSS)"
	@echo "   Spaces: $(HYPEROPT_SPACES)"
	$(DOCKER_COMPOSE) run --rm freqtrade hyperopt \
		--strategy $(STRATEGY) \
		--freqaimodel $(FREQAI_MODEL) \
		--hyperopt-loss $(HYPEROPT_LOSS) \
		--epochs $(HYPEROPT_EPOCHS) \
		--spaces $(HYPEROPT_SPACES) \
		--timerange $(TRAIN_TIMERANGE) \
		--random-state $(RANDOM_STATE) \
		-j 2
	@echo "✅ Hyperopt complete! Use 'make hyperopt-show' to see best results"
	@echo "💾 Backing up new models..."
	./scripts/backup_to_drive.sh models



hyperopt-show: ## Show best hyperopt results
	$(DOCKER_COMPOSE) run --rm freqtrade hyperopt-show --best

hyperopt-list: ## List top 10 hyperopt results
	$(DOCKER_COMPOSE) run --rm freqtrade hyperopt-list --best 10 --no-details


docker-stats: ## Monitor Docker container memory/CPU usage
	@echo "📊 Docker container stats (Ctrl+C to exit):"
	docker stats freqtrade --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}"

docker-inspect-oom: ## Check if container was killed by OOM
	@echo "🔍 Checking container exit status..."
	@docker inspect freqtrade --format='{{.State.ExitCode}}' 2>/dev/null && \
		docker inspect freqtrade --format='Exit Code: {{.State.ExitCode}}, OOMKilled: {{.State.OOMKilled}}' || \
		echo "Container not found. It may have been removed."
	@echo ""
	@echo "Exit codes:"
	@echo "  137 = SIGKILL (usually OOM)"
	@echo "  139 = SIGSEGV (segfault)"
	@echo "  143 = SIGTERM (graceful stop)"
	@echo ""
	@echo "💡 Check dmesg for OOM killer logs: dmesg | grep -i 'killed process'"

show-params: ## Show current strategy parameters from JSON
	@echo "📊 Current Strategy Parameters:"
	@if [ -f user_data/strategies/FreqAIStrategy.json ]; then \
		cat user_data/strategies/FreqAIStrategy.json | python3 -m json.tool; \
	else \
		echo "⚠️  No parameter file found. Using defaults from code."; \
	fi

reset-params: ## Delete JSON params and use defaults from code
	@echo "🔄 Resetting to default parameters..."
	@rm -f user_data/strategies/FreqAIStrategy.json
	@echo "✅ Parameters reset. Will use defaults from code."

backup: ## Manual backup to Google Drive
	./scripts/backup_to_drive.sh incremental

backup-full: ## Full backup to Google Drive
	./scripts/backup_to_drive.sh full

backup-models: ## Backup models to Google Drive (versioned)
	@echo "☁️ Backing up models to Google Drive..."
	./scripts/backup_to_drive.sh models
	@echo "✅ Models backed up!"

clean-models: ## Delete models + docker cache (with optional backup)
	rm -rf user_data/models/freqai-*
	rm -rf user_data/hyperopt_results/*
	docker system prune -f --volumes 2>/dev/null || true
	@echo "🗑️ Models and cache deleted."

# ===========================================
# Model Testing (Local)
# ===========================================

test-lightgbm: ## Test LightGBM model on Mac
	@echo "🧪 Testing LightGBM..."
	rm -rf user_data/models/freqai-lightgbm-v1/*
	$(DOCKER_COMPOSE) run --rm freqtrade backtesting \
		--strategy $(STRATEGY) \
		--config user_data/configs/config-lightgbm.json \
		--timerange $(TRAIN_TIMERANGE) \
		--freqaimodel LightGBMRegressor

test-catboost: ## Test CatBoost model on Mac
	@echo "🧪 Testing CatBoost..."
	rm -rf user_data/models/freqai-catboost-v1/*
	$(DOCKER_COMPOSE) run --rm freqtrade backtesting \
		--strategy $(STRATEGY) \
		--config user_data/configs/config-catboost.json \
		--timerange $(TRAIN_TIMERANGE) \
		--freqaimodel CatBoostRegressor

compare-models: ## Compare all model backtest results
	@echo "📊 Model Comparison Results:"
	@echo "=============================="
	@for f in user_data/backtest_results/*.meta.json; do \
		echo "\n📁 $$f"; \
		cat "$$f" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Win Rate: {d.get(\"wins\",0)}/{d.get(\"total_trades\",0)}'); print(f'  Profit: {d.get(\"profit_total\",0):.2%}')"; \
	done 2>/dev/null || echo "No backtest results found"

# ===========================================
# GCP Cloud Operations
# ===========================================

gcp-setup: ## Setup GCP project and enable APIs
	@chmod +x scripts/gcp/*.sh
	./scripts/gcp/setup-project.sh

gcp-hyperopt: ## Create Spot VM for massive hyperopt
	./scripts/gcp/create-hyperopt-vm.sh

gcp-tournament: ## Create 3 VMs for model tournament
	./scripts/gcp/create-tournament.sh

gcp-live: ## Create production VM for live trading
	./scripts/gcp/create-live-vm.sh

gcp-deploy: ## Deploy to production VM
	./scripts/gcp/deploy.sh

gcp-teardown: ## Delete all GCP VMs (save costs!)
	./scripts/gcp/teardown.sh

gcp-status: ## Check status of all GCP VMs
	@gcloud compute instances list --filter="name~freqtrade" --project=$(GCP_PROJECT)

gcp-ssh: ## SSH into freqtrade-live VM
	gcloud compute ssh freqtrade-live --zone=$(GCP_ZONE) --project=$(GCP_PROJECT)

gcp-logs: ## View logs from freqtrade-live VM
	gcloud compute ssh freqtrade-live --zone=$(GCP_ZONE) --project=$(GCP_PROJECT) --command="cd /opt/freqtrade && docker compose logs -f --tail=100"

# Simple GCP Training (sử dụng $300 credit)
gcp-create-small: ## Create small VM (16 vCPU) ~$0.60/h
	./scripts/gcp_create.sh small

gcp-create-medium: ## Create medium VM (32 vCPU) ~$1.20/h  
	./scripts/gcp_create.sh medium

gcp-create-beast: ## Create BEAST VM (128 vCPU) ~$1.94/h
	./scripts/gcp_create.sh beast

gcp-train-remote: ## Run training on GCP with auto-shutdown
	./scripts/gcp_train.sh $(STRATEGY) $(TRAIN_TIMERANGE)

gcp-destroy-train: ## Destroy training VM (stop charges!)
	./scripts/gcp_destroy.sh

# ===========================================
# Debugging & Monitoring
# ===========================================

check-memory: ## Check available system memory
	@echo "💾 System Memory Status:"
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "  Total RAM: $$(sysctl -n hw.memsize | awk '{print $$1/1024/1024/1024 " GB"}')"; \
		vm_stat | head -10; \
	else \
		free -h; \
	fi
	@echo ""
	@echo "🐳 Docker Memory Settings:"
	@docker system info 2>/dev/null | grep -E "Total Memory|CPUs" || echo "  Docker not running"

check-oom: ## Check system logs for OOM killer events
	@echo "🔍 Checking for OOM killer events..."
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "  macOS: Check Activity Monitor > Memory tab"; \
		log show --predicate 'eventMessage contains "killed"' --last 1h 2>/dev/null | head -20 || echo "  No recent OOM events"; \
	else \
		dmesg | grep -i "killed process" | tail -10 || echo "  No recent OOM events"; \
	fi

diagnose-137: ## Full diagnosis for Error 137 (OOM)
	@echo "=============================================="
	@echo "🔍 ERROR 137 DIAGNOSIS (OOM Kill)"
	@echo "=============================================="
	@echo ""
	@echo "1️⃣  System Memory:"
	@make check-memory 2>/dev/null || true
	@echo ""
	@echo "2️⃣  Docker Container Status:"
	@docker inspect freqtrade --format='OOMKilled: {{.State.OOMKilled}}, ExitCode: {{.State.ExitCode}}' 2>/dev/null || echo "  Container not found"
	@echo ""
	@echo "3️⃣  Docker Memory Limit:"
	@docker inspect freqtrade --format='Memory Limit: {{.HostConfig.Memory}}' 2>/dev/null || echo "  Container not found"
	@echo ""
	@echo "💡 SOLUTIONS:"
	@echo "  a) Reduce parallel jobs: make hyperopt-debug (uses -j 1)"
	@echo "  b) Use shorter timerange: make hyperopt-lowmem"
	@echo "  c) Increase memory in docker-compose.yml"
	@echo "  d) Close other applications to free RAM"
	@echo "  e) Use GCP VM: make gcp-hyperopt"
