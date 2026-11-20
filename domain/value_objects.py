from dataclasses import dataclass

@dataclass(frozen=True)
class Score:
    """
    Value Object для оценки. 
    Гарантирует, что балл является валидным числом и не меньше нуля.
    """
    value: float

    def __post_init__(self):
        if self.value < 0:
            raise ValueError(f"Балл не может быть отрицательным. Передано: {self.value}")

@dataclass(frozen=True)
class Weight:
    """
    Value Object для веса критерия в итоговой оценке.
    Вес должен быть в диапазоне (0, 1].
    """
    value: float

    def __post_init__(self):
        if self.value <= 0 or self.value > 1:
            raise ValueError(f"Вес должен быть в диапазоне (0, 1]. Передано: {self.value}")