"""Operations — работают с Parser v2 выходом.

Интерфейс:
    def op_name(df: pd.DataFrame, what: str, params: dict) -> dict:
        '''
        Args:
            df: DataFrame с OHLCV + enriched (уже отфильтрован)
            what: Метрика из atom.what (change, range, volume, gap)
            params: Параметры из step.params

        Returns:
            {"rows": [...], "summary": {...}}
        '''
"""

from agent.operations.list import op_list
from agent.operations.count import op_count
from agent.operations.compare import op_compare
from agent.operations.correlation import op_correlation
from agent.operations.streak import op_streak
from agent.operations.distribution import op_distribution
from agent.operations.probability import op_probability
from agent.operations.around import op_around
from agent.operations.formation import op_formation

OPERATIONS = {
    "list": op_list,
    "count": op_count,
    "compare": op_compare,
    "correlation": op_correlation,
    "streak": op_streak,
    "distribution": op_distribution,
    "probability": op_probability,
    "around": op_around,
    "formation": op_formation,
}

__all__ = ["OPERATIONS"]
