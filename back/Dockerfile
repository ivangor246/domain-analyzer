FROM python:3.14-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6

ENV POETRY_VERSION=2.1.3 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /project

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION" \
    && poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev --no-root

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /home/app --create-home app \
    && chown app:app /project

COPY . .

USER app

ENTRYPOINT [ "sh", "entrypoint.sh" ]
