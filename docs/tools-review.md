# Tools Review & Redesign

## Current State (6 tools)

| Tool | File | Purpose | Status |
|------|------|---------|--------|
| `query_ohlcv` | query.py | Raw SQL queries | 🔴 Remove |
| `get_statistics` | stats.py | Market statistics | 🔴 Remove (duplicate) |
| `analyze_data` | analyze.py | Smart analysis | 🟢 Keep + enhance |
| `find_optimal_entries` | entries.py | Find entry times | 🟡 Keep + simplify |
| `backtest_strategy` | backtest.py | Test strategy | 🟢 Keep + fix |
| `find_market_periods` | periods.py | Find market conditions | 🟢 Keep |

---

## Critical Bugs

### 1. Hardcoded tick_size (WRONG!)

**Location**: `entries.py:46`, `stats.py:71`, `backtest.py:67`

```python
tick_size = 0.01  # Only correct for CL!
```

**Correct values from config.py**:
```python
"NQ": {"tick_size": 0.25, "tick_value": 5.0}
"ES": {"tick_size": 0.25, "tick_value": 12.50}
"CL": {"tick_size": 0.01, "tick_value": 10.0}
```

**Impact**: All calculations for NQ and ES are 25x wrong!

**Fix**: Use `config.SYMBOLS[symbol]["tick_size"]`

---

## Problems

### 1. Tool Overlap

`get_statistics` and `analyze_data` do the same things:

| Feature | get_statistics | analyze_data |
|---------|---------------|--------------|
| Summary stats | ✅ | ✅ |
| Hourly volatility | ✅ | ✅ (analysis="hourly") |
| Daily breakdown | ✅ | ✅ (analysis="daily") |
| Trend stats | ✅ | ✅ (analysis="trend") |
| Anomalies | ❌ | ✅ (analysis="anomalies") |
| Smart period parsing | ❌ | ✅ ("last_month", "yesterday") |

**Decision**: Remove `get_statistics`, keep `analyze_data`

### 2. Raw SQL is Dangerous

`query_ohlcv` gives LLM full SQL access:
- Can generate `SELECT * FROM ohlcv_1min` (millions of rows)
- Can write syntactically incorrect SQL
- Can run infinitely long queries
- No LIMIT enforcement

**Decision**: Remove `query_ohlcv`

### 3. Complex Parameters

`find_optimal_entries` has 8 parameters:
- symbol, direction, risk_reward, max_stop_loss, min_winrate
- start_hour, end_hour, start_date, end_date

LLM often gets confused with so many options.

**Decision**: Simplify to essential parameters only

### 4. Large System Prompt

Current system prompt is ~100 lines with:
- Detailed tool descriptions (duplicated in tool schemas)
- Train/test split calculations
- Workflow instructions

**Decision**: Simplify, remove duplication

### 5. Suggestions Waste Tokens

```
[SUGGESTIONS]
Question 1?
Question 2?
[/SUGGESTIONS]
```

These are parsed and removed from response, but still use output tokens.

**Decision**: Keep for now (UX benefit outweighs cost)

---

## Target State (4 tools)

### 1. `analyze_data` - Primary Analysis Tool

```
Purpose: All data analysis needs
Parameters:
  - symbol: str (NQ, ES, CL)
  - period: str ("today", "last_week", "last_month", "2025-01-01 to 2025-01-31")
  - analysis: str ("summary", "daily", "hourly", "trend", "anomalies")
```

Enhancements:
- Add comparison analysis ("compare last_week vs previous_week")
- Better anomaly detection

### 2. `backtest_strategy` - Strategy Testing

```
Purpose: Test specific entry time + SL/TP
Parameters:
  - symbol: str
  - entry_hour: int
  - entry_minute: int
  - direction: str ("long", "short")
  - stop_loss: float (in ticks)
  - take_profit: float (in ticks)
  - start_date, end_date: optional
```

Fixes needed:
- Use correct tick_size from config
- Use correct tick_value from config

### 3. `find_optimal_entries` - Pattern Discovery

```
Purpose: Find best entry times based on criteria
Parameters (simplified):
  - symbol: str
  - direction: str ("long", "short", "both")
  - min_winrate: float (e.g., 60)
  - risk_reward: float (e.g., 1.5)
  - period: str ("last_month", "all", etc.) - NEW! Use same period parsing as analyze_data
```

Removed parameters:
- max_stop_loss → auto-calculate reasonable range
- start_hour, end_hour → analyze all hours, return best
- start_date, end_date → replaced by period

### 4. `find_market_periods` - Market Condition Finder

```
Purpose: Find periods matching conditions (trend, volatility)
Parameters:
  - symbol: str
  - condition: str ("uptrend", "downtrend", "high_volatility", "low_volatility", "sideways")
  - min_days: int (default: 5)
```

No changes needed.

---

## Implementation Plan

### Phase 1: Fix Critical Bugs
1. Fix tick_size in all tools (use config)
2. Fix tick_value in all tools (use config)
3. Add symbol validation

### Phase 2: Remove Duplicates
1. Remove `query_ohlcv`
2. Remove `get_statistics`
3. Update `__init__.py`

### Phase 3: Simplify
1. Simplify `find_optimal_entries` parameters
2. Add period parsing to `find_optimal_entries`
3. Reduce system prompt size

### Phase 4: Enhance
1. Add comparison to `analyze_data`
2. Better error messages
3. Consistent return formats

---

## Token Optimization

### Current Tool Descriptions (in llm.py)

| Tool | Description Length |
|------|-------------------|
| query_ohlcv | ~500 chars |
| find_optimal_entries | ~1200 chars |
| backtest_strategy | ~1500 chars |
| get_statistics | ~900 chars |
| analyze_data | ~1200 chars |
| find_market_periods | ~800 chars |
| **Total** | ~6100 chars |

### After Cleanup

| Tool | Description Length |
|------|-------------------|
| analyze_data | ~800 chars |
| backtest_strategy | ~1000 chars |
| find_optimal_entries | ~800 chars |
| find_market_periods | ~600 chars |
| **Total** | ~3200 chars |

**Savings**: ~50% reduction in tool description tokens

---

## Return Format Standardization

All tools should return consistent format:

```python
{
    "success": True,
    "data": { ... },  # actual result
    "metadata": {
        "symbol": "NQ",
        "period": "2025-01-01 to 2025-01-31",
        "execution_ms": 123
    }
}
```

Or on error:
```python
{
    "success": False,
    "error": "Error message",
    "suggestion": "Try this instead..."
}
```

---

## Questions to Decide

1. **Keep suggestions in response?**
   - Pro: Better UX
   - Con: Uses tokens
   - Current: Keep

2. **Add new tools later?**
   - `compare_periods` - compare two time periods
   - `export_data` - export to CSV
   - `get_calendar` - trading calendar, holidays

3. **Gemini migration impact?**
   - Tool format is similar (functionDeclarations)
   - May need adapter layer
   - Parallel function calling available

---

## Files to Modify

```
agent/
├── tools/
│   ├── __init__.py      # Remove exports for deleted tools
│   ├── query.py         # DELETE
│   ├── stats.py         # DELETE
│   ├── analyze.py       # Minor fixes
│   ├── entries.py       # Fix tick_size, simplify params
│   ├── backtest.py      # Fix tick_size/tick_value
│   └── periods.py       # No changes
└── llm.py               # Remove tool registrations, simplify descriptions
```
