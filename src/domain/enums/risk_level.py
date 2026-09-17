from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3

    @property
    def label(self) -> str:
        return self.name
