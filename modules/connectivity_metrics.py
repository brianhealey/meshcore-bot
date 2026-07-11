#!/usr/bin/env python3
"""
Connectivity Metrics Module

Provides functions to calculate mesh network connectivity statistics based on
repeater observations stored in the database. Uses the complete_contact_tracking
table for known repeaters and repeater_adverts table for advertisement observations.

Key metrics:
    - Repeaters known: Total repeaters in contact database
    - Repeaters heard: Repeaters that have advertised within a time window
    - Connectivity percentage: Ratio of heard to known repeaters
    - Average adverts per day: Mean advertisement frequency

Usage:
    metrics = ConnectivityMetrics(bot)
    known = metrics.get_repeaters_known()
    heard_24h = metrics.get_repeaters_heard(hours=24)
    pct = metrics.get_connectivity_percentage(hours=24)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from logging import Logger

    from .db_manager import DBManager


class ConnectivityMetrics:
    """Calculator for mesh network connectivity statistics.

    This class queries the database to compute metrics about the health
    and reachability of the mesh network based on repeater advertisements.

    Attributes:
        db_manager: Database manager instance for executing queries.
        logger: Logger instance for diagnostic output.
    """

    def __init__(self, bot: Any) -> None:
        """Initialize connectivity metrics calculator.

        Args:
            bot: Bot instance with db_manager and logger attributes.
        """
        self.db_manager: DBManager = bot.db_manager
        self.logger: Logger = bot.logger

    def get_repeaters_known(self) -> int:
        """Count total repeaters known in the contact database.

        Queries the complete_contact_tracking table for contacts with
        role='repeater'. This represents the total set of repeaters
        the bot has ever observed.

        Returns:
            Number of unique repeaters in the contact database.
            Returns 0 if query fails or no repeaters found.

        Example:
            >>> metrics = ConnectivityMetrics(bot)
            >>> known = metrics.get_repeaters_known()
            >>> print(f"We know about {known} repeaters")
        """
        try:
            result = self.db_manager.execute_query(
                "SELECT COUNT(DISTINCT public_key) as count "
                "FROM complete_contact_tracking "
                "WHERE role = 'repeater'"
            )
            if result and len(result) > 0:
                return int(result[0].get("count", 0))
            return 0
        except Exception as e:
            self.logger.error(f"[CONN_METRICS] Error getting known repeaters: {e}")
            return 0

    def get_repeaters_heard(self, hours: int = 24) -> int:
        """Count repeaters that have advertised within a time window.

        Queries the repeater_adverts table for unique repeaters that
        have sent advertisements within the specified number of hours.

        Args:
            hours: Time window in hours to look back for advertisements.
                   Must be positive. Default is 24 hours.

        Returns:
            Number of unique repeaters heard within the time window.
            Returns 0 if query fails, no adverts found, or hours <= 0.

        Example:
            >>> metrics = ConnectivityMetrics(bot)
            >>> heard_24h = metrics.get_repeaters_heard(hours=24)
            >>> heard_48h = metrics.get_repeaters_heard(hours=48)
            >>> print(f"Heard {heard_24h} in 24h, {heard_48h} in 48h")
        """
        if hours <= 0:
            return 0

        try:
            # Calculate cutoff timestamp
            cutoff = datetime.now() - timedelta(hours=hours)
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

            result = self.db_manager.execute_query(
                "SELECT COUNT(DISTINCT repeater_pubkey) as count "
                "FROM repeater_adverts "
                "WHERE observed_at >= ?",
                (cutoff_str,),
            )
            if result and len(result) > 0:
                return int(result[0].get("count", 0))
            return 0
        except Exception as e:
            self.logger.error(f"[CONN_METRICS] Error getting repeaters heard: {e}")
            return 0

    def get_connectivity_percentage(self, hours: int = 24) -> float:
        """Calculate the percentage of known repeaters that have been heard.

        Computes (repeaters heard / repeaters known) * 100 for the given
        time window. This metric indicates what fraction of the known
        mesh network is currently reachable.

        Args:
            hours: Time window in hours for the "heard" calculation.
                   Must be positive. Default is 24 hours.

        Returns:
            Connectivity percentage from 0.0 to 100.0.
            Returns 0.0 if no repeaters are known or query fails.
            Returns 100.0 if all known repeaters have been heard.

        Example:
            >>> metrics = ConnectivityMetrics(bot)
            >>> pct = metrics.get_connectivity_percentage(hours=24)
            >>> print(f"Mesh connectivity: {pct:.1f}%")
        """
        known = self.get_repeaters_known()
        if known == 0:
            return 0.0

        heard = self.get_repeaters_heard(hours=hours)
        return (heard / known) * 100.0

    def get_avg_adverts_per_day(self, days: int = 7) -> float:
        """Calculate average advertisements per day over a period.

        Queries the repeater_adverts table to count total advertisements
        in the specified day window, then divides by the number of days.

        Args:
            days: Number of days to include in the average calculation.
                  Must be positive. Default is 7 days.

        Returns:
            Average number of advertisements received per day.
            Returns 0.0 if query fails or days <= 0.

        Example:
            >>> metrics = ConnectivityMetrics(bot)
            >>> avg = metrics.get_avg_adverts_per_day(days=7)
            >>> print(f"Average {avg:.1f} advertisements per day")
        """
        if days <= 0:
            return 0.0

        try:
            # Calculate cutoff timestamp
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

            result = self.db_manager.execute_query(
                "SELECT COUNT(*) as count FROM repeater_adverts WHERE observed_at >= ?",
                (cutoff_str,),
            )
            if result and len(result) > 0:
                total_adverts = int(result[0].get("count", 0))
                return total_adverts / days
            return 0.0
        except Exception as e:
            self.logger.error(f"[CONN_METRICS] Error getting avg adverts/day: {e}")
            return 0.0

    def get_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get a complete summary of connectivity metrics.

        Convenience method that gathers all metrics into a single dictionary,
        useful for reporting or display purposes.

        Args:
            hours: Time window for heard/connectivity calculations.
                   Default is 24 hours.

        Returns:
            Dictionary with keys:
                - repeaters_known: Total repeaters in database
                - repeaters_heard: Repeaters heard in time window
                - connectivity_pct: Percentage connectivity
                - avg_adverts_per_day: 7-day average adverts/day
                - hours_window: The time window used

        Example:
            >>> metrics = ConnectivityMetrics(bot)
            >>> summary = metrics.get_summary(hours=48)
            >>> print(f"Known: {summary['repeaters_known']}")
        """
        return {
            "repeaters_known": self.get_repeaters_known(),
            "repeaters_heard": self.get_repeaters_heard(hours=hours),
            "connectivity_pct": self.get_connectivity_percentage(hours=hours),
            "avg_adverts_per_day": self.get_avg_adverts_per_day(days=7),
            "hours_window": hours,
        }
