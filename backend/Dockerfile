FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有 backend 目录下的 .py 文件和 index.html
COPY backend/*.py ./
COPY backend/index.html ./
COPY backend/views/ ./views/

RUN mkdir -p upload/images upload/logo

EXPOSE 8000

CMD ["sh", "-c", "sleep 5 && uvicorn main:app --host 0.0.0.0 --port 8000"]
