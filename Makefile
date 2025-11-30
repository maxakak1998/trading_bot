# Makefile for Freqtrade

.PHONY: help start stop restart logs update trade-dry create-userdir list-strategies train backtest hyperopt backup

help: ## Show this help message
	@echo 'Usage:'
	@echo '  make [target]'
	@echo ''
	@echo 'Targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

start: ## Start Freqtrade in background (Daemon mode)
	docker compose up -d

stop: ## Stop Freqtrade container
	docker compose down

restart: stop start ## Restart Freqtrade

logs: ## View Freqtrade logs
	docker compose logs -f

update: ## Update Freqtrade docker image
	docker compose pull

trade-dry: ## Run Freqtrade in dry-run mode (foreground)
	docker compose run --rm freqtrade trade --dry-run --strategy SampleStrategy

create-userdir: ## Initialize user directory
	docker compose run --rm freqtrade create-userdir --userdir user_data

list-strategies: ## List available strategies
	docker compose run --rm freqtrade list-strategies --userdir user_data

# ===========================================
# FreqAI Training & Optimization
# ===========================================

train: ## Train FreqAI model (5 months data) + auto backup
	@echo "🚀 Starting FreqAI training..."
	docker compose run --rm freqtrade backtesting \
		--strategy FreqAIStrategy \
		--timerange 20240601-20241101 \
		--freqaimodel XGBoostClassifier
	@echo "✅ Training complete! Starting backup..."
	./scripts/backup_to_drive.sh incremental
	@echo "☁️ Backup to Google Drive complete!"

backtest: ## Run backtesting on trained model
	docker compose run --rm freqtrade backtesting \
		--strategy FreqAIStrategy \
		--timerange 20241101-20241201 \
		--freqaimodel XGBoostClassifier

hyperopt: ## Optimize strategy parameters (50 epochs)
	docker compose run --rm freqtrade hyperopt \
		--strategy FreqAIStrategy \
		--hyperopt-loss SharpeHyperOptLoss \
		--epochs 50 \
		--spaces buy sell roi stoploss

backup: ## Manual backup to Google Drive
	./scripts/backup_to_drive.sh incremental

backup-full: ## Full backup to Google Drive
	./scripts/backup_to_drive.sh full
