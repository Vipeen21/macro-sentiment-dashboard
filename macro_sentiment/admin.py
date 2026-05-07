from django.contrib import admin

from .models import EconomicIndicator, PolicyDocument, SentimentResult


@admin.register(EconomicIndicator)
class EconomicIndicatorAdmin(admin.ModelAdmin):
    list_display = ("name", "value", "unit", "timestamp")
    list_filter = ("name", "unit")
    search_fields = ("name",)


@admin.register(PolicyDocument)
class PolicyDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "published_date", "is_latest", "fetched_at")
    list_filter = ("document_type", "is_latest", "published_date")
    search_fields = ("title", "content", "source")


@admin.register(SentimentResult)
class SentimentResultAdmin(admin.ModelAdmin):
    list_display = ("document", "label", "sentiment_score", "primary_impact", "created_at")
    list_filter = ("label", "created_at")
    search_fields = ("document__title", "primary_impact")
