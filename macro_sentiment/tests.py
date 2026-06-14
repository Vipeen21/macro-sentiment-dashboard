from datetime import datetime, timezone as dt_timezone

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .ingestion import _LinkParser, _policy_link_candidates
from .market_data import _rolling_annualized_volatility
from .models import PolicyDocument, SentimentResult


class IngestionParserTests(SimpleTestCase):
    def test_policy_link_candidates_prioritizes_current_full_document(self):
        page_url = "https://www.rbi.org.in/scripts/annualpolicy.aspx"
        page = """
            <div>Jun 05, 2026</div>
            <div>Resolution of the Monetary Policy Committee (MPC) June 3 to 5, 2026</div>
            <a href="/Scripts/BS_PressReleaseDisplay.aspx?prid=62863">Full Document</a>
            <a href="/Scripts/BS_PressReleaseDisplay.aspx?prid=62599">
                Minutes of the Monetary Policy Committee Meeting, April 6 to 8, 2026
            </a>
        """
        parser = _LinkParser()
        parser.feed(page)

        candidates = _policy_link_candidates(page_url, parser.links, page)

        self.assertEqual(
            candidates[0],
            "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62863",
        )


class MarketDataTests(SimpleTestCase):
    def test_rolling_annualized_volatility_returns_expected_window_count(self):
        closes = [
            (datetime(2026, 1, day, tzinfo=dt_timezone.utc), 80 + day)
            for day in range(1, 8)
        ]

        points = _rolling_annualized_volatility(closes, window=3)

        self.assertEqual(len(points), 4)
        self.assertTrue(all(value > 0 for _, value in points))


class SeedDataTests(TestCase):
    def test_seed_does_not_demote_newer_live_policy_document(self):
        live_doc = PolicyDocument.objects.create(
            title=(
                "Monetary Policy Statement, 2026-27 Resolution of the "
                "Monetary Policy Committee June 3 to 5, 2026"
            ),
            content=(
                "Date : Jun 05, 2026\n"
                "The MPC voted unanimously to keep the policy repo rate under "
                "the liquidity adjustment facility unchanged at 5.25 per cent."
            ),
            source="https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62863",
            published_date=timezone.make_aware(datetime(2026, 6, 5)),
            document_type=PolicyDocument.DocumentType.RBI_MONETARY_POLICY,
            is_latest=True,
            fetched_at=timezone.now(),
        )
        SentimentResult.objects.create(
            document=live_doc,
            sentiment_score=-0.2,
            label=SentimentResult.Label.NEUTRAL,
            primary_impact="Monetary Policy",
        )

        call_command("seed_five_year_mpc_data", verbosity=0)

        live_doc.refresh_from_db()
        self.assertTrue(live_doc.is_latest)
        self.assertEqual(
            PolicyDocument.objects.filter(
                document_type=PolicyDocument.DocumentType.RBI_MONETARY_POLICY,
                is_latest=True,
            ).count(),
            1,
        )
