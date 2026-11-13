# Ảnh chạy thật: build giao diện React → cài backend → một tiến trình uvicorn phục vụ cả API lẫn web.
# docker compose up -d   (xem docker-compose.yml)

# ---------- 1. Build frontend ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 2. Backend ----------
FROM python:3.12-slim
ARG EXTRAS="google,postgres"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/app backend/app
RUN pip install "./backend[${EXTRAS}]"
COPY backend/ backend/
COPY --from=web /web/dist frontend/dist
# Chạy bằng user thường, không phải root (nếu bị khai thác thì quyền bị giới hạn).
RUN useradd --create-home appuser && mkdir -p backend/data && chown -R appuser backend/data
USER appuser
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
