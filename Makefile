# Docker Desktop on macOS may be installed without CLI symlinks in PATH.
ifneq ($(wildcard /Applications/Docker.app/Contents/Resources/bin/docker),)
export PATH := $(PATH):/Applications/Docker.app/Contents/Resources/bin
COMPOSE ?= /Applications/Docker.app/Contents/Resources/cli-plugins/docker-compose
else
COMPOSE ?= docker compose
endif

.PHONY: help up down build logs ps migrate revision test test-backend test-frontend lint fmt clean shell-backend shell-db deploy-cognito destroy-cognito deploy-backend destroy-backend logs-backend migrate-backend cert domain deploy-frontend destroy-frontend github-role

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start the whole stack (detached)
	$(COMPOSE) up -d --build

down: ## Stop the stack
	$(COMPOSE) down

clean: ## Stop the stack and wipe the database volume
	$(COMPOSE) down -v

build: ## Rebuild images
	$(COMPOSE) build

logs: ## Tail all logs
	$(COMPOSE) logs -f

ps: ## Show service status
	$(COMPOSE) ps

migrate: ## Apply migrations
	$(COMPOSE) exec backend alembic upgrade head

revision: ## Autogenerate a migration: make revision m="add x"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	$(COMPOSE) exec backend pytest

test-frontend: ## Run frontend tests
	$(COMPOSE) exec frontend pnpm test

lint: ## Lint both sides
	$(COMPOSE) exec backend ruff check .
	$(COMPOSE) exec frontend pnpm lint

fmt: ## Format both sides
	$(COMPOSE) exec backend ruff format .
	$(COMPOSE) exec frontend pnpm format

shell-backend: ## Shell into the backend container
	$(COMPOSE) exec backend bash

shell-db: ## psql into the database
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-peach} -d $${POSTGRES_DB:-peach}

deploy-cognito: ## Create/update the Cognito user pool; writes COGNITO_* to .env and prints them
	./scripts/deploy-cognito.sh

destroy-cognito: ## Delete the Cognito stack, every account in the pool included
	./scripts/destroy-cognito.sh

deploy-backend: ## Build + push the image, roll the Lambda (function URL + Aurora), migrate, write BACKEND_URL to .env
	./scripts/deploy-backend.sh

destroy-backend: ## Delete the backend stack, Aurora cluster included
	./scripts/destroy-backend.sh

logs-backend: ## Tail the deployed backend's CloudWatch logs
	aws logs tail /aws/lambda/$${PROJECT_NAME:-peach}-backend --follow --since 10m

migrate-backend: ## Re-run migrations on the deployed backend (deploy-backend already does)
	aws lambda invoke --function-name $${PROJECT_NAME:-peach}-backend \
		--cli-binary-format raw-in-base64-out --payload '{"action":"migrate"}' /dev/stdout

cert: ## Request + DNS-validate a us-east-1 certificate for the frontend: make cert DOMAIN=app.example.com
	./scripts/domain-frontend.sh cert

domain: ## Assign a custom domain to the frontend: make domain DOMAIN=app.example.com
	./scripts/domain-frontend.sh domain

deploy-frontend: ## Build the static export against BACKEND_URL and ship it to S3 + CloudFront
	./scripts/deploy-frontend.sh

destroy-frontend: ## Delete the frontend stack (bucket + distribution)
	./scripts/destroy-frontend.sh

github-role: ## Create the IAM role GitHub Actions assumes to deploy (OIDC, no keys)
	./scripts/github-role.sh

.PHONY: report-now
report-now:
	aws sqs send-message \
		--queue-url https://sqs.us-east-1.amazonaws.com/506126098984/peach-reports-queue \
		--message-body '{"week":"$(WEEK)","source":"manual"}' \
		--region us-east-1

.PHONY: deploy-reports
deploy-reports: ## Update the existing reports stack using REPORT_IMAGE_URI and REPORT_* email settings
	./scripts/deploy-reports.sh

UV ?= $(if $(wildcard $(HOME)/.local/bin/uv),$(HOME)/.local/bin/uv,uv)
.PHONY: llm-hello parse
llm-hello: ## One short Bedrock Messages request; requires AWS login
	cd backend && $(UV) run python -m app.ai.cli hello

export TEXT
export TODAY
parse: ## Parse TEXT="..." using Bedrock without writing a meeting
	cd backend && $(UV) run python -m app.ai.cli parse

.PHONY: deploy-ai
deploy-ai: ## Deploy the isolated parser (disabled by default) and $5 monthly budget
	./scripts/deploy-ai.sh

.PHONY: free-ai-server free-ai-frontend free-ai-parse free-ai-hello free-ai-evaluate
free-ai-server: ## Free cloud inference adapter on localhost:8001
	bash scripts/free-ai.sh server
free-ai-frontend: ## Local UI with free cloud parsing
	bash scripts/free-ai.sh frontend
free-ai-parse: ## Parse TEXT with openrouter/free only
	bash scripts/free-ai.sh parse
free-ai-hello: ## Test free API access
	bash scripts/free-ai.sh hello
free-ai-evaluate: ## Collect the five real free-provider API outputs
	bash scripts/free-ai.sh evaluate
