"""Regression tests for digest date naming across timezone boundaries."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.agents.publish_digest import DigestFormatterAgent
from src.config.settings import Settings
from src.models.contracts import RunContext, SummaryItem


def build_summary() -> SummaryItem:
    return SummaryItem(
        url="https://example.com/story",
        title="Example story",
        summary="Example summary.",
        key_points=["point one"],
        source="Example Source",
        category="tooling",
        strategic_why="This matters for the test.",
    )


def build_context() -> RunContext:
    return RunContext(
        run_id="digest-test-run",
        start_time=datetime(2026, 5, 9, 22, 59),
        fetch_count=10,
        deduplicated_count=8,
        summarized_count=1,
        budget_spent_usd=0.01,
    )


def test_digest_uses_business_timezone_for_date_and_title(monkeypatch):
    settings = Settings(digest_tz="Asia/Hong_Kong")
    fixed_digest_now = datetime(2026, 5, 10, 7, 0, tzinfo=ZoneInfo("Asia/Hong_Kong"))

    monkeypatch.setattr("src.agents.publish_digest.get_settings", lambda: settings)
    with patch.object(Settings, "get_digest_now", return_value=fixed_digest_now):
        agent = DigestFormatterAgent()
        digest = agent._create_digest([build_summary()], build_context())

    assert digest.date == "2026-05-10"
    assert digest.title == "Daily AI and Technology Digest - 2026-05-10"


def test_settings_business_date_uses_configured_timezone(monkeypatch):
    settings = Settings(digest_tz="Asia/Hong_Kong")

    monkeypatch.setattr(
        "src.config.settings.datetime",
        type(
            "FrozenDateTime",
            (),
            {
                "now": staticmethod(lambda tz=None: datetime(2026, 5, 10, 7, 0, tzinfo=tz)),
            },
        ),
    )

    assert settings.get_digest_date_str() == "2026-05-10"