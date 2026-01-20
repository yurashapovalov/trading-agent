"""
Backtest output configuration.

Defines what metrics and data to return from backtest:
- Which performance metrics to calculate
- Level of detail for trade list
- Whether to include equity curve, monthly returns, etc.
"""

from __future__ import annotations

from enum import Enum
from typing import ClassVar
from pydantic import BaseModel, Field


# =============================================================================
# BACKTEST METRICS
# =============================================================================


class BacktestMetric(str, Enum):
    """Available backtest performance metrics."""

    # Basic counts
    TOTAL_TRADES = "total_trades"
    WINNING_TRADES = "winning_trades"
    LOSING_TRADES = "losing_trades"

    # Win/Loss
    WIN_RATE = "win_rate"  # % of winning trades
    LOSS_RATE = "loss_rate"  # % of losing trades
    AVG_WIN = "avg_win"  # Average profit on winners
    AVG_LOSS = "avg_loss"  # Average loss on losers
    LARGEST_WIN = "largest_win"
    LARGEST_LOSS = "largest_loss"
    WIN_LOSS_RATIO = "win_loss_ratio"  # avg_win / avg_loss

    # Profit
    TOTAL_PROFIT = "total_profit"
    TOTAL_LOSS = "total_loss"
    NET_PROFIT = "net_profit"
    PROFIT_FACTOR = "profit_factor"  # gross profit / gross loss
    EXPECTANCY = "expectancy"  # Expected $ per trade

    # Risk
    MAX_DRAWDOWN = "max_drawdown"  # Maximum peak-to-trough decline
    MAX_DRAWDOWN_PCT = "max_drawdown_pct"  # As percentage
    MAX_DRAWDOWN_DURATION = "max_drawdown_duration"  # Days in drawdown
    AVG_DRAWDOWN = "avg_drawdown"

    # Returns
    TOTAL_RETURN = "total_return"  # Total % return
    ANNUALIZED_RETURN = "annualized_return"  # CAGR
    MONTHLY_RETURN = "monthly_return"  # Average monthly

    # Risk-adjusted
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"  # Return / max drawdown

    # Trade analysis
    AVG_HOLD_TIME = "avg_hold_time"  # Average time in trade
    AVG_BARS_IN_TRADE = "avg_bars_in_trade"
    MAX_CONSECUTIVE_WINS = "max_consecutive_wins"
    MAX_CONSECUTIVE_LOSSES = "max_consecutive_losses"

    # Exposure
    TIME_IN_MARKET = "time_in_market"  # % of time with open position
    AVG_EXPOSURE = "avg_exposure"  # Average position size


class BacktestMetrics(BaseModel):
    """Specify which metrics to calculate for backtest.

    If not specified, returns default set of key metrics.

    Examples:
        Basic metrics:
        {"include": ["win_rate", "profit_factor", "max_drawdown", "sharpe_ratio"]}

        All metrics:
        {"include": "all"}

        Exclude some:
        {"exclude": ["monthly_return", "time_in_market"]}
    """

    include: list[BacktestMetric] | str = Field(
        default="default",
        description="Metrics to include: list of metrics, 'all', or 'default'"
    )
    exclude: list[BacktestMetric] | None = Field(
        default=None,
        description="Metrics to exclude (applied after include)"
    )

    # Default metrics when include="default"
    DEFAULT_METRICS: ClassVar[list[BacktestMetric]] = [
        BacktestMetric.TOTAL_TRADES,
        BacktestMetric.WIN_RATE,
        BacktestMetric.PROFIT_FACTOR,
        BacktestMetric.NET_PROFIT,
        BacktestMetric.MAX_DRAWDOWN_PCT,
        BacktestMetric.SHARPE_RATIO,
        BacktestMetric.AVG_HOLD_TIME,
    ]


# =============================================================================
# TRADE DETAIL LEVEL
# =============================================================================


class TradeDetailLevel(str, Enum):
    """Level of detail for trade list in backtest results."""

    NONE = "none"  # Don't return individual trades
    SUMMARY = "summary"  # Entry/exit price, P&L
    DETAILED = "detailed"  # Include bars, indicators at entry/exit
    FULL = "full"  # Full trade lifecycle with all data points


class BacktestOutput(BaseModel):
    """Configure backtest output format.

    Example:
        {
            "metrics": {"include": ["win_rate", "sharpe_ratio", "max_drawdown"]},
            "trades": "summary",
            "equity_curve": true,
            "monthly_returns": true
        }
    """

    metrics: BacktestMetrics = Field(
        default_factory=BacktestMetrics,
        description="Which metrics to calculate"
    )
    trades: TradeDetailLevel = Field(
        default=TradeDetailLevel.SUMMARY,
        description="Level of detail for trade list"
    )
    equity_curve: bool = Field(
        default=True,
        description="Include equity curve data points"
    )
    monthly_returns: bool = Field(
        default=False,
        description="Include monthly return breakdown"
    )
    drawdown_periods: bool = Field(
        default=False,
        description="Include detailed drawdown period analysis"
    )
