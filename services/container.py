from typing import Any, Callable, Dict, Type, TypeVar

from application.use_cases import (
    CriterionUseCases,
    EvaluationUseCases,
    ReportExporter,
    ReportUseCases,
    StudentUseCases,
)
from domain.repositories import (
    CriterionRepository,
    EvaluationRepository,
    StudentRepository,
)
from domain.services import (
    CalculationStrategy,
    NormalizedTenPointStrategy,
    TotalScoreCalculator,
    WeightedSumStrategy,
)
from infrastructure.console_ui import ConsoleUI, POSFacade
from infrastructure.persistence import (
    CsvReportExporter,
    InMemoryCriterionRepository,
    InMemoryEvaluationRepository,
    InMemoryStudentRepository,
    JsonReportExporter,
)

T = TypeVar("T")


class DIContainer:
    """
    Простой DI-контейнер для сборки графа зависимостей на краю приложения
    (Composition Root).
    """

    def __init__(self) -> None:
        self._factories: Dict[Type[Any], Callable[["DIContainer"], Any]] = {}
        self._singletons: Dict[Type[Any], Any] = {}
        self._singleton_types: set = set()

    def register_singleton(
        self,
        interface: Type[T],
        factory: Callable[["DIContainer"], T],
    ) -> None:
        """Регистрирует зависимость как singleton (создаётся один раз)."""
        self._factories[interface] = factory
        self._singleton_types.add(interface)

    def register_transient(
        self,
        interface: Type[T],
        factory: Callable[["DIContainer"], T],
    ) -> None:
        """Регистрирует зависимость, создаваемую заново при каждом запросе."""
        self._factories[interface] = factory
        self._singleton_types.discard(interface)

    def resolve(self, interface: Type[T]) -> T:
        """Разрешает зависимость по абстракции или классу."""
        if interface in self._singletons:
            return self._singletons[interface]

        factory = self._factories.get(interface)
        if factory is None:
            raise KeyError(
                f"Зависимость '{interface.__name__}' не зарегистрирована в DI-контейнере."
            )

        instance = factory(self)
        if interface in self._singleton_types:
            self._singletons[interface] = instance
        return instance


def build_container(
    export_format: str = "csv",
    strategy_name: str = "weighted",
) -> DIContainer:
    """
    Конфигурирует и возвращает готовый DI-контейнер.

    :param export_format: Формат экспорта итоговой ведомости ('csv' или 'json').
    :param strategy_name: Начальная стратегия расчёта ('weighted' или 'normalized').
    """
    container = DIContainer()

    # 1. Адаптеры хранилища (Ports -> In-Memory Adapters)
    container.register_singleton(
        StudentRepository,
        lambda _: InMemoryStudentRepository(),
    )
    container.register_singleton(
        CriterionRepository,
        lambda _: InMemoryCriterionRepository(),
    )
    container.register_singleton(
        EvaluationRepository,
        lambda _: InMemoryEvaluationRepository(),
    )

    # 2. Адаптер экспорта (Outbound Port -> CSV / JSON Adapter)
    normalized_format = export_format.lower().strip()
    if normalized_format == "json":
        container.register_singleton(ReportExporter, lambda _: JsonReportExporter())
    elif normalized_format == "csv":
        container.register_singleton(ReportExporter, lambda _: CsvReportExporter())
    else:
        raise ValueError(
            f"Неподдерживаемый формат экспорта: '{export_format}'. "
            f"Допустимые значения: 'csv', 'json'."
        )

    # 3. Domain Service и начальная стратегия (Strategy)
    normalized_strategy = strategy_name.lower().strip()
    if normalized_strategy == "normalized":
        container.register_singleton(
            CalculationStrategy,
            lambda _: NormalizedTenPointStrategy(),
        )
    elif normalized_strategy == "weighted":
        container.register_singleton(
            CalculationStrategy,
            lambda _: WeightedSumStrategy(),
        )
    else:
        raise ValueError(
            f"Неподдерживаемая стратегия: '{strategy_name}'. "
            f"Допустимые значения: 'weighted', 'normalized'."
        )

    container.register_singleton(
        TotalScoreCalculator,
        lambda c: TotalScoreCalculator(strategy=c.resolve(CalculationStrategy)),
    )

    # 4. Сценарии приложения (Application / Use Cases)
    container.register_singleton(
        StudentUseCases,
        lambda c: StudentUseCases(student_repo=c.resolve(StudentRepository)),
    )
    container.register_singleton(
        CriterionUseCases,
        lambda c: CriterionUseCases(criterion_repo=c.resolve(CriterionRepository)),
    )
    container.register_singleton(
        EvaluationUseCases,
        lambda c: EvaluationUseCases(
            student_repo=c.resolve(StudentRepository),
            criterion_repo=c.resolve(CriterionRepository),
            evaluation_repo=c.resolve(EvaluationRepository),
        ),
    )
    container.register_singleton(
        ReportUseCases,
        lambda c: ReportUseCases(
            student_repo=c.resolve(StudentRepository),
            criterion_repo=c.resolve(CriterionRepository),
            evaluation_repo=c.resolve(EvaluationRepository),
            calculator=c.resolve(TotalScoreCalculator),
            exporter=c.resolve(ReportExporter),
        ),
    )

    # 5. Фасад и консольный интерфейс (Facade + Console UI)
    container.register_singleton(
        POSFacade,
        lambda c: POSFacade(
            student_uc=c.resolve(StudentUseCases),
            criterion_uc=c.resolve(CriterionUseCases),
            evaluation_uc=c.resolve(EvaluationUseCases),
            report_uc=c.resolve(ReportUseCases),
        ),
    )
    container.register_transient(
        ConsoleUI,
        lambda c: ConsoleUI(facade=c.resolve(POSFacade)),
    )

    return container