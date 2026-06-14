FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_DEBUG=False \
    DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0 \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --no-input

EXPOSE 8000

CMD python manage.py migrate \
    && python manage.py seed_five_year_mpc_data \
    && (python manage.py ingest_latest_rbi_policy || true) \
    && (python manage.py update_usdinr_volatility --years 5 --window 20 || true) \
    && exec gunicorn macro_sentiment_project.wsgi:application --bind 0.0.0.0:${PORT}
