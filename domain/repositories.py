from abc import ABC, abstractmethod
from typing import List, Optional

from .entities import Criterion, Evaluation, Student


class StudentRepository(ABC):
    """Порт (интерфейс) хранилища студентов."""

    @abstractmethod
    def save(self, student: Student) -> None:
        """Сохраняет или обновляет данные студента."""
        pass

    @abstractmethod
    def get(self, student_id: str) -> Optional[Student]:
        """Возвращает студента по ID или None."""
        pass

    @abstractmethod
    def get_all(self) -> List[Student]:
        """Возвращает список всех студентов."""
        pass


class CriterionRepository(ABC):
    """Порт (интерфейс) хранилища критериев рубрикатора."""

    @abstractmethod
    def save(self, criterion: Criterion) -> None:
        """Сохраняет критерий в рубрикатор."""
        pass

    @abstractmethod
    def get(self, criterion_id: str) -> Optional[Criterion]:
        """Получает критерий по его ID."""
        pass

    @abstractmethod
    def get_all(self) -> List[Criterion]:
        """Возвращает весь рубрикатор."""
        pass


class EvaluationRepository(ABC):
    """Порт (интерфейс) хранилища выставленных оценок."""

    @abstractmethod
    def save(self, evaluation: Evaluation) -> None:
        """Сохраняет или обновляет выставленную оценку."""
        pass

    @abstractmethod
    def get(self, evaluation_id: str) -> Optional[Evaluation]:
        """Возвращает оценку по её ID или None."""
        pass

    @abstractmethod
    def delete(self, evaluation_id: str) -> bool:
        """Удаляет оценку по ID. Возвращает True, если удаление прошло успешно."""
        pass

    @abstractmethod
    def get_by_student(self, student_id: str) -> List[Evaluation]:
        """Получает все оценки конкретного студента."""
        pass

    @abstractmethod
    def get_by_student_and_criterion(
        self,
        student_id: str,
        criterion_id: str,
    ) -> Optional[Evaluation]:
        """Получает оценку студента по конкретному критерию."""
        pass