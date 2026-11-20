from abc import ABC, abstractmethod
from typing import Dict, List

from .entities import Criterion, Evaluation


class CalculationStrategy(ABC):
    """
    Паттерн: Strategy (Поведенческий).
    Определяет общий интерфейс для алгоритмов подсчёта итогового балла.
    """

    @abstractmethod
    def calculate(
        self,
        evaluations: List[Evaluation],
        criteria: List[Criterion],
    ) -> float:
        pass


class WeightedSumStrategy(CalculationStrategy):
    """
    Расчёт итогового балла как прямой взвешенной суммы.
    Формула: Итог = Сумма(Балл * Вес).
    """

    def calculate(
        self,
        evaluations: List[Evaluation],
        criteria: List[Criterion],
    ) -> float:
        if not evaluations or not criteria:
            return 0.0

        criteria_map: Dict[str, Criterion] = {c.criterion_id: c for c in criteria}
        total_score = 0.0

        for eval_obj in evaluations:
            criterion = criteria_map.get(eval_obj.criterion_id)
            if criterion:
                total_score += eval_obj.score.value * criterion.weight.value

        return round(total_score, 2)


class NormalizedTenPointStrategy(CalculationStrategy):
    """
    Приводит каждый критерий к 10-балльной шкале с учётом его максимума и веса.
    Формула: Итог = Сумма((Балл / max_score) * 10 * Вес).
    """

    def calculate(
        self,
        evaluations: List[Evaluation],
        criteria: List[Criterion],
    ) -> float:
        if not evaluations or not criteria:
            return 0.0

        criteria_map: Dict[str, Criterion] = {c.criterion_id: c for c in criteria}
        total_score = 0.0

        for eval_obj in evaluations:
            criterion = criteria_map.get(eval_obj.criterion_id)
            if criterion:
                normalized = (eval_obj.score.value / criterion.max_score) * 10.0
                total_score += normalized * criterion.weight.value

        return round(total_score, 2)


class TotalScoreCalculator:
    """
    Domain Service для расчёта согласованного итогового балла.
    Вынесен в доменный сервис, так как правило зависит одновременно
    от набора оценок студента и рубрикатора критериев.
    """

    def __init__(self, strategy: CalculationStrategy) -> None:
        self.strategy = strategy

    def set_strategy(self, strategy: CalculationStrategy) -> None:
        """Позволяет динамически переключить правило расчёта итога."""
        self.strategy = strategy

    def calculate_total(
        self,
        evaluations: List[Evaluation],
        criteria: List[Criterion],
    ) -> float:
        return self.strategy.calculate(evaluations, criteria)