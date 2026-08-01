BACKEND_COMPOSE := back/docker-compose.yml
FRONTEND_DIR := front

# develop
up:
	docker compose -f $(BACKEND_COMPOSE) up -d --build --force-recreate $(for)

dev:
	DEV_MODE=True docker compose -f $(BACKEND_COMPOSE) watch

stop:
	docker compose -f $(BACKEND_COMPOSE) stop $(for)

rm:
	docker compose -f $(BACKEND_COMPOSE) down -v $(for)

logs:
	docker compose -f $(BACKEND_COMPOSE) logs $(for)

clear:
	docker compose -f $(BACKEND_COMPOSE) down -v --rmi all --remove-orphans $(for)

test:
	cd back && PYTHONPATH=src poetry run python -m unittest discover -s tests

coverage:
	cd back && PYTHONPATH=src poetry run coverage run -m unittest discover -s tests && poetry run coverage report --fail-under=80

lint:
	cd back && poetry run ruff check src tests

format-check:
	cd back && poetry run ruff format --check src tests

check: test lint format-check

front-install:
	npm --prefix $(FRONTEND_DIR) install

front-dev:
	npm --prefix $(FRONTEND_DIR) run dev

front-build:
	npm --prefix $(FRONTEND_DIR) run build

front-image:
	docker build --build-arg VITE_API_URL=http://localhost:8000 -t domain-analyzer-front $(FRONTEND_DIR)

front-lint:
	npm --prefix $(FRONTEND_DIR) run lint

front-test:
	npm --prefix $(FRONTEND_DIR) run test

front-typecheck:
	npm --prefix $(FRONTEND_DIR) run typecheck

front-check: front-typecheck front-lint front-test
