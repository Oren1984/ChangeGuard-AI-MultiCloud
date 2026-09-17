from enum import StrEnum


class Decision(StrEnum):
    AUTO_CLEAR = "AUTO_CLEAR"
    CAB_REVIEW_REQUIRED = "CAB_REVIEW_REQUIRED"
    HARD_BLOCK = "HARD_BLOCK"
