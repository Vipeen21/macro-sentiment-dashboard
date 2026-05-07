from django.core.management.base import BaseCommand

from macro_sentiment.ingestion import ingest_latest_rbi_policy


class Command(BaseCommand):
    help = "Fetch the latest RBI monetary policy statement and analyze it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default="",
            help="Optional explicit RBI policy URL. Overrides auto-discovery.",
        )

    def handle(self, *args, **options):
        result = ingest_latest_rbi_policy(url=options["url"])
        status = "created" if result.created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{status}: {result.document.title} "
                f"({result.document.published_date.date()}) "
                f"sentiment_id={result.sentiment_id}"
            )
        )
