from enum import StrEnum


class GateName(StrEnum):
    SCHEMA = "schema"
    GROUNDING = "grounding"
    CONFIDENCE = "confidence"
    SAFETY = "safety"
    CONSISTENCY = "consistency"


class GateStatus(StrEnum):
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
