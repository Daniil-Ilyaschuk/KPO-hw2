import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from application.use_cases import (
    ApplicationError,
    DuplicateEvaluationError,
    EntityNotFoundError,
    RubricWeightExceededError,
)
from domain.entities import Criterion, Evaluation, Student
from domain.services import (
    NormalizedTenPointStrategy,
    TotalScoreCalculator,
    WeightedSumStrategy,
)
from domain.value_objects import Score, Weight
from infrastructure.console_ui import POSFacade
from services.container import build_container


class TestValueObjects(unittest.TestCase):
    def test_score_accepts_zero_and_positive(self) -> None:
        self.assertEqual(Score(0.0).value, 0.0)
        self.assertEqual(Score(8.5).value, 8.5)

    def test_score_rejects_negative(self) -> None:
        with self.assertRaises(ValueError):
            Score(-0.1)

    def test_score_is_immutable(self) -> None:
        score = Score(5.0)
        with self.assertRaises(FrozenInstanceError):
            score.value = 10.0  # type: ignore[misc]

    def test_weight_bounds(self) -> None:
        self.assertEqual(Weight(0.5).value, 0.5)
        self.assertEqual(Weight(1.0).value, 1.0)
        with self.assertRaises(ValueError):
            Weight(0.0)
        with self.assertRaises(ValueError):
            Weight(-0.2)
        with self.assertRaises(ValueError):
            Weight(1.01)


class TestDomainEntitiesAndFactory(unittest.TestCase):
    def setUp(self) -> None:
        self.student = Student(name="Иван Петров")
        self.criterion = Criterion(
            name="Семинары",
            max_score=10.0,
            weight=Weight(0.5),
        )

    def test_student_empty_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Student(name="   ")

    def test_criterion_non_positive_max_score_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Criterion(name="Тест", max_score=0.0, weight=Weight(0.5))

    def test_evaluation_factory_creates_valid_evaluation(self) -> None:
        ev = Evaluation.create(self.student, self.criterion, 9.0, "Отлично")
        self.assertEqual(ev.score.value, 9.0)
        self.assertEqual(ev.comment, "Отлично")
        self.assertEqual(ev.student_id, self.student.student_id)
        self.assertEqual(ev.criterion_id, self.criterion.criterion_id)

    def test_evaluation_factory_blocks_score_above_max(self) -> None:
        with self.assertRaises(ValueError):
            Evaluation.create(self.student, self.criterion, 12.0)

    def test_evaluation_factory_blocks_negative_score(self) -> None:
        with self.assertRaises(ValueError):
            Evaluation.create(self.student, self.criterion, -1.0)

    def test_evaluation_update_enforces_invariants(self) -> None:
        ev = Evaluation.create(self.student, self.criterion, 7.0)
        ev.update_score(self.criterion, 10.0, "Пересдача")
        self.assertEqual(ev.score.value, 10.0)
        self.assertEqual(ev.comment, "Пересдача")

        with self.assertRaises(ValueError):
            ev.update_score(self.criterion, 10.5)

        other_criterion = Criterion(
            name="Другой",
            max_score=20.0,
            weight=Weight(0.5),
        )
        with self.assertRaises(ValueError):
            ev.update_score(other_criterion, 5.0)


class TestDomainServiceAndStrategies(unittest.TestCase):
    def setUp(self) -> None:
        self.student = Student(name="Мария Соколова")
        self.c1 = Criterion(name="Лекции", max_score=10.0, weight=Weight(0.4))
        self.c2 = Criterion(name="ДЗ", max_score=20.0, weight=Weight(0.6))
        self.evaluations = [
            Evaluation.create(self.student, self.c1, 8.0),
            Evaluation.create(self.student, self.c2, 15.0),
        ]
        self.criteria = [self.c1, self.c2]

    def test_weighted_sum_strategy(self) -> None:
        calculator = TotalScoreCalculator(WeightedSumStrategy())
        # 8.0 * 0.4 + 15.0 * 0.6 = 3.2 + 9.0 = 12.2
        self.assertEqual(
            calculator.calculate_total(self.evaluations, self.criteria),
            12.2,
        )

    def test_normalized_ten_point_strategy_and_switching(self) -> None:
        calculator = TotalScoreCalculator(WeightedSumStrategy())
        calculator.set_strategy(NormalizedTenPointStrategy())
        # (8/10)*10*0.4 + (15/20)*10*0.6 = 3.2 + 4.5 = 7.7
        self.assertEqual(
            calculator.calculate_total(self.evaluations, self.criteria),
            7.7,
        )

    def test_empty_evaluations_returns_zero(self) -> None:
        calculator = TotalScoreCalculator(WeightedSumStrategy())
        self.assertEqual(calculator.calculate_total([], self.criteria), 0.0)


class TestApplicationUseCasesAndDI(unittest.TestCase):
    def setUp(self) -> None:
        container = build_container(export_format="csv", strategy_name="weighted")
        self.facade = container.resolve(POSFacade)

    def test_cannot_evaluate_nonexistent_criterion(self) -> None:
        student = self.facade.add_student("Алексей")
        with self.assertRaises(EntityNotFoundError):
            self.facade.evaluate_student(student.student_id, "missing-id", 5.0)

    def test_cannot_exceed_total_rubric_weight(self) -> None:
        self.facade.add_criterion("К1", max_score=10.0, weight_value=0.7)
        with self.assertRaises(RubricWeightExceededError):
            self.facade.add_criterion("К2", max_score=10.0, weight_value=0.4)

    def test_duplicate_criterion_name_rejected(self) -> None:
        self.facade.add_criterion("Лекции", max_score=10.0, weight_value=0.5)
        with self.assertRaises(ApplicationError):
            self.facade.add_criterion("лекции", max_score=10.0, weight_value=0.2)

    def test_duplicate_evaluation_rejected(self) -> None:
        student = self.facade.add_student("Ольга")
        crit = self.facade.add_criterion("Семинары", max_score=10.0, weight_value=0.5)
        self.facade.evaluate_student(student.student_id, crit.criterion_id, 8.0)

        with self.assertRaises(DuplicateEvaluationError):
            self.facade.evaluate_student(student.student_id, crit.criterion_id, 9.0)

    def test_update_and_cancel_evaluation_affects_total(self) -> None:
        student = self.facade.add_student("Дмитрий")
        crit = self.facade.add_criterion("ДЗ", max_score=10.0, weight_value=1.0)
        ev = self.facade.evaluate_student(student.student_id, crit.criterion_id, 6.0)

        summaries = self.facade.get_course_summaries()
        self.assertEqual(summaries[0].total_score, 6.0)

        self.facade.update_evaluation(ev.evaluation_id, 9.0)
        self.assertEqual(self.facade.get_course_summaries()[0].total_score, 9.0)

        self.facade.cancel_evaluation(ev.evaluation_id)
        self.assertEqual(self.facade.get_course_summaries()[0].total_score, 0.0)

    def test_csv_and_json_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # CSV экспорт
            csv_path = Path(tmp_dir) / "report.csv"
            student = self.facade.add_student("Елена")
            crit = self.facade.add_criterion("Проект", max_score=10.0, weight_value=1.0)
            self.facade.evaluate_student(student.student_id, crit.criterion_id, 9.5)

            saved_csv = self.facade.export_report(str(csv_path))
            self.assertTrue(Path(saved_csv).exists())
            content = Path(saved_csv).read_text(encoding="utf-8-sig")
            self.assertIn("Елена", content)
            self.assertIn("9.50", content)

            # JSON экспорт через отдельный контейнер
            json_container = build_container(export_format="json")
            json_facade = json_container.resolve(POSFacade)
            s2 = json_facade.add_student("Максим")
            c2 = json_facade.add_criterion("Экзамен", max_score=10.0, weight_value=1.0)
            json_facade.evaluate_student(s2.student_id, c2.criterion_id, 8.0)

            json_path = Path(tmp_dir) / "report.json"
            saved_json = json_facade.export_report(str(json_path))
            data = json.loads(Path(saved_json).read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["student_name"], "Максим")
            self.assertEqual(data[0]["total_score"], 8.0)


if __name__ == "__main__":
    unittest.main()