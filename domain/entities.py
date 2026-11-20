import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .value_objects import Score, Weight


@dataclass
class Student:
    name: str
    student_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Имя студента не может быть пустым.")


@dataclass
class Criterion:
    name: str
    max_score: float
    weight: Weight
    criterion_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.max_score <= 0:
            raise ValueError("Максимальный балл критерия должен быть больше нуля.")


@dataclass
class Evaluation:
    student_id: str
    criterion_id: str
    score: Score
    comment: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    evaluation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def create(
        cls,
        student: Student,
        criterion: Criterion,
        score_val: float,
        comment: str = "",
    ) -> "Evaluation":
        """
        Паттерн: Factory Method (Порождающий).
        Защищает бизнес-инвариант: балл не может превышать max_score критерия.
        """
        if score_val > criterion.max_score:
            raise ValueError(
                f"Нарушение инварианта: балл {score_val} превышает допустимый "
                f"максимум ({criterion.max_score}) для критерия '{criterion.name}'."
            )

        return cls(
            student_id=student.student_id,
            criterion_id=criterion.criterion_id,
            score=Score(score_val),
            comment=comment.strip(),
        )

    def update_score(
        self,
        criterion: Criterion,
        new_score_val: float,
        comment: Optional[str] = None,
    ) -> None:
        """Изменяет балл оценки с повторной проверкой доменного инварианта."""
        if criterion.criterion_id != self.criterion_id:
            raise ValueError("Критерий не соответствует данной оценке.")
        if new_score_val > criterion.max_score:
            raise ValueError(
                f"Нарушение инварианта: балл {new_score_val} превышает допустимый "
                f"максимум ({criterion.max_score}) для критерия '{criterion.name}'."
            )

        self.score = Score(new_score_val)
        if comment is not None:
            self.comment = comment.strip()