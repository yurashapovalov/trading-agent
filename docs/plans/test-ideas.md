# Test Questions

## Trading Day vs Calendar Day

- "Статистика по дням за 2024"
  → group: [day], period: 2024

- "Статистика по календарным дням за 2024"
  → group: [calendar_day], period: 2024

- "Что было 15 января?"
  → period: 2025-01-15, data query (raw bars)

- "Волатильность по дням"
  → group: [day], metrics: [stddev(range)]

## Sessions

- "Волатильность для RTH"
  → filter: session=RTH, metrics: [stddev(range)]

- "Средний range по сессиям"
  → group: [session], metrics: [avg(range)]

- "Сравни RTH и Overnight"
  → compare: {a: session=RTH, b: session=OVERNIGHT}

- "Статистика для ночной сессии"
  → filter: session=OVERNIGHT

## Combined

- "Статистика по дням для RTH"
  → group: [day], filter: session=RTH

- "Волатильность по дням, только RTH"
  → group: [day], filter: session=RTH, metrics: [stddev(range)]

- "Что было 15 января в RTH?"
  → period: 2025-01-15, filter: session=RTH

## Edge Cases

- "Статистика за понедельник"
  → filter: weekday=Monday? или group: [weekday], filter: weekday=Monday?

- "Данные за воскресенье"
  → NQ: данные есть (18:00-23:59 = начало trading day понедельника)
  → Stocks: нет данных, предупредить?

- "Статистика за понедельник" (для NQ)
  → trading day понедельника = Sunday 18:00 → Monday 17:00
  → как парсер это понимает?

## Questions

1. "по дням" — всегда DAY (trading day)?
2. "календарный день" — явный триггер для CALENDAR_DAY?
3. "понедельник" — weekday filter или trading day filter?
4. Как отличить "15 января" (конкретная дата) от "по январям" (группировка)?
