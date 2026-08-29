FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir ".[production]" \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /app/data \
    && chown -R app:app /app/data

USER app
EXPOSE 8000
CMD ["uvicorn", "ultimate_stock_analyzer.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
