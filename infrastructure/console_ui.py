from typing import List, Optional

from application.use_cases import (
    ApplicationError,
    CriterionUseCases,
    EvaluationUseCases,
    EvaluationView,
    ReportUseCases,
    StudentSummaryDTO,
    StudentUseCases,
)
from domain.entities import Criterion, Evaluation, Student
from domain.services import NormalizedTenPointStrategy, WeightedSumStrategy


class POSFacade:
    """
    Паттерн: Facade (Структурный).
    Предоставляет единую точку входа для консольного интерфейса,
    скрывая оркестрацию четырёх отдельных Use Cases и смену стратегий расчёта.
    """

    def __init__(
        self,
        student_uc: StudentUseCases,
        criterion_uc: CriterionUseCases,
        evaluation_uc: EvaluationUseCases,
        report_uc: ReportUseCases,
    ) -> None:
        self._student_uc = student_uc
        self._criterion_uc = criterion_uc
        self._evaluation_uc = evaluation_uc
        self._report_uc = report_uc
        self._strategy_name = "Взвешенная сумма (WeightedSumStrategy)"

    @property
    def current_strategy_name(self) -> str:
        return self._strategy_name

    # --- Студенты ---

    def add_student(self, name: str) -> Student:
        return self._student_uc.add_student(name)

    def list_students(self) -> List[Student]:
        return self._student_uc.list_students()

    # --- Критерии рубрикатора ---

    def add_criterion(
        self,
        name: str,
        max_score: float,
        weight_value: float,
    ) -> Criterion:
        return self._criterion_uc.add_criterion(name, max_score, weight_value)

    def list_criteria(self) -> List[Criterion]:
        return self._criterion_uc.list_criteria()

    def get_total_rubric_weight(self) -> float:
        return self._criterion_uc.get_total_weight()

    # --- Оценки ---

    def evaluate_student(
        self,
        student_id: str,
        criterion_id: str,
        score_value: float,
        comment: str = "",
    ) -> Evaluation:
        return self._evaluation_uc.evaluate_student(
            student_id=student_id,
            criterion_id=criterion_id,
            score_value=score_value,
            comment=comment,
        )

    def update_evaluation(
        self,
        evaluation_id: str,
        new_score_value: float,
        comment: Optional[str] = None,
    ) -> Evaluation:
        return self._evaluation_uc.update_evaluation(
            evaluation_id=evaluation_id,
            new_score_value=new_score_value,
            comment=comment,
        )

    def cancel_evaluation(self, evaluation_id: str) -> None:
        self._evaluation_uc.cancel_evaluation(evaluation_id)

    def get_student_evaluations(self, student_id: str) -> List[EvaluationView]:
        return self._evaluation_uc.get_student_evaluations(student_id)

    # --- Итоги, стратегии и экспорт ---

    def use_weighted_sum_strategy(self) -> None:
        self._report_uc.set_calculation_strategy(WeightedSumStrategy())
        self._strategy_name = "Взвешенная сумма (WeightedSumStrategy)"

    def use_normalized_ten_point_strategy(self) -> None:
        self._report_uc.set_calculation_strategy(NormalizedTenPointStrategy())
        self._strategy_name = (
            "Нормализация к 10-балльной шкале (NormalizedTenPointStrategy)"
        )

    def get_course_summaries(self) -> List[StudentSummaryDTO]:
        return self._report_uc.get_course_summaries()

    def export_report(self, destination: str) -> str:
        return self._report_uc.export_course_report(destination)


class ConsoleUI:
    """Интерактивный консольный интерфейс модуля ПОС."""

    def __init__(self, facade: POSFacade) -> None:
        self._facade = facade

    # --- Вспомогательные методы ввода и выбора ---

    @staticmethod
    def _read_non_empty(prompt: str) -> str:
        while True:
            value = input(prompt).strip()
            if value:
                return value
            print("[!] Поле не может быть пустым. Попробуйте ещё раз.")

    @staticmethod
    def _read_float(prompt: str) -> float:
        while True:
            raw = input(prompt).strip().replace(",", ".")
            try:
                return float(raw)
            except ValueError:
                print("[!] Введите корректное число (например, 8.5).")

    @staticmethod
    def _read_index(prompt: str, max_index: int) -> Optional[int]:
        raw = input(prompt).strip()
        if raw == "0":
            return None
        try:
            idx = int(raw)
            if 1 <= idx <= max_index:
                return idx - 1
        except ValueError:
            pass
        print(f"[!] Введите число от 1 до {max_index} (или 0 для отмены).")
        return None

    def _select_student(self) -> Optional[Student]:
        students = self._facade.list_students()
        if not students:
            print("[!] Список студентов пуст. Сначала добавьте студента.")
            return None

        print("\nСписок студентов:")
        for i, student in enumerate(students, start=1):
            print(f"  {i}. {student.name}")

        idx = self._read_index("Выберите номер студента (0 — отмена): ", len(students))
        return students[idx] if idx is not None else None

    def _select_criterion(self) -> Optional[Criterion]:
        criteria = self._facade.list_criteria()
        if not criteria:
            print("[!] Рубрикатор пуст. Сначала добавьте хотя бы один критерий.")
            return None

        print("\nРубрикатор критериев:")
        for i, crit in enumerate(criteria, start=1):
            print(
                f"  {i}. {crit.name} "
                f"(макс: {crit.max_score}, вес: {crit.weight.value})"
            )

        idx = self._read_index("Выберите номер критерия (0 — отмена): ", len(criteria))
        return criteria[idx] if idx is not None else None

    # --- Обработчики пунктов меню ---

    def _handle_add_student(self) -> None:
        name = self._read_non_empty("Введите ФИО студента: ")
        student = self._facade.add_student(name)
        print(f"[+] Студент '{student.name}' добавлен (ID: {student.student_id[:8]}...).")

    def _handle_list_students(self) -> None:
        students = self._facade.list_students()
        if not students:
            print("\nСтудентов пока нет.")
            return
        print("\n--- Список студентов ---")
        for i, student in enumerate(students, start=1):
            print(f"{i}. {student.name} [ID: {student.student_id[:8]}...]")

    def _handle_add_criterion(self) -> None:
        used_weight = self._facade.get_total_rubric_weight()
        print(f"Текущая сумма весов в рубрикаторе: {used_weight} / 1.0")
        name = self._read_non_empty("Название критерия: ")
        max_score = self._read_float("Максимальный балл (> 0): ")
        weight = self._read_float("Вес критерия (в диапазоне (0, 1]): ")
        criterion = self._facade.add_criterion(name, max_score, weight)
        print(
            f"[+] Критерий '{criterion.name}' добавлен "
            f"(макс: {criterion.max_score}, вес: {criterion.weight.value})."
        )

    def _handle_list_criteria(self) -> None:
        criteria = self._facade.list_criteria()
        if not criteria:
            print("\nРубрикатор пуст.")
            return
        print("\n--- Рубрикатор оценивания ---")
        for i, crit in enumerate(criteria, start=1):
            print(
                f"{i}. {crit.name} | Макс. балл: {crit.max_score} | "
                f"Вес: {crit.weight.value}"
            )
        print(f"Суммарный вес: {self._facade.get_total_rubric_weight()} / 1.0")

    def _handle_evaluate_student(self) -> None:
        student = self._select_student()
        if not student:
            return
        criterion = self._select_criterion()
        if not criterion:
            return

        score_val = self._read_float(
            f"Введите балл для '{student.name}' по '{criterion.name}' "
            f"(0..{criterion.max_score}): "
        )
        comment = input("Комментарий преподавателя (необязательно): ").strip()
        evaluation = self._facade.evaluate_student(
            student_id=student.student_id,
            criterion_id=criterion.criterion_id,
            score_value=score_val,
            comment=comment,
        )
        print(
            f"[+] Оценка выставлена: {evaluation.score.value}/{criterion.max_score} "
            f"по критерию '{criterion.name}'."
        )

    def _handle_view_student_evaluations(self) -> None:
        student = self._select_student()
        if not student:
            return
        evaluations = self._facade.get_student_evaluations(student.student_id)
        if not evaluations:
            print(f"\nУ студента '{student.name}' пока нет выставленных оценок.")
            return

        print(f"\n--- Оценки студента: {student.name} ---")
        for i, ev in enumerate(evaluations, start=1):
            comment_part = f" | Комментарий: {ev.comment}" if ev.comment else ""
            date_str = ev.created_at.strftime("%Y-%m-%d %H:%M")
            print(
                f"{i}. {ev.criterion_name}: {ev.score}/{ev.max_score} "
                f"(вес {ev.weight}) [{date_str}]{comment_part}"
            )

    def _handle_update_evaluation(self) -> None:
        student = self._select_student()
        if not student:
            return
        evaluations = self._facade.get_student_evaluations(student.student_id)
        if not evaluations:
            print(f"[!] У студента '{student.name}' нет оценок для исправления.")
            return

        print(f"\nОценки студента {student.name}:")
        for i, ev in enumerate(evaluations, start=1):
            print(f"  {i}. {ev.criterion_name}: {ev.score}/{ev.max_score}")

        idx = self._read_index("Выберите оценку для исправления (0 — отмена): ", len(evaluations))
        if idx is None:
            return

        target = evaluations[idx]
        new_score = self._read_float(
            f"Новый балл для '{target.criterion_name}' (0..{target.max_score}): "
        )
        new_comment_raw = input(
            "Новый комментарий (Enter — оставить текущий): "
        ).strip()
        new_comment = new_comment_raw if new_comment_raw else None

        updated = self._facade.update_evaluation(
            evaluation_id=target.evaluation_id,
            new_score_value=new_score,
            comment=new_comment,
        )
        print(
            f"[+] Оценка обновлена: {target.criterion_name} -> "
            f"{updated.score.value}/{target.max_score}."
        )

    def _handle_cancel_evaluation(self) -> None:
        student = self._select_student()
        if not student:
            return
        evaluations = self._facade.get_student_evaluations(student.student_id)
        if not evaluations:
            print(f"[!] У студента '{student.name}' нет оценок для отмены.")
            return

        print(f"\nОценки студента {student.name}:")
        for i, ev in enumerate(evaluations, start=1):
            print(f"  {i}. {ev.criterion_name}: {ev.score}/{ev.max_score}")

        idx = self._read_index("Выберите оценку для отмены (0 — отмена): ", len(evaluations))
        if idx is None:
            return

        target = evaluations[idx]
        self._facade.cancel_evaluation(target.evaluation_id)
        print(f"[-] Оценка по критерию '{target.criterion_name}' отменена.")

    def _handle_show_summaries(self) -> None:
        summaries = self._facade.get_course_summaries()
        if not summaries:
            print("\nНет студентов для расчёта ведомости.")
            return

        print(f"\n=== Итоговая ведомость ПОС ===")
        print(f"Активная стратегия: {self._facade.current_strategy_name}")
        print("-" * 64)
        for rank, item in enumerate(summaries, start=1):
            evals_str = ", ".join(
                f"{ev.criterion_name}: {ev.score}/{ev.max_score}"
                for ev in item.evaluations
            ) or "оценок нет"
            print(f"{rank}. {item.student_name:<25} | Итог: {item.total_score:>6.2f}")
            print(f"   Оценки: {evals_str}")
        print("-" * 64)

    def _handle_switch_strategy(self) -> None:
        print(f"\nТекущая стратегия: {self._facade.current_strategy_name}")
        print("1. Взвешенная сумма: Сумма(Балл * Вес)")
        print("2. Нормализация к 10-балльной шкале: Сумма((Балл / max_score) * 10 * Вес)")
        choice = input("Выберите стратегию (1/2): ").strip()
        if choice == "1":
            self._facade.use_weighted_sum_strategy()
            print(f"[+] Установлена стратегия: {self._facade.current_strategy_name}")
        elif choice == "2":
            self._facade.use_normalized_ten_point_strategy()
            print(f"[+] Установлена стратегия: {self._facade.current_strategy_name}")
        else:
            print("[!] Отменено.")

    def _handle_export_report(self) -> None:
        path_raw = input(
            "Путь к файлу для экспорта (Enter для 'pos_report.csv'): "
        ).strip()
        destination = path_raw or "pos_report.csv"
        saved_path = self._facade.export_report(destination)
        print(f"[+] Итоговая ведомость успешно экспортирована в: {saved_path}")

    # --- Сквозной демонстрационный сценарий ---

    def run_demo(self, export_path: str = "pos_demo_report.csv") -> None:
        """
        Сквозной сценарий по ТЗ:
        студенты и критерии -> оценки -> проверка инвариантов ->
        исправление/отмена -> расчёт итога -> экспорт ведомости.
        """
        print("\n" + "=" * 66)
        print("  СКВОЗНАЯ ДЕМОНСТРАЦИЯ МОДУЛЯ «ПОС» (Преподавательская Оценка)")
        print("=" * 66)

        if self._facade.list_students() or self._facade.list_criteria():
            print(
                "[!] В системе уже есть данные. Для чистого прогона демо "
                "запустите программу заново и выберите демо-режим."
            )
            return

        print("\n[Шаг 1] Заводим студентов и рубрикатор критериев...")
        s1 = self._facade.add_student("Иван Петров")
        s2 = self._facade.add_student("Мария Соколова")

        c_lec = self._facade.add_criterion("Посещение лекций", max_score=10.0, weight_value=0.2)
        c_sem = self._facade.add_criterion("Работа на семинарах", max_score=10.0, weight_value=0.3)
        c_hw = self._facade.add_criterion("Домашние задания", max_score=20.0, weight_value=0.5)
        print(f"  Студенты: {s1.name}, {s2.name}")
        print(
            f"  Критерии: '{c_lec.name}' (до 10, вес 0.2), "
            f"'{c_sem.name}' (до 10, вес 0.3), "
            f"'{c_hw.name}' (до 20, вес 0.5)"
        )

        print("\n[Шаг 2] Выставляем корректные оценки...")
        ev1 = self._facade.evaluate_student(s1.student_id, c_lec.criterion_id, 9.0, "Стабильное посещение")
        self._facade.evaluate_student(s1.student_id, c_sem.criterion_id, 8.0, "Отвечал у доски")
        self._facade.evaluate_student(s1.student_id, c_hw.criterion_id, 18.0, "Хорошая архитектура")

        self._facade.evaluate_student(s2.student_id, c_lec.criterion_id, 10.0, "Без пропусков")
        self._facade.evaluate_student(s2.student_id, c_sem.criterion_id, 9.5, "Отличные вопросы")
        self._facade.evaluate_student(s2.student_id, c_hw.criterion_id, 19.0, "Идеальные тесты")
        print("  Оценки успешно сохранены.")

        print("\n[Шаг 3] Проверяем защиту доменных инвариантов:")
        try:
            self._facade.evaluate_student(s1.student_id, c_lec.criterion_id, 12.0)
        except (ValueError, ApplicationError) as exc:
            print(f"  [OK] Блокировка дубликата / превышения балла: {exc}")

        try:
            self._facade.update_evaluation(ev1.evaluation_id, 12.0)
        except (ValueError, ApplicationError) as exc:
            print(f"  [OK] Блокировка 12 из 10 при исправлении: {exc}")

        try:
            self._facade.evaluate_student(s1.student_id, "non-existent-criterion", 5.0)
        except (ValueError, ApplicationError) as exc:
            print(f"  [OK] Блокировка несуществующего критерия: {exc}")

        print("\n[Шаг 4] Корректное исправление оценки (лекции Ивана: 9.0 -> 10.0)...")
        self._facade.update_evaluation(ev1.evaluation_id, 10.0, "Пересчёт посещаемости")

        print("\n[Шаг 5] Расчёт итогов по двум разным стратегиям (паттерн Strategy):")
        self._facade.use_weighted_sum_strategy()
        self._handle_show_summaries()

        self._facade.use_normalized_ten_point_strategy()
        self._handle_show_summaries()

        print("\n[Шаг 6] Экспорт итоговой ведомости через порт ReportExporter...")
        saved_file = self._facade.export_report(export_path)
        print(f"  [+] Файл сохранён: {saved_file}")
        print("=" * 66)

    # --- Главный цикл меню ---

    def run_interactive(self) -> None:
        actions = {
            "1": self._handle_add_student,
            "2": self._handle_list_students,
            "3": self._handle_add_criterion,
            "4": self._handle_list_criteria,
            "5": self._handle_evaluate_student,
            "6": self._handle_view_student_evaluations,
            "7": self._handle_update_evaluation,
            "8": self._handle_cancel_evaluation,
            "9": self._handle_show_summaries,
            "10": self._handle_switch_strategy,
            "11": self._handle_export_report,
            "12": self.run_demo,
        }

        while True:
            print("\n" + "=" * 50)
            print("  ПОС — Преподавательская Оценка Студентов")
            print(f"  Стратегия: {self._facade.current_strategy_name}")
            print("=" * 50)
            print(" 1. Добавить студента")
            print(" 2. Список студентов")
            print(" 3. Добавить критерий в рубрикатор")
            print(" 4. Показать рубрикатор")
            print(" 5. Выставить оценку студенту")
            print(" 6. Посмотреть оценки студента")
            print(" 7. Исправить оценку")
            print(" 8. Отменить (удалить) оценку")
            print(" 9. Показать итоговую ведомость")
            print("10. Сменить стратегию расчёта итога")
            print("11. Экспортировать ведомость в файл")
            print("12. Запустить сквозную демонстрацию")
            print(" 0. Выход")

            choice = input("\nВыберите пункт меню: ").strip()
            if choice == "0":
                print("До свидания!")
                break

            handler = actions.get(choice)
            if not handler:
                print("[!] Неизвестный пункт меню.")
                continue

            try:
                handler()
            except (ValueError, ApplicationError, OSError) as exc:
                print(f"\n[ОШИБКА]: {exc}")