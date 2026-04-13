FROM python:3.11-slim

WORKDIR /app

# 系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 先複製 requirements.txt 利用 Docker layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製 agent 程式碼
COPY . .

# Python stdout 不 buffer，確保 log 即時輸出
ENV PYTHONUNBUFFERED=1

# Cloud Run 預設 PORT=8080
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
