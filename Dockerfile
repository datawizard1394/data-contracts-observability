FROM python:3.12-slim

LABEL org.opencontainers.image.title="Synthetic Data Contracts Observability Demo"
LABEL org.opencontainers.image.description="Dependency-free portfolio reference implementation"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN useradd --create-home --uid 10001 observer

COPY --chown=observer:observer src ./src
COPY --chown=observer:observer contracts ./contracts
COPY --chown=observer:observer data ./data
COPY --chown=observer:observer lineage ./lineage

USER observer

ENTRYPOINT ["python", "-m", "data_observer"]
CMD ["run", "--contract", "contracts/orders.contract.json", "--data", "data/orders_healthy.csv", "--lineage", "lineage/manifest.json", "--output-dir", "/tmp/observability", "--now", "2026-07-28T12:00:00Z"]
