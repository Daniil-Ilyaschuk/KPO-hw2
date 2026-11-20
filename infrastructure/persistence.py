import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

from application.use_cases import ReportExporter, StudentSummaryDTO
from domain.entities import Criterion, Evaluation, Student
from domain.repositories import (
    CriterionRepository,
    EvaluationRepository,
    StudentRepository,
)


class InMemoryStudentRepository(StudentRepository):
    """In-memory адаптер репозитория студентов."""

    def __init__(self) -> None:
        self._storage: Dict[str, Student] = {}

    def save(self, student: Student) -> None:
        self._storage[student.student_id] = student

    def get(self, student_id: str) -> Optional[Student]:
        return self._storage.get(student_id)

    def get_all(self) -> List[Student]:
        return list(self._storage.values())


class InMemoryCriterionRepository(CriterionRepository):
    """In-memory адаптер репозитория критериев рубрикатора."""

    def __init__(self) -> None:
        self._storage: Dict[str, Criterion] = {}

    def save(self, criterion: Criterion) -> None:
        self._storage[criterion.criterion_id] = criterion

    def get(self, criterion_id: str) -> Optional[Criterion]:
        return self._storage.get(criterion_id)

    def get_all(self) -> List[Criterion]:
        return list(self._storage.values())


class InMemoryEvaluationRepository(EvaluationRepository):
    """In-memory адаптер репозитория оценок."""

    def __init__(self) -> None:
        self._storage: Dict[str, Evaluation] = {}

    def save(self, evaluation: Evaluation) -> None:
        self._storage[evaluation.evaluation_id] = evaluation

    def get(self, evaluation_id: str) -> Optional[Evaluation]:
        return self._storage.get(evaluation_id)

    def delete(self, evaluation_id: str) -> bool:
        if evaluation_id in self._storage:
            del self._storage[evaluation_id]
            return True
        return False

    def get_by_student(self, student_id: str) -> List[Evaluation]:
        return [
            ev for ev in self._storage.values() if ev.student_id == student_id
        ]

    def get_by_student_and_criterion(
        self,
        student_id: str,
        criterion_id: str,
    ) -> Optional[Evaluation]:
        for ev in self._storage.values():
            if ev.student_id == student_id and ev.criterion_id == criterion_id:
                return ev
        return None


class CsvReportExporter(ReportExporter):
    """Адаптер экспорта итоговой ведомости в CSV-файл."""

    def export(self, summaries: List[StudentSummaryDTO], destination: str) -> str:
        output_path = Path(destination)
        if output_path.parent and not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file, delimiter=";")
            writer.writerow(
                [
                    "ID студента",
                    "Студент",
                    "Итоговый балл",
                    "Количество оценок",
                    "Детализация оценок",
                ]
            )
            for item in summaries:
                details = " | ".join(
                    f"{ev.criterion_name}: {ev.score}/{ev.max_score} (вес {ev.weight})"
                    for ev in item.evaluations
                )
                writer.writerow(
                    [
                        item.student_id,
                        item.student_name,
                        f"{item.total_score:.2f}",
                        len(item.evaluations),
                        details,
                    ]
                )

        return str(output_path.resolve())


class JsonReportExporter(ReportExporter):
    """Адаптер экспорта итоговой ведомости в JSON-файл."""

    def export(self, summaries: List[StudentSummaryDTO], destination: str) -> str:
        output_path = Path(destination)
        if output_path.parent and not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)

        payload = [
            {
                "student_id": item.student_id,
                "student_name": item.student_name,
                "total_score": item.total_score,
                "evaluations": [
                    {
                        "evaluation_id": ev.evaluation_id,
                        "criterion_name": ev.criterion_name,
                        "score": ev.score,
                        "max_score": ev.max_score,
                        "weight": ev.weight,
                        "comment": ev.comment,
                        "created_at": ev.created_at.isoformat(),
                    }
                    for ev in item.evaluations
                ],
            }
            for item in summaries
        ]

        with output_path.open("w", encoding="utf-8") as json_file:
            json.dump(payload, json_file, ensure_ascii=False, indent=2)

        return str(output_path.resolve())