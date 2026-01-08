"""Backtest trading strategies - optimized with pure SQL"""

import duckdb
from typing import Optional, List
from dataclasses import dataclass, asdict


@dataclass
class Trade:
    """Single trade result"""
    date: str
    entry_time: str
    exit_time: str
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    pnl_ticks: int
    pnl_dollars: float
    result: str  # 'win', 'loss', 'timeout'


@dataclass
class BacktestResult:
    """Backtest results summary"""
    total_trades: int
    wins: int
    losses: int
    timeouts: int
    winrate: float
    total_profit_ticks: int
    total_profit_dollars: float
    max_drawdown_ticks: int
    max_drawdown_dollars: float
    profit_factor: float
    avg_win_ticks: float
    avg_loss_ticks: float
    best_trades: List[dict]  # Top 5 winning trades
    worst_trades: List[dict]  # Top 5 losing trades

    def to_dict(self) -> dict:
        return asdict(self)


def backtest_strategy(
    symbol: str,
    entry_hour: int,
    entry_minute: int,
    direction: str,
    stop_loss: float,
    take_profit: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: str = None
) -> dict:
    """
    Backtest a specific strategy on historical data.
    Optimized version using pure SQL for 100x faster execution on large datasets.

    Use start_date/end_date to filter data period (e.g., for train/test splits).
    """
    import config
    if db_path is None:
        db_path = config.DATABASE_PATH
    db_symbol = symbol
    tick_size = 0.01
    tick_value = 10.0

    sl_distance = stop_loss * tick_size
    tp_distance = take_profit * tick_size

    # Build date filter
    date_conditions = []
    if start_date:
        date_conditions.append(f"AND trade_date >= '{start_date}'")
    if end_date:
        date_conditions.append(f"AND trade_date <= '{end_date}'")
    date_filter = " ".join(date_conditions)

    # Direction-specific conditions
    if direction == 'long':
        sl_price_expr = "entry_price - sl_distance"
        tp_price_expr = "entry_price + tp_distance"
        sl_hit_expr = "b.low <= e.sl_price"
        tp_hit_expr = "b.high >= e.tp_price"
        pnl_expr = "exit_price - entry_price"
    else:
        sl_price_expr = "entry_price + sl_distance"
        tp_price_expr = "entry_price - tp_distance"
        sl_hit_expr = "b.high >= e.sl_price"
        tp_hit_expr = "b.low <= e.tp_price"
        pnl_expr = "entry_price - exit_price"

    query = f"""
    WITH
    -- Find all entry bars (first occurrence per day at specified time)
    entries AS (
        SELECT
            DATE(timestamp) as trade_date,
            timestamp as entry_time,
            close as entry_price,
            {sl_distance} as sl_distance,
            {tp_distance} as tp_distance
        FROM ohlcv_1min
        WHERE symbol = '{db_symbol}'
            AND EXTRACT(HOUR FROM timestamp) = {entry_hour}
            AND EXTRACT(MINUTE FROM timestamp) = {entry_minute}
        QUALIFY ROW_NUMBER() OVER (PARTITION BY DATE(timestamp) ORDER BY timestamp) = 1
    ),

    -- Add SL/TP price levels
    entries_with_levels AS (
        SELECT
            trade_date,
            entry_time,
            entry_price,
            {sl_price_expr} as sl_price,
            {tp_price_expr} as tp_price
        FROM entries
        WHERE 1=1 {date_filter}
    ),

    -- Find exit for each entry by joining with subsequent bars
    -- and finding the first bar where SL or TP is hit
    exits AS (
        SELECT
            e.trade_date,
            e.entry_time,
            e.entry_price,
            e.sl_price,
            e.tp_price,
            b.timestamp as exit_time,
            b.high,
            b.low,
            b.close as last_close,
            CASE
                WHEN {sl_hit_expr} THEN 'loss'
                WHEN {tp_hit_expr} THEN 'win'
                ELSE NULL
            END as hit_type,
            ROW_NUMBER() OVER (PARTITION BY e.trade_date ORDER BY b.timestamp) as bar_num
        FROM entries_with_levels e
        JOIN ohlcv_1min b
            ON DATE(b.timestamp) = e.trade_date
            AND b.timestamp > e.entry_time
            AND b.symbol = '{db_symbol}'
    ),

    -- Get first hit or last bar for each trade
    first_exit AS (
        SELECT
            trade_date,
            entry_time,
            entry_price,
            sl_price,
            tp_price,
            exit_time,
            last_close,
            hit_type,
            bar_num,
            -- Find the bar number of first hit
            MIN(CASE WHEN hit_type IS NOT NULL THEN bar_num END)
                OVER (PARTITION BY trade_date) as first_hit_bar,
            -- Find the last bar number for timeout
            MAX(bar_num) OVER (PARTITION BY trade_date) as last_bar
        FROM exits
    ),

    -- Final trades: select first hit or timeout
    trades AS (
        SELECT
            trade_date,
            entry_time,
            entry_price,
            sl_price,
            tp_price,
            exit_time,
            CASE
                WHEN hit_type = 'loss' THEN sl_price
                WHEN hit_type = 'win' THEN tp_price
                ELSE last_close
            END as exit_price,
            COALESCE(hit_type, 'timeout') as result
        FROM first_exit
        WHERE
            -- Either this is the first hit
            (first_hit_bar IS NOT NULL AND bar_num = first_hit_bar)
            -- Or no hit and this is the last bar (timeout)
            OR (first_hit_bar IS NULL AND bar_num = last_bar)
    )

    SELECT
        trade_date::VARCHAR as date,
        entry_time::VARCHAR as entry_time,
        exit_time::VARCHAR as exit_time,
        '{direction}' as direction,
        ROUND(entry_price, 2) as entry_price,
        ROUND(exit_price, 2) as exit_price,
        ROUND(sl_price, 2) as stop_loss,
        ROUND(tp_price, 2) as take_profit,
        ROUND(({pnl_expr}) / {tick_size})::INTEGER as pnl_ticks,
        ROUND(({pnl_expr}) / {tick_size}) * {tick_value} as pnl_dollars,
        result
    FROM trades
    ORDER BY trade_date
    """

    with duckdb.connect(db_path, read_only=True) as conn:
        result_df = conn.execute(query).df()

    if result_df.empty:
        return {"error": f"No trades executed for {symbol}"}

    # Convert to list of Trade objects
    trades = [
        Trade(
            date=row['date'],
            entry_time=row['entry_time'],
            exit_time=row['exit_time'],
            direction=row['direction'],
            entry_price=row['entry_price'],
            exit_price=row['exit_price'],
            stop_loss=row['stop_loss'],
            take_profit=row['take_profit'],
            pnl_ticks=int(row['pnl_ticks']),
            pnl_dollars=float(row['pnl_dollars']),
            result=row['result']
        )
        for _, row in result_df.iterrows()
    ]

    # Calculate statistics (this is fast - just iterating over results)
    wins = [t for t in trades if t.result == 'win']
    losses = [t for t in trades if t.result == 'loss']
    timeouts = [t for t in trades if t.result == 'timeout']

    total_profit_ticks = sum(t.pnl_ticks for t in trades)
    total_profit_dollars = sum(t.pnl_dollars for t in trades)

    decided_trades = len(wins) + len(losses)
    winrate = (len(wins) / decided_trades * 100) if decided_trades > 0 else 0

    gross_profit = sum(t.pnl_ticks for t in trades if t.pnl_ticks > 0)
    gross_loss = abs(sum(t.pnl_ticks for t in trades if t.pnl_ticks < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    avg_win = (sum(t.pnl_ticks for t in wins) / len(wins)) if wins else 0
    avg_loss = (sum(t.pnl_ticks for t in losses) / len(losses)) if losses else 0

    # Max drawdown
    cumulative = 0
    peak = 0
    max_dd = 0
    for t in trades:
        cumulative += t.pnl_ticks
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    # Get top 5 best and worst trades for context
    sorted_by_pnl = sorted(trades, key=lambda x: x.pnl_ticks, reverse=True)
    best_trades = [asdict(t) for t in sorted_by_pnl[:5] if t.pnl_ticks > 0]
    worst_trades = [asdict(t) for t in sorted_by_pnl[-5:] if t.pnl_ticks < 0]

    result = BacktestResult(
        total_trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        timeouts=len(timeouts),
        winrate=round(winrate, 1),
        total_profit_ticks=total_profit_ticks,
        total_profit_dollars=total_profit_dollars,
        max_drawdown_ticks=max_dd,
        max_drawdown_dollars=max_dd * tick_value,
        profit_factor=round(profit_factor, 2) if profit_factor != float('inf') else 999.0,
        avg_win_ticks=round(avg_win, 1),
        avg_loss_ticks=round(avg_loss, 1),
        best_trades=best_trades,
        worst_trades=worst_trades
    )

    return result.to_dict()
