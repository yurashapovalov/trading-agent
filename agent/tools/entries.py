"""Find optimal entry points - optimized with pure SQL"""

import duckdb
from typing import Optional, List
from dataclasses import dataclass, asdict


@dataclass
class EntryCandidate:
    """Candidate entry time with statistics"""
    hour: int
    minute: int
    direction: str
    stop_loss_ticks: int
    take_profit_ticks: int
    total_trades: int
    wins: int
    losses: int
    winrate: float
    avg_profit_ticks: float
    profit_factor: float


def find_optimal_entries(
    symbol: str,
    direction: str,
    risk_reward: float,
    max_stop_loss: float,
    min_winrate: float,
    start_hour: int = 0,
    end_hour: int = 23,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: str = None
) -> List[dict]:
    """
    Find optimal entry times based on criteria.
    Optimized version using pure SQL for 100x faster execution on large datasets.

    Use start_date/end_date to filter data period (e.g., for train/test splits).
    """
    import config
    if db_path is None:
        db_path = config.DATABASE_PATH
    db_symbol = symbol
    tick_size = 0.01
    min_trades = 5

    # Stop loss levels to test
    stop_losses = [sl for sl in [10, 15, 20, 25, 30] if sl <= max_stop_loss]
    if not stop_losses:
        stop_losses = [int(max_stop_loss)]

    # Directions to test
    directions = ['long', 'short'] if direction == 'both' else [direction]

    # Build date filter
    date_conditions = []
    if start_date:
        date_conditions.append(f"AND DATE(timestamp) >= '{start_date}'")
    if end_date:
        date_conditions.append(f"AND DATE(timestamp) <= '{end_date}'")
    date_filter = " ".join(date_conditions)

    all_candidates = []

    with duckdb.connect(db_path, read_only=True) as conn:
        # Check if data exists
        count = conn.execute(f"""
            SELECT COUNT(*) FROM ohlcv_1min WHERE symbol = '{db_symbol}'
        """).fetchone()[0]

        if count == 0:
            return [{"error": f"No data found for {symbol}"}]

        # Process each direction and stop loss combination
        for dir in directions:
            for sl in stop_losses:
                tp = int(sl * risk_reward)
                sl_distance = sl * tick_size
                tp_distance = tp * tick_size

                # Direction-specific expressions
                if dir == 'long':
                    sl_price_expr = "entry_price - sl_distance"
                    tp_price_expr = "entry_price + tp_distance"
                    sl_hit_expr = "b.low <= e.sl_price"
                    tp_hit_expr = "b.high >= e.tp_price"
                else:
                    sl_price_expr = "entry_price + sl_distance"
                    tp_price_expr = "entry_price - tp_distance"
                    sl_hit_expr = "b.high >= e.sl_price"
                    tp_hit_expr = "b.low <= e.tp_price"

                query = f"""
                WITH
                -- All potential entry bars within hour range
                entries AS (
                    SELECT
                        DATE(timestamp) as trade_date,
                        EXTRACT(HOUR FROM timestamp)::INTEGER as entry_hour,
                        EXTRACT(MINUTE FROM timestamp)::INTEGER as entry_minute,
                        timestamp as entry_time,
                        close as entry_price,
                        {sl_distance} as sl_distance,
                        {tp_distance} as tp_distance,
                        {sl_price_expr} as sl_price,
                        {tp_price_expr} as tp_price
                    FROM ohlcv_1min
                    WHERE symbol = '{db_symbol}'
                        AND EXTRACT(HOUR FROM timestamp) >= {start_hour}
                        AND EXTRACT(HOUR FROM timestamp) <= {end_hour}
                        {date_filter}
                    QUALIFY ROW_NUMBER() OVER (
                        PARTITION BY DATE(timestamp), EXTRACT(HOUR FROM timestamp), EXTRACT(MINUTE FROM timestamp)
                        ORDER BY timestamp
                    ) = 1
                ),

                -- Find exits for all entries
                with_exits AS (
                    SELECT
                        e.trade_date,
                        e.entry_hour,
                        e.entry_minute,
                        e.entry_time,
                        e.entry_price,
                        e.sl_price,
                        e.tp_price,
                        b.timestamp as bar_time,
                        CASE
                            WHEN {sl_hit_expr} THEN 'loss'
                            WHEN {tp_hit_expr} THEN 'win'
                            ELSE NULL
                        END as hit_type,
                        ROW_NUMBER() OVER (
                            PARTITION BY e.trade_date, e.entry_hour, e.entry_minute
                            ORDER BY b.timestamp
                        ) as bar_num
                    FROM entries e
                    JOIN ohlcv_1min b
                        ON DATE(b.timestamp) = e.trade_date
                        AND b.timestamp > e.entry_time
                        AND b.symbol = '{db_symbol}'
                ),

                -- Get first hit for each trade
                first_hits AS (
                    SELECT
                        trade_date,
                        entry_hour,
                        entry_minute,
                        entry_time,
                        entry_price,
                        sl_price,
                        tp_price,
                        hit_type,
                        bar_num,
                        MIN(CASE WHEN hit_type IS NOT NULL THEN bar_num END)
                            OVER (PARTITION BY trade_date, entry_hour, entry_minute) as first_hit_bar
                    FROM with_exits
                ),

                -- Trade results
                trade_results AS (
                    SELECT
                        entry_hour,
                        entry_minute,
                        COALESCE(hit_type, 'timeout') as result
                    FROM first_hits
                    WHERE bar_num = first_hit_bar
                       OR (first_hit_bar IS NULL AND bar_num = (
                           SELECT MAX(bar_num)
                           FROM first_hits f2
                           WHERE f2.trade_date = first_hits.trade_date
                             AND f2.entry_hour = first_hits.entry_hour
                             AND f2.entry_minute = first_hits.entry_minute
                       ))
                ),

                -- Aggregate statistics per time slot
                stats AS (
                    SELECT
                        entry_hour,
                        entry_minute,
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
                        SUM(CASE WHEN result = 'win' THEN {tp} ELSE 0 END) as gross_win,
                        SUM(CASE WHEN result = 'loss' THEN {sl} ELSE 0 END) as gross_loss,
                        SUM(CASE
                            WHEN result = 'win' THEN {tp}
                            WHEN result = 'loss' THEN -{sl}
                            ELSE 0
                        END) as total_profit
                    FROM trade_results
                    GROUP BY entry_hour, entry_minute
                    HAVING COUNT(*) >= {min_trades}
                )

                SELECT
                    entry_hour as hour,
                    entry_minute as minute,
                    '{dir}' as direction,
                    {sl} as stop_loss_ticks,
                    {tp} as take_profit_ticks,
                    total_trades,
                    wins,
                    losses,
                    ROUND(wins * 100.0 / (wins + losses), 1) as winrate,
                    ROUND(total_profit * 1.0 / total_trades, 1) as avg_profit_ticks,
                    CASE
                        WHEN gross_loss > 0 THEN ROUND(gross_win * 1.0 / gross_loss, 2)
                        ELSE 999.0
                    END as profit_factor
                FROM stats
                WHERE wins + losses > 0
                  AND (wins * 100.0 / (wins + losses)) >= {min_winrate}
                ORDER BY winrate DESC, profit_factor DESC
                """

                result_df = conn.execute(query).df()

                for _, row in result_df.iterrows():
                    candidate = EntryCandidate(
                        hour=int(row['hour']),
                        minute=int(row['minute']),
                        direction=row['direction'],
                        stop_loss_ticks=int(row['stop_loss_ticks']),
                        take_profit_ticks=int(row['take_profit_ticks']),
                        total_trades=int(row['total_trades']),
                        wins=int(row['wins']),
                        losses=int(row['losses']),
                        winrate=float(row['winrate']),
                        avg_profit_ticks=float(row['avg_profit_ticks']),
                        profit_factor=float(row['profit_factor'])
                    )
                    all_candidates.append(candidate)

    # Sort by winrate, then profit factor
    all_candidates.sort(key=lambda x: (x.winrate, x.profit_factor), reverse=True)

    # Remove duplicates (same time/direction, keep best SL)
    seen = set()
    unique_candidates = []
    for c in all_candidates:
        key = (c.hour, c.minute, c.direction)
        if key not in seen:
            seen.add(key)
            unique_candidates.append(c)

    # Limit results
    unique_candidates = unique_candidates[:20]

    if not unique_candidates:
        return [{
            "message": f"No entries found matching criteria: winrate >= {min_winrate}%, stop <= {max_stop_loss} ticks",
            "suggestion": "Try lowering min_winrate or increasing max_stop_loss"
        }]

    return [asdict(c) for c in unique_candidates]
