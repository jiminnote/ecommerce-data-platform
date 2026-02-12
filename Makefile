.PHONY: help setup dev test lint docker-up docker-down k8s-deploy tf-plan tf-apply

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Development ──────────────────────────────────────────────
setup: ## Initial project setup
	pip install -e ".[dev]"
	pre-commit install

dev: ## Start local development environment
	docker compose up -d postgres bigquery-emulator grafana
	@echo "✅ Local dev environment ready"
	@echo "   PostgreSQL:  localhost:5432"
	@echo "   BigQuery:    localhost:9050"
	@echo "   Grafana:     localhost:3000"

dev-full: ## Start full environment with CDC
	docker compose up -d
	@sleep 10
	@echo "Registering Debezium connector..."
	curl -X POST http://localhost:8083/connectors \
		-H "Content-Type: application/json" \
		-d @scripts/debezium-connector.json
	@echo "\n✅ Full environment ready"

test: ## Run tests
	pytest tests/ -v --cov=src --cov-report=term-missing

lint: ## Run linter
	ruff check src/ tests/
	mypy src/

# ─── Docker ───────────────────────────────────────────────────
docker-build: ## Build all Docker images
	docker build --target event-collector -t event-collector:latest .
	docker build --target batch-pipeline -t batch-pipeline:latest .
	docker build --target cdc-pipeline -t cdc-pipeline:latest .
	docker build --target genai-agent -t genai-agent:latest .

docker-up: ## Start all Docker services
	docker compose up -d

docker-down: ## Stop all Docker services
	docker compose down -v

# ─── Kubernetes ───────────────────────────────────────────────
k8s-deploy: ## Deploy to Kubernetes cluster
	kubectl apply -f kubernetes/namespace.yaml
	kubectl apply -f kubernetes/configmap.yaml
	kubectl apply -f kubernetes/secrets.yaml
	kubectl apply -f kubernetes/event-collector/
	kubectl apply -f kubernetes/cdc-pipeline/
	kubectl apply -f kubernetes/airflow/
	kubectl apply -f kubernetes/monitoring/

k8s-delete: ## Remove from Kubernetes
	kubectl delete -f kubernetes/ --recursive --ignore-not-found

k8s-status: ## Check Kubernetes deployment status
	kubectl -n data-platform get all

# ─── Terraform (GCP) ─────────────────────────────────────────
tf-init: ## Initialize Terraform
	cd terraform && terraform init

tf-plan: ## Plan Terraform changes
	cd terraform && terraform plan -var-file=environments/dev.tfvars

tf-apply: ## Apply Terraform changes
	cd terraform && terraform apply -var-file=environments/dev.tfvars

tf-destroy: ## Destroy Terraform resources
	cd terraform && terraform destroy -var-file=environments/dev.tfvars

# ─── Data Pipeline ────────────────────────────────────────────
generate-events: ## Generate fake e-commerce events for testing
	python -m src.scripts.event_generator --count 1000

run-batch: ## Run batch pipeline locally
	python -m src.pipelines.batch_pipeline --date yesterday

run-quality: ## Run GenAI data quality agent
	python -m src.genai.data_quality_agent
