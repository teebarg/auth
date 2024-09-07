# Makefile for FastAPI Auth Service

# Variables
PIP := pip3
DOCKER_COMPOSE := docker compose
PROJECT_SLUG := auth

# Commands
.PHONY: install run test format start update stop clean

install:
	$(PIP) install -r requirements.txt

run:
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest

format:
	black .

start:
	@echo "$(YELLOW)Starting docker environment...$(RESET)"
	$(DOCKER_COMPOSE) -p $(PROJECT_SLUG) up --build

update:
	@echo "$(BLUE)Starting docker environment...$(RESET)"
	$(DOCKER_COMPOSE) -p $(PROJECT_SLUG) up --build -d

stop:
	@echo "$(RED)Removing docker environment...$(RESET)"
	@COMPOSE_PROJECT_NAME=$(PROJECT_SLUG) $(DOCKER_COMPOSE) down

clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete

# Database migrations
db-migrate:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-revision:
	alembic revision --autogenerate -m "$(message)"

# Development helpers
dev-setup: install db-migrate

dev-reset: down clean install db-migrate up

# Production helpers
prod-build: build

prod-deploy: prod-build up

# Deployment to vercel
vercel-deploy:
	vercel deploy --prod

# Help command
help:
	@echo "Available commands:"
	@echo "  install      : Install project dependencies"
	@echo "  run          : Run the FastAPI server locally"
	@echo "  test         : Run tests"
	@echo "  format       : Format code"
	@echo "  start        : Start Docker containers"
	@echo "  update       : Update Docker containers"
	@echo "  stop         : Stop Docker containers"
	@echo "  clean        : Remove Python cache files"
	@echo "  db-migrate   : Run database migrations"
	@echo "  db-downgrade : Downgrade database by one revision"
	@echo "  db-revision  : Create a new database revision"
	@echo "  dev-setup    : Set up development environment"
	@echo "  dev-reset    : Reset development environment"
	@echo "  prod-build   : Build for production"
	@echo "  prod-deploy  : Deploy to production"
