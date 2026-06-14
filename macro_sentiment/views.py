import json
import re
from datetime import timedelta

from django.conf import settings
from django.db.models import Avg
from django.shortcuts import render
from django.utils import timezone

from .ingestion import ingest_latest_rbi_policy
from .logic import get_policy_answer_with_meta
from .models import EconomicIndicator, PolicyDocument, SentimentResult


def _extract_policy_rate(text):
    patterns = [
        r"policy repo rate[^.]*?(?:unchanged at|to|at)\s+([0-9.]+)\s*per cent",
        r"repo rate[^.]*?(?:unchanged at|to|at)\s+([0-9.]+)\s*per cent",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _refresh_latest_rbi_policy():
    if not getattr(settings, "RBI_REFRESH_ON_REQUEST", True):
        return ""

    try:
        ingest_latest_rbi_policy()
    except Exception as exc:
        return str(exc)
    return ""


def dashboard_view(request):
    refresh_error = _refresh_latest_rbi_policy()
    five_years_ago = timezone.now() - timedelta(days=365 * 5)
    policy_documents = list(
        PolicyDocument.objects.filter(
            document_type=PolicyDocument.DocumentType.RBI_MONETARY_POLICY,
            sentiment__isnull=False,
            published_date__gte=five_years_ago,
        )
        .select_related("sentiment")
        .order_by("published_date")
    )

    sentiment_data = list(
        SentimentResult.objects.filter(document__in=policy_documents)
        .values("document__published_date__date")
        .annotate(avg_sentiment=Avg("sentiment_score"))
        .order_by("document__published_date__date")
    )

    economic_data = list(
        EconomicIndicator.objects.filter(
            name="Exchange Rate Volatility",
            timestamp__gte=five_years_ago,
        )
        .order_by("timestamp")
        .values("timestamp", "value", "unit")
    )

    sentiment_dates = [
        str(row["document__published_date__date"]) for row in sentiment_data
    ]
    sentiment_scores = [
        (
            round(float(row["avg_sentiment"]), 4)
            if row["avg_sentiment"] is not None
            else None
        )
        for row in sentiment_data
    ]
    policy_rates = [_extract_policy_rate(doc.content) for doc in policy_documents]
    meeting_titles = [
        doc.title.replace("Minutes of the Monetary Policy Committee Meeting, ", "")
        for doc in policy_documents
    ]
    indicator_dates = [row["timestamp"].date().isoformat() for row in economic_data]
    indicator_values = [float(row["value"]) for row in economic_data]
    indicator_unit = next(
        (row["unit"] for row in economic_data if row["unit"]),
        "",
    )
    latest_document = (
        PolicyDocument.objects.filter(
            document_type=PolicyDocument.DocumentType.RBI_MONETARY_POLICY,
            is_latest=True,
        )
        .select_related("sentiment")
        .order_by("-published_date")
        .first()
    )

    answer = ""
    answer_source_label = ""
    answer_source_type = ""
    answer_model = ""
    question = ""
    if request.method == "POST":
        question = request.POST.get("question", "").strip()
        if question:
            policy_answer = get_policy_answer_with_meta(question)
            answer = policy_answer.text
            answer_source_label = policy_answer.source_label
            answer_source_type = policy_answer.source_type
            answer_model = policy_answer.model

    context = {
        "sentiment_dates": json.dumps(sentiment_dates),
        "sentiment_scores": json.dumps(sentiment_scores),
        "policy_rates": json.dumps(policy_rates),
        "meeting_titles": json.dumps(meeting_titles),
        "indicator_dates": json.dumps(indicator_dates),
        "indicator_values": json.dumps(indicator_values),
        "indicator_unit": indicator_unit or "value",
        "indicator_unit_json": json.dumps(indicator_unit or "value"),
        "latest_document": latest_document,
        "refresh_error": refresh_error,
        "question": question,
        "answer": answer,
        "answer_source_label": answer_source_label,
        "answer_source_type": answer_source_type,
        "answer_model": answer_model,
    }
    return render(request, "dashboard.html", context)
