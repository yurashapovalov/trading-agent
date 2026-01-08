"""Statistics and analytics tools"""

import duckdb
import pandas as pd
from typing import Optional


def get_statistics(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_by: str = 'hour',
    db_path: str = "data/trading.duckdb"
) -> dict:
    """
    Get comprehensive statistics for a trading symbol.

    Args:
        symbol: Trading symbol (e.g. 'NQ', 'CL')
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)
        group_by: Grouping period ('hour', 'day', 'week', 'month')
        db_path: Path to database

    Returns:
        Dictionary with market statistics
    """
    db_symbol = symbol

    with duckdb.connect(db_path, read_only=True) as conn:
        # Build date filter
        date_filter = f"symbol = '{db_symbol}'"
        if start_date:
            date_filter += f" AND timestamp >= '{start_date}'"
        if end_date:
            date_filter += f" AND timestamp <= '{end_date}'"

        # Get basic info
        summary = conn.execute(f"""
            SELECT
                COUNT(*) as total_bars,
                MIN(timestamp) as start_date,
                MAX(timestamp) as end_date,
                COUNT(DISTINCT DATE(timestamp)) as trading_days,
                AVG(volume) as avg_volume,
                SUM(volume) as total_volume
            FROM ohlcv_1min
            WHERE {date_filter}
        """).df().iloc[0].to_dict()

        # Daily range statistics
        daily_stats = conn.execute(f"""
            SELECT
                DATE(timestamp) as date,
                MIN(low) as day_low,
                MAX(high) as day_high,
                MAX(high) - MIN(low) as daily_range,
                FIRST(open) as day_open,
                LAST(close) as day_close,
                SUM(volume) as day_volume
            FROM ohlcv_1min
            WHERE {date_filter}
            GROUP BY DATE(timestamp)
            ORDER BY date
        """).df()

        # Calculate daily range in ticks (CL tick = 0.01)
        tick_size = 0.01
        daily_stats['daily_range_ticks'] = (daily_stats['daily_range'] / tick_size).astype(int)

        avg_daily_range = daily_stats['daily_range'].mean()
        avg_daily_range_ticks = int(avg_daily_range / tick_size)

        # Volatility by hour
        hourly_stats = conn.execute(f"""
            SELECT
                HOUR(timestamp) as hour,
                AVG(high - low) as avg_bar_range,
                AVG(volume) as avg_volume,
                COUNT(*) as bar_count
            FROM ohlcv_1min
            WHERE {date_filter}
            GROUP BY HOUR(timestamp)
            ORDER BY hour
        """).df()

        hourly_stats['avg_range_ticks'] = (hourly_stats['avg_bar_range'] / tick_size).astype(int)

        # Find most/least volatile hours
        most_volatile_hour = hourly_stats.loc[hourly_stats['avg_range_ticks'].idxmax()]
        least_volatile_hour = hourly_stats.loc[hourly_stats['avg_range_ticks'].idxmin()]

        # Trend stats (up days vs down days)
        daily_stats['direction'] = (daily_stats['day_close'] - daily_stats['day_open']).apply(
            lambda x: 'up' if x > 0 else ('down' if x < 0 else 'flat')
        )
        direction_counts = daily_stats['direction'].value_counts().to_dict()

        # Average move size
        daily_stats['move_size'] = abs(daily_stats['day_close'] - daily_stats['day_open'])
        avg_move_ticks = int(daily_stats['move_size'].mean() / tick_size)

        return {
            "data_summary": {
                "symbol": symbol,
                "start_date": str(summary['start_date'])[:10],
                "end_date": str(summary['end_date'])[:10],
                "trading_days": int(summary['trading_days']),
                "total_bars": int(summary['total_bars']),
                "avg_volume_per_bar": round(summary['avg_volume'], 1)
            },
            "daily_range": {
                "avg_ticks": avg_daily_range_ticks,
                "avg_dollars": round(avg_daily_range, 2),
                "min_ticks": int(daily_stats['daily_range_ticks'].min()),
                "max_ticks": int(daily_stats['daily_range_ticks'].max())
            },
            "volatility_by_hour": [
                {
                    "hour": int(row['hour']),
                    "avg_range_ticks": int(row['avg_range_ticks']),
                    "avg_volume": round(row['avg_volume'], 1)
                }
                for _, row in hourly_stats.iterrows()
            ],
            "most_volatile_hour": {
                "hour": int(most_volatile_hour['hour']),
                "avg_range_ticks": int(most_volatile_hour['avg_range_ticks'])
            },
            "least_volatile_hour": {
                "hour": int(least_volatile_hour['hour']),
                "avg_range_ticks": int(least_volatile_hour['avg_range_ticks'])
            },
            "trend_stats": {
                "up_days": direction_counts.get('up', 0),
                "down_days": direction_counts.get('down', 0),
                "flat_days": direction_counts.get('flat', 0),
                "avg_move_ticks": avg_move_ticks
            },
            "daily_breakdown": [
                {
                    "date": str(row['date']),
                    "range_ticks": int(row['daily_range_ticks']),
                    "direction": row['direction'],
                    "volume": int(row['day_volume'])
                }
                for _, row in daily_stats.iterrows()
            ]
        }
