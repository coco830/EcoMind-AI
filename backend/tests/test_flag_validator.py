"""Tests for flag validator."""

import pytest

from app.services.flag_validator import FlagValidator, DataFlag


class TestFlagValidator:
    """Test cases for flag validator."""

    def setup_method(self) -> None:
        """Setup validator instance."""
        self.validator = FlagValidator()

    def test_validate_normal_flag(self) -> None:
        """Test validating normal flag."""
        result = self.validator.validate("N")

        assert result.is_valid is True
        assert result.is_normal is True
        assert result.severity == 0
        assert result.should_alarm is False
        assert result.description == "数据正常"

    def test_validate_fault_flag(self) -> None:
        """Test validating fault flag."""
        result = self.validator.validate("D")

        assert result.is_valid is True
        assert result.is_normal is False
        assert result.severity == 3
        assert result.should_alarm is True
        assert result.description == "设备故障"

    def test_validate_stop_flag(self) -> None:
        """Test validating stop flag."""
        result = self.validator.validate("F")

        assert result.is_valid is True
        assert result.should_alarm is True
        assert result.description == "设备停运"

    def test_validate_maintenance_flag(self) -> None:
        """Test validating maintenance flag."""
        result = self.validator.validate("M")

        assert result.is_valid is True
        assert result.should_alarm is False
        assert result.severity == 1

    def test_validate_unknown_flag(self) -> None:
        """Test validating unknown flag."""
        result = self.validator.validate("X")

        assert result.is_valid is False
        assert result.is_normal is False
        assert result.should_alarm is True
        assert "未知" in result.description

    def test_validate_lowercase_flag(self) -> None:
        """Test validating lowercase flag."""
        result = self.validator.validate("n")

        assert result.is_valid is True
        assert result.flag == "N"

    def test_validate_empty_flag(self) -> None:
        """Test validating empty flag defaults to normal."""
        result = self.validator.validate("")

        assert result.flag == "N"
        assert result.is_normal is True

    def test_is_normal_helper(self) -> None:
        """Test is_normal helper method."""
        assert self.validator.is_normal("N") is True
        assert self.validator.is_normal("D") is False
        assert self.validator.is_normal("F") is False

    def test_should_generate_alarm_helper(self) -> None:
        """Test should_generate_alarm helper method."""
        assert self.validator.should_generate_alarm("N") is False
        assert self.validator.should_generate_alarm("D") is True
        assert self.validator.should_generate_alarm("B") is True
        assert self.validator.should_generate_alarm("M") is False

    def test_get_severity_helper(self) -> None:
        """Test get_severity helper method."""
        assert self.validator.get_severity("N") == 0
        assert self.validator.get_severity("M") == 1
        assert self.validator.get_severity("F") == 2
        assert self.validator.get_severity("D") == 3

    def test_batch_validate(self) -> None:
        """Test batch validation."""
        flags = ["N", "D", "M", "X"]
        results = self.validator.batch_validate(flags)

        assert len(results) == 4
        assert results[0].is_normal is True
        assert results[1].should_alarm is True
        assert results[2].severity == 1
        assert results[3].is_valid is False

    def test_all_valid_flags(self) -> None:
        """Test all valid flags are recognized."""
        valid_flags = ["N", "F", "M", "S", "D", "C", "T", "B"]

        for flag in valid_flags:
            result = self.validator.validate(flag)
            assert result.is_valid is True, f"Flag {flag} should be valid"
