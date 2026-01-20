"""
Backtest execution configuration.

Parameters for how backtest engine executes trades:
- Position sizing
- Slippage and commission
- Initial capital
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class PositionSizing(str, Enum):
    """Position sizing methods."""

    FIXED = "fixed"  # Fixed amount/contracts
    PERCENT = "percent"  # % of capital
    RISK_BASED = "risk_based"  # Size based on stop loss
    KELLY = "kelly"  # Kelly criterion


class Position(BaseModel):
    """Position sizing configuration.

    Example:
        {
            "sizing": "fixed",
            "value": 1,
            "max_positions": 1
        }
    """

    sizing: PositionSizing = Field(default=PositionSizing.FIXED, description="Sizing method")
    value: float = Field(default=1, description="Sizing value (amount, %, etc)")
    max_positions: int = Field(default=1, description="Max concurrent positions")


class Execution(BaseModel):
    """Execution parameters for backtest.

    Example:
        {
            "slippage": 0.01,
            "commission": 1.0,
            "initial_capital": 100000
        }
    """

    slippage: float = Field(default=0.0, description="Slippage (% or points)")
    commission: float = Field(default=0.0, description="Commission per trade")
    initial_capital: float = Field(default=100000, description="Starting capital")
