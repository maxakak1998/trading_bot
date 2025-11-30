# Makefile for Freqtrade

.PHONY: help start stop restart logs update trade-dry create-userdir list-strategies

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
