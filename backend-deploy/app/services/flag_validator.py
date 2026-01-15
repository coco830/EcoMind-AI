"""Flag validation service for HJ 212 data quality flags.

HJ 212 defines data quality flags:
- N: Normal (正常)
- F: Stop working (停运)
- M: Maintenance (维护)
- S: Manual (手工输入)
- D: Fault (故障)
- C: Calibration (校准)
- T: Abnormal (超测程)
- B: Power failure (断电)
"""

from dataclasses import dataclass
from enum import Enum


class DataFlag(str, Enum):
    """HJ 212 data quality flags."""

    NORMAL = "N"
    STOP = "F"
    MAINTENANCE = "M"
    MANUAL = "S"
    FAULT = "D"
    CALIBRATION = "C"
    OUT_OF_RANGE = "T"
    POWER_FAILURE = "B"


@dataclass
class FlagValidationResult:
    """Result of flag validation."""

    flag: str
    is_valid: bool
    is_normal: bool
    severity: int  # 0=normal, 1=info, 2=warning, 3=critical
    description: str
    should_alarm: bool


class FlagValidator:
    """Validator for HJ 212 data quality flags."""

    FLAG_INFO = {
        DataFlag.NORMAL.value: {
            "description": "数据正常",
            "severity": 0,
            "should_alarm": False,
        },
        DataFlag.STOP.value: {
            "description": "设备停运",
            "severity": 2,
            "should_alarm": True,
        },
        DataFlag.MAINTENANCE.value: {
            "description": "设备维护中",
            "severity": 1,
            "should_alarm": False,
        },
        DataFlag.MANUAL.value: {
            "description": "手工输入数据",
            "severity": 1,
            "should_alarm": False,
        },
        DataFlag.FAULT.value: {
            "description": "设备故障",
            "severity": 3,
            "should_alarm": True,
        },
        DataFlag.CALIBRATION.value: {
            "description": "设备校准中",
            "severity": 1,
            "should_alarm": False,
        },
        DataFlag.OUT_OF_RANGE.value: {
            "description": "数据超测程",
            "severity": 2,
            "should_alarm": True,
        },
        DataFlag.POWER_FAILURE.value: {
            "description": "设备断电",
            "severity": 3,
            "should_alarm": True,
        },
    }

    VALID_FLAGS = set(FLAG_INFO.keys())

    def validate(self, flag: str) -> FlagValidationResult:
        """Validate a data quality flag.

        Args:
            flag: The flag string to validate

        Returns:
            FlagValidationResult with validation details
        """
        flag = flag.upper().strip() if flag else "N"

        # Handle unknown flags
        if flag not in self.VALID_FLAGS:
            return FlagValidationResult(
                flag=flag,
                is_valid=False,
                is_normal=False,
                severity=2,
                description=f"未知标志位: {flag}",
                should_alarm=True,
            )

        info = self.FLAG_INFO[flag]
        return FlagValidationResult(
            flag=flag,
            is_valid=True,
            is_normal=flag == DataFlag.NORMAL.value,
            severity=info["severity"],
            description=info["description"],
            should_alarm=info["should_alarm"],
        )

    def is_normal(self, flag: str) -> bool:
        """Check if flag indicates normal data."""
        return self.validate(flag).is_normal

    def should_generate_alarm(self, flag: str) -> bool:
        """Check if flag should generate an alarm."""
        return self.validate(flag).should_alarm

    def get_severity(self, flag: str) -> int:
        """Get severity level for flag (0-3)."""
        return self.validate(flag).severity

    def batch_validate(self, flags: list[str]) -> list[FlagValidationResult]:
        """Validate multiple flags."""
        return [self.validate(f) for f in flags]


# Global validator instance
_validator: FlagValidator | None = None


def get_flag_validator() -> FlagValidator:
    """Get or create global flag validator instance."""
    global _validator
    if _validator is None:
        _validator = FlagValidator()
    return _validator
