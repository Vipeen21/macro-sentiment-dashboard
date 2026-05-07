from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from pgvector.django import VectorField


class EconomicIndicator(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    value = models.DecimalField(max_digits=20, decimal_places=4)
    unit = models.CharField(max_length=50, blank=True)
    timestamp = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["timestamp", "name"]

    def __str__(self):
        unit = f" {self.unit}" if self.unit else ""
        return f"{self.name}: {self.value}{unit}"


class PolicyDocument(models.Model):
    class DocumentType(models.TextChoices):
        RBI_MONETARY_POLICY = "RBI_MONETARY_POLICY", "RBI monetary policy"
        OTHER = "OTHER", "Other"

    title = models.CharField(max_length=255)
    content = models.TextField()
    source = models.URLField(blank=True)
    published_date = models.DateTimeField(db_index=True)
    embedding = VectorField(dimensions=768, null=True, blank=True)
    document_type = models.CharField(
        max_length=40,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
        db_index=True,
    )
    is_latest = models.BooleanField(default=False, db_index=True)
    fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_date", "title"]

    def __str__(self):
        return self.title


class SentimentResult(models.Model):
    class Label(models.TextChoices):
        HAWKISH = "Hawkish", "Hawkish"
        DOVISH = "Dovish", "Dovish"
        NEUTRAL = "Neutral", "Neutral"

    document = models.OneToOneField(
        PolicyDocument,
        on_delete=models.CASCADE,
        related_name="sentiment",
    )
    sentiment_score = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)]
    )
    label = models.CharField(max_length=20, choices=Label.choices)
    primary_impact = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-document__published_date"]

    def __str__(self):
        return f"{self.document}: {self.label} ({self.sentiment_score:.2f})"
