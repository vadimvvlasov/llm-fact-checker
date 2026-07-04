FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv sync --no-dev

COPY . .

CMD ["uv", "run", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
