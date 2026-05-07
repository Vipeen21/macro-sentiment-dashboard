import json
import math
import ssl
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import urlencode
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.utils import timezone

from .models import EconomicIndicator


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/USDINR=X"


def update_usdinr_volatility(years=5, window=20):
    closes = _fetch_usdinr_closes(years=years)
    volatility_points = _rolling_annualized_volatility(closes, window=window)

    existing_dates = set()
    for observed_at, value in volatility_points:
        existing_dates.add(observed_at.date())
        EconomicIndicator.objects.update_or_create(
            name="Exchange Rate Volatility",
            timestamp=observed_at,
            defaults={
                "value": value,
                "unit": "% ann. 20d USD-INR",
            },
        )

    for indicator in EconomicIndicator.objects.filter(name="Exchange Rate Volatility"):
        if indicator.timestamp.date() not in existing_dates:
            indicator.delete()

    return len(volatility_points)


def _fetch_usdinr_closes(years):
    end = datetime.now(tz=dt_timezone.utc)
    start = end - timedelta(days=365 * years + 60)
    params = urlencode(
        {
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "interval": "1d",
            "events": "history",
        }
    )
    request = Request(
        f"{YAHOO_CHART_URL}?{params}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (ssl.SSLCertVerificationError, URLError) as exc:
        if isinstance(exc, URLError) and not isinstance(
            exc.reason, ssl.SSLCertVerificationError
        ):
            raise
        context = ssl._create_unverified_context()
        with urlopen(request, timeout=20, context=context) as response:
            payload = json.loads(response.read().decode("utf-8"))

    result = payload["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]

    rows = []
    cutoff = timezone.now() - timedelta(days=365 * years)
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        observed_at = datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)
        observed_at = timezone.datetime(
            observed_at.year,
            observed_at.month,
            observed_at.day,
            tzinfo=dt_timezone.utc,
        )
        if observed_at >= cutoff:
            rows.append((observed_at, float(close)))
    return rows


def _rolling_annualized_volatility(closes, window):
    returns = []
    for index in range(1, len(closes)):
        observed_at, close = closes[index]
        _, previous_close = closes[index - 1]
        if previous_close <= 0 or close <= 0:
            continue
        returns.append((observed_at, math.log(close / previous_close)))

    points = []
    for index in range(window - 1, len(returns)):
        observed_at = returns[index][0]
        values = [item[1] for item in returns[index - window + 1 : index + 1]]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
        annualized = math.sqrt(variance) * math.sqrt(252) * 100
        points.append((observed_at, round(annualized, 4)))
    return points
