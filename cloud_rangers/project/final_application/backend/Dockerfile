FROM python:3.12-slim

WORKDIR /app

# Install system deps required by psycopg2, pillow, redis, pymongo.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    default-libmysqlclient-dev \
    libssl-dev \
    cargo \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip && python -m pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LPS_SERVER=fastapi
ENV LPS_HOST=0.0.0.0
ENV FASTAPI_PORT=8000

CMD ["python", "run.py"]
