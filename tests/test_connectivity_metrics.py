#!/usr/bin/env python3
"""Tests for modules/connectivity_metrics.py — ConnectivityMetrics class.

Tests connectivity metric calculations including:
- Repeaters known (from complete_contact_tracking)
- Repeaters heard (from repeater_adverts within time window)
- Connectivity percentage calculations
- Average adverts per day calculations
- Edge cases: empty DB, 0 known, 100% connectivity
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from modules.connectivity_metrics import ConnectivityMetrics
from modules.db_manager import DBManager


@pytest.fixture
def metrics_db(mock_logger, tmp_path):
    """Create a DBManager with repeater_adverts and complete_contact_tracking tables."""
    db_path = str(tmp_path / "metrics_test.db")

    # Create a minimal bot mock for DBManager
    mock_bot = Mock()
    mock_bot.logger = mock_logger

    # Create DBManager - this runs migrations automatically
    db_manager = DBManager(mock_bot, db_path)

    return db_manager


@pytest.fixture
def metrics_bot(mock_logger, metrics_db):
    """Create a mock bot with db_manager and logger for ConnectivityMetrics."""
    bot = Mock()
    bot.logger = mock_logger
    bot.db_manager = metrics_db
    return bot


@pytest.fixture
def metrics(metrics_bot):
    """Create a ConnectivityMetrics instance for testing."""
    return ConnectivityMetrics(metrics_bot)


def insert_repeater(db_manager: DBManager, public_key: str, name: str) -> None:
    """Insert a repeater into complete_contact_tracking table."""
    db_manager.execute_update(
        "INSERT INTO complete_contact_tracking (public_key, name, role) VALUES (?, ?, 'repeater')",
        (public_key, name),
    )


def insert_advert(
    db_manager: DBManager,
    repeater_pubkey: str,
    observed_at: datetime,
    snr: float = 10.0,
    rssi: float = -80.0,
    hops: int = 1,
) -> None:
    """Insert an advertisement into repeater_adverts table."""
    observed_at_str = observed_at.strftime("%Y-%m-%d %H:%M:%S")
    db_manager.execute_update(
        "INSERT INTO repeater_adverts (repeater_pubkey, observed_at, snr, rssi, hops) VALUES (?, ?, ?, ?, ?)",
        (repeater_pubkey, observed_at_str, snr, rssi, hops),
    )


class TestGetRepeatersKnown:
    """Tests for get_repeaters_known() method."""

    def test_empty_database_returns_zero(self, metrics):
        """Empty complete_contact_tracking table returns 0."""
        result = metrics.get_repeaters_known()
        assert result == 0

    def test_single_repeater(self, metrics, metrics_bot):
        """Single repeater in database returns 1."""
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        result = metrics.get_repeaters_known()
        assert result == 1

    def test_multiple_repeaters(self, metrics, metrics_bot):
        """Multiple repeaters in database returns correct count."""
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        insert_repeater(metrics_bot.db_manager, "pubkey2", "Repeater2")
        insert_repeater(metrics_bot.db_manager, "pubkey3", "Repeater3")
        result = metrics.get_repeaters_known()
        assert result == 3

    def test_excludes_non_repeater_roles(self, metrics, metrics_bot):
        """Only counts contacts with role='repeater'."""
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        # Insert a non-repeater contact
        metrics_bot.db_manager.execute_update(
            "INSERT INTO complete_contact_tracking (public_key, name, role) VALUES (?, ?, ?)",
            ("pubkey2", "Client1", "client"),
        )
        result = metrics.get_repeaters_known()
        assert result == 1

    def test_duplicate_pubkey_counted_once(self, metrics, metrics_bot):
        """Same public_key counted only once (DISTINCT)."""
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        # Insert same pubkey again with different name (edge case)
        metrics_bot.db_manager.execute_update(
            "INSERT INTO complete_contact_tracking (public_key, name, role) VALUES (?, ?, 'repeater')",
            ("pubkey1", "Repeater1-Updated"),
        )
        result = metrics.get_repeaters_known()
        # Both rows have same pubkey, COUNT(DISTINCT) should return 1
        assert result == 1


class TestGetRepeatersHeard:
    """Tests for get_repeaters_heard() method."""

    def test_empty_database_returns_zero(self, metrics):
        """Empty repeater_adverts table returns 0."""
        result = metrics.get_repeaters_heard(hours=24)
        assert result == 0

    def test_single_recent_advert(self, metrics, metrics_bot):
        """Single advertisement within time window returns 1."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=1))
        result = metrics.get_repeaters_heard(hours=24)
        assert result == 1

    def test_multiple_repeaters_heard(self, metrics, metrics_bot):
        """Multiple repeaters with recent adverts returns correct count."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=1))
        insert_advert(metrics_bot.db_manager, "pubkey2", now - timedelta(hours=2))
        insert_advert(metrics_bot.db_manager, "pubkey3", now - timedelta(hours=3))
        result = metrics.get_repeaters_heard(hours=24)
        assert result == 3

    def test_old_adverts_excluded(self, metrics, metrics_bot):
        """Adverts outside time window are excluded."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=25))
        insert_advert(metrics_bot.db_manager, "pubkey2", now - timedelta(hours=1))
        result = metrics.get_repeaters_heard(hours=24)
        assert result == 1

    def test_multiple_adverts_same_repeater_counted_once(self, metrics, metrics_bot):
        """Multiple adverts from same repeater counted as one (DISTINCT)."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=1))
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=2))
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=3))
        result = metrics.get_repeaters_heard(hours=24)
        assert result == 1

    def test_48_hour_window(self, metrics, metrics_bot):
        """48-hour window includes adverts older than 24 hours."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=30))
        insert_advert(metrics_bot.db_manager, "pubkey2", now - timedelta(hours=1))
        result = metrics.get_repeaters_heard(hours=48)
        assert result == 2

    def test_zero_hours_returns_zero(self, metrics, metrics_bot):
        """hours=0 returns 0 (no time window)."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now)
        result = metrics.get_repeaters_heard(hours=0)
        assert result == 0

    def test_negative_hours_returns_zero(self, metrics, metrics_bot):
        """Negative hours returns 0 (invalid input)."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now)
        result = metrics.get_repeaters_heard(hours=-5)
        assert result == 0


class TestGetConnectivityPercentage:
    """Tests for get_connectivity_percentage() method."""

    def test_no_repeaters_known_returns_zero(self, metrics):
        """Zero known repeaters returns 0.0% (avoid division by zero)."""
        result = metrics.get_connectivity_percentage(hours=24)
        assert result == 0.0

    def test_all_repeaters_heard_returns_100(self, metrics, metrics_bot):
        """All known repeaters heard returns 100.0%."""
        now = datetime.now()
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        insert_repeater(metrics_bot.db_manager, "pubkey2", "Repeater2")
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=1))
        insert_advert(metrics_bot.db_manager, "pubkey2", now - timedelta(hours=1))
        result = metrics.get_connectivity_percentage(hours=24)
        assert result == 100.0

    def test_half_repeaters_heard_returns_50(self, metrics, metrics_bot):
        """Half of known repeaters heard returns 50.0%."""
        now = datetime.now()
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        insert_repeater(metrics_bot.db_manager, "pubkey2", "Repeater2")
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=1))
        result = metrics.get_connectivity_percentage(hours=24)
        assert result == 50.0

    def test_no_repeaters_heard_returns_zero(self, metrics, metrics_bot):
        """Known repeaters but none heard returns 0.0%."""
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        insert_repeater(metrics_bot.db_manager, "pubkey2", "Repeater2")
        result = metrics.get_connectivity_percentage(hours=24)
        assert result == 0.0

    def test_fractional_percentage(self, metrics, metrics_bot):
        """Non-round percentage calculated correctly."""
        now = datetime.now()
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        insert_repeater(metrics_bot.db_manager, "pubkey2", "Repeater2")
        insert_repeater(metrics_bot.db_manager, "pubkey3", "Repeater3")
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=1))
        result = metrics.get_connectivity_percentage(hours=24)
        # 1/3 = 33.333...%
        assert abs(result - 33.333333) < 0.001

    def test_heard_more_than_known_over_100(self, metrics, metrics_bot):
        """Heard repeaters not in known list can cause >100% (edge case)."""
        now = datetime.now()
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        # Insert adverts for pubkey1 and pubkey2 (pubkey2 not in known list)
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=1))
        insert_advert(metrics_bot.db_manager, "pubkey2", now - timedelta(hours=1))
        result = metrics.get_connectivity_percentage(hours=24)
        # 2 heard / 1 known = 200%
        assert result == 200.0


class TestGetAvgAdvertsPerDay:
    """Tests for get_avg_adverts_per_day() method."""

    def test_empty_database_returns_zero(self, metrics):
        """Empty repeater_adverts table returns 0.0."""
        result = metrics.get_avg_adverts_per_day(days=7)
        assert result == 0.0

    def test_single_advert_over_7_days(self, metrics, metrics_bot):
        """Single advertisement over 7 days returns 1/7."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(days=1))
        result = metrics.get_avg_adverts_per_day(days=7)
        assert abs(result - (1 / 7)) < 0.001

    def test_multiple_adverts_per_day(self, metrics, metrics_bot):
        """Multiple adverts in 1-day window returns correct average."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=1))
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=2))
        insert_advert(metrics_bot.db_manager, "pubkey2", now - timedelta(hours=3))
        result = metrics.get_avg_adverts_per_day(days=1)
        assert result == 3.0

    def test_adverts_outside_window_excluded(self, metrics, metrics_bot):
        """Adverts outside the day window are excluded."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(days=1))
        insert_advert(metrics_bot.db_manager, "pubkey2", now - timedelta(days=10))
        result = metrics.get_avg_adverts_per_day(days=7)
        # Only 1 advert in 7-day window
        assert abs(result - (1 / 7)) < 0.001

    def test_zero_days_returns_zero(self, metrics, metrics_bot):
        """days=0 returns 0.0 (invalid input)."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now)
        result = metrics.get_avg_adverts_per_day(days=0)
        assert result == 0.0

    def test_negative_days_returns_zero(self, metrics, metrics_bot):
        """Negative days returns 0.0 (invalid input)."""
        now = datetime.now()
        insert_advert(metrics_bot.db_manager, "pubkey1", now)
        result = metrics.get_avg_adverts_per_day(days=-5)
        assert result == 0.0


class TestGetSummary:
    """Tests for get_summary() method."""

    def test_empty_database_summary(self, metrics):
        """Summary with empty database returns all zeros."""
        result = metrics.get_summary(hours=24)
        assert result["repeaters_known"] == 0
        assert result["repeaters_heard"] == 0
        assert result["connectivity_pct"] == 0.0
        assert result["avg_adverts_per_day"] == 0.0
        assert result["hours_window"] == 24

    def test_populated_database_summary(self, metrics, metrics_bot):
        """Summary with populated database returns correct values."""
        now = datetime.now()
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        insert_repeater(metrics_bot.db_manager, "pubkey2", "Repeater2")
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=1))
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=2))

        result = metrics.get_summary(hours=24)
        assert result["repeaters_known"] == 2
        assert result["repeaters_heard"] == 1
        assert result["connectivity_pct"] == 50.0
        assert result["hours_window"] == 24
        # avg_adverts_per_day calculated over 7 days, 2 adverts in window
        assert result["avg_adverts_per_day"] == 2 / 7

    def test_custom_hours_window(self, metrics, metrics_bot):
        """Summary respects custom hours parameter."""
        now = datetime.now()
        insert_repeater(metrics_bot.db_manager, "pubkey1", "Repeater1")
        insert_advert(metrics_bot.db_manager, "pubkey1", now - timedelta(hours=30))

        # 24-hour window should not see 30-hour-old advert
        result_24 = metrics.get_summary(hours=24)
        assert result_24["repeaters_heard"] == 0
        assert result_24["hours_window"] == 24

        # 48-hour window should see it
        result_48 = metrics.get_summary(hours=48)
        assert result_48["repeaters_heard"] == 1
        assert result_48["hours_window"] == 48


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_db_query_error_returns_zero(self, mock_logger):
        """Database query error returns 0 and logs error."""
        bot = Mock()
        bot.logger = mock_logger
        # Create a db_manager that raises exceptions
        bot.db_manager = Mock()
        bot.db_manager.execute_query = Mock(side_effect=Exception("Database error"))

        metrics = ConnectivityMetrics(bot)

        assert metrics.get_repeaters_known() == 0
        assert metrics.get_repeaters_heard(hours=24) == 0
        assert metrics.get_avg_adverts_per_day(days=7) == 0.0
        # Connectivity percentage also returns 0 when known is 0
        assert metrics.get_connectivity_percentage(hours=24) == 0.0

        # Verify errors were logged
        assert mock_logger.error.call_count >= 3
