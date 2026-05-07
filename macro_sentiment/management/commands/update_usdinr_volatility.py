from django.core.management.base import BaseCommand

from macro_sentiment.market_data import update_usdinr_volatility


class Command(BaseCommand):
    help = "Fetch live USD-INR market data and store rolling exchange-rate volatility."

    def add_arguments(self, parser):
        parser.add_argument("--years", type=int, default=5)
        parser.add_argument("--window", type=int, default=20)

    def handle(self, *args, **options):
        count = update_usdinr_volatility(
            years=options["years"],
            window=options["window"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Stored {count} live USD-INR rolling volatility observations."
            )
        )
