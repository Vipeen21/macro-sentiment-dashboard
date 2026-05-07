from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from macro_sentiment.models import EconomicIndicator, PolicyDocument, SentimentResult


MPC_SERIES = [
    ("2021-06-18", "June 2 to 4, 2021", 4.00, -0.70, "Dovish", "Growth support", 3.1),
    ("2021-08-20", "August 4 to 6, 2021", 4.00, -0.65, "Dovish", "Growth support", 3.3),
    ("2021-10-22", "October 6 to 8, 2021", 4.00, -0.50, "Dovish", "Liquidity normalization", 3.6),
    ("2021-12-22", "December 6 to 8, 2021", 4.00, -0.45, "Dovish", "Growth-inflation balance", 3.8),
    ("2022-02-24", "February 8 to 10, 2022", 4.00, -0.35, "Dovish", "Growth support", 4.0),
    ("2022-04-22", "April 6 to 8, 2022", 4.00, 0.15, "Neutral", "Inflation vigilance", 4.8),
    ("2022-05-18", "May 2 and 4, 2022", 4.40, 0.75, "Hawkish", "Inflation control", 6.9),
    ("2022-06-22", "June 6 to 8, 2022", 4.90, 0.85, "Hawkish", "Inflation control", 7.4),
    ("2022-08-19", "August 3 to 5, 2022", 5.40, 0.80, "Hawkish", "Inflation control", 7.1),
    ("2022-10-14", "September 28 to 30, 2022", 5.90, 0.82, "Hawkish", "Inflation control", 7.6),
    ("2022-12-21", "December 5 to 7, 2022", 6.25, 0.65, "Hawkish", "Inflation moderation", 6.8),
    ("2023-02-22", "February 6 to 8, 2023", 6.50, 0.60, "Hawkish", "Inflation anchoring", 6.2),
    ("2023-04-20", "April 3, 5 and 6, 2023", 6.50, 0.20, "Neutral", "Growth-inflation balance", 5.5),
    ("2023-06-22", "June 6 to 8, 2023", 6.50, 0.15, "Neutral", "Inflation vigilance", 5.0),
    ("2023-08-24", "August 8 to 10, 2023", 6.50, 0.25, "Neutral", "Food inflation", 5.7),
    ("2023-10-20", "October 4 to 6, 2023", 6.50, 0.30, "Neutral", "Inflation vigilance", 5.4),
    ("2023-12-22", "December 6 to 8, 2023", 6.50, 0.25, "Neutral", "Disinflation", 4.9),
    ("2024-02-22", "February 6 to 8, 2024", 6.50, 0.20, "Neutral", "Inflation vigilance", 4.7),
    ("2024-04-19", "April 3 to 5, 2024", 6.50, 0.18, "Neutral", "Inflation vigilance", 4.8),
    ("2024-06-21", "June 5 to 7, 2024", 6.50, 0.15, "Neutral", "Growth-inflation balance", 4.6),
    ("2024-08-22", "August 6 to 8, 2024", 6.50, 0.18, "Neutral", "Inflation vigilance", 4.9),
    ("2024-10-23", "October 7 to 9, 2024", 6.50, 0.10, "Neutral", "Neutral stance", 4.5),
    ("2024-12-20", "December 4 to 6, 2024", 6.50, 0.05, "Neutral", "Liquidity conditions", 4.4),
    ("2025-02-21", "February 5 to 7, 2025", 6.25, -0.45, "Dovish", "Growth support", 4.2),
    ("2025-04-23", "April 7 to 9, 2025", 6.00, -0.50, "Dovish", "Growth support", 4.1),
    ("2025-06-20", "June 4 to 6, 2025", 5.50, -0.60, "Dovish", "Growth support", 4.6),
    ("2025-08-20", "August 4 to 6, 2025", 5.50, -0.10, "Neutral", "Growth-inflation balance", 4.3),
    ("2025-10-15", "September 29, 30 and October 1, 2025", 5.50, -0.05, "Neutral", "Monetary policy stance", 4.5),
    ("2025-12-19", "December 3 to 5, 2025", 5.25, -0.55, "Dovish", "Growth support", 4.7),
    ("2026-02-20", "February 4 to 6, 2026", 5.25, 0.05, "Neutral", "Growth-inflation balance", 4.3),
    ("2026-04-22", "April 6 to 8, 2026", 5.25, 0.35, "Hawkish", "Inflation and energy-price risk", 5.2),
]


class Command(BaseCommand):
    help = "Seed a five-year MPC sentiment/rate series and matching exchange-rate volatility proxy."

    def handle(self, *args, **options):
        doc_type = PolicyDocument.DocumentType.RBI_MONETARY_POLICY
        latest_date = MPC_SERIES[-1][0]
        policy_dates = set()

        for date, meeting, repo_rate, score, label, impact, volatility in MPC_SERIES:
            published_date = timezone.make_aware(datetime.strptime(date, "%Y-%m-%d"))
            policy_dates.add(published_date.date())
            is_latest = date == latest_date
            title = f"Minutes of the Monetary Policy Committee Meeting, {meeting}"
            content = (
                f"Date : {published_date.strftime('%b %d, %Y')}\n"
                f"{title}\n"
                "The Monetary Policy Committee reviewed domestic and global "
                "macroeconomic conditions, inflation, growth, liquidity, and financial "
                "market developments.\n"
                f"Voting on the Resolution to keep policy repo rate unchanged at "
                f"{repo_rate:.2f} per cent.\n"
                f"The policy repo rate under the liquidity adjustment facility is "
                f"{repo_rate:.2f} per cent.\n"
                f"Primary policy theme: {impact}."
            )

            doc = PolicyDocument.objects.filter(title=title).first()
            if doc and is_latest and "rbi.org.in/Scripts/BS_PressReleaseDisplay" in doc.source:
                doc.published_date = published_date
                doc.document_type = doc_type
                doc.is_latest = True
                doc.fetched_at = timezone.now()
                doc.save(
                    update_fields=[
                        "published_date",
                        "document_type",
                        "is_latest",
                        "fetched_at",
                    ]
                )
            else:
                doc, _ = PolicyDocument.objects.update_or_create(
                    title=title,
                    defaults={
                        "content": content,
                        "source": "https://www.rbi.org.in/scripts/annualpolicy.aspx",
                        "published_date": published_date,
                        "document_type": doc_type,
                        "is_latest": is_latest,
                        "fetched_at": timezone.now(),
                    },
                )

            SentimentResult.objects.update_or_create(
                document=doc,
                defaults={
                    "sentiment_score": score,
                    "label": label,
                    "primary_impact": impact,
                },
            )

            EconomicIndicator.objects.update_or_create(
                name="Exchange Rate Volatility",
                timestamp=published_date,
                defaults={
                    "value": Decimal(str(volatility)),
                    "unit": "proxy index",
                },
            )

        for indicator in EconomicIndicator.objects.filter(name="Exchange Rate Volatility"):
            if indicator.timestamp.date() not in policy_dates:
                indicator.delete()

        PolicyDocument.objects.filter(document_type=doc_type).exclude(
            title__in=[f"Minutes of the Monetary Policy Committee Meeting, {row[1]}" for row in MPC_SERIES]
        ).update(is_latest=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(MPC_SERIES)} MPC observations and volatility points."
            )
        )
