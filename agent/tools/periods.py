"""Find market periods by condition (trend, volatility, etc.)"""

import duckdb
from typing import Optional, List
from dataclasses import dataclass, asdict


@dataclass
class MarketPeriod:
    """A period of market with specific characteristics"""
    start_date: str
    end_date: str
    days: int
    condition: str
    description: str
    metrics: dict


def find_market_periods(
    symbol: str,
    condition: str,
    min_days: int = 5,
    db_path: str = None
) -> List[dict]:
    """
    Find periods in the market that match a specific condition.

    Args:
        symbol: Trading symbol (NQ, ES, CL)
        condition: Type of market condition to find:
            - "uptrend": Periods where price is rising
            - "downtrend": Periods where price is falling
            - "sideways": Low directional movement
            - "high_volatility": Periods with above-average daily ranges
            - "low_volatility": Periods with below-average daily ranges
        min_days: Minimum consecutive days to consider a period (default: 5)
        db_path: Path to database

    Returns:
        List of periods matching the condition with start/end dates and metrics
    """
    import config
    if db_path is None:
        db_path = config.DATABASE_PATH
    with duckdb.connect(db_path, read_only=True) as conn:
        # Get daily data
        daily_df = conn.execute(f"""
            SELECT
                DATE(timestamp) as date,
                FIRST(open) as open,
                LAST(close) as close,
                MAX(high) as high,
                MIN(low) as low,
                MAX(high) - MIN(low) as range,
                SUM(volume) as volume
            FROM ohlcv_1min
            WHERE symbol = '{symbol}'
            GROUP BY DATE(timestamp)
            ORDER BY date
        """).df()

        if daily_df.empty:
            return [{"error": f"No data found for {symbol}"}]

        # Calculate metrics
        daily_df['change'] = daily_df['close'] - daily_df['open']
        daily_df['change_pct'] = (daily_df['change'] / daily_df['open'] * 100).round(2)

        avg_range = daily_df['range'].mean()
        std_range = daily_df['range'].std()

        # Define condition logic
        if condition == "uptrend":
            # Day is bullish if close > open
            daily_df['matches'] = daily_df['change'] > 0
        elif condition == "downtrend":
            # Day is bearish if close < open
            daily_df['matches'] = daily_df['change'] < 0
        elif condition == "sideways":
            # Low change percentage (less than 0.3%)
            daily_df['matches'] = abs(daily_df['change_pct']) < 0.3
        elif condition == "high_volatility":
            # Range above average + 0.5 std
            threshold = avg_range + 0.5 * std_range
            daily_df['matches'] = daily_df['range'] > threshold
        elif condition == "low_volatility":
            # Range below average - 0.5 std
            threshold = avg_range - 0.5 * std_range
            daily_df['matches'] = daily_df['range'] < threshold
        else:
            return [{"error": f"Unknown condition: {condition}. Use: uptrend, downtrend, sideways, high_volatility, low_volatility"}]

        # Find consecutive periods
        periods = []
        current_period = None

        for idx, row in daily_df.iterrows():
            if row['matches']:
                if current_period is None:
                    current_period = {
                        'start_idx': idx,
                        'start_date': row['date'],
                        'start_price': row['open'],
                        'days': 1,
                        'total_change': row['change'],
                        'total_range': row['range'],
                        'total_volume': row['volume']
                    }
                else:
                    current_period['days'] += 1
                    current_period['end_date'] = row['date']
                    current_period['end_price'] = row['close']
                    current_period['total_change'] += row['change']
                    current_period['total_range'] += row['range']
                    current_period['total_volume'] += row['volume']
            else:
                if current_period is not None and current_period['days'] >= min_days:
                    # Finalize period
                    if 'end_date' not in current_period:
                        current_period['end_date'] = current_period['start_date']
                        current_period['end_price'] = daily_df.loc[current_period['start_idx'], 'close']

                    change_pct = ((current_period['end_price'] - current_period['start_price']) /
                                  current_period['start_price'] * 100)

                    period = MarketPeriod(
                        start_date=str(current_period['start_date']),
                        end_date=str(current_period['end_date']),
                        days=current_period['days'],
                        condition=condition,
                        description=_get_description(condition, change_pct, current_period),
                        metrics={
                            'price_change': round(current_period['end_price'] - current_period['start_price'], 2),
                            'price_change_pct': round(change_pct, 2),
                            'avg_daily_range': round(current_period['total_range'] / current_period['days'], 2),
                            'total_volume': int(current_period['total_volume'])
                        }
                    )
                    periods.append(asdict(period))
                current_period = None

        # Don't forget the last period
        if current_period is not None and current_period['days'] >= min_days:
            if 'end_date' not in current_period:
                current_period['end_date'] = current_period['start_date']
                current_period['end_price'] = daily_df.loc[current_period['start_idx'], 'close']

            change_pct = ((current_period['end_price'] - current_period['start_price']) /
                          current_period['start_price'] * 100)

            period = MarketPeriod(
                start_date=str(current_period['start_date']),
                end_date=str(current_period['end_date']),
                days=current_period['days'],
                condition=condition,
                description=_get_description(condition, change_pct, current_period),
                metrics={
                    'price_change': round(current_period['end_price'] - current_period['start_price'], 2),
                    'price_change_pct': round(change_pct, 2),
                    'avg_daily_range': round(current_period['total_range'] / current_period['days'], 2),
                    'total_volume': int(current_period['total_volume'])
                }
            )
            periods.append(asdict(period))

        # Sort by days descending (longest periods first)
        periods.sort(key=lambda x: x['days'], reverse=True)

        if not periods:
            return [{
                "message": f"No {condition} periods found with at least {min_days} consecutive days",
                "suggestion": f"Try reducing min_days or use a different condition"
            }]

        # Add summary
        result = {
            "symbol": symbol,
            "condition": condition,
            "periods_found": len(periods),
            "total_days_matched": sum(p['days'] for p in periods),
            "periods": periods[:10]  # Limit to top 10
        }

        return [result]


def _get_description(condition: str, change_pct: float, period: dict) -> str:
    """Generate human-readable description of the period."""
    days = period['days']

    if condition == "uptrend":
        return f"{days} days of growth, +{abs(change_pct):.1f}%"
    elif condition == "downtrend":
        return f"{days} days of decline, -{abs(change_pct):.1f}%"
    elif condition == "sideways":
        return f"{days} days of sideways movement"
    elif condition == "high_volatility":
        return f"{days} days of high volatility"
    elif condition == "low_volatility":
        return f"{days} days of low volatility"
    return f"{days} days"
