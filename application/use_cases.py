from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from domain.entities import Criterion, Evaluation, Student
from domain.repositories import (
    CriterionRepository,
    EvaluationRepository,
    StudentRepository,
)
from domain.services import CalculationStrategy, TotalScoreCalculator
from domain.value_objects import Weight


# --- Исключения слоя приложения ---

class ApplicationError(Exception):
    """Базовое исключение сценариев приложения."""


class EntityNotFoundError(ApplicationError):
    """Запрошенная сущность (студент, критерий или оценка) не найдена."""


class DuplicateEvaluationError(ApplicationError):
    """Оценка данному студенту по данному критерию уже выставлена."""


class RubricWeightExceededError(ApplicationError):
    """Суммарный вес критериев в рубрикаторе превышает 1.0."""


# --- DTO для передачи данных в UI и адаптеры экспорта ---

@dataclass(frozen=True)
class EvaluationView:
    evaluation_id: str
    student_id: str
    student_name: str
    criterion_id: str
    criterion_name: str
    score: float
    max_score: float
    weight: float
    comment: str
    created_at: datetime


@dataclass(frozen=True)
class StudentSummaryDTO:
    student_id: str
    student_name: str
    total_score: float
    evaluations: List[EvaluationView]


# --- Выходной порт (Outbound Port) для экспорта ---

class ReportExporter(ABC):
    """
    Порт экспорта итоговой ведомости.
    Реализуется в слое infrastructure (например, CSV или JSON адаптером).
    """
    @abstractmethod
    def export(self, summaries: List[StudentSummaryDTO], destination: str) -> str:
        """Экспортирует ведомость и возвращает путь/описание результата."""
        pass


# --- Сценарии использования (Use Cases) ---

class StudentUseCases:
    """Сценарии управления списком студентов."""

    def __init__(self, student_repo: StudentRepository) -> None:
        self._student_repo = student_repo

    def add_student(self, name: str) -> Student:
        student = Student(name=name.strip())
        self._student_repo.save(student)
        return student

    def get_student(self, student_id: str) -> Student:
        student = self._student_repo.get(student_id)
        if not student:
            raise EntityNotFoundError(f"Студент с ID '{student_id}' не найден.")
        return student

    def list_students(self) -> List[Student]:
        return self._student_repo.get_all()


class CriterionUseCases:
    """Сценарии управления рубрикатором (критериями оценивания)."""

    def __init__(self, criterion_repo: CriterionRepository) -> None:
        self._criterion_repo = criterion_repo

    def add_criterion(
        self,
        name: str,
        max_score: float,
        weight_value: float,
    ) -> Criterion:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ApplicationError("Название критерия не может быть пустым.")

        existing = self._criterion_repo.get_all()
        if any(c.name.lower() == cleaned_name.lower() for c in existing):
            raise ApplicationError(
                f"Критерий с названием '{cleaned_name}' уже есть в рубрикаторе."
            )

        weight = Weight(weight_value)
        current_total_weight = sum(c.weight.value for c in existing)
        if current_total_weight + weight.value > 1.0 + 1e-9:
            available = round(max(0.0, 1.0 - current_total_weight), 4)
            raise RubricWeightExceededError(
                f"Суммарный вес рубрикатора превысит 1.0. "
                f"Доступный остаток веса: {available}."
            )

        criterion = Criterion(
            name=cleaned_name,
            max_score=max_score,
            weight=weight,
        )
        self._criterion_repo.save(criterion)
        return criterion

    def list_criteria(self) -> List[Criterion]:
        return self._criterion_repo.get_all()

    def get_total_weight(self) -> float:
        return round(sum(c.weight.value for c in self._criterion_repo.get_all()), 4)


class EvaluationUseCases:
    """Сценарии выставления, просмотра, исправления и отмены оценок."""

    def __init__(
        self,
        student_repo: StudentRepository,
        criterion_repo: CriterionRepository,
        evaluation_repo: EvaluationRepository,
    ) -> None:
        self._student_repo = student_repo
        self._criterion_repo = criterion_repo
        self._evaluation_repo = evaluation_repo

    def evaluate_student(
        self,
        student_id: str,
        criterion_id: str,
        score_value: float,
        comment: str = "",
    ) -> Evaluation:
        student = self._student_repo.get(student_id)
        if not student:
            raise EntityNotFoundError(f"Студент с ID '{student_id}' не найден.")

        criterion = self._criterion_repo.get(criterion_id)
        if not criterion:
            raise EntityNotFoundError(
                f"Критерий с ID '{criterion_id}' отсутствует в рубрикаторе."
            )

        existing = self._evaluation_repo.get_by_student_and_criterion(
            student_id, criterion_id
        )
        if existing:
            raise DuplicateEvaluationError(
                f"Оценка для '{student.name}' по критерию '{criterion.name}' "
                f"уже выставлена (ID: {existing.evaluation_id}). "
                f"Используйте исправление оценки."
            )

        evaluation = Evaluation.create(
            student=student,
            criterion=criterion,
            score_val=score_value,
            comment=comment,
        )
        self._evaluation_repo.save(evaluation)
        return evaluation

    def update_evaluation(
        self,
        evaluation_id: str,
        new_score_value: float,
        comment: Optional[str] = None,
    ) -> Evaluation:
        evaluation = self._evaluation_repo.get(evaluation_id)
        if not evaluation:
            raise EntityNotFoundError(f"Оценка с ID '{evaluation_id}' не найдена.")

        criterion = self._criterion_repo.get(evaluation.criterion_id)
        if not criterion:
            raise EntityNotFoundError(
                f"Критерий '{evaluation.criterion_id}' не найден в рубрикаторе."
            )

        evaluation.update_score(
            criterion=criterion,
            new_score_val=new_score_value,
            comment=comment,
        )
        self._evaluation_repo.save(evaluation)
        return evaluation

    def cancel_evaluation(self, evaluation_id: str) -> None:
        deleted = self._evaluation_repo.delete(evaluation_id)
        if not deleted:
            raise EntityNotFoundError(f"Оценка с ID '{evaluation_id}' не найдена.")

    def get_student_evaluations(self, student_id: str) -> List[EvaluationView]:
        student = self._student_repo.get(student_id)
        if not student:
            raise EntityNotFoundError(f"Студент с ID '{student_id}' не найден.")

        criteria_map = {c.criterion_id: c for c in self._criterion_repo.get_all()}
        evaluations = self._evaluation_repo.get_by_student(student_id)

        result: List[EvaluationView] = []
        for ev in evaluations:
            criterion = criteria_map.get(ev.criterion_id)
            if not criterion:
                continue
            result.append(
                EvaluationView(
                    evaluation_id=ev.evaluation_id,
                    student_id=student.student_id,
                    student_name=student.name,
                    criterion_id=criterion.criterion_id,
                    criterion_name=criterion.name,
                    score=ev.score.value,
                    max_score=criterion.max_score,
                    weight=criterion.weight.value,
                    comment=ev.comment,
                    created_at=ev.created_at,
                )
            )
        return result


class ReportUseCases:
    """Сценарии расчёта итогов, формирования аналитики и экспорта ведомости."""

    def __init__(
        self,
        student_repo: StudentRepository,
        criterion_repo: CriterionRepository,
        evaluation_repo: EvaluationRepository,
        calculator: TotalScoreCalculator,
        exporter: ReportExporter,
    ) -> None:
        self._student_repo = student_repo
        self._criterion_repo = criterion_repo
        self._evaluation_repo = evaluation_repo
        self._calculator = calculator
        self._exporter = exporter

    def set_calculation_strategy(self, strategy: CalculationStrategy) -> None:
        self._calculator.set_strategy(strategy)

    def calculate_student_total(self, student_id: str) -> float:
        student = self._student_repo.get(student_id)
        if not student:
            raise EntityNotFoundError(f"Студент с ID '{student_id}' не найден.")

        evaluations = self._evaluation_repo.get_by_student(student_id)
        criteria = self._criterion_repo.get_all()
        return self._calculator.calculate_total(evaluations, criteria)

    def get_student_summary(self, student_id: str) -> StudentSummaryDTO:
        student = self._student_repo.get(student_id)
        if not student:
            raise EntityNotFoundError(f"Студент с ID '{student_id}' не найден.")

        criteria = self._criterion_repo.get_all()
        criteria_map = {c.criterion_id: c for c in criteria}
        evaluations = self._evaluation_repo.get_by_student(student_id)
        total_score = self._calculator.calculate_total(evaluations, criteria)

        eval_views = [
            EvaluationView(
                evaluation_id=ev.evaluation_id,
                student_id=student.student_id,
                student_name=student.name,
                criterion_id=ev.criterion_id,
                criterion_name=criteria_map[ev.criterion_id].name,
                score=ev.score.value,
                max_score=criteria_map[ev.criterion_id].max_score,
                weight=criteria_map[ev.criterion_id].weight.value,
                comment=ev.comment,
                created_at=ev.created_at,
            )
            for ev in evaluations
            if ev.criterion_id in criteria_map
        ]

        return StudentSummaryDTO(
            student_id=student.student_id,
            student_name=student.name,
            total_score=total_score,
            evaluations=eval_views,
        )

    def get_course_summaries(self) -> List[StudentSummaryDTO]:
        summaries = [
            self.get_student_summary(student.student_id)
            for student in self._student_repo.get_all()
        ]
        return sorted(summaries, key=lambda item: item.total_score, reverse=True)

    def export_course_report(self, destination: str) -> str:
        summaries = self.get_course_summaries()
        return self._exporter.export(summaries, destination)