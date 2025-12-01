# Makefile for Freqtrade

# ===========================================
# CONFIGURATION - Sửa ở đây để áp dụng cho tất cả commands
# ===========================================

# Strategy & Model
STRATEGY := FreqAIStrategy
FREQAI_MODEL := XGBoostRegressor

# Timeranges
TRAIN_TIMERANGE := 20231101-20241101
BACKTEST_TIMERANGE := 20241101-20241201

# Hyperopt settings
HYPEROPT_EPOCHS := 500
HYPEROPT_LOSS := SortinoHyperOptLossDaily
HYPEROPT_SPACES := buy sell roi
RANDOM_STATE := 42

# GCP settings
GCP_ZONE := us-central1-a
GCP_PROJECT := $(shell gcloud config get-value project 2>/dev/null)

# Docker
DOCKER_COMPOSE := docker compose

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
	$(DOCKER_COMPOSE) run --rm freqtrade trade --dry-run --strategy $(STRATEGY)

create-userdir: ## Initialize user directory
	$(DOCKER_COMPOSE) run --rm freqtrade create-userdir --userdir user_data

list-strategies: ## List available strategies
	$(DOCKER_COMPOSE) run --rm freqtrade list-strategies --userdir user_data

# ===========================================
# FreqAI Training & Optimization
# ===========================================

train: ## Train FreqAI model với TRAIN_TIMERANGE + auto backup
	@echo "🚀 Starting FreqAI training..."
	@echo "   Strategy: $(STRATEGY)"
	@echo "   Model: $(FREQAI_MODEL)"
	@echo "   Timerange: $(TRAIN_TIMERANGE)"
	$(DOCKER_COMPOSE) run --rm freqtrade backtesting \
		--strategy $(STRATEGY) \
		--timerange $(TRAIN_TIMERANGE) \
		--freqaimodel $(FREQAI_MODEL)
	@echo "✅ Training complete! Starting backup..."
	./scripts/backup_to_drive.sh incremental
	@echo "☁️ Backup to Google Drive complete!"

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

live: ## Live trading (REAL MONEY - cẩn thận!)
	@echo "⚠️  WARNING: This will trade with REAL MONEY!"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ] || exit 1
	$(DOCKER_COMPOSE) run --rm freqtrade trade \
		--strategy $(STRATEGY) \
		--freqaimodel $(FREQAI_MODEL)

hyperopt: ## Hyperopt optimization với TRAIN_TIMERANGE
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
		--random-state $(RANDOM_STATE)
	@echo "✅ Hyperopt complete! Use 'make hyperopt-show' to see best results"
	@echo "💾 Backing up new models..."
	./scripts/backup_to_drive.sh models

hyperopt-show: ## Show best hyperopt results
	$(DOCKER_COMPOSE) run --rm freqtrade hyperopt-show --best

hyperopt-list: ## List top 10 hyperopt results
	$(DOCKER_COMPOSE) run --rm freqtrade hyperopt-list --best 10 --no-details

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
	@echo "⚠️  WARNING: This will delete all trained models and docker cache!"
	@read -p "Backup before delete? (yes/no): " backup && \
		if [ "$$backup" = "yes" ]; then \
			./scripts/backup_to_drive.sh models && echo "✅ Models backed up!"; \
		fi
	@read -p "Delete all models + cache? (yes/no): " confirm && [ "$$confirm" = "yes" ] || exit 1
	rm -rf user_data/models/freqai-*
	rm -rf user_data/hyperopt_results/*
	docker system prune -f --volumes 2>/dev/null || true
	@echo "🗑️ Models and cache deleted."

clean-models-force: ## Force delete models + docker cache (NO backup, NO confirm)
	@echo "🗑️ Force deleting all models and docker cache..."
	rm -rf user_data/models/freqai-*
	rm -rf user_data/hyperopt_results/*
	docker system prune -f --volumes 2>/dev/null || true
	@echo "✅ Models and cache deleted."

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
