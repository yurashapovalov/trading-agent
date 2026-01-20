# Anomaly Finder + Backtester

Модуль поиска торговых аномалий с защитой от overfitting.

## Концепция

**Проблема:** Трейдер хочет найти паттерны в данных и проверить работают ли они.

**Решение:** AI находит статистические аномалии, система автоматически валидирует на out-of-sample данных.

```
Естественный язык → Поиск аномалий → Валидация → Честный результат
                         ↓                ↓
                    in-sample        out-of-sample
                    (training)        (holdout)
```

## Принцип: честность по умолчанию

- Система **сама** разделяет данные на train/test
- Пользователь **всегда** видит на каких данных найдено vs проверено
- Нет возможности случайно обмануть себя подгонкой

---

## User Flow

### 1. Поиск аномалий

**User:** "найди интересные паттерны"

**Система:**
- Берёт данные 2015-2024
- Training: 2015-2021 (70%)
- Holdout: 2022-2024 (30%) — НЕ ТРОГАЕМ пока
- Сканирует training на аномалии

**Ответ:**
> Нашёл на данных 2015-2021:
>
> | # | Паттерн | Win Rate | Случаев |
> |---|---------|----------|---------|
> | 1 | После 3 красных подряд → зелёный | 63% | 147 |
> | 2 | Гэп вниз >1% → день зелёный | 67% | 89 |
> | 3 | Понедельник после красной пятницы | 61% | 112 |
>
> ⚠️ Это in-sample. Выбери паттерн для проверки на свежих данных.

### 2. Валидация на out-of-sample

**User:** "проверь первый"

**Система:**
- Берёт holdout данные (2022-2024)
- Тестирует паттерн "3 красных → зелёный"
- Сравнивает с in-sample

**Ответ:**
> Паттерн "после 3 красных подряд":
>
> | Период | Win Rate | Случаев |
> |--------|----------|---------|
> | 2015-2021 (training) | 63% | 147 |
> | 2022-2024 (holdout) | 58% | 53 |
>
> ✅ Паттерн **подтвердился** — просадка 5%, но статистически значимо.
> Протестировать как стратегию с конкретными entry/exit?

### 3. Бэктест стратегии

**User:** "да, покупка на открытии, выход в конце дня"

**Система:**
- Entry: открытие дня после 3 красных
- Exit: закрытие того же дня
- Считает P&L, drawdown, Sharpe

**Ответ:**
> Бэктест на 2022-2024 (out-of-sample):
>
> - Сделок: 53
> - Win rate: 58%
> - Общий P&L: +1,240 pts
> - Max drawdown: -380 pts
> - Sharpe: 1.2
>
> Хочешь добавить фильтры или изменить exit?

---

## Методы валидации

### Simple Holdout (по умолчанию)
```
[====== Training 70% ======][== Holdout 30% ==]
        2015-2021              2022-2024
```
Простой, понятный, достаточный для большинства случаев.

### Walk-Forward (продвинутый)
```
[Train 2015-2017] → Test 2018
[Train 2016-2018] → Test 2019
[Train 2017-2019] → Test 2020
[Train 2018-2020] → Test 2021
...
```
Показывает стабильность паттерна год к году.

### K-Fold по годам
```
Fold 1: Test=2020, Train=остальные
Fold 2: Test=2021, Train=остальные
Fold 3: Test=2022, Train=остальные
...
```
Для оценки variance результатов.

---

## Какие аномалии ищем

### Категории условий

```python
CONDITIONS = {
    # Streak patterns
    "streak_red_3": "3+ красных подряд",
    "streak_green_3": "3+ зелёных подряд",
    
    # Gap patterns  
    "gap_down_1pct": "гэп вниз > 1%",
    "gap_up_1pct": "гэп вверх > 1%",
    
    # Calendar
    "monday": "понедельник",
    "friday": "пятница",
    "month_start": "первые 3 дня месяца",
    "month_end": "последние 3 дня месяца",
    
    # Events
    "after_opex": "день после OPEX",
    "before_fomc": "день перед FOMC",
    
    # Volatility
    "high_vix": "VIX > 25",
    "low_vix": "VIX < 15",
    
    # Technical
    "above_sma50": "цена выше SMA50",
    "below_sma50": "цена ниже SMA50",
    
    # Combinations
    "monday_after_red_friday": "понедельник после красной пятницы",
    "gap_down_in_uptrend": "гэп вниз в аптренде",
}
```

### Что измеряем

Для каждого условия:
- **Next day direction**: % зелёных/красных
- **Next day range**: средний диапазон  
- **Next N days return**: доходность за N дней
- **Statistical significance**: p-value

### Фильтрация результатов

Показываем только если:
- Win rate > 55% или < 45% (отклонение от 50%)
- Минимум 30 случаев (статистическая значимость)
- p-value < 0.05

---

## Архитектура модуля

```
agent/
├── anomaly/
│   ├── __init__.py
│   ├── scanner.py      # Сканер аномалий
│   ├── conditions.py   # Определения условий
│   ├── validator.py    # Out-of-sample валидация
│   └── backtester.py   # Простой бэктестер
```

### scanner.py

```python
class AnomalyScanner:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        
    def scan(self, holdout_ratio: float = 0.3) -> list[Anomaly]:
        """Найти аномалии на training данных."""
        train, holdout = self.split_data(holdout_ratio)
        
        anomalies = []
        for condition in CONDITIONS:
            stats = self.test_condition(train, condition)
            if self.is_significant(stats):
                anomalies.append(Anomaly(
                    condition=condition,
                    win_rate=stats.win_rate,
                    count=stats.count,
                    p_value=stats.p_value,
                    data_period="training",
                ))
        
        return sorted(anomalies, key=lambda a: abs(a.win_rate - 0.5), reverse=True)
```

### validator.py

```python
class Validator:
    def validate(self, anomaly: Anomaly, holdout: pd.DataFrame) -> ValidationResult:
        """Проверить аномалию на holdout данных."""
        stats = test_condition(holdout, anomaly.condition)
        
        return ValidationResult(
            training_win_rate=anomaly.win_rate,
            holdout_win_rate=stats.win_rate,
            holdout_count=stats.count,
            confirmed=self.is_confirmed(anomaly, stats),
            degradation=anomaly.win_rate - stats.win_rate,
        )
    
    def is_confirmed(self, anomaly, holdout_stats) -> bool:
        """Паттерн подтверждён если win rate в том же направлении."""
        if anomaly.win_rate > 0.5:
            return holdout_stats.win_rate > 0.52  # small buffer
        else:
            return holdout_stats.win_rate < 0.48
```

### backtester.py

```python
class SimpleBacktester:
    def backtest(
        self,
        df: pd.DataFrame,
        condition: str,
        entry: str = "open",    # open, close
        exit: str = "close",    # close, next_open, target_pct, stop_pct
        hold_days: int = 1,
    ) -> BacktestResult:
        """Простой бэктест стратегии."""
        
        signals = evaluate_condition(df, condition)
        trades = []
        
        for i, row in df[signals].iterrows():
            entry_price = row[entry]
            exit_idx = min(i + hold_days, len(df) - 1)
            exit_price = df.iloc[exit_idx][exit]
            
            pnl = exit_price - entry_price
            trades.append(Trade(
                entry_date=row.date,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl=pnl,
            ))
        
        return BacktestResult(
            trades=trades,
            total_pnl=sum(t.pnl for t in trades),
            win_rate=len([t for t in trades if t.pnl > 0]) / len(trades),
            max_drawdown=calculate_drawdown(trades),
            sharpe=calculate_sharpe(trades),
        )
```

---

## Интеграция с чатом

### Новые intents

```python
class ParsedQuery:
    intent: str  # + "find_anomalies", "validate_pattern", "backtest_strategy"
```

### Parser понимает

- "найди паттерны" → intent: find_anomalies
- "проверь на свежих данных" → intent: validate_pattern  
- "протестируй как стратегию" → intent: backtest_strategy

### DataResponder форматирует

- Таблицы с аномалиями
- Сравнение training vs holdout
- Результаты бэктеста с метриками

---

## UI компоненты (фронт)

### AnomalyCard
```
┌─────────────────────────────────────┐
│ После 3 красных → зелёный           │
│ Win Rate: 63% (147 случаев)         │
│ Период: 2015-2021 (training)        │
│                                     │
│ [Проверить на свежих] [Бэктест]     │
└─────────────────────────────────────┘
```

### ValidationCard
```
┌─────────────────────────────────────┐
│ ✅ Паттерн подтверждён              │
│                                     │
│ Training (2015-2021): 63%           │
│ Holdout (2022-2024):  58% (-5%)     │
│                                     │
│ [Бэктест стратегии]                 │
└─────────────────────────────────────┘
```

### BacktestCard
```
┌─────────────────────────────────────┐
│ Бэктест: После 3 красных            │
│                                     │
│ Сделок: 53        Win Rate: 58%     │
│ P&L: +1,240 pts   Drawdown: -380    │
│ Sharpe: 1.2                         │
│                                     │
│ [Equity Curve]  [Список сделок]     │
│ [Добавить фильтр] [Изменить exit]   │
└─────────────────────────────────────┘
```

---

## TODO

- [ ] Базовый scanner с 10 условиями
- [ ] Simple holdout валидация
- [ ] Простой бэктестер (entry/exit на open/close)
- [ ] Интеграция с Parser (новые intents)
- [ ] UI карточки для фронта
- [ ] Walk-forward валидация (advanced)
- [ ] Больше условий и комбинаций
