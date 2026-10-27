# Build context: repository root (see docker-compose.yml), so samples/ can be copied in.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv
COPY backend/requirements.txt backend/requirements-dev.txt backend/
RUN pip install -r backend/requirements-dev.txt

COPY backend/ backend/
COPY samples/ samples/
WORKDIR /srv/backend

RUN useradd --create-home --uid 10001 aivanta && chown -R aivanta /srv
USER aivanta

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
