"""Smart data analysis tool with automatic date handling"""

import duckdb
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Literal
from data import get_data_info


def _get_data_boundaries(symbol: str, db_path: str = None) -> dict:
    """Get min/max dates for a symbol in the database."""
    import config
    if db_path is None:
        db_path = config.DATABASE_PATH
    with duckdb.connect(db_path, read_only=True) as conn:
        result = conn.execute("""
            SELECT
                MIN(timestamp) as min_date,
                MAX(timestamp) as max_date,
                COUNT(*) as total_bars
            FROM ohlcv_1min
            WHERE symbol = ?
        """, [symbol]).fetchone()

        if result and result[0]:
            return {
                "min_date": result[0],
                "max_date": result[1],
                "total_bars": result[2]
            }
        return {"min_date": None, "max_date": None, "total_bars": 0}


def _resolve_period(period: str, symbol: str, db_path: str = None) -> tuple:
    """
    Resolve period string to actual date range based on available data.

    Returns (start_date, end_date) as datetime objects.
    """
    import config
    if db_path is None:
        db_path = config.DATABASE_PATH
    boundaries = _get_data_boundaries(symbol, db_path)

    if not boundaries["max_date"]:
        raise ValueError(f"No data available for symbol {symbol}")

    # Use the latest data date as "today" reference
    data_end = boundaries["max_date"]
    data_start = boundaries["min_date"]

    # Parse period
    period_lower = period.lower().strip()

    # Exact date range: "2025-01-01 to 2025-01-31"
    if " to " in period_lower:
        parts = period.split(" to ")
        start = datetime.strptime(parts[0].strip(), "%Y-%m-%d")
        end = datetime.strptime(parts[1].strip(), "%Y-%m-%d")
        return (start, end)

    # Relative periods
    if period_lower in ["today", "сегодня"]:
        start = data_end.replace(hour=0, minute=0, second=0)
        end = data_end
    elif period_lower in ["yesterday", "вчера"]:
        yesterday = data_end - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0)
        end = yesterday.replace(hour=23, minute=59, second=59)
    elif period_lower in ["last_week", "последняя_неделя", "прошлая неделя"]:
        start = data_end - timedelta(days=7)
        end = data_end
    elif period_lower in ["last_month", "последний_месяц", "прошлый месяц"]:
        start = data_end - timedelta(days=30)
        end = data_end
    elif period_lower in ["last_3_months", "последние_3_месяца"]:
        start = data_end - timedelta(days=90)
        end = data_end
    elif period_lower in ["last_year", "последний_год", "прошлый год"]:
        start = data_end - timedelta(days=365)
        end = data_end
    elif period_lower in ["all", "все", "all_time"]:
        start = data_start
        end = data_end
    else:
        # Try to parse as number of days
        try:
            days = int(period_lower.replace("d", "").replace("days", "").replace("дней", "").strip())
            start = data_end - timedelta(days=days)
            end = data_end
        except:
            raise ValueError(f"Unknown period: {period}. Use: today, yesterday, last_week, last_month, last_3_months, last_year, all, or 'YYYY-MM-DD to YYYY-MM-DD'")

    # Clamp to available data range
    start = max(start, data_start)
    end = min(end, data_end)

    return (start, end)


def analyze_data(
    symbol: str,
    period: str = "last_month",
    analysis: str = "summary",
    group_by: str = "day",
    db_path: str = None
) -> dict:
    """
    Analyze trading data with automatic date handling.

    Args:
        symbol: Trading symbol (NQ, ES, CL)
        period: Time period - "today", "yesterday", "last_week", "last_month",
                "last_3_months", "last_year", "all", or "YYYY-MM-DD to YYYY-MM-DD"
        analysis: Type of analysis:
            - "summary": Overview with key stats
            - "daily": Daily breakdown (range, volume, open, close)
            - "anomalies": Find unusual days (high volatility, volume spikes)
            - "hourly": Hourly volatility pattern
            - "trend": Price trend and momentum
        group_by: Grouping for breakdown ("hour", "day", "week")
        db_path: Path to database

    Returns:
        dict with analysis results and metadata
    """
    import config
    if db_path is None:
        db_path = config.DATABASE_PATH
    # Resolve period to actual dates
    start_date, end_date = _resolve_period(period, symbol, db_path)

    result = {
        "symbol": symbol,
        "period": period,
        "actual_range": {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "days": (end_date - start_date).days
        },
        "analysis_type": analysis
    }

    with duckdb.connect(db_path, read_only=True) as conn:

        if analysis == "summary":
            # Overall summary stats
            summary = conn.execute("""
                SELECT
                    COUNT(*) as total_bars,
                    COUNT(DISTINCT DATE(timestamp)) as trading_days,
                    MIN(low) as period_low,
                    MAX(high) as period_high,
                    MAX(high) - MIN(low) as total_range,
                    AVG(volume) as avg_volume,
                    SUM(volume) as total_volume
                FROM ohlcv_1min
                WHERE symbol = ?
                    AND timestamp >= ?
                    AND timestamp <= ?
            """, [symbol, start_date, end_date]).fetchone()

            # Daily stats
            daily = conn.execute("""
                SELECT
                    AVG(daily_range) as avg_daily_range,
                    MAX(daily_range) as max_daily_range,
                    MIN(daily_range) as min_daily_range,
                    AVG(daily_volume) as avg_daily_volume
                FROM (
                    SELECT
                        DATE(timestamp) as date,
                        MAX(high) - MIN(low) as daily_range,
                        SUM(volume) as daily_volume
                    FROM ohlcv_1min
                    WHERE symbol = ?
                        AND timestamp >= ?
                        AND timestamp <= ?
                    GROUP BY DATE(timestamp)
                )
            """, [symbol, start_date, end_date]).fetchone()

            result["summary"] = {
                "total_bars": summary[0],
                "trading_days": summary[1],
                "period_low": summary[2],
                "period_high": summary[3],
                "total_range": summary[4],
                "avg_bar_volume": round(summary[5], 0) if summary[5] else 0,
                "total_volume": summary[6],
                "avg_daily_range": round(daily[0], 2) if daily[0] else 0,
                "max_daily_range": daily[1],
                "min_daily_range": daily[2],
                "avg_daily_volume": round(daily[3], 0) if daily[3] else 0
            }

        elif analysis == "daily":
            # Get total count first
            total_days = conn.execute("""
                SELECT COUNT(DISTINCT DATE(timestamp))
                FROM ohlcv_1min
                WHERE symbol = ?
                    AND timestamp >= ?
                    AND timestamp <= ?
            """, [symbol, start_date, end_date]).fetchone()[0]

            # Daily breakdown - limit to last 30 days to save tokens
            df = conn.execute("""
                SELECT
                    DATE(timestamp) as date,
                    FIRST(open) as open,
                    MAX(high) as high,
                    MIN(low) as low,
                    LAST(close) as close,
                    MAX(high) - MIN(low) as range,
                    SUM(volume) as volume
                FROM ohlcv_1min
                WHERE symbol = ?
                    AND timestamp >= ?
                    AND timestamp <= ?
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                LIMIT 30
            """, [symbol, start_date, end_date]).df()

            result["total_days_in_period"] = total_days
            result["showing"] = len(df)
            result["data"] = df.to_dict('records')
            if total_days > 30:
                result["hint"] = f"Показаны последние 30 из {total_days} дней. Укажи конкретный период 'YYYY-MM-DD to YYYY-MM-DD' для других дат."

        elif analysis == "anomalies":
            # Find anomalies - days with unusual range or volume
            # First get baseline stats
            baseline = conn.execute("""
                SELECT
                    AVG(daily_range) as avg_range,
                    STDDEV(daily_range) as std_range,
                    AVG(daily_volume) as avg_volume,
                    STDDEV(daily_volume) as std_volume
                FROM (
                    SELECT
                        DATE(timestamp) as date,
                        MAX(high) - MIN(low) as daily_range,
                        SUM(volume) as daily_volume
                    FROM ohlcv_1min
                    WHERE symbol = ?
                        AND timestamp >= ?
                        AND timestamp <= ?
                    GROUP BY DATE(timestamp)
                )
            """, [symbol, start_date, end_date]).fetchone()

            avg_range, std_range, avg_volume, std_volume = baseline

            # Threshold: 2 standard deviations above mean
            range_threshold = avg_range + 2 * std_range if std_range else avg_range * 2
            volume_threshold = avg_volume + 2 * std_volume if std_volume else avg_volume * 2

            # Find anomaly days - limit to top 15 most significant
            df = conn.execute("""
                SELECT
                    DATE(timestamp) as date,
                    MAX(high) - MIN(low) as range,
                    SUM(volume) as volume,
                    CASE
                        WHEN MAX(high) - MIN(low) > ? THEN 'high_volatility'
                        WHEN SUM(volume) > ? THEN 'high_volume'
                        ELSE 'normal'
                    END as anomaly_type
                FROM ohlcv_1min
                WHERE symbol = ?
                    AND timestamp >= ?
                    AND timestamp <= ?
                GROUP BY DATE(timestamp)
                HAVING anomaly_type != 'normal'
                ORDER BY range DESC
                LIMIT 15
            """, [range_threshold, volume_threshold, symbol, start_date, end_date]).df()

            # Get total count of anomalies
            total_anomalies = conn.execute("""
                SELECT COUNT(*) FROM (
                    SELECT DATE(timestamp) as date
                    FROM ohlcv_1min
                    WHERE symbol = ?
                        AND timestamp >= ?
                        AND timestamp <= ?
                    GROUP BY DATE(timestamp)
                    HAVING MAX(high) - MIN(low) > ? OR SUM(volume) > ?
                )
            """, [symbol, start_date, end_date, range_threshold, volume_threshold]).fetchone()[0]

            result["baseline"] = {
                "avg_daily_range": round(avg_range, 2) if avg_range else 0,
                "range_threshold": round(range_threshold, 2) if range_threshold else 0,
                "avg_daily_volume": round(avg_volume, 0) if avg_volume else 0
            }
            result["total_anomalies"] = total_anomalies
            result["showing"] = len(df)
            result["anomalies"] = df.to_dict('records')

        elif analysis == "hourly":
            # Hourly volatility pattern
            df = conn.execute("""
                SELECT
                    HOUR(timestamp) as hour,
                    AVG(high - low) as avg_bar_range,
                    AVG(volume) as avg_volume,
                    COUNT(*) as sample_size
                FROM ohlcv_1min
                WHERE symbol = ?
                    AND timestamp >= ?
                    AND timestamp <= ?
                GROUP BY HOUR(timestamp)
                ORDER BY hour
            """, [symbol, start_date, end_date]).df()

            result["hourly_pattern"] = df.to_dict('records')

        elif analysis == "trend":
            # Price trend analysis
            trend = conn.execute("""
                SELECT
                    FIRST(open) as period_open,
                    LAST(close) as period_close,
                    MAX(high) as period_high,
                    MIN(low) as period_low
                FROM ohlcv_1min
                WHERE symbol = ?
                    AND timestamp >= ?
                    AND timestamp <= ?
            """, [symbol, start_date, end_date]).fetchone()

            period_open, period_close = trend[0], trend[1]
            change = period_close - period_open
            change_pct = (change / period_open * 100) if period_open else 0

            # Daily trend
            daily_df = conn.execute("""
                SELECT
                    DATE(timestamp) as date,
                    LAST(close) - FIRST(open) as daily_change
                FROM ohlcv_1min
                WHERE symbol = ?
                    AND timestamp >= ?
                    AND timestamp <= ?
                GROUP BY DATE(timestamp)
            """, [symbol, start_date, end_date]).df()

            up_days = len(daily_df[daily_df['daily_change'] > 0])
            down_days = len(daily_df[daily_df['daily_change'] < 0])

            result["trend"] = {
                "period_open": period_open,
                "period_close": period_close,
                "period_high": trend[2],
                "period_low": trend[3],
                "change": round(change, 2),
                "change_percent": round(change_pct, 2),
                "direction": "up" if change > 0 else "down" if change < 0 else "flat",
                "up_days": up_days,
                "down_days": down_days,
                "up_ratio": round(up_days / (up_days + down_days) * 100, 1) if (up_days + down_days) > 0 else 0
            }

    return result
