FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl gnupg2 unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-postgres.txt ./
RUN pip install -r requirements.txt -r requirements-postgres.txt

# AI é opcional — descomente se for usar no container:
# COPY requirements-ai.txt ./
# RUN pip install -r requirements-ai.txt

COPY . .

EXPOSE 8000
CMD ["python", "-m", "app.main"]
