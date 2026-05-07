#!/usr/bin/env bash
set -o errexit

python manage.py collectstatic --no-input
python manage.py migrate
python manage.py seed_five_year_mpc_data
python manage.py update_usdinr_volatility --years 5 --window 20 || true
