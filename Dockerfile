FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data

# Installed Python packages live in site-packages, while demo JSON ships in /app/data.
ENV AGENTOPS_DATA_DIR=/app/data

RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "agentops_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
