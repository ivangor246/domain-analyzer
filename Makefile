# develop
up:
	docker compose -f docker-compose.yml up -d --build --force-recreate $(for)

dev:
	DEV_MODE=True docker compose -f docker-compose.yml watch

stop:
	docker compose -f docker-compose.yml stop $(for)

rm:
	docker compose -f docker-compose.yml down -v $(for)

logs:
	docker compose -f docker-compose.yml logs $(for)

clear:
	docker compose -f docker-compose.yml down -v --rmi all --remove-orphans $(for)
