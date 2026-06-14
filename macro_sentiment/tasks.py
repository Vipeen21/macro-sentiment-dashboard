import json
import re

from django.conf import settings

from .models import PolicyDocument, SentimentResult

try:
    from celery import shared_task
except ImportError:
    def shared_task(func):
        return func


def _response_text(response):
    return getattr(response, "content", response)


def _extract_json(text):
    if not isinstance(text, str):
        return text

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("LLM response did not contain a JSON object.")
        return json.loads(match.group(0))


def _normalise_label(value, score):
    label = str(value or "").strip().title()
    allowed_labels = {choice.value for choice in SentimentResult.Label}

    if label in allowed_labels:
        return label
    if score > 0.15:
        return SentimentResult.Label.HAWKISH
    if score < -0.15:
        return SentimentResult.Label.DOVISH
    return SentimentResult.Label.NEUTRAL


def _fallback_analysis(text):
    lowered = text.lower()
    hawkish_words = [
        "inflation",
        "tightening",
        "upside risks",
        "vigilant",
        "price pressures",
        "rate hike",
        "withdrawal of accommodation",
    ]
    dovish_words = [
        "growth support",
        "accommodative",
        "rate cut",
        "liquidity",
        "support growth",
        "easing",
    ]
    hawkish_hits = sum(lowered.count(word) for word in hawkish_words)
    dovish_hits = sum(lowered.count(word) for word in dovish_words)
    raw_score = (hawkish_hits - dovish_hits) / max(hawkish_hits + dovish_hits, 1)
    score = max(-1.0, min(1.0, raw_score))

    return {
        "sentiment_score": round(score, 2),
        "label": _normalise_label("", score),
        "primary_impact": "Inflation and monetary policy",
    }


def analyze_policy_document(doc):
    model_name = getattr(settings, "GOOGLE_GENAI_CHAT_MODEL", "gemini-1.5-flash")
    prompt = f"""
Analyze the economic policy text below.
Return only valid JSON with these keys:
- sentiment_score: number from -1.0 to 1.0
- label: one of Hawkish, Dovish, Neutral
- primary_impact: the main economic indicator or area affected

Text:
{doc.content[:24000]}
""".strip()

    try:
        if not getattr(settings, "GOOGLE_API_KEY", ""):
            raise RuntimeError("GOOGLE_API_KEY is not configured.")

        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        payload = _extract_json(_response_text(llm.invoke(prompt)))
    except Exception:
        payload = _fallback_analysis(doc.content)

    score = max(-1.0, min(1.0, float(payload.get("sentiment_score", 0))))
    label = _normalise_label(payload.get("label"), score)
    primary_impact = str(
        payload.get("primary_impact")
        or payload.get("main_economic_indicator")
        or ""
    )[:100]

    result, _ = SentimentResult.objects.update_or_create(
        document=doc,
        defaults={
            "sentiment_score": score,
            "label": label,
            "primary_impact": primary_impact,
        },
    )
    return result


@shared_task
def process_new_document(doc_id):
    doc = PolicyDocument.objects.get(id=doc_id)
    return analyze_policy_document(doc).id
