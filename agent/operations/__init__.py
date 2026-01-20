"""Operations — трансформации данных для ответа на вопросы.

Каждая операция принимает DataFrame и params, возвращает dict с результатом.
Операции не знают про DuckDB — работают только с pandas DataFrame.

Добавить новую операцию:
    1. Создать файл operation_name.py с функцией op_operation_name(df, params)
    2. Добавить импорт и регистрацию в OPERATIONS dict

Интерфейс операции:
    def op_name(df: pd.DataFrame, params: dict) -> dict:
        '''
        Args:
            df: DataFrame с OHLCV + enriched полями
            params: Параметры из DomainSpec.params

        Returns:
            dict с результатом (структура зависит от операции)
        '''
"""

from agent.operations.stats import op_stats
from agent.operations.compare import op_compare
from agent.operations.top_n import op_top_n
from agent.operations.streak import op_streak
from agent.operations.sequence import op_sequence
from agent.operations.distribution import op_distribution
from agent.operations.correlation import op_correlation
from agent.operations.seasonality import op_seasonality

OPERATIONS = {
    "stats": op_stats,
    "compare": op_compare,
    "top_n": op_top_n,
    "streak": op_streak,
    "sequence": op_sequence,
    "distribution": op_distribution,
    "correlation": op_correlation,
    "seasonality": op_seasonality,
}

__all__ = ["OPERATIONS"]
