BACKEND_COMPOSE := back/docker-compose.yml

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
